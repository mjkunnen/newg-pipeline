import "dotenv/config";
import { readdir, readFile, mkdir, writeFile, copyFile, rm } from "fs/promises";
import { join, extname } from "path";
import { existsSync } from "fs";
import { execSync } from "child_process";
import sharp from "sharp";
import type { ScrapedAd } from "../scraper/types.js";
import { renderDashboard, formatReach } from "./template.js";
import type { DashboardAd, DateEntry } from "./template.js";

const PROJECT_ROOT = join(import.meta.dirname, "../..");
const RAW_DIR = join(PROJECT_ROOT, "output/raw");
const DOCS_DIR = join(PROJECT_ROOT, "docs");
const DATA_DIR = join(DOCS_DIR, "data");
const THUMBS_DIR = join(DOCS_DIR, "thumbs");
const CREATIVES_DIR = join(DOCS_DIR, "creatives");

const COMPETITOR = "decarba";
const THUMB_WIDTH = 400;
const MAX_DAYS_KEEP = 7;

async function findAllScrapes(): Promise<{ date: string; ads: ScrapedAd[] }[]> {
  if (!existsSync(RAW_DIR)) return [];

  const dirs = await readdir(RAW_DIR);
  const dateDirs = dirs
    .filter((d) => /^\d{4}-\d{2}-\d{2}$/.test(d))
    .sort()
    .reverse();

  const results: { date: string; ads: ScrapedAd[] }[] = [];

  for (const date of dateDirs) {
    const ads: ScrapedAd[] = [];

    // Load PPSpy ads
    const metaPath = join(RAW_DIR, date, "metadata.json");
    if (existsSync(metaPath)) {
      try {
        const raw = await readFile(metaPath, "utf-8");
        const ppspyAds: ScrapedAd[] = JSON.parse(raw);
        ads.push(...ppspyAds);
      } catch {
        console.log(`[dashboard] Skipping ${date}/metadata.json: invalid`);
      }
    }

    // Load Pinterest pins
    const pinterestPath = join(RAW_DIR, date, "metadata-pinterest.json");
    if (existsSync(pinterestPath)) {
      try {
        const raw = await readFile(pinterestPath, "utf-8");
        const pinterestAds: ScrapedAd[] = JSON.parse(raw);
        ads.push(...pinterestAds);
        console.log(`[dashboard] ${date}: loaded ${pinterestAds.length} Pinterest pins`);
      } catch {
        console.log(`[dashboard] Skipping ${date}/metadata-pinterest.json: invalid`);
      }
    }

    if (ads.length > 0) {
      results.push({ date, ads });
    }
  }

  return results;
}

async function generateThumbnail(
  ad: ScrapedAd,
  thumbDir: string,
): Promise<string> {
  const thumbFilename = `${ad.id}.jpg`;
  const thumbPath = join(thumbDir, thumbFilename);

  // Skip if already generated
  if (existsSync(thumbPath)) {
    return `thumbs/${thumbFilename}`;
  }

  let sourceBuffer: Buffer | null = null;

  // For image ads: use local downloaded file
  if (ad.type === "image" && ad.localPath && existsSync(ad.localPath)) {
    sourceBuffer = await readFile(ad.localPath);
  }
  // For video ads: use saved thumbnail URL
  else if (ad.thumbnailUrl) {
    try {
      const resp = await fetch(ad.thumbnailUrl);
      if (resp.ok) sourceBuffer = Buffer.from(await resp.arrayBuffer());
    } catch {
      // fall through
    }
  }
  // Fallback: try creativeUrl if it's an image
  if (
    !sourceBuffer &&
    ad.creativeUrl &&
    !ad.creativeUrl.includes(".mp4") &&
    !ad.creativeUrl.includes(".webm")
  ) {
    try {
      const resp = await fetch(ad.creativeUrl);
      if (resp.ok) sourceBuffer = Buffer.from(await resp.arrayBuffer());
    } catch {
      // fall through
    }
  }

  if (!sourceBuffer) {
    // Placeholder SVG
    const svg = `<svg width="${THUMB_WIDTH}" height="${THUMB_WIDTH}" xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="#e5e0d8"/>
      <text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="#b0a99e" font-size="18" font-family="sans-serif">${ad.type.toUpperCase()}</text>
    </svg>`;
    await sharp(Buffer.from(svg))
      .resize(THUMB_WIDTH)
      .jpeg({ quality: 80 })
      .toFile(thumbPath);
    return `thumbs/${thumbFilename}`;
  }

  await sharp(sourceBuffer)
    .resize(THUMB_WIDTH)
    .jpeg({ quality: 80 })
    .toFile(thumbPath);
  return `thumbs/${thumbFilename}`;
}

async function copyCreative(ad: ScrapedAd, dateDir: string): Promise<string> {
  if (!ad.localPath || !existsSync(ad.localPath)) return "";
  const ext = extname(ad.localPath) || (ad.type === "video" ? ".mp4" : ".jpg");
  const filename = `${ad.id}${ext}`;
  const destPath = join(dateDir, filename);
  if (!existsSync(destPath)) {
    await copyFile(ad.localPath, destPath);
  }
  return filename;
}

