import "dotenv/config";
import { readdir, readFile, mkdir, writeFile, copyFile, rm } from "fs/promises";
import { join, extname } from "path";
import { existsSync } from "fs";
import { execSync } from "child_process";
import sharp from "sharp";
import YAML from "yaml";
import type { ScrapedAd, Product } from "../scraper/types.js";
import { renderDashboard, formatReach } from "./template.js";
import type { DashboardAd, DateEntry, SuggestedProduct } from "./template.js";

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

  try {
    await sharp(sourceBuffer)
      .resize(THUMB_WIDTH)
      .jpeg({ quality: 80 })
      .toFile(thumbPath);
  } catch (err) {
    console.warn(`[dashboard] Thumbnail failed for ${ad.id}: ${err}. Using placeholder.`);
    const svg = `<svg width="${THUMB_WIDTH}" height="${THUMB_WIDTH}" xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="#e5e0d8"/>
      <text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="#b0a99e" font-size="18" font-family="sans-serif">${ad.type.toUpperCase()}</text>
    </svg>`;
    await sharp(Buffer.from(svg))
      .resize(THUMB_WIDTH)
      .jpeg({ quality: 80 })
      .toFile(thumbPath);
  }
  return `thumbs/${thumbFilename}`;
}

async function copyCreative(ad: ScrapedAd, dateDir: string): Promise<string> {
  // TikTok carousels: copy ZIP file instead of single image
  if (ad.id.startsWith("tiktok_") && ad.localPath) {
    const rawDir = join(ad.localPath, ".."); // localPath is slide_1.jpg inside slides dir
    const zipSource = join(rawDir, "..", `${ad.id}.zip`);
    const zipFilename = `${ad.id}.zip`;
    const destPath = join(dateDir, zipFilename);
    if (existsSync(zipSource)) {
      if (!existsSync(destPath)) {
        await copyFile(zipSource, destPath);
      }
      return zipFilename;
    }
    // Already copied from a previous run
    if (existsSync(destPath)) return zipFilename;
  }

  // Check if already copied from a previous run (try common extensions)
  if (!ad.localPath || !existsSync(ad.localPath)) {
    for (const ext of [".jpg", ".mp4", ".png", ".webp", ".zip"]) {
      const candidate = join(dateDir, `${ad.id}${ext}`);
      if (existsSync(candidate)) return `${ad.id}${ext}`;
    }
    return "";
  }

  const ext = extname(ad.localPath) || (ad.type === "video" ? ".mp4" : ".jpg");
  const filename = `${ad.id}${ext}`;
  const destPath = join(dateDir, filename);
  if (!existsSync(destPath)) {
    await copyFile(ad.localPath, destPath);
  }
  return filename;
}

/** Copy individual TikTok carousel slides and return their relative paths */
async function copyTiktokSlides(ad: ScrapedAd, dateDir: string, date: string): Promise<string[]> {
  if (!ad.id.startsWith("tiktok_") || !ad.localPath) return [];

  const slidesDir = join(ad.localPath, ".."); // localPath points to slide_1.jpg
  if (!existsSync(slidesDir)) return [];

  const files = await readdir(slidesDir);
  const slideFiles = files
    .filter((f) => /^slide_\d+\.jpg$/i.test(f))
    .sort((a, b) => {
      const numA = parseInt(a.match(/\d+/)?.[0] || "0");
      const numB = parseInt(b.match(/\d+/)?.[0] || "0");
      return numA - numB;
    });

  const paths: string[] = [];
  for (const sf of slideFiles) {
    const slideNum = sf.match(/\d+/)?.[0] || "0";
    const destName = `${ad.id}_slide${slideNum}.jpg`;
    const destPath = join(dateDir, destName);
    if (!existsSync(destPath)) {
      await copyFile(join(slidesDir, sf), destPath);
    }
    paths.push(`creatives/${date}/${destName}`);
  }
  return paths;
}

