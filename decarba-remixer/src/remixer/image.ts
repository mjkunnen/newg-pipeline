import { fal } from "@fal-ai/client";
import { readFile, writeFile, mkdir } from "fs/promises";
import { join } from "path";
import sharp from "sharp";
import type { AdAnalysis, ScrapedAd, Product, RemixResult, TextOverlay } from "../scraper/types.js";

const OUTPUT_BASE = join(import.meta.dirname, "../../output/remixed");

function todayDir(): string {
  return new Date().toISOString().split("T")[0];
}

function detectAspectRatio(width: number, height: number): string {
  const ratio = width / height;
  if (ratio > 1.7) return "landscape_16_9";
  if (ratio > 1.2) return "landscape_4_3";
  if (ratio < 0.6) return "portrait_9_16";
  if (ratio < 0.85) return "portrait_4_5";
  return "square";
}

export async function remixStaticAd(
  originalPath: string,
  analysis: AdAnalysis,
  products: Product[]
): Promise<string[]> {
  // Configure fal client
  fal.config({ credentials: process.env.FAL_KEY });

  const outputDir = join(OUTPUT_BASE, todayDir());
  await mkdir(outputDir, { recursive: true });

  // Get original dimensions for aspect ratio
  const originalBuffer = await readFile(originalPath);
  const metadata = await sharp(originalBuffer).metadata();
  const aspectRatio = detectAspectRatio(metadata.width || 1080, metadata.height || 1080);

  // Build prompt with NEWGARMENTS products
  const productNames = products.map((p) => p.name).join(", ");
  const prompt = `${analysis.remake_prompt}. Model wearing NEWGARMENTS ${productNames}. High quality fashion ad photography, professional studio or urban setting, no text, no logos, no brand names visible on clothing.`;

  console.log(`[remix] Prompt: ${prompt.slice(0, 120)}...`);
  console.log(`[remix] Aspect ratio: ${aspectRatio}`);

  // Generate 2 variations
  const result = await fal.subscribe("fal-ai/nano-banana-2", {
    input: {
      prompt,
      image_size: aspectRatio,
      num_images: 2,
    },
  });

  const images = (result.data as { images?: Array<{ url: string }> }).images || [];
  if (images.length === 0) throw new Error("No images returned from fal.ai");

  // Download generated images
  const outputPaths: string[] = [];
  for (let i = 0; i < images.length; i++) {
    const imgRes = await fetch(images[i].url);
    const imgBuffer = Buffer.from(await imgRes.arrayBuffer());

    const filename = `remix_${todayDir()}_${Date.now()}_v${i + 1}.jpg`;
    const outPath = join(outputDir, filename);
    await writeFile(outPath, imgBuffer);
    outputPaths.push(outPath);
    console.log(`[remix] Saved variation ${i + 1}: ${filename}`);
  }

  return outputPaths;
}

export async function addTextOverlay(
  imagePath: string,
  texts: TextOverlay[]
): Promise<string> {
  const img = sharp(imagePath);
  const meta = await img.metadata();
  const width = meta.width || 1080;
  const height = meta.height || 1080;

  const svgParts: string[] = [];

  for (const overlay of texts) {
    const text = overlay.text
      .replace(/decarba/gi, "NEWGARMENTS")
      .replace(/decarbas?/gi, "NEWGARMENTS");

    const fontSize =
      overlay.approximate_size === "large"
        ? Math.round(width * 0.08)
        : overlay.approximate_size === "medium"
          ? Math.round(width * 0.05)
          : Math.round(width * 0.035);

    const y =
      overlay.position === "top"
        ? Math.round(height * 0.1)
        : overlay.position === "center"
          ? Math.round(height * 0.5)
          : Math.round(height * 0.9);

    const fontWeight = overlay.style === "bold" ? "bold" : "normal";

    svgParts.push(
      `<text x="${Math.round(width / 2)}" y="${y}" text-anchor="middle" ` +
        `font-family="Arial, Helvetica, sans-serif" font-size="${fontSize}" ` +
        `font-weight="${fontWeight}" fill="${overlay.color || "#FFFFFF"}" ` +
        `stroke="#000000" stroke-width="1">${escapeXml(text)}</text>`
    );
  }

  if (svgParts.length === 0) return imagePath;

  const svg = `<svg width="${width}" height="${height}">${svgParts.join("")}</svg>`;
  const outPath = imagePath.replace(/\.jpg$/, "_text.jpg");

  await sharp(imagePath)
    .composite([{ input: Buffer.from(svg), top: 0, left: 0 }])
    .jpeg({ quality: 95 })
    .toFile(outPath);

  console.log(`[remix] Added text overlay: ${outPath}`);
  return outPath;
}

function escapeXml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
