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

    // Pinterest virtualizes the DOM — pins get removed as you scroll past them.
    // Collect pin data on EVERY scroll, accumulating in a Map to deduplicate.
    // IMPORTANT: only collect pins from the board grid, not "More ideas" below.
    const allPins = new Map<string, string>(); // pinId → imageUrl

    // First, get the board pin count from the page header
    const boardPinCount = await page.evaluate(() => {
      // Look for text like "31 Pins" in the page
      const allText = document.body.innerText;
      const match = allText.match(/(\d+)\s*Pins/i);
      return match ? parseInt(match[1]) : 50; // fallback to 50
    });
    console.log(`[pinterest] Board says ${boardPinCount} pins`);

    let staleRounds = 0;
    for (let i = 0; i < 15; i++) {
      const prevSize = allPins.size;

      // Extract visible pins
      const visible = await page.evaluate(() => {
        const results: Array<{ pinId: string; imageUrl: string }> = [];
        const links = document.querySelectorAll('a[href*="/pin/"]');
        for (const el of links) {
          const href = el.getAttribute("href") || "";
          const match = href.match(/\/pin\/(\d+)/);
          if (!match) continue;
          const img = el.querySelector("img");
          if (!img) continue;
          const src = img.getAttribute("src") || "";
          if (!src.includes("pinimg.com")) continue;
          const imageUrl = src.replace(/\/(236x|474x|564x|736x)\//, "/originals/");
          results.push({ pinId: match[1], imageUrl });
        }
        return results;
      });

      for (const { pinId, imageUrl } of visible) {
        if (!allPins.has(pinId)) {
          allPins.set(pinId, imageUrl);
        }
      }

      console.log(`[pinterest] Scroll ${i + 1}: ${visible.length} visible, ${allPins.size} total collected`);

      // Stop once we've collected at least the board's pin count
      if (allPins.size >= boardPinCount) {
        console.log(`[pinterest] Reached board pin count (${boardPinCount}), stopping scroll`);
        break;
      }

      // Stop if no new pins found for 2 consecutive scrolls
      if (allPins.size === prevSize) {
        staleRounds++;
        if (staleRounds >= 2) {
          console.log(`[pinterest] No new pins in ${staleRounds} scrolls, stopping`);
          break;
        }
      } else {
        staleRounds = 0;
      }

      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await delay(2000);
    }

    console.log(`[pinterest] Found ${allPins.size} total unique pins on board`);

    // Filter out already-processed pins
    const newPins: Array<{ pinId: string; imageUrl: string }> = [];
    for (const [pinId, imageUrl] of allPins) {
      if (!processedIds.has(pinId)) {
        newPins.push({ pinId, imageUrl });
      }
    }
    console.log(`[pinterest] ${newPins.length} new pins (${allPins.size - newPins.length} already remade)`);

    if (newPins.length === 0) {
      console.log("[pinterest] No new pins to add to dashboard");
      const metaPath = join(outputDir, "metadata-pinterest.json");
      await writeFile(metaPath, JSON.stringify([], null, 2));
      return [];
    }

    // Download images
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