async function cleanupOldCreatives(keepDates: string[]) {
  if (!existsSync(CREATIVES_DIR)) return;
  const dirs = await readdir(CREATIVES_DIR);
  const keepSet = new Set(keepDates);

  // Also preserve any date that already has a JSON data file (manually curated content)
  if (existsSync(DATA_DIR)) {
    const dataFiles = await readdir(DATA_DIR);
    for (const f of dataFiles) {
      const match = f.match(/^(\d{4}-\d{2}-\d{2})\.json$/);
      if (match) keepSet.add(match[1]);
    }
  }

  for (const dir of dirs) {
    if (/^\d{4}-\d{2}-\d{2}$/.test(dir) && !keepSet.has(dir)) {
      console.log(`[dashboard] Removing old creatives: ${dir}`);
      await rm(join(CREATIVES_DIR, dir), { recursive: true, force: true });
    }
  }
}

async function loadProductCatalog(): Promise<Product[]> {
  const configPath = join(PROJECT_ROOT, "config/products.yaml");
  if (!existsSync(configPath)) return [];
  const raw = await readFile(configPath, "utf-8");
  return YAML.parse(raw) as Product[];
}

function assignProducts(ad: ScrapedAd, allProducts: Product[]): SuggestedProduct[] {
  const tops = allProducts
    .filter((p) => p.collection === "bestseller-tops")
    .sort((a, b) => (a.sales_rank || 99) - (b.sales_rank || 99));
  const bottoms = allProducts
    .filter((p) => p.collection === "bestseller-bottoms")
    .sort((a, b) => (a.sales_rank || 99) - (b.sales_rank || 99));
  const shoes = allProducts
    .filter((p) => p.collection === "bestseller-shoes")
    .sort((a, b) => (a.sales_rank || 99) - (b.sales_rank || 99));

  // Use ad id hash to rotate through products so not every ad gets the same combo
  let hash = 0;
  for (const ch of ad.id) hash = ((hash << 5) - hash + ch.charCodeAt(0)) | 0;
  hash = Math.abs(hash);

  const result: SuggestedProduct[] = [];

  if (tops.length > 0) {
    const top = tops[hash % tops.length];
    result.push({ name: top.name, collection: top.collection, role: "top" });
  }
  if (bottoms.length > 0) {
    const bottom = bottoms[(hash >> 3) % bottoms.length];
    result.push({ name: bottom.name, collection: bottom.collection, role: "bottom" });
  }
  if (shoes.length > 0) {
    const shoe = shoes[(hash >> 6) % shoes.length];
    result.push({ name: shoe.name, collection: shoe.collection, role: "shoes" });
  }

  return result;
}

