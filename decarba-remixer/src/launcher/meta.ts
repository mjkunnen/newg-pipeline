import { readFile, writeFile, mkdir } from "fs/promises";
import { join } from "path";
import type { CampaignDraft, MetaCampaign, RemixResult } from "../scraper/types.js";

const GRAPH_API = "https://graph.facebook.com/v21.0";
const CAMPAIGNS_DIR = join(import.meta.dirname, "../../output/campaigns");

const CAMPAIGN_NAME = "NEWG-Scaling";
const ADSET_NAME = "AdSet_Broad";

const BRAND_TONE = `You are the copywriter for NEWGARMENTS, a premium Gen Z streetwear brand.

Current campaign: ARCHIVE SALE — our biggest sale ever. Create urgency.

Brand voice:
- Confident, bold, direct — never try-hard or cringe
- Short punchy sentences. No fluff, no filler
- Create urgency: this sale won't last, sizes selling out, archive pieces going fast
- Reference "Archive Sale" by name — it's our biggest sale ever
- Mix English with light streetwear slang
- Emojis: minimal and tasteful (max 1-2), never "🔥" or "💯"
- Premium feel: quality over hype, even on sale

Examples of good NEWGARMENTS copy:
- "Archive Sale is live. Our biggest ever. Once it's gone, it's gone."
- "Up to 70% off archive pieces. Sizes are moving fast."
- "The vault is open. Archive Sale — don't sleep on this."
- "Premium streetwear at archive prices. This won't happen again."`;

interface AdCopyResult {
  primaryText: string;
  headline: string;
}

async function rewriteAdCopy(
  originalCopy: string,
  landingPage: string,
): Promise<AdCopyResult> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.log("[meta] No OPENAI_API_KEY, using fallback copy");
    return {
      primaryText: originalCopy.replace(/decarba/gi, "NEWGARMENTS"),
      headline: "NEWGARMENTS",
    };
  }

  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "gpt-4o-mini",
      temperature: 0.8,
      messages: [
        { role: "system", content: BRAND_TONE },
        {
          role: "user",
          content: `Rewrite this competitor ad copy for NEWGARMENTS. Keep the same intent/offer but make it ours.

Original copy: "${originalCopy}"
Landing page: ${landingPage}

Return JSON only, no markdown:
{"primaryText": "the main ad text (2-3 sentences max, under 125 chars ideal)", "headline": "short punchy headline (under 40 chars)"}`,
        },
      ],
    }),
  });

  if (!res.ok) {
    console.error("[meta] OpenAI rewrite failed:", await res.text());
    return {
      primaryText: originalCopy.replace(/decarba/gi, "NEWGARMENTS"),
      headline: "NEWGARMENTS",
    };
  }

  const data = await res.json();
  const content = data.choices?.[0]?.message?.content || "";
  try {
    const cleaned = content.replace(/```json?\n?|\n?```/g, "").trim();
    const parsed: AdCopyResult = JSON.parse(cleaned);
    console.log(`[meta] Rewritten copy: "${parsed.headline}" / "${parsed.primaryText.slice(0, 50)}..."`);
    return parsed;
  } catch {
    console.error("[meta] Failed to parse rewritten copy, using fallback");
    return {
      primaryText: originalCopy.replace(/decarba/gi, "NEWGARMENTS"),
      headline: "NEWGARMENTS",
    };
  }
}

function todayDir(): string {
  return new Date().toISOString().split("T")[0];
}

function getConfig() {
  const token = process.env.META_ACCESS_TOKEN;
  const adAccountId = process.env.META_AD_ACCOUNT_ID;
  const igAccountId = process.env.META_INSTAGRAM_ACCOUNT_ID;

  if (!token || !adAccountId) {
    throw new Error("META_ACCESS_TOKEN and META_AD_ACCOUNT_ID required");
  }

  return { token, adAccountId, igAccountId };
}

async function graphPost(
  path: string,
  body: Record<string, unknown>,
  token: string
): Promise<Record<string, string>> {
  const res = await fetch(`${GRAPH_API}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Meta API ${path}: ${res.status} ${err}`);
  }

  return res.json();
}

