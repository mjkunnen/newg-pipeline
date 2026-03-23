import { readFile, writeFile, mkdir } from "fs/promises";
import { join } from "path";
import type { CampaignDraft, MetaCampaign, RemixResult } from "../scraper/types.js";

const GRAPH_API = "https://graph.facebook.com/v21.0";
const CAMPAIGNS_DIR = join(import.meta.dirname, "../../output/campaigns");

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

export function prepareAdCampaign(
  remix: RemixResult,
  dailyBudget: number = 1000 // €10 in cents
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

async function uploadCreative(
  filePath: string,
  isVideo: boolean,
  token: string,
  adAccountId: string
): Promise<string> {
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
    return data.id;
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
    return images[firstKey]?.hash;
  }
}

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
  adSets: { adId: string; adSetId: string; adCreativeId: string; metaAdId: string }[];
}

/**
 * Launch all pending submissions as one campaign with separate ad sets.
 * One campaign per day, each submission gets its own ad set + creative + ad.
 */
export async function launchBatch(
  inputs: SubmissionInput[],
): Promise<BatchResult> {
  const { token, adAccountId, igAccountId } = getConfig();
  const actId = `act_${adAccountId}`;
  const pageId = process.env.META_PAGE_ID || "337283139475030";
  const date = todayDir();

  console.log(`[meta] Creating campaign NEWG-${date} with ${inputs.length} ad set(s)`);

  // 1. Create one campaign for the day
  const campaign = await graphPost(`/${actId}/campaigns`, {
    name: `NEWG-${date}`,
    objective: "OUTCOME_SALES",
    status: "ACTIVE",
    special_ad_categories: [],
    is_adset_budget_sharing_enabled: false,
  }, token);
  console.log(`[meta] Campaign: ${campaign.id}`);

  const adSets: BatchResult["adSets"] = [];

  // 2. For each submission: ad set + creative + ad
  for (const input of inputs) {
    const isVideo = input.creativeType === "video";
    const link = input.landingPage || "https://newgarments.nl";
    const adCopy = input.adCopy?.replace(/decarba/gi, "NEWGARMENTS") ||
      "Discover our latest streetwear collection. Premium quality, unmatched style.";

    console.log(`[meta] Creating ad set for ${input.adId}...`);

    // Upload creative
    const mediaId = await uploadCreative(input.creativePath, isVideo, token, adAccountId);
    console.log(`[meta] Uploaded media: ${mediaId}`);

    // Create ad set
    const adSet = await graphPost(`/${actId}/adsets`, {
      name: `AdSet_${input.adId}`,
      campaign_id: campaign.id,
      billing_event: "IMPRESSIONS",
      optimization_goal: "OFFSITE_CONVERSIONS",
      promoted_object: { pixel_id: process.env.META_PIXEL_ID, custom_event_type: "PURCHASE" },
      daily_budget: input.dailyBudget || 2500,
      bid_strategy: "LOWEST_COST_WITHOUT_CAP",
      targeting: {
        geo_locations: { countries: ["NL", "BE", "DE", "FR", "PL", "IT", "AT"] },
        age_min: 18,
        age_max: 65,
      },
      status: "ACTIVE",
      start_time: new Date(Date.now() + 3600000).toISOString(),
    }, token);
    console.log(`[meta] Ad Set: ${adSet.id}`);

    // Create ad creative
    const creativeData: Record<string, unknown> = {
      name: `Creative_${input.adId}`,
      object_story_spec: {
        page_id: pageId,
        ...(igAccountId ? { instagram_actor_id: igAccountId } : {}),
        ...(isVideo
          ? {
              video_data: {
                video_id: mediaId,
                message: adCopy,
                call_to_action: { type: "SHOP_NOW", value: { link } },
              },
            }
          : {
              link_data: {
                message: adCopy,
                link,
                image_hash: mediaId,
                call_to_action: { type: "SHOP_NOW" },
              },
            }),
      },
    };

    const creative = await graphPost(`/${actId}/adcreatives`, creativeData, token);
    console.log(`[meta] Creative: ${creative.id}`);

    // Create ad
    const ad = await graphPost(`/${actId}/ads`, {
      name: `Ad_${input.adId}`,
      adset_id: adSet.id,
      creative: { creative_id: creative.id },
      status: "ACTIVE",
    }, token);
    console.log(`[meta] Ad: ${ad.id}`);

    adSets.push({
      adId: input.adId,
      adSetId: adSet.id,
      adCreativeId: creative.id,
      metaAdId: ad.id,
    });
  }

  return { campaignId: campaign.id, adSets };
}

/** Legacy wrapper for index.ts — launches a single draft as its own campaign */
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
    adSetId: result.adSets[0].adSetId,
    adId: result.adSets[0].metaAdId,
    creativeId: result.adSets[0].adCreativeId,
    status: "ACTIVE",
  };
}
