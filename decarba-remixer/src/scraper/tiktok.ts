import "dotenv/config";
import { writeFile, mkdir, readFile } from "fs/promises";
import { join } from "path";
import { existsSync } from "fs";
import { execSync } from "child_process";
import type { ScrapedAd } from "./types.js";

const OUTPUT_BASE = join(import.meta.dirname, "../../output/raw");

const APIFY_TOKEN = process.env.APIFY_TOKEN || "";
const APIFY_ACTOR_ID = "GdWCkxBtKWOsKjdch"; // clockworks/tiktok-scraper

const TIKTOK_ACCOUNTS = [
  "fiveleafsclo",
  "thefitscene",
  "azeliasolo",
  "nfits_18",
  "aightfits_clo",
  "fupgun",
  "copenhagenlove1",
  "strhvn2",
  "thebrand4u",
  "outfits.nstra",
  "outfitinspostreet",
  "away.fl",
  "havenfit",
];

const MAX_CAROUSELS = 2;
const MAX_AGE_DAYS = 14;
const RESULTS_PER_PAGE = 50;
const MIN_REACH = 3000; // skip carousels under this view count

// Local tracking of processed post IDs (shared with tiktok_checker.py)
const PROCESSED_FILE = join(import.meta.dirname, "../../../scout/processed_tiktok.json");

