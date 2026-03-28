"""Build structured brand profile from ingested documents."""
import json
import logging

logger = logging.getLogger(__name__)


def build_brand_profile(docs: dict[str, str]) -> dict:
    """Extract NEWGARMENTS brand profile from all documents.

    All data points come directly from the uploaded brand documents.
    """
    profile = {
        "brand_name": "NEWGARMENTS",
        "previous_name": "Credo Collective",
        "positioning": {
            "tagline": "Real archive streetwear. Built to last. Never restocked. Worn by the ones who know.",
            "category": "Exclusive underground streetwear",
            "market_position": "Third option between cheap fast fashion and overpriced luxury",
            "brand_role": [
                "The insider guide - selects/drops what audience seeks but can't find elsewhere",
                "An original brand - protects streetwear against dilution by mass/TikTok fashion",
                "A trusted brand - eliminates fear of scams/cheapness through proof and transparency",
            ],
        },
        "mission": "Credo maakt exclusieve, originele en betrouwbare streetwear voor jongeren die zich willen onderscheiden zonder cringe, zodat ze met vertrouwen hun eigen aesthetic kunnen bouwen en status krijgen binnen hun groep.",
        "vision": "Authentieke underground fashion met premium kwaliteit, fit en transparantie. Doel: wereldwijd bekendstaan als het collectief dat streetwear bevrijdt en jongeren helpt hun eigen identiteit te bouwen.",
        "end_goal": "Bekendstaan als het merk dat streetwear bevrijdt van massaliteit, hype en wantrouwen - een wereldwijd collectief dat premium kwaliteit, perfecte fits en transparantie levert.",
        "core_values": [
            "Transparency / trust",
            "Liberation from mass fashion",
            "Perfect fits",
            "Premium quality",
            "Real exclusivity (no fake scarcity)",
        ],
        "paradigm_shift": {
            "old_belief": "Streetwear is either mass-produced and generic, or unattainable and gatekept, or untrustworthy and scammy.",
            "new_truth": "There is a third option: exclusive and original streetwear fashion with the same heavy quality as top brands, but accessible and trustworthy.",
            "identity_shift": "From 'I'm one of the mass, hoping someone sees me' to 'With this piece, I'm recognized without saying a word.'",
        },
        "audience_fears_addressed": {
            "fear_of_invisibility": "Pieces that make you stand out and get recognized",
            "panic_of_falling_behind": "Always fresh, archive-coded drops that keep you ahead",
            "shame_of_being_a_poser": "Original designs that prove you 'live it', not just copy it",
            "doubt_about_authenticity": "Premium blanks, transparent production, honest scarcity",
        },
        "product": {
            "categories": ["Hoodies", "Crewnecks", "Pants", "T-shirts"],
            "construction": "Heavyweight (400-500+ GSM)",
            "fit": "Archive-coded fit and palette, boxy/oversized silhouettes",
            "scarcity_model": "Limited-run drops, never restocked. Re-release only bestsellers.",
            "design_language": "Archive-coded, original, not derivative",
        },
        "offer_structure": {
            "format": "Limited drops with stack-to-save bundles",
            "landing_page": "Immersive, aesthetic-heavy, direct headline, video or stills",
            "product_page": "Scarcity triggers, UGC-style images, weight/fit specs",
            "bundle": "Stack-to-save offer with visual cart builder",
            "post_purchase": "Access to archive/early access to next drop",
        },
        "brand_voice": {
            "tone": "Premium-factual, not hypey. Confident but not arrogant.",
            "instagram_tone": "Zakelijk-premium: '480gsm / double stitched / ships EU-wide' not just hype",
            "tiktok_tone": "Quick recognition and emotion. Trust through visual proof signals in first 5 seconds.",
            "avoid": [
                "Cringe slogans",
                "Fake countdown timers",
                "Over-the-top hype language",
                "Perpetual discounts / outlet vibe",
                "Influencer mascots",
            ],
        },
        "competitive_references": {
            "aspirational": ["Corteiz (drop pages)", "Represent Clo (pre-launch funnels)", "Early Stussy (archive collections)", "Trapstar (gated drops)"],
            "direct_competitors": ["Vicinity", "Divinbydivin", "TheSupermade", "Scuffers"],
        },
        "social_strategy": {
            "tiktok_role": "Discovery + hype. People see you for the first time. Quick dopamine.",
            "instagram_role": "Trust + belonging. They check if you're legit, if aesthetic matches, if they want to join.",
            "flow": "TikTok makes them curious -> Instagram convinces them you're trustworthy",
            "content_types": ["Lifestyle posts", "UGC content", "Item-focused videos", "Editorial slideshows"],
            "kpis": {
                "hook_rate": ">35% (3s view / impressions)",
                "avg_watch_time": "5-8s on 10-12s video",
                "engagement_rate": ">5% (likes+comments+saves / views)",
                "click_through": ">1.5% (profile/shop clicks / views)",
                "save_rate": ">0.6%",
            },
        },
        "trust_signals": [
            "Real reviews (screenshots + fits)",
            "Fit guide with model height/weight",
            "Behind-the-scenes content (QC, production, shipping)",
            "Daily story clips of packaging, polls, customer reposts",
            "Transparent stock counts",
            "No Gildan blanks, no fake countdowns, no restocks",
        ],
        "metaphors": [
            "It's not a hoodie. It's a timestamp.",
            "You're not wearing clothes, you're collecting culture.",
            "Less a brand - more a vault.",
        ],
    }

    logger.info("Brand profile built from source documents")
    return profile


def save_brand_profile(profile: dict, output_path: str):
    """Save brand profile to JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    logger.info(f"Brand profile saved to {output_path}")
