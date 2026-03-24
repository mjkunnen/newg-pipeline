import { chromium } from "playwright";
import { writeFile, mkdir } from "fs/promises";
import { join } from "path";
import type { ScrapedAd } from "./types.js";

const OUTPUT_BASE = join(import.meta.dirname, "../../output/raw");
const BOARD_URL = "https://www.pinterest.com/mygarmentseu/ads-newgarments/";

// Pinterest remake tracking sheet (same one used by cloud_pinterest.py)
const SHEET_ID = "1BQ54wjilxW3F8rQFnVjwCRJtBTPDrSj3U5D0XYHjsgY";
const SHEET_CSV_URL = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Blad1`;

function todayDir(): string {
  return new Date().toISOString().split("T")[0];
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms + Math.random() * 500));
}

async function getProcessedPinIds(): Promise<Set<string>> {
  try {
    const resp = await fetch(SHEET_CSV_URL);
    if (!resp.ok) throw new Error(`Sheet fetch failed: ${resp.status}`);
    const text = await resp.text();
    const lines = text.split("\n");
    if (lines.length < 2) return new Set();

    // Find pin_id column (G = index 6, or by header)
    const headers = lines[0].split(",").map((h) => h.replace(/"/g, "").trim().toLowerCase());
    let pinCol = 6;
    for (let i = 0; i < headers.length; i++) {
      if (headers[i] === "pin_id") {
        pinCol = i;
        break;
      }
    }

    const ids = new Set<string>();
    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(",");
      if (cols.length > pinCol) {
        const val = cols[pinCol].replace(/"/g, "").trim();
        if (val) ids.add(val);
      }
    }
    console.log(`[pinterest] Sheet: ${ids.size} already-processed pin IDs`);
    return ids;
  } catch (err) {
    console.error(`[pinterest] Failed to read tracking sheet: ${err}`);
    return new Set();
  }
}

export async function scrapePinterest(): Promise<ScrapedAd[]> {
  const outputDir = join(OUTPUT_BASE, todayDir());
  await mkdir(outputDir, { recursive: true });

  // Check which pins are already remade
  const processedIds = await getProcessedPinIds();

  console.log("[pinterest] Launching browser...");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });

  try {
    console.log(`[pinterest] Navigating to board: ${BOARD_URL}`);
    await page.goto(BOARD_URL, { waitUntil: "networkidle", timeout: 30000 });
    await delay(3000);

    // Scroll to load ALL pins (board may have 30+ pins, Pinterest lazy-loads)
    let prevCount = 0;
    for (let i = 0; i < 15; i++) {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await delay(2000);
      const currentCount = await page.locator('a[href*="/pin/"]').count();
      console.log(`[pinterest] Scroll ${i + 1}: ${currentCount} pin links found`);
      if (currentCount === prevCount && i > 2) break; // no new pins loaded
      prevCount = currentCount;
    }

    // Extract pin data
    const rawPins = await page.evaluate(() => {
      const pins: Array<{ pinId: string; imageUrl: string }> = [];
      const seen = new Set<string>();

      const links = document.querySelectorAll('a[href*="/pin/"]');
      for (const el of links) {
        const href = el.getAttribute("href") || "";
        const match = href.match(/\/pin\/(\d+)/);
        if (!match) continue;

        const pinId = match[1];
        if (seen.has(pinId)) continue;
        seen.add(pinId);

        const img = el.querySelector("img");
        if (!img) continue;

        const src = img.getAttribute("src") || "";
        if (!src.includes("pinimg.com")) continue;

        // Get highest resolution
        const imageUrl = src.replace(
          /\/(236x|474x|564x|736x)\//,
          "/originals/",
        );
        pins.push({ pinId, imageUrl });
      }

      return pins;
    });

    console.log(`[pinterest] Found ${rawPins.length} total pins on board`);

    // Filter out already-processed pins
    const newPins = rawPins.filter((p) => !processedIds.has(p.pinId));
    console.log(`[pinterest] ${newPins.length} new pins (${rawPins.length - newPins.length} already remade)`);

    if (newPins.length === 0) {
      console.log("[pinterest] No new pins to add to dashboard");
      const metaPath = join(outputDir, "metadata-pinterest.json");
      await writeFile(metaPath, JSON.stringify([], null, 2));
      return [];
    }

    // Convert to ScrapedAd format + download images
    const ads: ScrapedAd[] = [];

    for (const pin of newPins) {
      const id = `pinterest_${pin.pinId}`;

      try {
        const response = await page.request.get(pin.imageUrl);
        const buffer = await response.body();
        const ext = pin.imageUrl.includes(".png") ? ".png" : ".jpg";
        const filename = `${id}${ext}`;
        const filepath = join(outputDir, filename);
        await writeFile(filepath, buffer);

        const sizeKB = (buffer.length / 1024).toFixed(0);
        console.log(`[pinterest] Downloaded: ${filename} (${sizeKB}KB)`);

        ads.push({
          id,
          type: "image",
          creativeUrl: pin.imageUrl,
          localPath: filepath,
          adCopy: "",
          reach: 0,
          daysActive: 0,
          startedAt: todayDir(),
          platforms: ["pinterest"],
          scrapedAt: new Date().toISOString(),
        });
      } catch (err) {
        console.error(`[pinterest] Failed to download pin ${pin.pinId}:`, err);
      }

      await delay(300);
    }

    // Save metadata
    const metaPath = join(outputDir, "metadata-pinterest.json");
    await writeFile(metaPath, JSON.stringify(ads, null, 2));
    console.log(`[pinterest] Saved ${ads.length} new pins to ${metaPath}`);

    return ads;
  } finally {
    await browser.close();
  }
}

// Run directly
if (process.argv[1]?.includes("pinterest")) {
  scrapePinterest().catch(console.error);
}