function todayDir(): string {
  return new Date().toISOString().split("T")[0];
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

interface ProcessedEntry {
  id: string;
  processedAt: string; // ISO date
}

async function getProcessedIds(): Promise<Set<string>> {
  try {
    if (existsSync(PROCESSED_FILE)) {
      const raw = JSON.parse(await readFile(PROCESSED_FILE, "utf-8"));

      // Support both old format (string[]) and new format (ProcessedEntry[])
      if (Array.isArray(raw) && raw.length > 0) {
        if (typeof raw[0] === "string") {
          // Old format — migrate: treat all as current
          return new Set(raw);
        }
        // New format — prune entries older than 30 days
        const cutoff = Date.now() - 30 * 86400 * 1000;
        const entries = (raw as ProcessedEntry[]).filter(
          (e) => new Date(e.processedAt).getTime() > cutoff,
        );
        if (entries.length < raw.length) {
          console.log(`[tiktok] Pruned ${raw.length - entries.length} processed IDs older than 30 days`);
          await writeFile(PROCESSED_FILE, JSON.stringify(entries, null, 2));
        }
        return new Set(entries.map((e) => e.id));
      }
    }
  } catch {
    // ignore
  }
  return new Set();
}

async function saveProcessedId(postId: string) {
  let entries: ProcessedEntry[] = [];
  try {
    if (existsSync(PROCESSED_FILE)) {
      const raw = JSON.parse(await readFile(PROCESSED_FILE, "utf-8"));
      if (Array.isArray(raw) && raw.length > 0) {
        if (typeof raw[0] === "string") {
          // Migrate old format → new format
          entries = (raw as string[]).map((id) => ({ id, processedAt: new Date().toISOString() }));
        } else {
          entries = raw as ProcessedEntry[];
        }
      }
    }
  } catch {
    // ignore
  }
  entries.push({ id: postId, processedAt: new Date().toISOString() });
  await writeFile(PROCESSED_FILE, JSON.stringify(entries, null, 2));
}

interface ApifyPost {
  id: string;
  isSlideshow?: boolean;
  slideshowImageLinks?: Array<{ downloadLink?: string; tiktokLink?: string }>;
  createTime?: number;
  createTimeISO?: string;
  playCount?: number;
  webVideoUrl?: string;
  text?: string;
  authorMeta?: { name?: string };
}

interface CarouselCandidate {
  postId: string;
  username: string;
  playCount: number;
  createDate: string;
  webUrl: string;
  text: string;
  numSlides: number;
  slides: Array<{ downloadLink?: string; tiktokLink?: string }>;
}

async function fetchPostsViaApify(): Promise<ApifyPost[]> {
  if (!APIFY_TOKEN) {
    console.log("[tiktok] No APIFY_TOKEN set, skipping");
    return [];
  }

  const profileUrls = TIKTOK_ACCOUNTS.map((a) => `https://www.tiktok.com/@${a}`);
  const runInput = {
    profiles: profileUrls,
    resultsPerPage: RESULTS_PER_PAGE,
    shouldDownloadVideos: false,
    shouldDownloadCovers: false,
  };

  console.log(`[tiktok] Starting Apify run for ${TIKTOK_ACCOUNTS.length} accounts...`);
  const startResp = await fetch(
    `https://api.apify.com/v2/acts/${APIFY_ACTOR_ID}/runs?token=${APIFY_TOKEN}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(runInput),
    },
  );
  if (!startResp.ok) {
    console.error(`[tiktok] Apify start failed: ${startResp.status}`);
    return [];
  }

  const runData = (await startResp.json()) as { data: { id: string; defaultDatasetId: string } };
  const runId = runData.data.id;
  const datasetId = runData.data.defaultDatasetId;
  console.log(`[tiktok] Apify run started: ${runId}`);

  // Poll for completion (max 8 min)
  const statusUrl = `https://api.apify.com/v2/actor-runs/${runId}?token=${APIFY_TOKEN}`;
  for (let i = 0; i < 96; i++) {
    await delay(5000);
    try {
      const statusResp = await fetch(statusUrl);
      const statusData = (await statusResp.json()) as { data: { status: string } };
      const status = statusData.data.status;

      if (status === "SUCCEEDED") {
        console.log(`[tiktok] Apify run completed after ${(i + 1) * 5}s`);
        break;
      }
      if (["FAILED", "ABORTED", "TIMED-OUT"].includes(status)) {
        console.error(`[tiktok] Apify run failed: ${status}`);
        return [];
      }
    } catch {
      // retry
    }
  }

  // Fetch results
  const itemsUrl = `https://api.apify.com/v2/datasets/${datasetId}/items?token=${APIFY_TOKEN}&format=json`;
  const itemsResp = await fetch(itemsUrl);
  const items = (await itemsResp.json()) as ApifyPost[];
  console.log(`[tiktok] Fetched ${items.length} total posts from Apify`);
  return items;
}

function selectTopCarousels(
  posts: ApifyPost[],
  processedIds: Set<string>,
): CarouselCandidate[] {
  const cutoff = Date.now() / 1000 - MAX_AGE_DAYS * 86400;

  const candidates: CarouselCandidate[] = [];
  for (const post of posts) {
    if (!post.isSlideshow) continue;
    const slides = post.slideshowImageLinks || [];
    if (slides.length < 2) continue;
    if ((post.createTime || 0) < cutoff) continue;

    const postId = String(post.id || "");
    if (!postId || processedIds.has(postId)) continue;

    candidates.push({
      postId,
      username: post.authorMeta?.name || "unknown",
      playCount: post.playCount || 0,
      createDate: post.createTimeISO || "",
      webUrl: post.webVideoUrl || "",
      text: (post.text || "").slice(0, 100),
      numSlides: slides.length,
      slides,
    });
  }

  candidates.sort((a, b) => b.playCount - a.playCount);

  // Log ALL candidates so we can see what's available
  console.log(`[tiktok] ${candidates.length} carousel candidates (sorted by reach):`);
  for (const c of candidates) {
    const flag = c.playCount < MIN_REACH ? " [SKIP: low reach]" : "";
    console.log(`[tiktok]   @${c.username} — ${c.playCount.toLocaleString()} views — ${c.numSlides} slides — ${c.createDate.split("T")[0]} — ${c.postId}${flag}`);
  }

  // Filter by minimum reach
  const qualified = candidates.filter((c) => c.playCount >= MIN_REACH);
  if (qualified.length === 0 && candidates.length > 0) {
    console.log(`[tiktok] No carousels above ${MIN_REACH.toLocaleString()} views — skipping low-reach content`);
    return [];
  }

  const selected = qualified.slice(0, MAX_CAROUSELS);
  console.log(`[tiktok] Selected top ${selected.length} (above ${MIN_REACH.toLocaleString()} views):`);
  for (const c of selected) {
    console.log(`[tiktok]   ✓ @${c.username} — ${c.playCount.toLocaleString()} views — ${c.postId}`);
  }

  return selected;
}

async function downloadSlideImage(
  url: string,
  outputPath: string,
): Promise<boolean> {
  try {
    const resp = await fetch(url, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        Referer: "https://www.tiktok.com/",
      },
    });
    if (!resp.ok) return false;
    const buffer = Buffer.from(await resp.arrayBuffer());
    await writeFile(outputPath, buffer);
    return true;
  } catch {
    return false;
  }
}

