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

export async function launchFromSubmission(
  input: SubmissionInput,
): Promise<MetaCampaign> {
  const draft: CampaignDraft = {
    name: `NEWG-${input.date}-${input.adId}`,
    objective: "OUTCOME_SALES",
    adCopy:
      input.adCopy?.replace(/decarba/gi, "NEWGARMENTS") ||
      "Discover our latest streetwear collection. Premium quality, unmatched style.",
    creativePath: input.creativePath,
    creativeType: input.creativeType,
    targeting: {
      countries: ["NL", "BE", "DE", "FR"],
      ageMin: 18,
      ageMax: 35,
      interests: ["Streetwear", "Fashion", "Urban fashion"],
      placements: ["IG Feed", "IG Stories", "IG Reels"],
    },
    dailyBudget: input.dailyBudget || 1000,
    originalAdId: input.adId,
  };

  return launchCampaign(draft, input.landingPage);
}

export async function launchCampaign(
  draft: CampaignDraft,
  landingPage?: string,
): Promise<MetaCampaign> {
  const { token, adAccountId, igAccountId } = getConfig();
  const actId = `act_${adAccountId}`;
  const isVideo = draft.creativeType === "video";
  const link = landingPage || "https://newgarments.nl";

  console.log(`[meta] Launching: ${draft.name}`);

  // 1. Upload creative
  const mediaId = await uploadCreative(draft.creativePath, isVideo, token, adAccountId);
  console.log(`[meta] Uploaded media: ${mediaId}`);

  // 2. Create campaign (ACTIVE)
  const campaign = await graphPost(`/${actId}/campaigns`, {
    name: draft.name,
    objective: draft.objective,
    status: "ACTIVE",
    special_ad_categories: [],
  }, token);
  console.log(`[meta] Campaign: ${campaign.id}`);

  // 3. Create ad set — Instagram only
  const adSet = await graphPost(`/${actId}/adsets`, {
    name: `AdSet_${draft.originalAdId}`,
    campaign_id: campaign.id,
    billing_event: "IMPRESSIONS",
    optimization_goal: "OFFSITE_CONVERSIONS",
    daily_budget: draft.dailyBudget,
    bid_strategy: "LOWEST_COST_WITHOUT_CAP",
    targeting: {
      geo_locations: { countries: draft.targeting.countries },
      age_min: draft.targeting.ageMin,
      age_max: draft.targeting.ageMax,
      flexible_spec: [{
        interests: [
          { id: "6003384297645", name: "Streetwear" },
          { id: "6003107902433", name: "Fashion" },
          { id: "6003236498529", name: "Urban fashion" },
        ],
      }],
      publisher_platforms: ["instagram"],
      instagram_positions: ["stream", "story", "reels"],
    },
    status: "ACTIVE",
    start_time: new Date(Date.now() + 3600000).toISOString(), // 1 hour from now
  }, token);
  console.log(`[meta] Ad Set: ${adSet.id}`);

  // 4. Create ad creative
  const creativeData: Record<string, unknown> = {
    name: `Creative_${draft.originalAdId}`,
    object_story_spec: {
      ...(igAccountId ? { instagram_actor_id: igAccountId } : {}),
      ...(isVideo
        ? {
            video_data: {
              video_id: mediaId,
              message: draft.adCopy,
              call_to_action: { type: "SHOP_NOW", value: { link } },
            },
          }
        : {
            link_data: {
              message: draft.adCopy,
              link,
              image_hash: mediaId,
              call_to_action: { type: "SHOP_NOW" },
            },
          }),
    },
  };

  const creative = await graphPost(`/${actId}/adcreatives`, creativeData, token);
  console.log(`[meta] Creative: ${creative.id}`);

  // 5. Create ad (ACTIVE)
  const ad = await graphPost(`/${actId}/ads`, {
    name: `Ad_${draft.originalAdId}`,
    adset_id: adSet.id,
    creative: { creative_id: creative.id },
    status: "ACTIVE",
  }, token);
  console.log(`[meta] Ad: ${ad.id}`);

  return {
    campaignId: campaign.id,
    adSetId: adSet.id,
    adId: ad.id,
    creativeId: creative.id,
    status: "ACTIVE",
  };
}
