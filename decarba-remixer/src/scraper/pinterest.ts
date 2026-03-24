import { chromium } from "playwright";
import { writeFile, mkdir } from "fs/promises";
import { join } from "path";
import type { ScrapedAd } from "./types.js";

const OUTPUT_BASE = join(import.meta.dirname, "../../output/raw");
const BOARD_URL = "https://www.pinterest.com/MyGarmentsEU/ads-newgarments/";

function todayDir(): string {
  return new Date().toISOString().split("T")[0];
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms + Math.random() * 500));
}

export async function scrapePinterest(): Promise<ScrapedAd[]> {
  const outputDir = join(OUTPUT_BASE, todayDir());
  await mkdir(outputDir, { recursive: true });

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

    // Scroll to load more pins
    for (let i = 0; i < 5; i++) {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await delay(2000);
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

    console.log(`[pinterest] Found ${rawPins.length} pins on board`);

    // Convert to ScrapedAd format + download images
    const ads: ScrapedAd[] = [];

    for (let i = 0; i < rawPins.length; i++) {
      const pin = rawPins[i];
      const id = `pinterest_${pin.pinId}`;

      // Download image
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