export async function scrapeTiktok(): Promise<ScrapedAd[]> {
  const outputDir = join(OUTPUT_BASE, todayDir());
  await mkdir(outputDir, { recursive: true });

  const processedIds = await getProcessedIds();
  console.log(`[tiktok] ${processedIds.size} previously processed post IDs`);

  const posts = await fetchPostsViaApify();
  if (posts.length === 0) {
    const metaPath = join(outputDir, "metadata-tiktok.json");
    await writeFile(metaPath, JSON.stringify([], null, 2));
    return [];
  }

  const carousels = selectTopCarousels(posts, processedIds);
  if (carousels.length === 0) {
    console.log("[tiktok] No new carousels to show");
    const metaPath = join(outputDir, "metadata-tiktok.json");
    await writeFile(metaPath, JSON.stringify([], null, 2));
    return [];
  }

  const ads: ScrapedAd[] = [];

  for (const carousel of carousels) {
    const baseId = `tiktok_${carousel.username}_${carousel.postId}`;

    // Create subfolder for this carousel's slides
    const slidesDir = join(outputDir, baseId);
    await mkdir(slidesDir, { recursive: true });

    // Download ALL slides
    const slidePaths: string[] = [];
    for (let si = 0; si < carousel.slides.length; si++) {
      const slide = carousel.slides[si];
      const slideUrl = slide?.downloadLink || slide?.tiktokLink || "";
      if (!slideUrl) continue;

      const filename = `slide_${si + 1}.jpg`;
      const filepath = join(slidesDir, filename);

      const ok = await downloadSlideImage(slideUrl, filepath);
      if (!ok) {
        console.log(`[tiktok] Failed to download slide ${si + 1} for ${baseId}`);
        continue;
      }

      const sizeKB = ((await readFile(filepath)).length / 1024).toFixed(0);
      console.log(`[tiktok] Downloaded: ${baseId}/slide_${si + 1}.jpg (${sizeKB}KB)`);
      slidePaths.push(filepath);
      await delay(300);
    }

    if (slidePaths.length === 0) {
      console.log(`[tiktok] No slides downloaded for ${baseId}, skipping`);
      continue;
    }

    console.log(`[tiktok] @${carousel.username} — ${slidePaths.length}/${carousel.numSlides} slides downloaded`);

    // Create ZIP of all slides
    const zipPath = join(outputDir, `${baseId}.zip`);
    try {
      execSync(`cd "${slidesDir}" && zip -j "${zipPath}" *.jpg`, { stdio: "pipe" });
      console.log(`[tiktok] Created ZIP: ${baseId}.zip`);
    } catch (err) {
      console.error(`[tiktok] ZIP creation failed for ${baseId}:`, err);
    }

    // One entry per carousel — slide 1 as thumbnail, ZIP as download
    const thumbPath = join(slidesDir, "slide_1.jpg");
    ads.push({
      id: baseId,
      type: "image",
      creativeUrl: carousel.webUrl || "",
      localPath: existsSync(thumbPath) ? thumbPath : slidePaths[0],
      adCopy: `@${carousel.username} — ${slidePaths.length} slides — ${carousel.text}`,
      reach: carousel.playCount,
      daysActive: 0,
      startedAt: carousel.createDate.split("T")[0] || todayDir(),
      platforms: ["tiktok"],
      scrapedAt: new Date().toISOString(),
      // ZIP path stored via naming convention: {id}.zip in same dir
    });

    // Mark as processed so it won't appear again
    await saveProcessedId(carousel.postId);
  }

  const metaPath = join(outputDir, "metadata-tiktok.json");
  await writeFile(metaPath, JSON.stringify(ads, null, 2));
  console.log(`[tiktok] Saved ${ads.length} carousels to ${metaPath}`);

  return ads;
}

// Run directly
if (process.argv[1]?.includes("tiktok")) {
  scrapeTiktok().catch(console.error);
}
