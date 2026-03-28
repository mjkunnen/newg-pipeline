import "dotenv/config";
import { writeFile, mkdir, readFile } from "fs/promises";
import { join } from "path";
import { execSync } from "child_process";
import { writeToContentAPI } from "../lib/contentApi.js";
import type { ScrapedAd } from "./types.js";

const OUTPUT_BASE = join(import.meta.dirname, "../../output/raw");

const CONFIG_PATH = join(import.meta.dirname, "../../config/tiktok-accounts.json");

interface TiktokConfig {
  enabled: boolean;
  accounts: string[];
  viral_filter: {
    min_reach: number;
    max_age_days: number;
    max_carousels_per_run: number;
  };
}

async function loadConfig(): Promise<TiktokConfig> {
  const raw = await readFile(CONFIG_PATH, "utf-8");
  return JSON.parse(raw) as TiktokConfig;
}

function requireEnv(key: string): string {
  const val = process.env[key];
  if (!val) {
    throw new Error(
      `Required env var ${key} is not set. ` +
      "Add it to .env (local) or GitHub Actions secrets (CI)."
    );
  }
  return val;
}

const ENSEMBLEDATA_TOKEN = requireEnv("ENSEMBLEDATA_TOKEN");

function todayDir(): string {
  return new Date().toISOString().split("T")[0];
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
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

async function fetchPostsViaEnsemble(accounts: string[]): Promise<EnsemblePost[]> {
  const allPosts: EnsemblePost[] = [];

  for (const username of accounts) {
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

  console.log(`[tiktok] Fetched ${allPosts.length} total posts from EnsembleData (${accounts.length} accounts, ${accounts.length} units used)`);
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
  config: TiktokConfig,
): CarouselCandidate[] {
  const { min_reach, max_age_days, max_carousels_per_run } = config.viral_filter;
  const cutoff = Date.now() / 1000 - max_age_days * 86400;

  const candidates: CarouselCandidate[] = [];
  for (const post of posts) {
    if (!post.image_post_info) continue;
    const slideUrls = getSlideUrls(post);
    if (slideUrls.length < 2) continue;
    if ((post.create_time || 0) < cutoff) continue;

    const postId = String(post.aweme_id || "");
    if (!postId) continue;

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
    const flag = c.playCount < min_reach ? " [SKIP: low reach]" : "";
    console.log(`[tiktok]   @${c.username} — ${c.playCount.toLocaleString()} views — ${c.numSlides} slides — ${c.createDate.split("T")[0]} — ${c.postId}${flag}`);
  }

  // Filter by minimum reach
  const qualified = candidates.filter((c) => c.playCount >= min_reach);
  if (qualified.length === 0 && candidates.length > 0) {
    console.log(`[tiktok] No carousels above ${min_reach.toLocaleString()} views — skipping low-reach content`);
    return [];
  }

  const selected = qualified.slice(0, max_carousels_per_run);
  console.log(`[tiktok] Selected top ${selected.length} (above ${min_reach.toLocaleString()} views):`);
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
  const config = await loadConfig();

  if (!config.enabled) {
    console.log("[tiktok] Scraping disabled via config (enabled=false)");
    return [];
  }

  const outputDir = join(OUTPUT_BASE, todayDir());
  await mkdir(outputDir, { recursive: true });

  // Dedup is handled by Postgres ON CONFLICT DO NOTHING via content API.
  // No local file tracking needed.
  const posts = await fetchPostsViaEnsemble(config.accounts);
  if (posts.length === 0) {
    const metaPath = join(outputDir, "metadata-tiktok.json");
    await writeFile(metaPath, JSON.stringify([], null, 2));
    return [];
  }

  const carousels = selectTopCarousels(posts, config);
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
    const { existsSync } = await import("fs");
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
  }

  const metaPath = join(outputDir, "metadata-tiktok.json");
  await writeFile(metaPath, JSON.stringify(ads, null, 2));
  console.log(`[tiktok] Saved ${ads.length} carousels to ${metaPath}`);

  // Write to Postgres via content API (dedup handled by ON CONFLICT DO NOTHING)
  await writeToContentAPI(ads, "tiktok");

  return ads;
}

// Run directly
if (process.argv[1]?.includes("tiktok")) {
  scrapeTiktok().catch(console.error);
}
