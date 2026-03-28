"""
Scout configuration — subscription brand discovery settings.
"""

# Niches to search for subscription brands (rotates daily)
SEARCH_QUERIES = [
    # Pet niche
    "monthly dog treat box subscription",
    "cat toy subscription box",
    "pet subscription box brand",
    # Hobby/craft
    "monthly craft subscription box",
    "sticker subscription box",
    "stationery subscription monthly",
    "art supply subscription box",
    # Home/lifestyle
    "candle subscription box monthly",
    "home fragrance subscription",
    "plant subscription box monthly",
    "mystery snack box subscription",
    # Niche fashion accessories
    "sock subscription box monthly",
    "jewelry subscription box",
    "watch accessories subscription",
    # Kids/family
    "kids activity box subscription",
    "baby essentials subscription box",
    "educational toy subscription",
    # Food (non-supplement)
    "coffee subscription box",
    "tea subscription monthly box",
    "hot sauce subscription box",
    "spice subscription box monthly",
    # Unique/niche
    "mystery box subscription brand",
    "book subscription box niche",
    "vinyl record subscription monthly",
    "puzzle subscription box",
]

# Meta Ad Library search terms for finding subscription advertisers
AD_LIBRARY_SEARCH_TERMS = [
    "subscribe and save",
    "monthly box",
    "subscription box",
    "get yours monthly",
    "delivered monthly",
    "join the club",
    "monthly membership",
    "first box free",
    "cancel anytime",
]

# Exclude these niches (regulated, high-risk, or saturated)
EXCLUDED_NICHES = [
    "supplement", "vitamin", "protein", "probiotic",
    "skincare", "skin care", "anti-aging", "serum", "retinol",
    "cbd", "cannabis", "thc", "hemp",
    "pharma", "medication", "drug",
    "weight loss", "diet pill", "fat burner",
    "crypto", "forex", "trading",
    "gambling", "casino", "betting",
]

# Winning signals — what makes a brand worth cloning
WINNING_SIGNALS = {
    "min_ad_duration_days": 30,        # Ad running 30+ days = likely profitable
    "min_active_ads": 3,               # Multiple active ads = scaling
    "min_ad_variations": 2,            # Testing creatives = serious advertiser
    "subscription_keywords": [         # Must mention subscription somehow
        "subscribe", "subscription", "monthly", "recurring",
        "membership", "club", "box", "delivered every",
        "auto-ship", "replenish", "refill",
    ],
}

# Target countries for ad library search
TARGET_COUNTRIES = ["NL", "BE", "DE", "FR", "GB", "US", "IE", "AT", "DK", "SE"]

# Output directory
OUTPUT_DIR = "scout/output"
