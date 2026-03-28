import "dotenv/config";
import { readFile, writeFile, mkdir, readdir } from "fs/promises";
import { join } from "path";
import YAML from "yaml";
import { scrapePPSpy } from "./scraper/ppspy.js";
import { analyzeAd } from "./analyzer/vision.js";
import { matchProducts } from "./analyzer/matcher.js";
import { remixStaticAd, addTextOverlay } from "./remixer/image.js";
import { remixVideoAd } from "./remixer/video.js";
import { prepareAdCampaign, saveDrafts, launchCampaign } from "./launcher/meta.js";
import { uploadToGoogleDrive } from "./output/drive.js";
import type { ScrapedAd, RemixResult, CampaignDraft, Settings } from "./scraper/types.js";

const OUTPUT_BASE = join(import.meta.dirname, "../output");
const skipScrape = process.argv.includes("--skip-scrape");
const skipLaunch = process.argv.includes("--skip-launch");

async function loadSettings(): Promise<Settings> {
  try {
    const raw = await readFile(join(import.meta.dirname, "../config/settings.yaml"), "utf-8");
    return YAML.parse(raw) as Settings;
  } catch {
    return {
      max_ads: 5,
      trim_seconds: 2,
      collections_to_use: ["Graphic Items", "Comfy Vibe"],
      auto_upload_drive: false,
      auto_launch_meta: false,
    };
  }
}

async function loadLatestScrape(): Promise<ScrapedAd[]> {
  const rawDir = join(OUTPUT_BASE, "raw");
  const dates = await readdir(rawDir);
  const latest = dates.sort().reverse()[0];
  if (!latest) throw new Error("No scrape data found in output/raw/");

  const data = await readFile(join(rawDir, latest, "metadata.json"), "utf-8");
  return JSON.parse(data);
}

function todayDir(): string {
  return new Date().toISOString().split("T")[0];
}

