/**
 * Shared Content API client.
 * Writes scraped ads to the Postgres content_items table via the ad-command-center API.
 * Non-fatal: if the API is unavailable the scrape pipeline continues normally.
 */

export type ContentSource = "ppspy" | "tiktok" | "pinterest" | "meta";

export interface ContentApiItem {
  id: string;
  type: string;
  creativeUrl?: string;
  thumbnailUrl?: string;
  adCopy?: string;
  reach?: number;
  daysActive?: number;
  startedAt?: string;
  platforms?: string[];
  scrapedAt?: string;
  [key: string]: unknown;
}

/**
 * POST an array of scraped items to the content API.
 * Duplicates are silently absorbed (ON CONFLICT DO NOTHING in Postgres).
 *
 * @param items  Array of scraped items from any source
 * @param source Source identifier — used as the `source` column in content_items
 */
export async function writeToContentAPI(
  items: ContentApiItem[],
  source: ContentSource,
): Promise<void> {
  const contentApiUrl = process.env.CONTENT_API_URL;
  const dashboardSecret = process.env.DASHBOARD_SECRET;

  if (!contentApiUrl || !dashboardSecret) {
    console.log(
      `[content-api] CONTENT_API_URL or DASHBOARD_SECRET not set — skipping Postgres write (source=${source})`,
    );
    return;
  }

  let written = 0;
  let skipped = 0;

  for (const item of items) {
    try {
      const body = {
        content_id: item.id,
        source,
        creative_url: item.creativeUrl ?? null,
        thumbnail_url: item.thumbnailUrl ?? null,
        ad_copy: item.adCopy ?? null,
        metadata_json: JSON.stringify({
          reach: item.reach ?? 0,
          daysActive: item.daysActive ?? 0,
          platforms: item.platforms ?? [],
          type: item.type,
          scrapedAt: item.scrapedAt,
        }),
      };

      const resp = await fetch(`${contentApiUrl}/api/content`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${dashboardSecret}`,
        },
        body: JSON.stringify(body),
      });

      if (resp.ok) {
        written++;
      } else {
        const text = await resp.text().catch(() => "");
        console.error(
          `[content-api] Failed to write ${item.id} (source=${source}): HTTP ${resp.status} ${text.slice(0, 100)}`,
        );
        skipped++;
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`[content-api] Network error for ${item.id} (source=${source}): ${msg}`);
      skipped++;
      // Non-fatal: scrape pipeline continues
    }
  }

  console.log(`[content-api] source=${source} written=${written} skipped/failed=${skipped}`);
}
