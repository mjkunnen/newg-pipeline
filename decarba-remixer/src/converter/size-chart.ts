import OpenAI from "openai";
import sharp from "sharp";
import { readFile } from "fs/promises";
import type { SizeChartEntry } from "../scraper/types.js";

function requireEnv(key: string): string {
  const val = process.env[key];
  if (!val) {
    throw new Error(
      `Required env var ${key} is not set. ` +
      "Add it to .env (local) or GitHub Actions secrets (CI)."
    );
  }
  return val;
}

const OXYLABS_USER = requireEnv("OXYLABS_USERNAME");
const OXYLABS_PASS = requireEnv("OXYLABS_PASSWORD");

/**
 * Extract size chart from product images using GPT-4o Vision.
 *
 * Strategy:
 * 1. Send all product images to GPT-4o Vision, ask if any contain a size chart
 * 2. If not found, try fetching Taobao description images via Oxylabs
 * 3. Extract measurements from whichever image has the size chart
 */
export async function extractSizeChart(
  productId: string,
  imagePaths: string[],
  imageUrls: string[],
): Promise<SizeChartEntry[] | null> {
  if (!process.env.OPENAI_API_KEY) {
    console.log("[size-chart] No OPENAI_API_KEY, skipping size chart extraction");
    return null;
  }

  const openai = new OpenAI();

  // Step 1: Check product images for size chart
  console.log(`[size-chart] Checking ${imagePaths.length} product images for size chart...`);
  const chart = await checkImagesForSizeChart(openai, imagePaths);
  if (chart) return chart;

  // Step 2: Try fetching Taobao description images
  console.log("[size-chart] No size chart in product images, trying Taobao description...");
  const descImages = await fetchTaobaoDescriptionImages(productId);
  if (descImages.length > 0) {
    console.log(`[size-chart] Found ${descImages.length} description images, checking for size chart...`);
    const descChart = await checkImageUrlsForSizeChart(openai, descImages);
    if (descChart) return descChart;
  }

  console.log("[size-chart] No size chart found");
  return null;
}

/**
 * Send local image files to GPT-4o Vision to find and extract size chart.
 */
async function checkImagesForSizeChart(
  openai: OpenAI,
  imagePaths: string[],
): Promise<SizeChartEntry[] | null> {
  const imageContent: Array<{ type: "image_url"; image_url: { url: string } }> = [];

  for (const imgPath of imagePaths) {
    try {
      const buffer = await readFile(imgPath);
      const preview = await sharp(buffer)
        .resize(800, 800, { fit: "inside" })
        .jpeg({ quality: 80 })
        .toBuffer();
      imageContent.push({
        type: "image_url",
        image_url: { url: `data:image/jpeg;base64,${preview.toString("base64")}` },
      });
    } catch {
      // skip unreadable images
    }
  }

  if (imageContent.length === 0) return null;
  return await askVisionForSizeChart(openai, imageContent);
}

/**
 * Send image URLs to GPT-4o Vision to find and extract size chart.
 */
async function checkImageUrlsForSizeChart(
  openai: OpenAI,
  imageUrls: string[],
): Promise<SizeChartEntry[] | null> {
  // Download and resize for Vision
  const imageContent: Array<{ type: "image_url"; image_url: { url: string } }> = [];

  for (const url of imageUrls.slice(0, 10)) {
    try {
      const resp = await fetch(url);
      if (!resp.ok) continue;
      const buffer = Buffer.from(await resp.arrayBuffer());
      const preview = await sharp(buffer)
        .resize(800, 800, { fit: "inside" })
        .jpeg({ quality: 80 })
        .toBuffer();
      imageContent.push({
        type: "image_url",
        image_url: { url: `data:image/jpeg;base64,${preview.toString("base64")}` },
      });
    } catch {
      // skip
    }
  }

  if (imageContent.length === 0) return null;
  return await askVisionForSizeChart(openai, imageContent);
}

/**
 * Ask GPT-4o Vision to extract size chart from images.
 */
