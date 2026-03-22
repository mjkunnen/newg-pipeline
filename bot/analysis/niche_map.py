"""Build a structured niche map from audience and brand profiles."""
import json
import logging

logger = logging.getLogger(__name__)


def build_niche_map(audience: dict, brand: dict) -> dict:
    """Create a niche map combining audience insights and brand positioning."""
    niche_map = {
        "niche_definition": {
            "name": "Gen Z Premium Underground Streetwear",
            "description": "Exclusive, archive-coded streetwear targeting 16-25 year olds who use clothing as identity expression, value rarity over hype, and demand real quality with brand transparency.",
        },
        "audience_summary": {
            "who": "Gen Z (16-25, core 18-22) urban youth, digitally native, streetwear-obsessed. Students, creatives, part-time workers. 60-70% male, growing female segment.",
            "what_they_want": "Heavyweight, limited-run pieces with archive aesthetic that set them apart. Quality they can trust. A brand that feels real, not another TikTok scam.",
            "emotional_outcome_buying": [
                "Confidence and status within their peer group",
                "Recognition: 'where did you get that?' moments",
                "Belonging to an exclusive, in-the-know community",
                "Relief from FOMO - knowing they secured something rare",
                "Pride in owning something no one else can get",
            ],
        },
        "brand_image_attraction": {
            "visual": "Archive-coded, clean but not sterile, UGC-authentic not over-polished. Dark/muted tones with premium feel.",
            "messaging": "Premium-factual ('480gsm / double stitched'). Confident without being arrogant. Uses audience language naturally, not forced.",
            "values": "Transparency, real scarcity, quality-first, community over clout",
        },
        "resonating_messaging": [
            "No restocks. No cringe. Real streetwear.",
            "Built heavy. Worn hard. Gone fast.",
            "The hoodie they'll ask about. The one you can't get again.",
            "Streetwear with a memory. Not just a logo.",
            "This isn't fast fashion. It's a one-time drop.",
        ],
        "resonating_aesthetics": [
            "Archive/vintage-inspired but contemporary",
            "Heavyweight fabric close-ups, texture shots",
            "Real people styling pieces (UGC, not studio-perfect)",
            "Muted color palettes, earth tones, washed-out effects",
            "Minimal branding, clean silhouettes",
            "Behind-the-scenes production/QC footage",
        ],
        "resonating_offers": [
            "Limited numbered drops (e.g., 50-100 pieces)",
            "Stack-to-save bundles (2+ items for % off)",
            "Early access for community members",
            "Transparent stock counters on product pages",
            "Free shipping thresholds",
        ],
        "market_gaps": [
            "Reliable quality at mid-range prices (not luxury, not fast fashion)",
            "Truly limited drops with integrity (no fake scarcity)",
            "Transparent, communicative brand (not faceless IG shop)",
            "Original archive-coded design (not copycat)",
            "Community-driven brand with real involvement",
            "Excellent customer service (fast replies, easy returns, tracking)",
        ],
        "competitor_search_criteria": {
            "must_match": [
                "Targets Gen Z (16-25)",
                "Streetwear / fashion category",
                "Online D2C model",
                "Active on TikTok and/or Instagram",
            ],
            "strong_signals": [
                "Limited/exclusive drop model",
                "Archive or vintage aesthetic",
                "Heavyweight / premium quality positioning",
                "Community-building efforts",
                "Active Meta/TikTok ads",
            ],
            "adjacent_signals": [
                "Similar price range (mid-tier: $40-$120 per piece)",
                "EU/UK/US market focus",
                "Instagram-born or TikTok-native brand",
                "Uses UGC-style content",
            ],
        },
    }

    logger.info("Niche map built from audience + brand profiles")
    return niche_map


def save_niche_map(niche_map: dict, output_path: str):
    """Save niche map to JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(niche_map, f, indent=2, ensure_ascii=False)
    logger.info(f"Niche map saved to {output_path}")
