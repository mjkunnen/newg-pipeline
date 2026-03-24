import "dotenv/config";
import { writeFile, mkdir, unlink } from "fs/promises";
import { join, extname } from "path";
import { launchBatch, type SubmissionInput } from "./meta.js";

const APPS_SCRIPT_URL =
  "https://script.google.com/macros/s/AKfycbxN7hSUicVX6-JvOpFQMbABsQqc8CxPHMbUCjsYkhRNcNeddjw-4GP2F66PSDXhDrKsjA/exec";

const TMP_DIR = join(import.meta.dirname, "../../output/tmp");

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
  const sheetId =
    process.env.GOOGLE_SHEET_ID ||
    "1p8pdlNQKYRoX8HydJAHqAX6NhK_FAMxt2WHmWWps-yw";
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

async function downloadCreative(
  driveLink: string,
  adId: string,
): Promise<string> {
  await mkdir(TMP_DIR, { recursive: true });

  // Convert Drive share link to direct download
  let downloadUrl = driveLink;
  const fileIdMatch = driveLink.match(
    /\/d\/([a-zA-Z0-9_-]+)/,
  );
  if (fileIdMatch) {
    // confirm=t bypasses the "virus scan" confirmation page for larger files
    downloadUrl = `https://drive.google.com/uc?export=download&confirm=t&id=${fileIdMatch[1]}`;
  }

  console.log(`[launcher] Downloading creative for ${adId}...`);
  const resp = await fetch(downloadUrl, { redirect: "follow" });
  if (!resp.ok) throw new Error(`Download failed: ${resp.status} ${downloadUrl}`);

  const contentType = resp.headers.get("content-type") || "";
  let ext = ".jpg";
  if (contentType.includes("video") || contentType.includes("mp4")) ext = ".mp4";
  else if (contentType.includes("png")) ext = ".png";
  else if (contentType.includes("webp")) ext = ".webp";

  const buffer = Buffer.from(await resp.arrayBuffer());

  // Verify we got actual media, not an HTML confirmation page
  const head = buffer.subarray(0, 20).toString("utf8");
  if (head.includes("<!DOCTYPE") || head.includes("<html")) {
    throw new Error(`Download returned HTML page instead of media file — is the Drive file shared publicly?`);
  }

  const filePath = join(TMP_DIR, `${adId}${ext}`);
  await writeFile(filePath, buffer);
  console.log(`[launcher] Downloaded: ${filePath} (${(buffer.length / 1024).toFixed(0)}KB)`);
  return filePath;
}

async function updateSheetStatus(
  adId: string,
  status: string,
  campaignId?: string,
  error?: string,
): Promise<void> {
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

  // Download all creatives first
  const inputs: SubmissionInput[] = [];
  const tempFiles: string[] = [];

  for (const sub of submissions) {
    try {
      const creativePath = await downloadCreative(sub.drive_link, sub.ad_id);
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
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`[launcher] Failed to download ${sub.ad_id}:`, msg);
      await updateSheetStatus(sub.ad_id, "failed", undefined, msg.slice(0, 200));
    }
  }

  if (inputs.length === 0) {
    console.log("[launcher] No creatives downloaded successfully. Done.");
    return;
  }

  // Launch all as one campaign with separate ad sets
  try {
    const result = await launchBatch(inputs);
    console.log(`[launcher] Campaign ${result.campaignId} / AdSet ${result.adSetId} — ${result.ads.length} ad(s) added`);

    // Update Sheet for each successful ad
    for (const ad of result.ads) {
      await updateSheetStatus(ad.adId, "launched", result.campaignId);
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`[launcher] Batch launch failed:`, msg);
    // Mark all as failed
    for (const input of inputs) {
      await updateSheetStatus(input.adId, "failed", undefined, msg.slice(0, 200));
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
