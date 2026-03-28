import "dotenv/config";
import { ApifyClient } from "apify-client";
import type { ScrapedAd } from "./types.js";
import { writeToContentAPI } from "./contentApi.js";
import { loadConfig } from "./config.js";

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

interface MetaConfig {
  advertiser_urls: string[];
  max_ads_per_competitor: number;
  country: string;
  timeout_seconds: number;
}

export interface MetaAdResult {
  adArchiveID: string;
  pageName?: string;
  snapshot?: {
    images?: Array<{ original_image_url?: string }>;
    videos?: Array<{ video_hd_url?: string; video_preview_image_url?: string }>;
    body?: { text?: string };
  };
  startDate?: string;
  isActive?: boolean;
}

export function transformMetaResults(items: MetaAdResult[]): ScrapedAd[] {
  const ads: ScrapedAd[] = [];
  for (const item of items) {
    const imageUrl = item.snapshot?.images?.[0]?.original_image_url;
    const videoUrl = item.snapshot?.videos?.[0]?.video_hd_url;
    const creativeUrl = videoUrl ?? imageUrl ?? "";
    const type: "image" | "video" = videoUrl ? "video" : "image";

    if (!creativeUrl || !item.adArchiveID) continue;

    ads.push({
      id: `meta_${item.adArchiveID}`,
      type,
      creativeUrl,
      thumbnailUrl: item.snapshot?.videos?.[0]?.video_preview_image_url ?? imageUrl,
      adCopy: item.snapshot?.body?.text ?? "",
      reach: 0,
      daysActive: 0,
      startedAt: item.startDate ?? new Date().toISOString().split("T")[0],
      platforms: ["meta"],
      scrapedAt: new Date().toISOString(),
    });
  }
  return ads;
}

export async function scrapeMetaAds(): Promise<ScrapedAd[]> {
  const APIFY_TOKEN = requireEnv("APIFY_TOKEN");
  const config = loadConfig<MetaConfig>("meta-competitors.json");
  const client = new ApifyClient({ token: APIFY_TOKEN });

  console.log(`[meta] Starting Apify actor with ${config.advertiser_urls.length} competitor URLs`);

  const startUrls = config.advertiser_urls.map((url) => ({ url }));

  const run = await client.actor("apify/facebook-ads-scraper").call({
    startUrls,
    resultsLimit: config.max_ads_per_competitor,
  }, { timeout: config.timeout_seconds });

  const { items } = await client.dataset(run.defaultDatasetId).listItems();
  console.log(`[meta] Apify returned ${items.length} raw items`);

  const ads = transformMetaResults(items as unknown as MetaAdResult[]);
  const skippedNoCreative = items.length - ads.length;

  console.log(`[meta] ${ads.length} ads with creatives (${skippedNoCreative} skipped — no creative/ID)`);

  const result = await writeToContentAPI(ads, "meta");
  console.log(`[result] source=meta found=${items.length} written=${result.written} skipped=${result.skipped} errors=${skippedNoCreative}`);

  return ads;
}

// Run directly
if (process.argv[1]?.includes("meta")) {
  scrapeMetaAds().catch((err) => {
    console.error("[meta] Fatal error:", err);
    process.exit(1);
  });
}
