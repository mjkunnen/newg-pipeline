import "dotenv/config";
import { writeFile, mkdir, readFile } from "fs/promises";
import { join } from "path";
import { existsSync } from "fs";
import { execSync } from "child_process";
import type { ScrapedAd } from "./types.js";

const OUTPUT_BASE = join(import.meta.dirname, "../../output/raw");

const ENSEMBLEDATA_TOKEN = process.env.ENSEMBLEDATA_TOKEN || "";

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

// EnsembleData post format (TikTok internal API)
interface EnsemblePost {
  aweme_id: string;
  desc?: string;
  create_time?: number;
  share_url?: string;
  statistics?: {
    play_count?: number;
    digg_count?: number;
    share_count?: number;
    comment_count?: number;
  };
  author?: {
    unique_id?: string;
    nickname?: string;
  };
  image_post_info?: {
    images?: Array<{
      display_image?: { url_list?: string[] };
      owner_watermark_image?: { url_list?: string[] };
      thumbnail?: { url_list?: string[] };
    }>;
  };
}

interface CarouselCandidate {
  postId: string;
  username: string;
  playCount: number;
  createDate: string;
  webUrl: string;
  text: string;
  numSlides: number;
  slideUrls: string[];
}

async function fetchPostsViaEnsemble(): Promise<EnsemblePost[]> {
  if (!ENSEMBLEDATA_TOKEN) {
    console.log("[tiktok] No ENSEMBLEDATA_TOKEN set, skipping");
    return [];
  }

  const allPosts: EnsemblePost[] = [];

  for (const username of TIKTOK_ACCOUNTS) {
    const url = `https://ensembledata.com/apis/tt/user/posts?username=${username}&depth=1&token=${ENSEMBLEDATA_TOKEN}`;
    try {
      const resp = await fetch(url);
      if (!resp.ok) {
        console.log(`[tiktok] EnsembleData error for @${username}: ${resp.status}`);
        continue;
      }
      const result = await resp.json() as { data?: EnsemblePost[] };
      const posts = result.data || [];
      console.log(`[tiktok] @${username}: ${posts.length} posts`);
      allPosts.push(...posts);
    } catch (err) {
      console.log(`[tiktok] EnsembleData fetch failed for @${username}: ${err}`);
    }
    // Small delay between API calls to be polite
    await delay(500);
  }

  console.log(`[tiktok] Fetched ${allPosts.length} total posts from EnsembleData (${TIKTOK_ACCOUNTS.length} accounts, ${TIKTOK_ACCOUNTS.length} units used)`);
  return allPosts;
}

function getSlideUrls(post: EnsemblePost): string[] {
  const images = post.image_post_info?.images || [];
  const urls: string[] = [];
  for (const img of images) {
    const urlList = img.display_image?.url_list
      || img.owner_watermark_image?.url_list
      || img.thumbnail?.url_list
      || [];
    if (urlList.length > 0) {
      urls.push(urlList[0]);
    }
  }
  return urls;
}

function selectTopCarousels(
  posts: EnsemblePost[],
  processedIds: Set<string>,
): CarouselCandidate[] {
  const cutoff = Date.now() / 1000 - MAX_AGE_DAYS * 86400;

  const candidates: CarouselCandidate[] = [];
  for (const post of posts) {
    if (!post.image_post_info) continue;
    const slideUrls = getSlideUrls(post);
    if (slideUrls.length < 2) continue;
    if ((post.create_time || 0) < cutoff) continue;

    const postId = String(post.aweme_id || "");
    if (!postId || processedIds.has(postId)) continue;

    const username = post.author?.unique_id || "unknown";
    const playCount = post.statistics?.play_count || 0;
    const createDate = post.create_time
      ? new Date(post.create_time * 1000).toISOString()
      : "";

    candidates.push({
      postId,
      username,
      playCount,
      createDate,
      webUrl: post.share_url || `https://www.tiktok.com/@${username}/photo/${postId}`,
      text: (post.desc || "").slice(0, 100),
      numSlides: slideUrls.length,
      slideUrls,
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
    console.log(`[tiktok]   @${c.username} — ${c.playCount.toLocaleString()} views — ${c.postId}`);
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

  const posts = await fetchPostsViaEnsemble();
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
    for (let si = 0; si < carousel.slideUrls.length; si++) {
      const slideUrl = carousel.slideUrls[si];
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
