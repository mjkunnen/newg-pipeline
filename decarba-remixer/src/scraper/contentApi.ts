import type { ScrapedAd } from "./types.js";

export interface WriteResult {
  written: number;
  skipped: number;
}

export async function writeToContentAPI(
  ads: ScrapedAd[],
  source: "ppspy" | "tiktok" | "pinterest" | "meta"
): Promise<WriteResult> {
  const contentApiUrl = process.env.CONTENT_API_URL;
  const dashboardSecret = process.env.DASHBOARD_SECRET;

  if (!contentApiUrl || !dashboardSecret) {
    console.log(`[content-api] CONTENT_API_URL or DASHBOARD_SECRET not set — skipping`);
    return { written: 0, skipped: 0 };
  }

  let written = 0;
  let skipped = 0;

  for (const ad of ads) {
    try {
      const body = {
        content_id: ad.id,
        source,
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
    }
  }

  console.log(`[content-api] source=${source} written=${written} skipped=${skipped}`);
  return { written, skipped };
}