async function generate() {
  console.log("[dashboard] Scanning for scrapes...");
  const productCatalog = await loadProductCatalog();
  console.log(`[dashboard] Loaded ${productCatalog.length} products from catalog`);
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

  // Cross-day dedup for TikTok (by post ID) and Pinterest (by pin ID)
  const seenTiktokPostIds = new Set<string>();
  const seenPinterestPinIds = new Set<string>();

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

    // Limit Pinterest to top 2 per day, dedup across dates by pin ID
    const MAX_PINTEREST = 2;
    const newPinterest = pinterestRaw.filter((a) => {
      const pinId = a.id.replace("pinterest_", "");
      if (seenPinterestPinIds.has(pinId)) return false;
      seenPinterestPinIds.add(pinId);
      return true;
    });
    const pinterestToShow = newPinterest.slice(0, MAX_PINTEREST);
    if (pinterestRaw.length > pinterestToShow.length) {
      console.log(`[dashboard] Pinterest: showing ${pinterestToShow.length} of ${pinterestRaw.length} pins (${pinterestRaw.length - newPinterest.length} dupes skipped)`);
    }

    // Limit TikTok to top 2 by reach (views), dedup across dates by post ID
    const MAX_TIKTOK = 2;
    const newTiktok = tiktokRaw.filter((a) => {
      // Extract post ID from id format: tiktok_{username}_{postId}
      const parts = a.id.split("_");
      const postId = parts.length >= 3 ? parts.slice(2).join("_") : a.id;
      if (seenTiktokPostIds.has(postId)) return false;
      seenTiktokPostIds.add(postId);
      return true;
    });
    newTiktok.sort((a, b) => b.reach - a.reach);
    const tiktokToShow = newTiktok.slice(0, MAX_TIKTOK);
    if (tiktokRaw.length > tiktokToShow.length) {
      console.log(`[dashboard] TikTok: showing top ${tiktokToShow.length} of ${tiktokRaw.length} carousels (${tiktokRaw.length - newTiktok.length} dupes skipped)`);
    }

    // Combine new PPSpy + limited Pinterest + top TikTok
    const adsToShow = [...newPpspy, ...pinterestToShow, ...tiktokToShow];

    // Generate thumbnails + copy creatives
    const dashboardAds: DashboardAd[] = [];
    for (const ad of adsToShow) {
      const thumbPath = await generateThumbnail(ad, THUMBS_DIR);
      const creativeFilename = await copyCreative(ad, creativeDateDir);
      const downloadPath = creativeFilename ? `creatives/${date}/${creativeFilename}` : "";
      const suggestedProducts = productCatalog.length > 0
        ? assignProducts(ad, productCatalog)
        : undefined;
      // Copy individual slides for TikTok carousels
      const slides = await copyTiktokSlides(ad, creativeDateDir, date);
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
        suggestedProducts,
        ...(slides.length > 0 ? { slides } : {}),
      });
    }

    // Merge with existing date JSON (preserve manually-added ads)
    const dateJsonPath = join(DATA_DIR, `${date}.json`);
    let mergedAds = dashboardAds;
    if (existsSync(dateJsonPath)) {
      try {
        const existing = JSON.parse(await readFile(dateJsonPath, "utf-8"));
        const newIds = new Set(dashboardAds.map((a) => a.id));
        const preserved = (existing.ads || []).filter(
          (a: DashboardAd) => !newIds.has(a.id),
        );
        if (preserved.length > 0) {
          console.log(`[dashboard] ${date}: preserving ${preserved.length} existing ad(s) not in current scrape`);
          mergedAds = [...dashboardAds, ...preserved];
        }
      } catch {
        // existing file corrupt, overwrite
      }
    }
    await writeFile(
      dateJsonPath,
      JSON.stringify({ date, competitor: COMPETITOR, ads: mergedAds }, null, 2),
    );

    const videoCount = mergedAds.filter((a) => a.type === "video").length;
    dateIndex.push({
      date,
      adCount: mergedAds.length,
      videoCount,
      imageCount: mergedAds.length - videoCount,
    });
  }

  // Save seen PPSpy data (URLs + ad copies)
  const updatedSeen: SeenPpspy = {
    urls: [...seenPpspyUrls],
    adCopies: [...seenPpspyCopies],
  };
  await writeFile(SEEN_PPSPY_PATH, JSON.stringify(updatedSeen, null, 2));
  console.log(`[dashboard] Seen PPSpy: ${seenPpspyUrls.size} URLs, ${seenPpspyCopies.size} ad copies`);

  // Include existing date JSONs not covered by current scrape (manually curated dates)
  const indexedDates = new Set(dateIndex.map((d) => d.date));
  if (existsSync(DATA_DIR)) {
    const dataFiles = await readdir(DATA_DIR);
    for (const f of dataFiles) {
      const match = f.match(/^(\d{4}-\d{2}-\d{2})\.json$/);
      if (match && !indexedDates.has(match[1])) {
        try {
          const existing = JSON.parse(await readFile(join(DATA_DIR, f), "utf-8"));
          const ads: DashboardAd[] = existing.ads || [];
          const videoCount = ads.filter((a) => a.type === "video").length;
          dateIndex.push({
            date: match[1],
            adCount: ads.length,
            videoCount,
            imageCount: ads.length - videoCount,
          });
          keepDates.push(match[1]);
          console.log(`[dashboard] Preserved existing date: ${match[1]} (${ads.length} ads)`);
        } catch {
          // skip corrupt files
        }
      }
    }
    // Sort dateIndex newest-first
    dateIndex.sort((a, b) => b.date.localeCompare(a.date));
  }

  // Cleanup old creatives (keep only recent + preserved dates)
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
