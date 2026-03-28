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
  ad_archive_id: string;
  page_name?: string;
  snapshot?: {
    cards?: Array<{
      original_image_url?: string;
      video_hd_url?: string;
      video_sd_url?: string;
      video_preview_image_url?: string;
    }>;
    videos?: Array<{ video_hd_url?: string; video_sd_url?: string; video_preview_image_url?: string }>;
    images?: Array<{ original_image_url?: string }>;
    body?: { text?: string };
    display_format?: string;
  };
  start_date?: number;
  is_active?: boolean;
}

export function transformMetaResults(items: MetaAdResult[]): ScrapedAd[] {
  const ads: ScrapedAd[] = [];
  for (const item of items) {
    const card = item.snapshot?.cards?.[0];
    const vid = item.snapshot?.videos?.[0];
    const img = item.snapshot?.images?.[0];

    const videoUrl = card?.video_hd_url ?? card?.video_sd_url ?? vid?.video_hd_url ?? vid?.video_sd_url;
    const imageUrl = card?.original_image_url ?? img?.original_image_url;
    const creativeUrl = videoUrl ?? imageUrl ?? "";
    const type: "image" | "video" = videoUrl ? "video" : "image";

    if (!creativeUrl || !item.ad_archive_id) continue;

    const startDate = item.start_date
      ? new Date(item.start_date * 1000).toISOString().split("T")[0]
      : new Date().toISOString().split("T")[0];

    ads.push({
      id: `meta_${item.ad_archive_id}`,
      type,
      creativeUrl,
      thumbnailUrl: card?.video_preview_image_url ?? vid?.video_preview_image_url ?? imageUrl,
      adCopy: item.snapshot?.body?.text ?? "",
      reach: 0,
      daysActive: 0,
      startedAt: startDate,
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

  const urls = config.advertiser_urls.map((url) => ({ url }));

  const run = await client.actor("curious_coder/facebook-ads-library-scraper").call({
    urls,
    limitPerSource: config.max_ads_per_competitor,
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
