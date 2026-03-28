import "dotenv/config";
import { unlink } from "fs/promises";
import { join, extname } from "path";
import { launchBatch, type SubmissionInput } from "./meta.js";
import { downloadCreative } from "../lib/driveDownload.js";

const APPS_SCRIPT_URL = process.env.APPS_SCRIPT_URL || "";
const dryRun = process.argv.includes("--dry-run");

const TMP_DIR = join(import.meta.dirname, "../../output/tmp");

interface DryRunResult {
  ad_id: string;
  creative_type: "image" | "video";
  landing_page: string;
  status: "would_launch" | "skipped";
  reason?: string;
}

interface SheetSubmission {
  editor: string;
  date: string;
  ad_id: string;
  ad_copy: string;
  original_reach: string;
  drive_link: string;
  landing_page: string;
  platforms: string;
  submitted_at: string;
  status: string;
}

function parseCSV(text: string): string[][] {
  const rows: string[][] = [];
  let current: string[] = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (c === '"') {
        inQuotes = false;
      } else {
        field += c;
      }
    } else {
      if (c === '"') {
        inQuotes = true;
      } else if (c === ",") {
        current.push(field);
        field = "";
      } else if (c === "\n" || (c === "\r" && text[i + 1] === "\n")) {
        if (c === "\r") i++;
        current.push(field);
        field = "";
        if (current.some((f) => f !== "")) rows.push(current);
        current = [];
      } else {
        field += c;
      }
    }
  }
  current.push(field);
  if (current.some((f) => f !== "")) rows.push(current);
  return rows;
}

async function fetchPendingSubmissions(): Promise<SheetSubmission[]> {
  const sheetId = process.env.GOOGLE_SHEET_ID;
  if (!sheetId) {
    throw new Error("[launcher] GOOGLE_SHEET_ID env var is required but not set");
  }
  const url = `https://docs.google.com/spreadsheets/d/${sheetId}/gviz/tq?tqx=out:csv&sheet=Data`;

  console.log("[launcher] Fetching submissions from Sheet...");
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Sheet fetch failed: ${resp.status}`);

  const csv = await resp.text();
  const rows = parseCSV(csv);
  if (rows.length < 2) return [];

  const headers = rows[0].map((h) => h.trim().toLowerCase());
  const submissions: SheetSubmission[] = [];

  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    const obj: Record<string, string> = {};
    headers.forEach((h, idx) => (obj[h] = row[idx] || ""));

    if (obj.status === "pending") {
      submissions.push(obj as unknown as SheetSubmission);
    }
  }

  console.log(`[launcher] Found ${submissions.length} pending submission(s)`);
  return submissions;
}

async function updateSheetStatus(
  adId: string,
  status: string,
  campaignId?: string,
  error?: string,
): Promise<void> {
  if (!APPS_SCRIPT_URL) {
    console.warn(`[launcher] APPS_SCRIPT_URL not set — skipping Sheet status update for ${adId}`);
    return;
  }
  try {
    const body: Record<string, string> = {
      action: "update",
      ad_id: adId,
      status,
    };
    if (campaignId) body.campaign_id = campaignId;
    if (error) body.error = error;

    const params = new URLSearchParams(body);
    await fetch(APPS_SCRIPT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: params.toString(),
      redirect: "follow",
    });
    console.log(`[launcher] Sheet updated: ${adId} → ${status}`);
  } catch (err) {
    console.error(`[launcher] Failed to update sheet for ${adId}:`, err);
  }
}

async function main() {
  if (dryRun) {
    console.log("[launcher] DRY-RUN mode active — no Meta API calls or Sheet status writes");
  }
  console.log("[launcher] Starting campaign launcher...");

  const allSubmissions = await fetchPendingSubmissions();
  // Only process meta submissions
  const submissions = allSubmissions.filter((s) =>
    s.platforms.toLowerCase().includes("meta"),
  );

  if (submissions.length === 0) {
    console.log("[launcher] No pending meta submissions. Done.");
    return;
  }

  // Dedup: only keep the last submission per ad_id (skip already-launched duplicates)
  const seen = new Set<string>();
  const deduped = [...submissions].reverse().filter((s) => {
    if (seen.has(s.ad_id)) {
      console.log(`[launcher] Skipping duplicate ad_id: ${s.ad_id}`);
      return false;
    }
    seen.add(s.ad_id);
    return true;
  }).reverse();

  // Download all creatives first (always download even in dry-run — validates Drive links per D-06)
  const inputs: SubmissionInput[] = [];
  const tempFiles: string[] = [];
  const dryRunResults: DryRunResult[] = [];

  for (const sub of deduped) {
    try {
      const creativePath = await downloadCreative(sub.drive_link, sub.ad_id, TMP_DIR);
      tempFiles.push(creativePath);

      const ext = extname(creativePath).toLowerCase();
      const creativeType: "image" | "video" =
        ext === ".mp4" || ext === ".webm" ? "video" : "image";

      inputs.push({
        adId: sub.ad_id,
        adCopy: sub.ad_copy,
        creativePath,
        creativeType,
        landingPage: sub.landing_page,
        date: sub.date,
      });

      dryRunResults.push({
        ad_id: sub.ad_id,
        creative_type: creativeType,
        landing_page: sub.landing_page,
        status: "would_launch",
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`[launcher] Failed to download ${sub.ad_id}:`, msg);
      dryRunResults.push({
        ad_id: sub.ad_id,
        creative_type: "image",
        landing_page: sub.landing_page,
        status: "skipped",
        reason: `creative download failed: ${msg}`,
      });
      if (!dryRun) {
        await updateSheetStatus(sub.ad_id, "failed", undefined, msg.slice(0, 200));
      }
    }
  }

  if (inputs.length === 0) {
    if (dryRun) {
      console.log("[launcher] DRY-RUN summary:");
      console.log(JSON.stringify(dryRunResults, null, 2));
    }
    console.log("[launcher] No creatives downloaded successfully. Done.");
    return;
  }

  // Launch all as one campaign with separate ad sets (passes dryRun — meta.ts returns mock when true)
  try {
    const result = await launchBatch(inputs, dryRun);
    console.log(`[launcher] Campaign ${result.campaignId} / AdSet ${result.adSetId} — ${result.ads.length} ad(s) added`);

    if (dryRun) {
      // Log structured dry-run summary — do NOT update Sheet status
      console.log("[launcher] DRY-RUN summary:");
      console.log(JSON.stringify(dryRunResults, null, 2));
    } else {
      // Update Sheet for each successful ad
      for (const ad of result.ads) {
        await updateSheetStatus(ad.adId, "launched", result.campaignId);
      }
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`[launcher] Batch launch failed:`, msg);
    if (!dryRun) {
      // Mark all as failed
      for (const input of inputs) {
        await updateSheetStatus(input.adId, "failed", undefined, msg.slice(0, 200));
      }
    }
  } finally {
    // Cleanup temp files
    for (const f of tempFiles) {
      try { await unlink(f); } catch { /* ignore */ }
    }
  }

  console.log("[launcher] Done.");
}

main().catch(console.error);