async function askVisionForSizeChart(
  openai: OpenAI,
  imageContent: Array<{ type: "image_url"; image_url: { url: string } }>,
): Promise<SizeChartEntry[] | null> {
  const response = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: [
      {
        role: "system",
        content: `You extract size chart data from product images.

Look for any table, chart, or text showing garment measurements per size (S, M, L, XL, 2XL etc).
Common measurements: chest/bust (胸围), length (衣长), shoulder (肩宽), sleeve (袖长), waist (腰围), hip (臀围).

If you find a size chart, return JSON:
{
  "found": true,
  "unit": "cm",
  "chart": [
    {"size": "S", "chest": 116, "length": 62, "shoulder": 56, "sleeve": 53},
    {"size": "M", "chest": 120, "length": 64, "shoulder": 58, "sleeve": 54},
    ...
  ]
}

If NO size chart is found in any image, return:
{"found": false}

Only return measurements you can clearly read. Use cm. Return JSON only.`,
      },
      {
        role: "user",
        content: [
          { type: "text", text: "Check these product images for a size chart or measurement table. Extract all measurements if found:" },
          ...imageContent,
        ],
      },
    ],
    max_tokens: 800,
    temperature: 0.1,
  });

  const content = response.choices[0]?.message?.content || "";
  console.log(`[size-chart] Vision response: ${content.substring(0, 200)}`);

  try {
    const cleaned = content.replace(/```json?\n?|\n?```/g, "").trim();
    const parsed = JSON.parse(cleaned);

    if (parsed.found && Array.isArray(parsed.chart) && parsed.chart.length > 0) {
      console.log(`[size-chart] Found size chart with ${parsed.chart.length} sizes`);
      return parsed.chart as SizeChartEntry[];
    }
  } catch {
    console.warn("[size-chart] Failed to parse Vision response");
  }

  return null;
}

/**
 * Try to fetch Taobao product description images via Oxylabs.
 * The description section contains long images with specs, size charts, etc.
 */
async function fetchTaobaoDescriptionImages(productId: string): Promise<string[]> {
  try {
    // Try the mobile Taobao detail page which often has desc images inline
    const resp = await fetch("https://realtime.oxylabs.io/v1/queries", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Basic " + Buffer.from(`${OXYLABS_USER}:${OXYLABS_PASS}`).toString("base64"),
      },
      body: JSON.stringify({
        source: "universal",
        url: `https://m.intl.taobao.com/detail/detail.html?id=${productId}`,
        render: "html",
        user_agent_type: "mobile",
      }),
    });

    if (!resp.ok) {
      console.warn(`[size-chart] Oxylabs request failed: ${resp.status}`);
      return [];
    }

    const data = await resp.json();
    const html: string = data.results?.[0]?.content || "";

    if (!html) {
      console.log("[size-chart] Oxylabs returned empty HTML");
      return [];
    }

    // Extract image URLs from description section
    const imgRegex = /https?:\/\/img\.alicdn\.com\/imgextra\/[^"'\s)]+/g;
    const matches = html.match(imgRegex) || [];
    const unique = [...new Set(matches)];

    console.log(`[size-chart] Found ${unique.length} description images`);
    return unique;
  } catch (err) {
    console.warn("[size-chart] Failed to fetch description images:", err);
    return [];
  }
}

/**
 * Format size chart as HTML table for Shopify product description.
 */
export function sizeChartToHtml(chart: SizeChartEntry[]): string {
  if (!chart.length) return "";

  // Collect all measurement keys (excluding 'size')
  const keys = new Set<string>();
  for (const entry of chart) {
    for (const key of Object.keys(entry)) {
      if (key !== "size" && entry[key] !== undefined) keys.add(key);
    }
  }

  const labels: Record<string, string> = {
    chest: "Chest",
    length: "Length",
    shoulder: "Shoulder",
    sleeve: "Sleeve",
    waist: "Waist",
    hip: "Hip",
  };

  const cols = [...keys];
  let html = "<h3>Size Chart (cm)</h3>\n<table>\n<thead>\n<tr>";
  html += "<th>Size</th>";
  for (const col of cols) {
    html += `<th>${labels[col] || col}</th>`;
  }
  html += "</tr>\n</thead>\n<tbody>\n";

  for (const entry of chart) {
    html += "<tr>";
    html += `<td>${entry.size}</td>`;
    for (const col of cols) {
      html += `<td>${entry[col] ?? "-"}</td>`;
    }
    html += "</tr>\n";
  }

  html += "</tbody>\n</table>";
  return html;
}
