export interface ScrapedAd {
  id: string;
  type: "image" | "video";
  creativeUrl: string;
  thumbnailUrl?: string;
  localPath?: string;
  headline?: string;
  adCopy?: string;
  reach: number;
  daysActive: number;
  startedAt: string;
  platforms: string[];
  productLink?: string;
  scrapedAt: string;
}

export interface AdAnalysis {
  layout: string;
  text_overlays: string[];
  colors: string[];
  model_description: string;
  product_type: string;
  vibe: string;
  remake_prompt: string;
}

export interface TextOverlay {
  text: string;
  position: "top" | "center" | "bottom";
  style: "bold" | "regular" | "script";
  color: string;
  approximate_size: "small" | "medium" | "large";
}

export interface Product {
  name: string;
  collection: string;
  url?: string;
  imageUrl?: string;
  keywords: string[];
}

export interface RemixResult {
  originalAd: ScrapedAd;
  analysis?: AdAnalysis;
  remixedPaths: string[];
  method: "image-to-image" | "text-to-image" | "video-trim";
}

export interface CampaignDraft {
  name: string;
  objective: string;
  adCopy: string;
  creativePath: string;
  creativeType: "image" | "video";
  targeting: {
    countries: string[];
    ageMin: number;
    ageMax: number;
    interests: string[];
    placements: string[];
  };
  dailyBudget: number;
  originalAdId: string;
}

export interface MetaCampaign {
  campaignId: string;
  adSetId: string;
  adId: string;
  creativeId: string;
  status: string;
}

export interface Settings {
  max_ads: number;
  trim_seconds: number;
  collections_to_use: string[];
  auto_upload_drive: boolean;
  auto_launch_meta: boolean;
}