async function writeToContentAPI(ads: ScrapedAd[]): Promise<void> {
  const contentApiUrl = process.env.CONTENT_API_URL;
  const dashboardSecret = process.env.DASHBOARD_SECRET;

  if (!contentApiUrl || !dashboardSecret) {
    console.log("[content-api] CONTENT_API_URL or DASHBOARD_SECRET not set — skipping Postgres write");
    return;
  }

  let written = 0;
  let skipped = 0;

  for (const ad of ads) {
    try {
      const body = {
        content_id: ad.id,
        source: "ppspy",
        creative_url: ad.creativeUrl ?? null,
        thumbnail_url: ad.thumbnailUrl ?? null,
        ad_copy: ad.adCopy ?? null,
        metadata_json: JSON.stringify({
          reach: ad.reach,
          daysActive: ad.daysActive,
          platforms: ad.platforms,
          type: ad.type,
        }),
      };

      const resp = await fetch(`${contentApiUrl}/api/content`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${dashboardSecret}`,
        },
        body: JSON.stringify(body),
      });

      if (resp.ok) {
        written++;
      } else {
        const text = await resp.text().catch(() => "");
        console.error(`[content-api] Failed to write ${ad.id}: HTTP ${resp.status} ${text.slice(0, 100)}`);
        skipped++;
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`[content-api] Network error for ${ad.id}: ${msg}`);
      skipped++;
      // Non-fatal: scrape pipeline continues
    }
  }

  console.log(`[content-api] Written: ${written}, skipped/failed: ${skipped}`);
}

async function main() {
  const settings = await loadSettings();
  console.log("=== Decarba Ad Remixer ===");
  console.log(`Time: ${new Date().toISOString()}`);
  console.log(`Settings: max_ads=${settings.max_ads}, trim_seconds=${settings.trim_seconds}`);

  // Step 1: Scrape
  let ads: ScrapedAd[];
  if (skipScrape) {
    console.log("\n[1/4] Loading previous scrape...");
    ads = await loadLatestScrape();
  } else {
    console.log("\n[1/4] Scraping PPSpy...");
    ads = await scrapePPSpy();
  }
  console.log(`Found ${ads.length} ads, processing top ${settings.max_ads}`);
  // Write all discovered ads to Postgres content_items (non-fatal if API unavailable)
  await writeToContentAPI(ads);
  ads = ads.slice(0, settings.max_ads);

  // Step 2: Analyze & Remix
  console.log("\n[2/4] Analyzing and remixing...");
  const remixes: RemixResult[] = [];
  const errors: Array<{ adId: string; error: string }> = [];

  for (const ad of ads) {
    if (!ad.localPath) {
      console.log(`[skip] ${ad.id} — no local file`);
      continue;
    }

    try {
      if (ad.type === "video") {
        console.log(`\n--- Video: ${ad.id} ---`);
        const outputPath = await remixVideoAd(ad.localPath, settings.trim_seconds);
        remixes.push({
          originalAd: ad,
          remixedPaths: [outputPath],
          method: "video-trim",
        });
      } else {
        console.log(`\n--- Image: ${ad.id} ---`);
        const analysis = await analyzeAd(ad.localPath);
        const products = await matchProducts(analysis, settings.collections_to_use[0]);
        const paths = await remixStaticAd(ad.localPath, analysis, products);

        // Add text overlays if the original had text
        if (analysis.text_overlays.length > 0) {
          console.log(`[remix] Original had ${analysis.text_overlays.length} text overlays, adding to remixes`);
          // Only add brand name overlay, skip recreating all text
          for (const path of paths) {
            await addTextOverlay(path, [
              {
                text: "NEWGARMENTS",
                position: "bottom",
                style: "bold",
                color: "#FFFFFF",
                approximate_size: "medium",
              },
            ]);
          }
        }

        remixes.push({
          originalAd: ad,
          analysis,
          remixedPaths: paths,
          method: "text-to-image",
        });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`[error] ${ad.id}: ${msg}`);
      errors.push({ adId: ad.id, error: msg });
    }
  }

  console.log(`\nRemixed: ${remixes.length}/${ads.length} (${errors.length} errors)`);

  // Step 3: Upload to Drive
  if (settings.auto_upload_drive) {
    console.log("\n[3/4] Uploading to Google Drive...");
    const allFiles = remixes.flatMap((r) => r.remixedPaths);
    await uploadToGoogleDrive(allFiles, `${todayDir()}-decarba-remixes`);
  } else {
    console.log("\n[3/4] Drive upload skipped (auto_upload_drive: false)");
  }

  // Step 4: Meta campaigns
  console.log("\n[4/4] Preparing Meta campaign drafts...");
  const drafts: CampaignDraft[] = remixes.map((r) => prepareAdCampaign(r));
  const draftsPath = await saveDrafts(drafts);
  console.log(`Drafts saved to: ${draftsPath}`);

  if (settings.auto_launch_meta && !skipLaunch && process.env.AUTO_LAUNCH === "true") {
    console.log("\nLaunching campaigns...");
    for (const draft of drafts) {
      try {
        const result = await launchCampaign(draft);
        console.log(`[meta] Campaign ${result.campaignId} created (PAUSED)`);
      } catch (err) {
        console.error(`[meta] Launch failed:`, err);
      }
    }
  } else {
    console.log("Campaign launch skipped. Review drafts.json, then set AUTO_LAUNCH=true to launch.");
  }

  // Save report
  const reportDir = join(OUTPUT_BASE, "remixed", todayDir());
  await mkdir(reportDir, { recursive: true });
  const report = {
    timestamp: new Date().toISOString(),
    settings,
    adsScraped: ads.length,
    adsRemixed: remixes.length,
    errors,
    remixes: remixes.map((r) => ({
      originalId: r.originalAd.id,
      originalUrl: r.originalAd.creativeUrl,
      type: r.originalAd.type,
      reach: r.originalAd.reach,
      method: r.method,
      outputFiles: r.remixedPaths,
    })),
  };
  const reportPath = join(reportDir, "report.json");
  await writeFile(reportPath, JSON.stringify(report, null, 2));
  console.log(`\nReport: ${reportPath}`);
  console.log("=== Done ===");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
