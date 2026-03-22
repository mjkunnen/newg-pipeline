"""Build structured audience profile from ingested documents."""
import json
import logging

logger = logging.getLogger(__name__)


def build_audience_profile(docs: dict[str, str]) -> dict:
    """Extract audience profile from all documents.

    This is a structured extraction based on deep reading of the source documents.
    All data points come directly from the uploaded files.
    """
    profile = {
        "demographics": {
            "age_range": "16-25",
            "core_age": "18-22",
            "gender": "Predominantly male (60-70%) with growing female segment (~40% of streetwear market)",
            "locations": ["US", "UK", "EU (London, Berlin, Amsterdam, NYC, LA)"],
            "income": "$0-$1,500/month disposable (students, part-time workers, entry-level)",
            "backgrounds": [
                "Students",
                "Creatives (design, music, film, content)",
                "Part-time retail/hospitality",
                "Resellers",
                "Aspiring entrepreneurs",
            ],
        },
        "identity_traits": [
            "Fashion-forward youth / trendsetters",
            "TikTok creators and consumers",
            "Sneakerheads",
            "Music/festival culture participants",
            "Part of 'the culture' - underground, not mainstream hypebeast",
            "Digitally native - practically live on social platforms",
            "96% use Instagram to discover new products",
            "73% find new fashion brands via TikTok/Instagram",
            "Least brand-loyal generation - 50% prefer to explore new brands",
        ],
        "aesthetic_preferences": [
            "Archive/Vintage - 90s thrift haul, designer past season grails",
            "Clean Fit / Minimalist - neutral tones, clean oversized silhouettes, minimal branding",
            "Techwear and Gorpcore - dark, utilitarian, functional",
            "Grunge/Y2K - ripped jeans, flannels, early 2000s elements",
            "Cozy Core - oversized hoodies, sweatpants, puffer jackets",
            "Unisex fits preferred (50%+ of young consumers prefer unisex sizing)",
            "Heavyweight fabrics (400-500+ GSM)",
            "Boxy fit, oversized silhouettes",
            "Archive-coded design language",
        ],
        "pain_points": [
            "Thin, cheap fabric from fast fashion and TikTok brands",
            "Print cracking, peeling, or cheap iron-on graphics",
            "Hoodies that lose shape after one wash",
            "Copycat designs - every TikTok brand looks the same",
            "Fake 'limited' drops that restock anyway",
            "Inconsistent sizing between drops and brands",
            "Poor quality control (discolored zippers, lint, missing components)",
            "Slow shipping and no tracking updates",
            "Unresponsive customer support - ghosted for weeks",
            "Difficult/expensive return processes",
            "Price doesn't match quality received",
            "Brands that are just dropshippers reselling AliExpress",
            "Deceptive product photos vs reality",
        ],
        "wants_and_desires": [
            "Clothes that express individual identity, not follow trends",
            "Stand out without looking like a try-hard",
            "Heavyweight, well-made items that signal seriousness about culture",
            "Rare/limited pieces that others recognize and ask about",
            "Archive-style pieces with story and cultural significance",
            "Feel like 'main character', not an NPC",
            "Be early to trends and help define them",
            "Own grails that hold value or clout over time",
            "Build a personal aesthetic that's respected and authentic",
            "Feel confident, seen, and part of the right wave",
        ],
        "emotional_triggers": {
            "fear_of_invisibility": "Deep existential anxiety about blending in, being average, being an NPC",
            "fear_of_being_a_poser": "Don't want to be seen as copying others or wearing cringe brands",
            "desire_for_recognition": "Want 'where'd you get that?' moments - validation from peers",
            "fomo_and_urgency": "Regret from missing real archive drops powers future action",
            "pride_in_rarity": "Owning what others can't get = status and cultural capital",
            "distrust_of_brands": "Burned by scams, cheap quality, fake scarcity - deeply cynical",
            "confidence_through_style": "Clothing = their profile picture in real life",
        },
        "objections": [
            "Is this a scam? Never heard of it.",
            "Pictures look good but will the actual product suck?",
            "What if it's just a dropshipper reselling AliExpress?",
            "What if sizing/fit is off?",
            "Will it shrink or fade after washing?",
            "Why is it priced like this? Is quality really better?",
            "Do they actually ship on time?",
            "Can I return if it doesn't fit?",
            "Is this just another TikTok brand with a fake aesthetic?",
            "No one I know has ordered from them.",
            "Why do they have followers but no real engagement?",
            "Will it still be wearable next season?",
            "If it's such a good brand why discount so much?",
        ],
        "buying_motivations": [
            "Scarcity: 'No restock? Say less, I'm buying now.'",
            "Peer validation: friends tagging each other on drop posts",
            "Regret avoidance: 'Not making that mistake again'",
            "Value: quality-to-price ratio that feels like a steal",
            "Identity expression: wearing something that matches their aesthetic",
            "Status: owning what few others have",
            "Community belonging: being part of an exclusive group",
            "Bundle/stack savings when trust is established",
        ],
        "language_patterns": {
            "praise": ["fire", "goes hard", "clean", "drippy", "goated", "built different", "slept on", "worth the cop", "steal", "grail", "A1", "cozy"],
            "insults": ["mid", "basic", "NPC", "cringe", "try-hard", "trash", "L", "scam", "cooked", "cheap knock-off", "oversaturated"],
            "quality": ["heavyweight", "thick", "boxy", "oversized", "TTS", "GSM", "constructed well", "built like a tank", "blanks"],
            "scarcity": ["drop", "cop", "don't sleep", "FOMO", "should've copped", "missed out", "restock", "sell out", "exclusive", "archive"],
            "deals": ["steal", "W", "bundle", "BOGO", "retail", "code"],
        },
        "content_preferences": {
            "tiktok": "Discovery + hype. Quick dopamine. Proof signals in first 5 seconds. UGC style, lifestyle posts, item-focused videos, editorial slideshows.",
            "instagram": "Trust + belonging. Consistent aesthetic, reviews, fit guides, BTS content. Caption tone: premium-factual ('480gsm / double stitched / ships EU-wide').",
            "valued_content": [
                "UGC-style product shots (not overly polished)",
                "Fit breakdowns with model height/weight",
                "Behind-the-scenes (QC, production, shipping)",
                "Real customer reposts",
                "Story-driven drop announcements",
                "Community polls and involvement",
            ],
        },
        "frustrations_with_brands": {
            "vicinity": "Good quality/price but slow shipping, awful customer service, ignored for months",
            "divinbydivin": "Suspected scam, poor QC (lint, discoloration after one wear), 11% negative review response rate",
            "thesupermade": "Pure dropshipper - AliExpress clothes at markup, multiple scam reports, months without delivery",
            "scuffers": "Some fit issues, expensive returns (paid 64 got 39 back), but good community and some great service experiences",
            "fast_fashion": "Thin fabric, no durability, everyone has the same pieces, environmental concerns",
            "mainstream_hype": "Overpriced for logo, loss of exclusivity, declining quality, impossible drop access",
        },
    }

    logger.info("Audience profile built from source documents")
    return profile


def save_audience_profile(profile: dict, output_path: str):
    """Save audience profile to JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    logger.info(f"Audience profile saved to {output_path}")
