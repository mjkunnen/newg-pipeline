import { chromium } from "playwright";
import { writeFile, mkdir, readFile } from "fs/promises";
import { join } from "path";
import { writeToContentAPI } from "../lib/contentApi.js";
import type { ScrapedAd } from "./types.js";

const OUTPUT_BASE = join(import.meta.dirname, "../../output/raw");
const CONFIG_PATH = join(import.meta.dirname, "../../config/pinterest-boards.json");

interface PinterestConfig {
  enabled: boolean;
  boards: string[];
  max_new_pins_per_run: number;
}

async function loadConfig(): Promise<PinterestConfig> {
  const raw = await readFile(CONFIG_PATH, "utf-8");
  return JSON.parse(raw) as PinterestConfig;
}

function todayDir(): string {
  return new Date().toISOString().split("T")[0];
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms + Math.random() * 500));
}

export async function scrapePinterest(): Promise<ScrapedAd[]> {
  const config = await loadConfig();

  if (!config.enabled) {
    console.log("[pinterest] Scraping disabled via config (enabled=false)");
    return [];
  }

  if (config.boards.length === 0) {
    console.log("[pinterest] No boards configured");
    return [];
  }

  const outputDir = join(OUTPUT_BASE, todayDir());
  await mkdir(outputDir, { recursive: true });

  // Dedup is handled by Postgres ON CONFLICT DO NOTHING via content API.
  // No Google Sheet read needed for dedup — we write all discovered pins
  // and the content API silently absorbs duplicates.

  const allAds: ScrapedAd[] = [];

  for (const boardUrl of config.boards) {
    const boardAds = await scrapeBoardPins(boardUrl, config.max_new_pins_per_run, outputDir);
    allAds.push(...boardAds);
  }

  // Write to Postgres via content API (dedup handled by ON CONFLICT DO NOTHING)
  if (allAds.length > 0) {
    await writeToContentAPI(allAds, "pinterest");
  }

  return allAds;
}

async function scrapeBoardPins(
  boardUrl: string,
  maxNewPins: number,
  outputDir: string,
): Promise<ScrapedAd[]> {
  console.log("[pinterest] Launching browser...");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });

  try {
    console.log(`[pinterest] Navigating to board: ${boardUrl}`);
    await page.goto(boardUrl, { waitUntil: "networkidle", timeout: 30000 });
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
        if (!allPins.has(pinId) && allPins.size < boardPinCount) {
          allPins.set(pinId, imageUrl);
        }
      }

      console.log(`[pinterest] Scroll ${i + 1}: ${visible.length} visible, ${allPins.size} total collected`);

      // Stop once we've collected the board's pin count (no more = "More ideas" territory)
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

    // Take up to maxNewPins pins from the board.
    // The content API will handle dedup via ON CONFLICT DO NOTHING —
    // pins already in Postgres will be silently skipped.
    const pinsToProcess = Array.from(allPins.entries()).slice(0, maxNewPins);
    console.log(`[pinterest] Processing up to ${maxNewPins} pins (board has ${allPins.size})`);

    if (pinsToProcess.length === 0) {
      console.log("[pinterest] No pins to add to dashboard");
      const metaPath = join(outputDir, "metadata-pinterest.json");
      await writeFile(metaPath, JSON.stringify([], null, 2));
      return [];
    }

    // Download images
    const ads: ScrapedAd[] = [];

    for (const [pinId, imageUrl] of pinsToProcess) {
      const id = `pinterest_${pinId}`;

      try {
        const response = await page.request.get(imageUrl);
        const buffer = await response.body();
        const ext = imageUrl.includes(".png") ? ".png" : ".jpg";
        const filename = `${id}${ext}`;
        const filepath = join(outputDir, filename);
        await writeFile(filepath, buffer);

        const sizeKB = (buffer.length / 1024).toFixed(0);
        console.log(`[pinterest] Downloaded: ${filename} (${sizeKB}KB)`);

        // Skip corrupt/empty images
        if (buffer.length < 1024) {
          console.warn(`[pinterest] Skipping ${filename} — too small (${buffer.length} bytes), likely corrupt`);
          continue;
        }

        ads.push({
          id,
          type: "image",
          creativeUrl: imageUrl,
          localPath: filepath,
          adCopy: "",
          reach: 0,
          daysActive: 0,
          startedAt: todayDir(),
          platforms: ["pinterest"],
          scrapedAt: new Date().toISOString(),
        });
      } catch (err) {
        console.error(`[pinterest] Failed to download pin ${pinId}:`, err);
      }

      await delay(300);
    }

    const metaPath = join(outputDir, "metadata-pinterest.json");
    await writeFile(metaPath, JSON.stringify(ads, null, 2));
    console.log(`[pinterest] Saved ${ads.length} pins to ${metaPath}`);

    return ads;
  } finally {
    await browser.close();
  }
}

// Run directly
if (process.argv[1]?.includes("pinterest")) {
  scrapePinterest().catch(console.error);
}