async function graphGet(
  path: string,
  token: string,
): Promise<Record<string, unknown>> {
  const separator = path.includes("?") ? "&" : "?";
  const res = await fetch(`${GRAPH_API}${path}${separator}access_token=${token}`);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Meta API GET ${path}: ${res.status} ${err}`);
  }
  return res.json();
}

// --- Find or create persistent campaign ---

async function findOrCreateCampaign(
  actId: string,
  token: string,
): Promise<string> {
  const data = await graphGet(
    `/${actId}/campaigns?filtering=[{"field":"name","operator":"EQUAL","value":"${CAMPAIGN_NAME}"}]&fields=id,name,status&limit=1`,
    token,
  );

  const campaigns = (data.data as Array<{ id: string; name: string }>) || [];
  const existing = campaigns.find((c) => c.name === CAMPAIGN_NAME);

  if (existing) {
    console.log(`[meta] Found campaign: ${existing.id}`);
    return existing.id;
  }

  console.log(`[meta] Creating campaign: ${CAMPAIGN_NAME}`);
  const campaign = await graphPost(`/${actId}/campaigns`, {
    name: CAMPAIGN_NAME,
    objective: "OUTCOME_SALES",
    status: "ACTIVE",
    special_ad_categories: [],
    is_adset_budget_sharing_enabled: false,
  }, token);
  console.log(`[meta] Campaign created: ${campaign.id}`);
  return campaign.id;
}

// --- Find or create persistent ad set ---

async function findOrCreateAdSet(
  actId: string,
  campaignId: string,
  token: string,
  dailyBudget: number,
): Promise<string> {
  const data = await graphGet(
    `/${actId}/adsets?filtering=[{"field":"name","operator":"EQUAL","value":"${ADSET_NAME}"}]&fields=id,name,campaign_id,status&limit=5`,
    token,
  );

  const adSets = (data.data as Array<{ id: string; name: string; campaign_id: string }>) || [];
  const existing = adSets.find((a) => a.name === ADSET_NAME && a.campaign_id === campaignId);

  if (existing) {
    console.log(`[meta] Found ad set: ${existing.id}`);
    return existing.id;
  }

  console.log(`[meta] Creating ad set: ${ADSET_NAME}`);
  const adSet = await graphPost(`/${actId}/adsets`, {
    name: ADSET_NAME,
    campaign_id: campaignId,
    billing_event: "IMPRESSIONS",
    optimization_goal: "OFFSITE_CONVERSIONS",
    promoted_object: { pixel_id: process.env.META_PIXEL_ID, custom_event_type: "PURCHASE" },
    daily_budget: dailyBudget,
    bid_strategy: "LOWEST_COST_WITHOUT_CAP",
    targeting: {
      geo_locations: { countries: ["NL", "BE", "DE", "FR", "PL", "IT", "AT"] },
      age_min: 18,
      age_max: 30,
      targeting_automation: { advantage_audience: 0 },
    },
    status: "ACTIVE",
  }, token);
  console.log(`[meta] Ad Set created: ${adSet.id}`);
  return adSet.id;
}

// --- Upload creative ---

async function waitForVideoThumbnail(
  videoId: string,
  token: string,
  maxAttempts = 10,
): Promise<string> {
  for (let i = 0; i < maxAttempts; i++) {
    const data = await graphGet(`/${videoId}?fields=thumbnails`, token);
    const thumbs = (data.thumbnails as { data?: Array<{ uri: string }> })?.data;
    if (thumbs && thumbs.length > 0) return thumbs[0].uri;
    await new Promise((r) => setTimeout(r, 3000));
  }
  throw new Error(`Video ${videoId} thumbnail not ready after ${maxAttempts * 3}s`);
}

async function uploadCreative(
  filePath: string,
  isVideo: boolean,
  token: string,
  adAccountId: string
): Promise<{ id: string; thumbnailUrl?: string }> {
  const fileBuffer = await readFile(filePath);

  if (isVideo) {
    const formData = new FormData();
    formData.append("access_token", token);
    formData.append("source", new Blob([fileBuffer], { type: "video/mp4" }), "ad_video.mp4");

    const res = await fetch(`${GRAPH_API}/act_${adAccountId}/advideos`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error(`Video upload failed: ${await res.text()}`);
    const data: Record<string, string> = await res.json();
    console.log(`[meta] Video uploaded: ${data.id}, waiting for thumbnail...`);
    const thumbnailUrl = await waitForVideoThumbnail(data.id, token);
    return { id: data.id, thumbnailUrl };
  } else {
    const formData = new FormData();
    formData.append("access_token", token);
    formData.append("filename", new Blob([fileBuffer], { type: "image/jpeg" }), "ad_image.jpg");

    const res = await fetch(`${GRAPH_API}/act_${adAccountId}/adimages`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error(`Image upload failed: ${await res.text()}`);
    const data = await res.json();
    const images = data.images || {};
    const firstKey = Object.keys(images)[0];
    return { id: images[firstKey]?.hash };
  }
}

// --- Public interfaces ---

export interface SubmissionInput {
  adId: string;
  adCopy: string;
  creativePath: string;
  creativeType: "image" | "video";
  landingPage: string;
  date: string;
  dailyBudget?: number;
}

export interface BatchResult {
  campaignId: string;
  adSetId: string;
  ads: { adId: string; adCreativeId: string; metaAdId: string }[];
}

/**
 * Add new creatives as ads to the persistent NEWG-Scaling campaign + AdSet_Broad.
 * 1 campaign, 1 ad set, N ads. No learning phase resets.
 */
export async function launchBatch(
  inputs: SubmissionInput[],
): Promise<BatchResult> {
  const { token, adAccountId, igAccountId } = getConfig();
  const actId = `act_${adAccountId}`;
  const pageId = process.env.META_PAGE_ID || "337283139475030";
  const dailyBudget = inputs[0]?.dailyBudget || 5000;

  // Find or create persistent campaign + ad set
  const campaignId = await findOrCreateCampaign(actId, token);
  const adSetId = await findOrCreateAdSet(actId, campaignId, token, dailyBudget);

  console.log(`[meta] Adding ${inputs.length} ad(s) to ${ADSET_NAME}`);

  const ads: BatchResult["ads"] = [];

  for (const input of inputs) {
    const isVideo = input.creativeType === "video";
    const link = input.landingPage || "https://newgarments.nl";
    const { primaryText: adCopy, headline } = await rewriteAdCopy(
      input.adCopy || "Discover our latest streetwear collection.",
      link,
    );

    // Upload creative
    const media = await uploadCreative(input.creativePath, isVideo, token, adAccountId);
    console.log(`[meta] Uploaded media for ${input.adId}: ${media.id}`);

    // Create ad creative
    const creativeData: Record<string, unknown> = {
      name: `Creative_${input.adId}`,
      object_story_spec: {
        page_id: pageId,
        ...(igAccountId ? { instagram_user_id: igAccountId } : {}),
        ...(isVideo
          ? {
              video_data: {
                video_id: media.id,
                message: adCopy,
                title: headline,
                call_to_action: { type: "SHOP_NOW", value: { link } },
                image_url: media.thumbnailUrl,
              },
            }
          : {
              link_data: {
                message: adCopy,
                name: headline,
                link,
                image_hash: media.id,
                call_to_action: { type: "SHOP_NOW" },
              },
            }),
      },
    };

    const creative = await graphPost(`/${actId}/adcreatives`, creativeData, token);
    console.log(`[meta] Creative: ${creative.id}`);

    // Create ad in the persistent ad set
    const ad = await graphPost(`/${actId}/ads`, {
      name: `Ad_${input.adId}`,
      adset_id: adSetId,
      creative: { creative_id: creative.id },
      status: "ACTIVE",
    }, token);
    console.log(`[meta] Ad: ${ad.id}`);

    ads.push({
      adId: input.adId,
      adCreativeId: creative.id,
      metaAdId: ad.id,
    });
  }

  return { campaignId, adSetId, ads };
}

// --- Legacy functions for index.ts ---

export function prepareAdCampaign(
  remix: RemixResult,
  dailyBudget: number = 1000
): CampaignDraft {
  const adCopy =
    remix.originalAd.adCopy?.replace(/decarba/gi, "NEWGARMENTS") ||
    "Discover our latest streetwear collection. Premium quality, unmatched style.";

  const draft: CampaignDraft = {
    name: `NEWGARMENTS-${todayDir()}-${remix.originalAd.id}`,
    objective: "OUTCOME_SALES",
    adCopy,
    creativePath: remix.remixedPaths[0],
    creativeType: remix.originalAd.type,
    targeting: {
      countries: ["NL", "BE", "DE", "FR"],
      ageMin: 18,
      ageMax: 35,
      interests: ["Streetwear", "Fashion", "Urban fashion"],
      placements: ["IG Feed", "IG Stories", "IG Reels"],
    },
    dailyBudget,
    originalAdId: remix.originalAd.id,
  };

  console.log(`[meta] Prepared draft: ${draft.name}`);
  return draft;
}

export async function saveDrafts(drafts: CampaignDraft[]): Promise<string> {
  const dir = join(CAMPAIGNS_DIR, todayDir());
  await mkdir(dir, { recursive: true });

  const path = join(dir, "drafts.json");
  await writeFile(path, JSON.stringify(drafts, null, 2));
  console.log(`[meta] Saved ${drafts.length} drafts to ${path}`);
  return path;
}

export async function launchCampaign(
  draft: CampaignDraft,
  landingPage?: string,
): Promise<MetaCampaign> {
  const result = await launchBatch([{
    adId: draft.originalAdId,
    adCopy: draft.adCopy,
    creativePath: draft.creativePath,
    creativeType: draft.creativeType,
    landingPage: landingPage || "https://newgarments.nl",
    date: new Date().toISOString().split("T")[0],
    dailyBudget: draft.dailyBudget,
  }]);

  return {
    campaignId: result.campaignId,
    adSetId: result.adSetId,
    adId: result.ads[0].metaAdId,
    creativeId: result.ads[0].adCreativeId,
    status: "ACTIVE",
  };
}
