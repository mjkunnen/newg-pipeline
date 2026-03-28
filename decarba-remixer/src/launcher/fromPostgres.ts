import "dotenv/config";
import { unlink } from "fs/promises";
import { join, extname } from "path";
import { launchBatch, type SubmissionInput } from "./meta.js";
import { downloadCreative } from "../lib/driveDownload.js";

// ---------------------------------------------------------------------------
// Env helpers
// ---------------------------------------------------------------------------

function requireEnv(key: string): string {
  const val = process.env[key];
  if (!val) {
    throw new Error(
      `Required env var ${key} is not set. ` +
        "Add it to .env (local) or GitHub Actions secrets (CI).",
    );
  }
  return val;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TMP_DIR = join(import.meta.dirname, "../../output/tmp");

// Wire used in Plan 02 (dry-run support)
const dryRun = process.argv.includes("--dry-run");

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ContentItem {
  id: number;
  content_id: string;
  source: string;
  status: string;
  creative_url: string | null;
  ad_copy: string | null;
  metadata_json: string | null;
}

interface MetaFromItem {
  driveLink: string;
  landingPage: string;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

/**
 * Fetch all items with status=ready_to_launch from the content API.
 * Throws on network failure (triggers Sheets fallback via process.exit(1) in main).
 */
export async function fetchReadyItems(): Promise<ContentItem[]> {
  const contentApiUrl = requireEnv("CONTENT_API_URL");
  const dashboardSecret = requireEnv("DASHBOARD_SECRET");

  console.log("[fromPostgres] Fetching ready_to_launch items from content API...");
  const resp = await fetch(`${contentApiUrl}/api/content?status=ready_to_launch`, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${dashboardSecret}`,
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`Content API error: ${resp.status} ${text.slice(0, 200)}`);
  }

  const items: ContentItem[] = await resp.json();
  console.log(`[fromPostgres] Found ${items.length} item(s) ready_to_launch`);
  return items;
}

/**
 * Extract drive_link and landing_page from a ContentItem's metadata_json.
 * Returns null if drive_link is missing (D-05) or metadata_json is invalid JSON.
 */
export function extractMeta(item: ContentItem): MetaFromItem | null {
  if (!item.metadata_json) {
    console.warn(`[fromPostgres] Skipping ${item.content_id}: metadata_json is null`);
    return null;
  }

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(item.metadata_json) as Record<string, unknown>;
  } catch {
    console.warn(
      `[fromPostgres] Skipping ${item.content_id}: invalid JSON in metadata_json`,
    );
    return null;
  }

  const driveLink = typeof parsed.drive_link === "string" ? parsed.drive_link : null;
  if (!driveLink) {
    console.warn(
      `[fromPostgres] Skipping ${item.content_id}: no drive_link in metadata_json (D-05)`,
    );
    return null;
  }

  // landing_page defaults to newgarments.nl — dashboard submit form doesn't write it
  const landingPage =
    typeof parsed.landing_page === "string" && parsed.landing_page.length > 0
      ? parsed.landing_page
      : "https://newgarments.nl";

  return { driveLink, landingPage };
}

/**
 * Advance item status to "launched" in Postgres via the content API (D-02).
 * Non-throwing: logs and continues on failure.
 */
export async function markLaunched(itemId: number): Promise<void> {
  const contentApiUrl = requireEnv("CONTENT_API_URL");
  const dashboardSecret = requireEnv("DASHBOARD_SECRET");

  try {
    const resp = await fetch(`${contentApiUrl}/api/content/${itemId}/status`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${dashboardSecret}`,
      },
      body: JSON.stringify({ status: "launched" }),
    });

    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      console.error(
        `[fromPostgres] Failed to mark ${itemId} as launched: ${resp.status} ${text.slice(0, 100)}`,
      );
    } else {
      console.log(`[fromPostgres] Marked ${itemId} as launched`);
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`[fromPostgres] Network error marking ${itemId} as launched: ${msg}`);
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  if (dryRun) {
    console.log("[fromPostgres] DRY RUN mode — no Meta API calls or status writes");
  }

  console.log("[fromPostgres] Starting Postgres-driven launcher...");

  // Fetch ready items — on failure exit(1) to trigger Sheets fallback (D-04)
  let items: ContentItem[];
  try {
    items = await fetchReadyItems();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`[fromPostgres] Content API unreachable: ${msg}`);
    process.exit(1); // Triggers Sheets fallback in workflow (D-04)
  }

  if (items.length === 0) {
    console.log("[fromPostgres] No items ready to launch. Done.");
    process.exit(0); // No fallback needed (D-04)
  }

  const inputs: SubmissionInput[] = [];
  const tempFiles: string[] = [];
  const launchedItemIds: number[] = [];

  try {
    // Build inputs — skip items with missing drive_link
    for (const item of items) {
      const meta = extractMeta(item);
      if (!meta) continue; // Already warned in extractMeta

      let creativePath: string;
      try {
        creativePath = await downloadCreative(meta.driveLink, item.content_id, TMP_DIR);
        tempFiles.push(creativePath);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error(`[fromPostgres] Failed to download creative for ${item.content_id}: ${msg}`);
        continue;
      }

      const ext = extname(creativePath).toLowerCase();
      const creativeType: "image" | "video" =
        ext === ".mp4" || ext === ".webm" ? "video" : "image";

      inputs.push({
        adId: item.content_id,
        adCopy: item.ad_copy ?? "",
        creativePath,
        creativeType,
        landingPage: meta.landingPage,
        date: new Date().toISOString().split("T")[0],
      });

      launchedItemIds.push(item.id);
    }

    if (inputs.length === 0) {
      console.log("[fromPostgres] No valid creatives to launch. Done.");
      process.exit(0);
    }

    if (dryRun) {
      console.log(
        `[fromPostgres] DRY RUN — would launch ${inputs.length} ad(s): ${inputs.map((i) => i.adId).join(", ")}`,
      );
      process.exit(0);
    }

    // Launch via Meta
    const result = await launchBatch(inputs);
    console.log(
      `[fromPostgres] Campaign ${result.campaignId} / AdSet ${result.adSetId} — ${result.ads.length} ad(s) added`,
    );

    // Mark each launched item in Postgres (D-02)
    for (const itemId of launchedItemIds) {
      await markLaunched(itemId);
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`[fromPostgres] Batch launch failed: ${msg}`);
    // Do NOT advance status on failure (D-02)
    process.exit(1);
  } finally {
    // Cleanup temp files
    for (const f of tempFiles) {
      try {
        await unlink(f);
      } catch {
        /* ignore */
      }
    }
  }

  console.log("[fromPostgres] Done.");
}

// Only run when executed directly (not when imported by tests)
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore — import.meta.url is valid in ESM
if (import.meta.url === `file:///${process.argv[1].replace(/\\/g, "/")}` ||
    process.argv[1]?.endsWith("fromPostgres.js")) {
  main().catch((err) => {
    console.error("[fromPostgres] Fatal error:", err);
    process.exit(1);
  });
}