async function cleanupOldCreatives(keepDates: string[]) {
  if (!existsSync(CREATIVES_DIR)) return;
  const dirs = await readdir(CREATIVES_DIR);
  for (const dir of dirs) {
    if (/^\d{4}-\d{2}-\d{2}$/.test(dir) && !keepDates.includes(dir)) {
      console.log(`[dashboard] Removing old creatives: ${dir}`);
      await rm(join(CREATIVES_DIR, dir), { recursive: true, force: true });
    }
  }
}

async function generate() {
  console.log("[dashboard] Scanning for scrapes...");
  const allScrapes = await findAllScrapes();

  if (allScrapes.length === 0) {
    console.log("[dashboard] No scrape data found.");
    return;
  }

  // Only keep the latest N days
  const recentScrapes = allScrapes.slice(0, MAX_DAYS_KEEP);
  console.log(`[dashboard] Found ${allScrapes.length} date(s), keeping ${recentScrapes.length}`);

  await mkdir(DATA_DIR, { recursive: true });
  await mkdir(THUMBS_DIR, { recursive: true });
  await mkdir(CREATIVES_DIR, { recursive: true });

  // Dedup is handled differently per source:
  // - PPSpy ads: always show top 5 by reach (they change daily in stats)
  // - Pinterest pins: filtered by tracking sheet in the scraper already, no extra dedup needed

  const dateIndex: DateEntry[] = [];
  const keepDates: string[] = [];

  for (const { date, ads } of recentScrapes) {
    console.log(`[dashboard] Processing ${date} (${ads.length} ads)...`);
    keepDates.push(date);

    // Create per-date creatives dir
    const creativeDateDir = join(CREATIVES_DIR, date);
    await mkdir(creativeDateDir, { recursive: true });

    // Generate thumbnails + copy creatives
    const dashboardAds: DashboardAd[] = [];
    for (const ad of ads) {
      const thumbPath = await generateThumbnail(ad, THUMBS_DIR);
      const creativeFilename = await copyCreative(ad, creativeDateDir);
      const downloadPath = creativeFilename ? `creatives/${date}/${creativeFilename}` : "";
      dashboardAds.push({
        id: ad.id,
        type: ad.type,
        thumbPath,
        adCopy: ad.adCopy || "",
        reach: ad.reach,
        reachFormatted: formatReach(ad.reach),
        reachCost: "",
        daysActive: ad.daysActive,
        startDate: ad.startedAt,
        platforms: ad.platforms,
        downloadUrl: downloadPath,
      });
    }

    // Split PPSpy ads (have reach) and Pinterest pins (reach=0, id starts with pinterest_)
    const ppspyAds = dashboardAds.filter((a) => !a.id.startsWith("pinterest_"));
    const pinterestAds = dashboardAds.filter((a) => a.id.startsWith("pinterest_"));

    // Keep top 5 PPSpy ads by reach + all Pinterest pins
    ppspyAds.sort((a, b) => b.reach - a.reach);
    ppspyAds.splice(5);
    dashboardAds.length = 0;
    dashboardAds.push(...ppspyAds, ...pinterestAds);

    // Write per-date JSON
    const dateJsonPath = join(DATA_DIR, `${date}.json`);
    await writeFile(
      dateJsonPath,
      JSON.stringify({ date, competitor: COMPETITOR, ads: dashboardAds }, null, 2),
    );

    const videoCount = dashboardAds.filter((a) => a.type === "video").length;
    dateIndex.push({
      date,
      adCount: dashboardAds.length,
      videoCount,
      imageCount: dashboardAds.length - videoCount,
    });
  }

  // Cleanup old creatives (keep only recent dates)
  await cleanupOldCreatives(keepDates);

  // Write index
  await writeFile(
    join(DATA_DIR, "index.json"),
    JSON.stringify({ competitor: COMPETITOR, dates: dateIndex }, null, 2),
  );

  // Generate HTML
  const webhookUrl = process.env.ZAPIER_WEBHOOK_URL || "";
  const sheetId = process.env.GOOGLE_SHEET_ID || "1p8pdlNQKYRoX8HydJAHqAX6NhK_FAMxt2WHmWWps-yw";
  const html = renderDashboard(webhookUrl, sheetId, dateIndex);
  await writeFile(join(DOCS_DIR, "index.html"), html);
  console.log(`[dashboard] Written: docs/index.html + ${dateIndex.length} date files`);

  // Git push if enabled
  const autoPush = process.env.DASHBOARD_AUTO_PUSH !== "false";
  if (autoPush) {
    try {
      console.log("[dashboard] Pushing to GitHub...");
      execSync("git add docs/", { cwd: PROJECT_ROOT, stdio: "pipe" });
      const status = execSync("git status --porcelain docs/", {
        cwd: PROJECT_ROOT,
        encoding: "utf-8",
      });
      if (status.trim()) {
        const today = new Date().toISOString().split("T")[0];
        execSync(`git commit -m "dashboard: ${today}"`, {
          cwd: PROJECT_ROOT,
          stdio: "pipe",
        });
        execSync("git push origin master", {
          cwd: PROJECT_ROOT,
          stdio: "pipe",
        });
        console.log("[dashboard] Pushed to GitHub Pages");
      } else {
        console.log("[dashboard] No changes to push");
      }
    } catch (err) {
      console.error("[dashboard] Git push failed:", err);
    }
  }

  console.log(`[dashboard] Done. ${dateIndex.length} dates on dashboard.`);
}

generate().catch(console.error);
