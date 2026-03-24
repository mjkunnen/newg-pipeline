import "dotenv/config";
import { writeFile, mkdir, readFile } from "fs/promises";
import { join } from "path";
import { existsSync } from "fs";
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

const MAX_CAROUSELS = 5;
const MAX_AGE_DAYS = 7;
const RESULTS_PER_PAGE = 20;

// Local tracking of processed post IDs (shared with tiktok_checker.py)
const PROCESSED_FILE = join(import.meta.dirname, "../../../scout/processed_tiktok.json");

function todayDir(): string {
  return new Date().toISOString().split("T")[0];
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function getProcessedIds(): Promise<Set<string>> {
  try {
    if (existsSync(PROCESSED_FILE)) {
      const data = JSON.parse(await readFile(PROCESSED_FILE, "utf-8"));
      return new Set(data);
    }
  } catch {
    // ignore
  }
  return new Set();
}

async function saveProcessedId(postId: string) {
  const existing = await getProcessedIds();
  existing.add(postId);
  await writeFile(PROCESSED_FILE, JSON.stringify([...existing].sort(), null, 2));
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
  const selected = candidates.slice(0, MAX_CAROUSELS);

  console.log(`[tiktok] ${candidates.length} carousel candidates, selected top ${selected.length}`);
  for (const c of selected) {
    console.log(`[tiktok]   @${c.username} — ${c.playCount.toLocaleString()} views — ${c.numSlides} slides — ${c.postId}`);
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
    let downloadedAny = false;

    // Download ALL slides for this carousel
    for (let si = 0; si < carousel.slides.length; si++) {
      const slide = carousel.slides[si];
      const slideUrl = slide?.downloadLink || slide?.tiktokLink || "";
      if (!slideUrl) continue;

      const slideNum = si + 1;
      const id = `${baseId}_slide${slideNum}`;
      const filename = `${id}.jpg`;
      const filepath = join(outputDir, filename);

      const ok = await downloadSlideImage(slideUrl, filepath);
      if (!ok) {
        console.log(`[tiktok] Failed to download ${filename}`);
        continue;
      }

      const sizeKB = ((await readFile(filepath)).length / 1024).toFixed(0);
      console.log(`[tiktok] Downloaded: ${filename} (${sizeKB}KB)`);
      downloadedAny = true;

      ads.push({
        id,
        type: "image",
        creativeUrl: carousel.webUrl || slideUrl,
        localPath: filepath,
        adCopy: `@${carousel.username} — slide ${slideNum}/${carousel.numSlides}`,
        reach: carousel.playCount,
        daysActive: 0,
        startedAt: carousel.createDate.split("T")[0] || todayDir(),
        platforms: ["tiktok"],
        scrapedAt: new Date().toISOString(),
      });

      await delay(300);
    }

    if (downloadedAny) {
      console.log(`[tiktok] @${carousel.username} — ${carousel.numSlides} slides downloaded`);
    }

    // Mark as processed so we don't show it again tomorrow
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
