import { chromium } from "playwright";
import { writeFile, mkdir } from "fs/promises";
import { join } from "path";
import type { ScrapedAd } from "./types.js";

const OUTPUT_BASE = join(import.meta.dirname, "../../output/raw");
const DEBUG_DIR = join(import.meta.dirname, "../../output/debug");

const PPSPY_ADS_URL =
  'https://app.ppspy.com/ads?extend_keywords=[{"field":"all","value":"decarba","logic_operator":"and"}]&ad_forecast=[3]&order_by=ad_created_at&direction=desc';

function todayDir(): string {
  return new Date().toISOString().split("T")[0];
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms + Math.random() * 1000));
}

function parseReach(text: string): number {
  const str = text.toLowerCase().trim();
  if (str.includes("m")) return parseFloat(str) * 1_000_000;
  if (str.includes("k")) return parseFloat(str) * 1_000;
  return parseFloat(str) || 0;
}

function parseDays(text: string): number {
  const match = text.match(/(\d+)/);
  return match ? parseInt(match[1]) : 0;
}

export async function scrapePPSpy(): Promise<ScrapedAd[]> {
  const cookiesJson = process.env.PPSPY_COOKIES_JSON;
  if (!cookiesJson) throw new Error("PPSPY_COOKIES_JSON required in .env");

  const outputDir = join(OUTPUT_BASE, todayDir());
  await mkdir(outputDir, { recursive: true });
  await mkdir(DEBUG_DIR, { recursive: true });

  // Parse EditThisCookie export → Playwright cookie format
  const rawCookies: Array<{
    name: string;
    value: string;
    domain: string;
    path: string;
    expirationDate?: number;
    httpOnly?: boolean;
    secure?: boolean;
  }> = JSON.parse(cookiesJson);

  const playwrightCookies = rawCookies.map((c) => ({
    name: c.name,
    value: c.value,
    domain: c.domain || ".ppspy.com",
    path: c.path || "/",
    expires: c.expirationDate || -1,
    httpOnly: c.httpOnly ?? false,
    secure: c.secure ?? false,
    sameSite: "Lax" as const,
  }));

  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-blink-features=AutomationControlled"],
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  });

  // Set cookies BEFORE navigating
  await context.addCookies(playwrightCookies);
  console.log(`[ppspy] Set ${playwrightCookies.length} cookies`);

  const page = await context.newPage();

  try {
    // Go to the Ads page first (clean, no query params)
    console.log("[ppspy] Navigating to Ads page...");
    await page.goto("https://app.ppspy.com/ads", { waitUntil: "domcontentloaded", timeout: 60000 });
    await delay(5000);

    // Screenshot before search
    await page.screenshot({ path: join(DEBUG_DIR, "ppspy-before-search.png") });

    // Type "decarba" in the main search bar
    console.log("[ppspy] Typing 'decarba' in search...");
    const searchInput = page.locator('input[placeholder*="Search by"]').first();
    await searchInput.waitFor({ timeout: 10000 });
    await searchInput.click();
    await delay(500);
    await searchInput.fill("decarba");
    await delay(500);

    // Click the blue search icon button next to the input
    console.log("[ppspy] Clicking search icon...");
    await page.locator('button.el-button--primary').filter({ has: page.locator('i.el-icon-search, svg') }).first().click().catch(async () => {
      // Fallback: press Enter
      console.log("[ppspy] Fallback: pressing Enter...");
      await searchInput.press("Enter");
    });
    await delay(3000);

    // Check the "Winning" AI Score checkbox if not already checked
    console.log("[ppspy] Checking Winning filter...");
    const winningCheckbox = page.locator("text=Winning").first();
    try {
      await winningCheckbox.waitFor({ timeout: 5000 });
      // Check if already active
      const isChecked = await page.locator('.el-checkbox.is-checked:has-text("Winning"), .el-radio.is-checked:has-text("Winning")').count();
      if (!isChecked) {
        await winningCheckbox.click();
        console.log("[ppspy] Clicked Winning");
        await delay(1000);
      } else {
        console.log("[ppspy] Winning already selected");
      }
    } catch {
      console.log("[ppspy] Winning checkbox not found, may already be filtered via URL");
    }

    // Click the orange Search button
    console.log("[ppspy] Clicking Search button...");
    const searchBtn = page.locator("button").filter({ hasText: /^Search$/ }).first();
    try {
      await searchBtn.waitFor({ timeout: 5000 });
      await searchBtn.click();
      console.log("[ppspy] Search button clicked");
    } catch {
      console.log("[ppspy] Search button not found, pressing Enter instead");
      await searchInput.press("Enter");
    }

    // Wait for results to load
    console.log("[ppspy] Waiting for results...");
    await delay(10000);

    // Screenshot after search
    await page.screenshot({ path: join(DEBUG_DIR, "ppspy-after-search.png"), fullPage: true });

    // Scroll to trigger lazy loading
    for (let i = 0; i < 5; i++) {
      await page.evaluate(() => window.scrollBy(0, 800));
      await delay(1500);
    }
    // Scroll back to top
    await page.evaluate(() => window.scrollTo(0, 0));
    await delay(1000);

    // Save debug screenshot + HTML
    await page.screenshot({ path: join(DEBUG_DIR, "ppspy-page.png"), fullPage: true });
    const html = await page.content();
    await writeFile(join(DEBUG_DIR, "ppspy-raw.html"), html);
    console.log(`[ppspy] Debug saved: ppspy-page.png + ppspy-raw.html`);

    // Extract ad data from rendered DOM
    const rawAds = await page.evaluate(() => {
      const ads: Array<{
        creativeUrl: string;
        type: string;
        adCopy: string;
        reach: string;
        reachCost: string;
        duration: string;
        adsets: string;
        dateRange: string;
        platforms: string[];
      }> = [];

      // Ad cards are .card-item inside .page-list
      const cards = document.querySelectorAll(".card-item");
      if (cards.length === 0) return ads;

      for (const card of cards) {
        // Creative image URL
        const img = card.querySelector("img.el-image__inner") as HTMLImageElement | null;
        const creativeUrl = img?.src || "";

        // Video or image? Check for .video-play-icon
        const hasVideoIcon = !!card.querySelector(".video-play-icon");
        const type = hasVideoIcon ? "video" : "image";

        // Ad copy text (the <p> tooltip)
        const adCopyEl = card.querySelector("p.el-tooltip");
        const adCopy = adCopyEl?.textContent?.trim() || "";

        // Stats: Duration, Reach, Adset — they're in the blue stats box
        // Structure: pairs of (value div, label div)
        const statLabels = card.querySelectorAll(".tw-text-xs.tw-text-gray-1000.tw-leading-5");
        let duration = "";
        let reach = "";
        let reachCost = "";
        let adsets = "";

        for (const label of statLabels) {
          const labelText = label.textContent?.trim() || "";
          const valueEl = label.previousElementSibling;

          if (labelText === "Duration") {
            duration = valueEl?.textContent?.trim() || "";
          } else if (labelText === "Reach(cost)") {
            // Reach value and cost are in separate spans
            const reachSpan = valueEl?.querySelector(".tw-font-black");
            const costSpan = valueEl?.querySelector(".tw-text-gray-1400");
            reach = reachSpan?.textContent?.trim() || valueEl?.textContent?.trim() || "";
            reachCost = costSpan?.textContent?.trim().replace(/[()$]/g, "") || "";
          } else if (labelText === "Adset") {
            adsets = valueEl?.textContent?.trim() || "";
          }
        }

        // Date range
        const dateSpan = card.querySelector(".tw-text-xs.tw-text-gray-1000.tw-leading-4");
        const dateRange = dateSpan?.textContent?.trim() || "";

        // Platforms from SVG icons
        const platforms: string[] = [];
        card.querySelectorAll("use").forEach((use) => {
          const href = use.getAttribute("xlink:href") || use.getAttribute("href") || "";
          if (href.includes("facebook")) platforms.push("facebook");
          if (href.includes("instagram")) platforms.push("instagram");
          if (href.includes("messenger")) platforms.push("messenger");
          if (href.includes("audience_network")) platforms.push("audience_network");
          if (href.includes("threads")) platforms.push("threads");
        });

        if (creativeUrl) {
          ads.push({
            creativeUrl,
            type,
            adCopy,
            reach,
            reachCost,
            duration,
            adsets,
            dateRange,
            platforms: [...new Set(platforms)],
          });
        }
      }

      return ads;
    });

    console.log(`[ppspy] Extracted ${rawAds.length} ads from DOM`);

    // Parse into ScrapedAd format
    const ads: ScrapedAd[] = rawAds.slice(0, 10).map((raw, i) => ({
      id: `decarba_${todayDir()}_${i}`,
      type: raw.type as "image" | "video",
      creativeUrl: raw.creativeUrl,
      adCopy: raw.adCopy || undefined,
      reach: parseReach(raw.reach),
      daysActive: parseDays(raw.duration),
      startedAt: raw.dateRange.split(" - ")[0] || todayDir(),
      platforms: raw.platforms,
      scrapedAt: new Date().toISOString(),
    }));

    console.log(`[ppspy] Top ${ads.length} ads ready`);

    // For video ads: click into detail dialog to get real video URL
    for (let i = 0; i < ads.length; i++) {
      const ad = ads[i];
      if (ad.type !== "video") continue;

      try {
        console.log(`[ppspy] Opening detail for video ad ${ad.id} (card ${i})...`);

        // Scroll the card into view and click the image/video area
        const card = page.locator(`.card-item`).nth(i);
        await card.scrollIntoViewIfNeeded();
        await delay(500);

        // Listen for network requests that might contain video URLs
        const videoUrls: string[] = [];
        const requestHandler = (request: { url: () => string }) => {
          const url = request.url();
          if (url.includes(".mp4") || url.includes(".webm") || url.includes("video") || url.includes("fbcdn")) {
            videoUrls.push(url);
          }
        };
        page.on("request", requestHandler);

        // Click the card itself (the whole div)
        await card.click({ position: { x: 100, y: 100 } });
        await delay(4000);

        // Screenshot after click
        await page.screenshot({ path: join(DEBUG_DIR, `ppspy-click-${i}.png`) });

        // Check if a dialog/drawer opened
        const dialogVisible = await page.locator(".el-dialog:visible, .el-drawer:visible, .detail-drawer:visible, [class*='detail']:visible").count();
        console.log(`[ppspy] After click: ${dialogVisible} dialog(s) visible, ${videoUrls.length} video network requests`);

        // Check for video element anywhere on page now
        const videoUrl = await page.evaluate(() => {
          // Check for video elements
          const videos = document.querySelectorAll("video");
          for (const v of videos) {
            if (v.src) return v.src;
            const source = v.querySelector("source");
            if (source && source.src) return source.src;
          }

          // Check for any new dialogs/drawers
          const overlays = document.querySelectorAll(".el-dialog, .el-drawer, [class*='detail']");
          for (const overlay of overlays) {
            const style = window.getComputedStyle(overlay);
            if (style.display === "none" || style.visibility === "hidden") continue;

            const vid = overlay.querySelector("video");
            if (vid?.src) return vid.src;
            const src = overlay.querySelector("video source");
            if (src instanceof HTMLSourceElement && src.src) return src.src;

            // Check iframes
            const iframes = overlay.querySelectorAll("iframe");
            for (const iframe of iframes) {
              if (iframe.src && (iframe.src.includes("video") || iframe.src.includes(".mp4"))) {
                return iframe.src;
              }
            }
          }

          return null;
        });

        page.off("request", requestHandler);

        if (videoUrl) {
          console.log(`[ppspy] Found video element URL for ${ad.id}: ${videoUrl.slice(0, 80)}...`);
          ad.thumbnailUrl = ad.creativeUrl;
          ad.creativeUrl = videoUrl;
        } else if (videoUrls.length > 0) {
          console.log(`[ppspy] Found video via network for ${ad.id}: ${videoUrls[0].slice(0, 80)}...`);
          ad.thumbnailUrl = ad.creativeUrl;
          ad.creativeUrl = videoUrls[0];
        } else {
          // Save page HTML for debugging
          const pageHtml = await page.content();
          await writeFile(join(DEBUG_DIR, `ppspy-click-${i}.html`), pageHtml);
          console.log(`[ppspy] No video URL found for ${ad.id}, saved debug HTML`);
        }

        // Close any open dialog/drawer
        await page.keyboard.press("Escape");
        await delay(1000);
      } catch (err) {
        console.error(`[ppspy] Failed to get video URL for ${ad.id}:`, err);
        // Make sure dialog is closed
        await page.keyboard.press("Escape");
        await delay(500);
      }
    }

    // Download creatives
    for (const ad of ads) {
      if (!ad.creativeUrl) continue;
      try {
        const isVideo = ad.creativeUrl.includes(".mp4") || ad.creativeUrl.includes(".webm") || ad.creativeUrl.includes("video");
        const ext = isVideo ? ".mp4" : (ad.type === "video" ? ".mp4" : ".jpg");
        const filename = `${ad.id}${ext}`;
        const filepath = join(outputDir, filename);

        const response = await page.request.get(ad.creativeUrl);
        const buffer = await response.body();
        await writeFile(filepath, buffer);
        ad.localPath = filepath;

        const sizeKB = (buffer.length / 1024).toFixed(0);
        const sizeMB = (buffer.length / 1024 / 1024).toFixed(1);
        const sizeStr = buffer.length > 1024 * 1024 ? `${sizeMB}MB` : `${sizeKB}KB`;
        console.log(`[ppspy] Downloaded: ${filename} (${sizeStr})`);
      } catch (err) {
        console.error(`[ppspy] Failed to download ${ad.id}:`, err);
      }
      await delay(500);
    }

    // Save metadata
    const metaPath = join(outputDir, "metadata.json");
    await writeFile(metaPath, JSON.stringify(ads, null, 2));
    console.log(`[ppspy] Saved ${ads.length} ads to ${metaPath}`);

    return ads;
  } finally {
    await browser.close();
  }
}

// Run directly
if (process.argv[1]?.includes("ppspy")) {
  import("dotenv/config").then(() => scrapePPSpy().catch(console.error));
}
