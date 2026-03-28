import { chromium } from "playwright";
import { writeFile, mkdir } from "fs/promises";
import { join } from "path";
import type { ScrapedAd } from "./types.js";
import { loadConfig } from "./config.js";
import { writeToContentAPI } from "./contentApi.js";

const OUTPUT_BASE = join(import.meta.dirname, "../../output/raw");

interface PinterestConfig {
  board_url: string;
  max_new_pins: number;
  scroll_rounds: number;
  stale_rounds_limit: number;
}

function todayDir(): string {
  return new Date().toISOString().split("T")[0];
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms + Math.random() * 500));
}

async function getProcessedPinIds(): Promise<Set<string>> {
  const contentApiUrl = process.env.CONTENT_API_URL;
  const dashboardSecret = process.env.DASHBOARD_SECRET;

  if (!contentApiUrl || !dashboardSecret) {
    console.log("[pinterest] Content API not configured — dedup disabled for this run");
    return new Set();
  }

  try {
    const resp = await fetch(`${contentApiUrl}/api/content?source=pinterest&limit=1000`, {
      headers: { "Authorization": `Bearer ${dashboardSecret}` },
    });
    if (!resp.ok) {
      console.error(`[pinterest] Content API returned ${resp.status} — dedup disabled`);
      return new Set();
    }
    const items = await resp.json() as Array<{ content_id: string }>;
    // content_id is stored as "pinterest_12345" — strip prefix for comparison
    const ids = new Set(items.map(i => i.content_id.replace("pinterest_", "")));
    console.log(`[pinterest] ${ids.size} seen pin IDs from Postgres`);
    return ids;
  } catch (err) {
    console.error(`[pinterest] Failed to load seen IDs from Postgres: ${err}`);
    return new Set(); // fail open — better to re-discover than skip all
  }
}

export async function scrapePinterest(): Promise<ScrapedAd[]> {
  const config = loadConfig<PinterestConfig>("pinterest-boards.json");
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
    console.log(`[pinterest] Navigating to board: ${config.board_url}`);
    await page.goto(config.board_url, { waitUntil: "networkidle", timeout: 30000 });
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
    for (let i = 0; i < config.scroll_rounds; i++) {
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

      // Stop if no new pins found for configured stale rounds
      if (allPins.size === prevSize) {
        staleRounds++;
        if (staleRounds >= config.stale_rounds_limit) {
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

    // Show all board pins that are NOT in Postgres
    const newPins: Array<{ pinId: string; imageUrl: string }> = [];
    for (const [pinId, imageUrl] of allPins) {
      if (!processedIds.has(pinId)) {
        newPins.push({ pinId, imageUrl });
      }
    }
    console.log(`[pinterest] ${newPins.length} pins not in Postgres (${allPins.size - newPins.length} already seen)`);
    if (newPins.length > config.max_new_pins) {
      console.log(`[pinterest] Limiting to ${config.max_new_pins} new pins per day`);
      newPins.splice(config.max_new_pins);
    }

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

        // Skip corrupt/empty images
        if (buffer.length < 1024) {
          console.warn(`[pinterest] Skipping ${filename} — too small (${buffer.length} bytes), likely corrupt`);
          continue;
        }

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

    const result = await writeToContentAPI(ads, "pinterest");
    console.log(`[result] source=pinterest found=${allPins.size} written=${result.written} skipped=${result.skipped} errors=0`);

    return ads;
  } finally {
    await browser.close();
  }
}

// Run directly
if (process.argv[1]?.includes("pinterest")) {
  scrapePinterest().catch(console.error);
}
