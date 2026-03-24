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
const SEEN_PPSPY_PATH = join(DATA_DIR, "seen-ppspy.json");

interface SeenPpspy {
  urls: string[];
  adCopies: string[];
}

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

    // Load TikTok carousels
    const tiktokPath = join(RAW_DIR, date, "metadata-tiktok.json");
    if (existsSync(tiktokPath)) {
      try {
        const raw = await readFile(tiktokPath, "utf-8");
        const tiktokAds: ScrapedAd[] = JSON.parse(raw);
        ads.push(...tiktokAds);
        console.log(`[dashboard] ${date}: loaded ${tiktokAds.length} TikTok carousels`);
      } catch {
        console.log(`[dashboard] Skipping ${date}/metadata-tiktok.json: invalid`);
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
  // TikTok carousels: copy ZIP file instead of single image
  if (ad.id.startsWith("tiktok_") && ad.localPath) {
    const rawDir = join(ad.localPath, ".."); // localPath is slide_1.jpg inside slides dir
    const zipSource = join(rawDir, "..", `${ad.id}.zip`);
    if (existsSync(zipSource)) {
      const zipFilename = `${ad.id}.zip`;
      const destPath = join(dateDir, zipFilename);
      if (!existsSync(destPath)) {
        await copyFile(zipSource, destPath);
      }
      return zipFilename;
    }
  }

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

  // Load seen PPSpy data (persistent across runs)
  // Track both creative URLs and ad copy text to catch same campaigns with different creative variants
  let seenData: SeenPpspy = { urls: [], adCopies: [] };
  if (existsSync(SEEN_PPSPY_PATH)) {
    try {
      const raw = JSON.parse(await readFile(SEEN_PPSPY_PATH, "utf-8"));
      // Migrate from old format (plain string array) to new format
      if (Array.isArray(raw)) {
        seenData = { urls: raw, adCopies: [] };
      } else {
        seenData = raw;
      }
    } catch {
      seenData = { urls: [], adCopies: [] };
    }
  }
  const seenPpspyUrls = new Set<string>(seenData.urls);
  const seenPpspyCopies = new Set<string>(seenData.adCopies);
  console.log(`[dashboard] ${seenPpspyUrls.size} seen URLs, ${seenPpspyCopies.size} seen ad copies`);

  const dateIndex: DateEntry[] = [];
  const keepDates: string[] = [];

  for (const { date, ads } of recentScrapes) {
    console.log(`[dashboard] Processing ${date} (${ads.length} ads)...`);
    keepDates.push(date);

    // Create per-date creatives dir
    const creativeDateDir = join(CREATIVES_DIR, date);
    await mkdir(creativeDateDir, { recursive: true });

    // Split raw ads into PPSpy, Pinterest, and TikTok
    const ppspyRaw = ads.filter((a) => !a.id.startsWith("pinterest_") && !a.id.startsWith("tiktok_"));
    const pinterestRaw = ads.filter((a) => a.id.startsWith("pinterest_"));
    const tiktokRaw = ads.filter((a) => a.id.startsWith("tiktok_"));

    // Filter PPSpy: remove already-seen by URL OR ad copy (same campaign = same ad copy)
    const newPpspy = ppspyRaw.filter((a) => {
      const copyKey = (a.adCopy || "").trim().toLowerCase();
      return !seenPpspyUrls.has(a.creativeUrl) && (!copyKey || !seenPpspyCopies.has(copyKey));
    });
    console.log(`[dashboard] PPSpy: ${newPpspy.length} new of ${ppspyRaw.length} (${ppspyRaw.length - newPpspy.length} already shown before)`);

    // Sort by reach, no fixed limit — show whatever is new
    newPpspy.sort((a, b) => b.reach - a.reach);

    // Mark all PPSpy ads as seen (URLs + ad copies)
    for (const ad of ppspyRaw) {
      seenPpspyUrls.add(ad.creativeUrl);
      const copyKey = (ad.adCopy || "").trim().toLowerCase();
      if (copyKey) seenPpspyCopies.add(copyKey);
    }

    // Combine new PPSpy + Pinterest pins + TikTok carousels
    const adsToShow = [...newPpspy, ...pinterestRaw, ...tiktokRaw];

    // Generate thumbnails + copy creatives
    const dashboardAds: DashboardAd[] = [];
    for (const ad of adsToShow) {
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

  // Save seen PPSpy data (URLs + ad copies)
  const updatedSeen: SeenPpspy = {
    urls: [...seenPpspyUrls],
    adCopies: [...seenPpspyCopies],
  };
  await writeFile(SEEN_PPSPY_PATH, JSON.stringify(updatedSeen, null, 2));
  console.log(`[dashboard] Seen PPSpy: ${seenPpspyUrls.size} URLs, ${seenPpspyCopies.size} ad copies`);

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
