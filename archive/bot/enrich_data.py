"""Post-process competitor data: add explanations for every score and NEWGARMENTS analysis."""
import json
import os
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# Non-brand entries to filter out (blog articles, magazines, listicles)
NON_BRAND_NAMES = {
    "Top 17 streetwear brands in 2026",
    "Top 11 Streetwear Brands for 2025",
    "17 Premium African and Black",
    "7 Black",
    "Gq-Magazine",
    "Modaknits",
    "Fashionweekonline",
    "Goatagency",
    "The Instagram It",
    "Modash",
    "TikTok",
    "Apetogentleman",
    "Aoguactivewear",
    "Mexess",
    "Huntersandhounds",
    "Essential Super Heavyweight Hoodie",
}


def generate_score_explanations(comp: dict) -> dict:
    """Generate human-readable explanations for each score dimension."""
    scores = comp.get("scores", {})
    wa = comp.get("website_analysis", {})
    meta = comp.get("meta_ads", {})
    name = comp.get("name", "Unknown")
    explanations = {}

    # 1. Audience Overlap
    ao = scores.get("audience_overlap", 0)
    if ao >= 7:
        explanations["audience_overlap"] = (
            f"High ({ao}/10). {name} strongly targets the same Gen Z streetwear audience as NEWGARMENTS. "
            f"Their website content contains many references to streetwear culture, limited drops, heavyweight quality, "
            f"and youth/urban culture — all core NEWGARMENTS audience signals."
        )
    elif ao >= 4:
        explanations["audience_overlap"] = (
            f"Moderate ({ao}/10). {name} partially overlaps with the NEWGARMENTS target audience. "
            f"Some streetwear and youth culture signals are present, but the brand either targets a broader "
            f"demographic or focuses on a slightly different niche within streetwear."
        )
    else:
        explanations["audience_overlap"] = (
            f"Low ({ao}/10). {name} has limited audience overlap with NEWGARMENTS. "
            f"The brand's messaging and content don't strongly signal the Gen Z streetwear, limited-drop, "
            f"heavyweight quality positioning that defines NEWGARMENTS' core audience."
        )

    # 2. Aesthetic Similarity
    ae = scores.get("aesthetic_similarity", 0)
    if ae >= 5:
        explanations["aesthetic_similarity"] = (
            f"Notable ({ae}/10). {name} shares clear aesthetic DNA with NEWGARMENTS — references to archive, "
            f"vintage, oversized/boxy cuts, heavyweight fabrics, or minimalist/dark tones were detected. "
            f"This brand visually competes in the same space."
        )
    elif ae >= 2:
        explanations["aesthetic_similarity"] = (
            f"Some overlap ({ae}/10). {name} shows a few aesthetic similarities (e.g. oversized fits, "
            f"streetwear silhouettes), but the overall visual identity diverges from NEWGARMENTS' clean, "
            f"heavyweight, minimalist approach."
        )
    else:
        explanations["aesthetic_similarity"] = (
            f"Low ({ae}/10). {name}'s visual aesthetic doesn't closely match NEWGARMENTS. "
            f"No strong signals for archive, heavyweight, boxy, or minimalist design language were detected. "
            f"This doesn't mean they aren't a competitor — their aesthetic may simply not be captured in text."
        )

    # 3. Messaging Similarity
    ms = scores.get("messaging_similarity", 0)
    scarcity = wa.get("scarcity_signals", [])
    hero = wa.get("hero_messaging", "")
    if ms >= 6:
        explanations["messaging_similarity"] = (
            f"Strong match ({ms}/10). {name} uses messaging very similar to NEWGARMENTS: "
            f"scarcity signals like {', '.join(scarcity[:3]) if scarcity else 'limited/exclusive language'}, "
            f"combined with quality-focused and community-driven positioning. "
            f"Hero message: \"{hero[:100]}\"." if hero else
            f"Strong match ({ms}/10). {name} uses messaging very similar to NEWGARMENTS with heavy "
            f"scarcity/exclusivity language ({', '.join(scarcity[:3]) if scarcity else 'limited drops'}) "
            f"and quality positioning."
        )
    elif ms >= 4:
        explanations["messaging_similarity"] = (
            f"Moderate ({ms}/10). {name} shares some messaging themes with NEWGARMENTS — "
            f"{'uses scarcity signals: ' + ', '.join(scarcity[:2]) if scarcity else 'some limited/quality language'}. "
            f"However, the overall brand voice and positioning show differences in tone or focus."
        )
    else:
        explanations["messaging_similarity"] = (
            f"Weak ({ms}/10). {name}'s messaging doesn't strongly align with NEWGARMENTS' core themes "
            f"of scarcity, no-restock, heavyweight quality, and transparent brand building. "
            f"{'No scarcity signals detected.' if not scarcity else f'Only minor signals: {scarcity[0]}.'}"
        )

    # 4. Offer Similarity
    os_score = scores.get("offer_similarity", 0)
    price = wa.get("price_range", "")
    offer_sigs = wa.get("offer_signals", [])
    if os_score >= 7:
        explanations["offer_similarity"] = (
            f"Very similar ({os_score}/10). {name}'s offer structure closely matches NEWGARMENTS: "
            f"{'price range ' + price + ' falls in the ideal mid-tier bracket, ' if price else ''}"
            f"combined with {', '.join(offer_sigs) if offer_sigs else 'scarcity-driven offers'} "
            f"and {', '.join(scarcity[:2]) if scarcity else 'limited availability'}. "
            f"This brand competes directly on offer positioning."
        )
    elif os_score >= 4:
        explanations["offer_similarity"] = (
            f"Moderate ({os_score}/10). {name} has some offer overlap — "
            f"{'price range ' + price + ' is somewhat comparable' if price else 'pricing data not captured'}. "
            f"{'Offers include: ' + ', '.join(offer_sigs) + '.' if offer_sigs else 'Limited offer signals detected.'}"
        )
    else:
        explanations["offer_similarity"] = (
            f"Low ({os_score}/10). {name}'s offer structure differs from NEWGARMENTS. "
            f"{'Price range ' + price + ' is outside the ideal bracket.' if price else 'No pricing data found.'} "
            f"{'No clear offer signals detected.' if not offer_sigs else ''}"
        )

    # 5. Platform Presence
    pp = scores.get("platform_presence", 0)
    has_ig = bool(comp.get("instagram"))
    has_tt = bool(comp.get("tiktok"))
    has_web = bool(comp.get("website"))
    platforms = []
    if has_web: platforms.append("website")
    if has_ig: platforms.append(f"Instagram (@{comp.get('instagram', '')})")
    if has_tt: platforms.append(f"TikTok (@{comp.get('tiktok', '')})")
    if pp >= 8:
        explanations["platform_presence"] = (
            f"Strong ({pp}/10). {name} is present on all key platforms: {', '.join(platforms)}. "
            f"{'Bonus: this brand was mentioned in NEWGARMENTS research documents, confirming proven relevance.' if comp.get('source') == 'document_mention' else ''}"
            f"Full platform coverage means they can reach the same audience through the same channels."
        )
    elif pp >= 5:
        explanations["platform_presence"] = (
            f"Partial ({pp}/10). {name} is active on {', '.join(platforms)}. "
            f"Missing {'TikTok' if not has_tt else 'Instagram' if not has_ig else 'some channels'} "
            f"limits their reach to the full Gen Z streetwear audience."
        )
    else:
        explanations["platform_presence"] = (
            f"Weak ({pp}/10). {name} has limited platform presence ({', '.join(platforms) if platforms else 'minimal'}). "
            f"Without strong social media presence, this brand has less direct competition for NEWGARMENTS' audience attention."
        )

    # 6. Ad Activity
    ad = scores.get("ad_activity", 0)
    has_ads = meta.get("has_active_ads", False)
    ad_count = meta.get("approximate_ad_count", 0)
    ad_themes = meta.get("observed_themes", [])
    ad_summary = meta.get("summary", {})
    ad_platforms = ad_summary.get("platforms_used", [])
    ad_spend = ad_summary.get("spend_range")
    ad_hooks = ad_summary.get("hooks", [])
    if ad >= 7:
        spend_note = f" Estimated spend up to {ad_spend['currency']} {ad_spend['max']}." if ad_spend else ""
        platform_note = f" Active on {', '.join(ad_platforms)}." if ad_platforms else ""
        hook_note = f" Top hook: \"{ad_hooks[0]}\"" if ad_hooks else ""
        explanations["ad_activity"] = (
            f"Active advertiser ({ad}/10). {name} is running Meta ads"
            f"{' (~' + str(ad_count) + ' detected)' if ad_count > 0 else ''} "
            f"with themes including {', '.join(ad_themes) if ad_themes else 'general brand promotion'}."
            f"{platform_note}{spend_note}{hook_note} "
            f"This indicates marketing investment and active audience acquisition — direct competition "
            f"for NEWGARMENTS in paid channels."
        )
    elif ad >= 4:
        platform_note = f" Platforms: {', '.join(ad_platforms)}." if ad_platforms else ""
        explanations["ad_activity"] = (
            f"Some activity ({ad}/10). {name} {'has active Meta ads' if has_ads else 'shows limited ad presence'}. "
            f"{'Themes: ' + ', '.join(ad_themes) + '.' if ad_themes else 'No strong thematic patterns detected in ads.'}"
            f"{platform_note} "
            f"Moderate ad spend suggests the brand is investing in growth but may not be heavily competing on paid."
        )
    else:
        explanations["ad_activity"] = (
            f"Minimal ({ad}/10). {name} shows little to no Meta advertising activity. "
            f"This could mean they rely on organic growth (Instagram/TikTok viral, word-of-mouth, drops hype) "
            f"or simply aren't active in paid acquisition."
        )

    # 7. Website Quality
    wq = scores.get("website_quality", 0)
    trust = wa.get("trust_signals", [])
    has_reviews = wa.get("has_reviews", False)
    has_size = wa.get("has_size_guide", False)
    has_about = wa.get("has_about_page", False)
    email = wa.get("email_capture", False)
    if wq >= 7:
        explanations["website_quality"] = (
            f"High quality ({wq}/10). {name}'s website demonstrates strong e-commerce execution: "
            f"{'reviews visible, ' if has_reviews else ''}"
            f"{'size guide available, ' if has_size else ''}"
            f"{'about/brand story page, ' if has_about else ''}"
            f"{'email capture active, ' if email else ''}"
            f"{'trust signals: ' + ', '.join(trust) + '.' if trust else 'solid trust foundation.'} "
            f"This brand is converting visitors effectively."
        )
    elif wq >= 4:
        explanations["website_quality"] = (
            f"Decent ({wq}/10). {name}'s website has basic e-commerce elements in place. "
            f"{'Has reviews. ' if has_reviews else 'No reviews visible. '}"
            f"{'Has size guide. ' if has_size else 'No size guide found. '}"
            f"{'Has about page. ' if has_about else 'No brand story page. '}"
            f"{'Trust signals: ' + ', '.join(trust) + '.' if trust else 'Limited trust signals.'}"
        )
    else:
        explanations["website_quality"] = (
            f"Basic ({wq}/10). {name}'s website lacks several key conversion elements. "
            f"Missing reviews, size guides, and/or trust signals reduces buyer confidence. "
            f"This is an area where NEWGARMENTS can differentiate."
        )

    # 8. Confidence Level
    cl = scores.get("confidence_level", 0)
    source = comp.get("source", "")
    if cl >= 8:
        explanations["confidence_level"] = (
            f"High confidence ({cl}/10). {'This brand was directly mentioned in NEWGARMENTS research documents, ' if source == 'document_mention' else ''}"
            f"{'identified through targeted niche research, ' if source == 'niche_research' else ''}"
            f"we have solid data across website analysis, social profiles, and ad activity. "
            f"This competitor assessment is reliable."
        )
    elif cl >= 5:
        explanations["confidence_level"] = (
            f"Medium confidence ({cl}/10). Discovered via {'Google search' if source == 'google_search' else source}. "
            f"{'Website was accessible and analyzed. ' if wa.get('accessible') else 'Website data limited. '}"
            f"{'Has social profiles. ' if has_ig or has_tt else 'Social data limited. '}"
            f"Some data points may be incomplete."
        )
    else:
        explanations["confidence_level"] = (
            f"Low confidence ({cl}/10). Limited data available for {name}. "
            f"The competitor may be relevant but we couldn't verify enough signals to be certain. "
            f"Manual verification recommended."
        )

    return explanations


def build_newgarments_analysis() -> dict:
    """Build comprehensive NEWGARMENTS store analysis with optimization recommendations."""
    return {
        "store_url": "https://newgarments.store",
        "platform": "Shopify (Impulse theme v7.4.1)",
        "currency": "EUR",
        "overall_assessment": (
            "NEWGARMENTS.store has a solid foundation with clean design, clear brand messaging, "
            "and good trust signals. However, comparing against top competitors reveals several "
            "optimization opportunities in pricing strategy, scarcity execution, social proof, "
            "and brand differentiation that could significantly improve conversion and positioning."
        ),
        "brand_messaging": {
            "current": {
                "tagline": "Wear the identity",
                "hero": "Clean fit. Heavyweight fabric. Everyday gear designed to last.",
                "about": "Style isn't decoration — it's presence.",
                "unisex": "All our items are Unisex!"
            },
            "strengths": (
                "The 'Wear the identity' tagline is strong and memorable. The emphasis on heavyweight fabric "
                "and lasting quality directly addresses the Gen Z frustration with fast fashion. The about page "
                "clearly rejects trend-chasing, which builds authenticity. The 'no shortcuts, no guesswork' "
                "positioning is exactly what the target audience wants to hear."
            ),
            "weaknesses": (
                "The hero messaging is generic compared to competitors like Corteiz ('RULESTHEWORLD') or "
                "Trapstar who create cultural mystique. 'Clean fit. Heavyweight fabric. Everyday gear designed "
                "to last' reads like product specs, not an emotional hook. The brand lacks a distinctive cultural "
                "narrative or movement identity that makes Corteiz and Broken Planet so magnetic to Gen Z."
            ),
            "recommendations": [
                "Lead with identity/belonging messaging, not product specs. Instead of 'Heavyweight fabric', try something that makes the buyer feel part of something.",
                "Add a bold, polarizing brand statement. Corteiz has 'Rules The World', Trapstar has the street mystique. NEWGARMENTS needs a cultural stance.",
                "The Dutch roots are underutilized. Brands like Daily Paper and Patta leverage their Amsterdam heritage — NEWGARMENTS should too.",
                "Remove 'Everyday gear designed to last' — it sounds like workwear marketing. Replace with something that speaks to identity and belonging."
            ]
        },
        "pricing_analysis": {
            "current_range": "EUR 34.95 - EUR 46.95 (sale prices), EUR 77.95 - EUR 115.95 (original prices)",
            "competitor_comparison": {
                "Corteiz": "GBP 18 - GBP 210 (no discounts, full price always)",
                "Trapstar": "GBP 45 - GBP 275 (rare sales, mostly full price)",
                "Vicinity": "EUR 29.99 - EUR 179.99 (selective sales only)",
                "Represent": "Premium tier, rarely discounts",
                "Cole Buxton": "GBP 80 - GBP 250+ (never discounts)",
                "Scuffers": "EUR 19 - EUR 149 (clean pricing, minimal sales)",
                "Broken Planet": "GBP 40 - GBP 180 (sells out, no need to discount)"
            },
            "critical_issue": (
                "EVERYTHING on NEWGARMENTS.store is marked 'Sale' with 50-60% crossed-out discounts. "
                "Original prices like EUR 115.95 crossed out to EUR 46.95 make the brand look like a discount "
                "outlet, NOT a premium streetwear brand. This directly contradicts the 'no fast fashion' positioning. "
                "Every single top-performing competitor (Corteiz, Trapstar, Cole Buxton, Broken Planet) either "
                "never discounts or does so very selectively. Permanent sales destroy perceived value and trust."
            ),
            "recommendations": [
                "IMMEDIATELY remove all fake crossed-out prices. Set real prices at the sale price level (EUR 35-50) and own that price point honestly.",
                "If the true cost allows, price hoodies at EUR 65-85 without discounts. This matches Scuffers/Vicinity and signals quality.",
                "Never run sitewide permanent sales. Instead, use limited-time drops with full pricing — scarcity creates urgency better than discounts.",
                "The 'BUY 2 GET 30% OFF / BUY 3 GET 40% OFF' bundle offer is aggressive and cheapens the brand. Replace with a simple 'free shipping over EUR 100' or a gift-with-purchase.",
                "Study Corteiz: they price confidently (GBP 130+ for hoodies) and sell out within hours. Price signals quality to Gen Z."
            ]
        },
        "scarcity_and_urgency": {
            "current_signals": [
                "LAST SIZES, ITEM WILL NOT RESTOCK",
                "SELLING FAST labels on all products",
                "This page will be taken down once stock is gone",
                "Expected time the stock will last warning"
            ],
            "assessment": (
                "NEWGARMENTS uses scarcity language but undermines it by applying it to EVERYTHING. "
                "When every item says 'SELLING FAST' and every product is on 'Sale', nothing feels scarce. "
                "Compare to Corteiz where items genuinely sell out and show 'Sold Out' badges, or Trapstar "
                "with their 'Archive Drop' section of past items. Real scarcity > manufactured urgency."
            ),
            "recommendations": [
                "Only label items 'SELLING FAST' when stock is genuinely below 20% — apply it selectively.",
                "Implement actual sold-out states. When items sell out, leave them visible as 'Sold Out' (like Corteiz does). This proves demand.",
                "Create a proper drop model: release collections in small batches, announce drop dates on Instagram/TikTok, and let items sell out naturally.",
                "Add an 'Archive' section showing past drops that are gone forever. This validates the no-restock promise.",
                "Remove 'This page will be taken down once stock is gone' — it reads as desperation, not exclusivity."
            ]
        },
        "trust_signals": {
            "current": [
                "30 Days Money Back Guarantee",
                "24/7 Customer Support",
                "Free Express Shipping worldwide",
                "Branded packaging + handwritten thank-you card"
            ],
            "strengths": (
                "The money-back guarantee and free worldwide shipping are strong. The branded packaging with "
                "handwritten thank-you cards is excellent — this is exactly the kind of personal touch that "
                "creates unboxing content on TikTok and builds loyalty. 24/7 support is ambitious and reassuring."
            ),
            "weaknesses": (
                "No customer reviews visible on the site. This is a major gap — Represent, Vicinity, and other "
                "top competitors display reviews prominently. Gen Z heavily relies on social proof before buying. "
                "Also, the dual address (Netherlands + Hong Kong) may raise questions about product origin/quality."
            ),
            "recommendations": [
                "Add a review system immediately (Judge.me, Loox, or Stamped.io). Even 10-20 genuine reviews with photos massively boost conversion.",
                "Feature UGC (user-generated content) on the homepage — real customers wearing the pieces.",
                "Add a 'Made in...' or 'Designed in Netherlands, manufactured in...' transparency section. The audience values honesty about supply chain.",
                "The handwritten thank-you card is gold for TikTok unboxing content. Actively encourage customers to post unboxing videos with a card insert.",
                "Add order tracking directly on the site (they have 'Track Your Order' which is good — make it more prominent)."
            ]
        },
        "product_presentation": {
            "current_products": "~30+ items across knits, hoodies, jeans, jackets, sweaters",
            "vendors": "Multiple vendors detected (UNOWN LABEL, MyGarments, UNOWNLABEL) — suggests dropshipping or multi-supplier model",
            "critical_issue": (
                "The multiple vendor names (UNOWN LABEL, MyGarments, UNOWNLABEL) visible in the product listings "
                "are a RED FLAG. This suggests the products come from different suppliers and undermines the "
                "'designed to last' brand promise. Top competitors like Corteiz, Trapstar, and Cole Buxton "
                "all manufacture their own products. If NEWGARMENTS is sourcing from suppliers, this needs to "
                "be completely hidden from the customer experience."
            ),
            "product_naming": (
                "Product names like 'Distorted Knit', 'Break Free Knitted Sweater', 'Harajuku Knitted Sweater' "
                "lack brand identity. Compare to Trapstar's 'Trispeed 3000' or Corteiz's distinctive naming. "
                "Products should feel like they belong to a collection with narrative cohesion."
            ),
            "recommendations": [
                "Remove ALL vendor name visibility from the storefront. Every product should show only NEWGARMENTS.",
                "Create collection names with brand identity (e.g. 'Foundation Collection', 'Archive 001', 'Identity Series').",
                "Reduce product count. Having 30+ items all on sale dilutes exclusivity. Better to have 12-15 core pieces at full price that sell out.",
                "Add lifestyle photography showing the clothes on real people. Most product images appear to be standard supplier shots.",
                "Add fabric weight/GSM details prominently — if the brand claims 'heavyweight', prove it with specs (400+ GSM)."
            ]
        },
        "website_ux": {
            "theme": "Shopify Impulse v7.4.1",
            "design": "Black/white with orange accent (#ed4f31), Montserrat + Poppins typography",
            "strengths": (
                "Clean, modern layout. Good use of video backgrounds. Typography is professional. "
                "The category navigation with circular icons works well. Mobile-responsive. "
                "Size chart with cm/inches toggle is a nice touch."
            ),
            "weaknesses": (
                "The homepage feels cluttered with too many sale banners and urgency messages competing for attention. "
                "The 'BUY 2 GET 30% OFF' banner dominates and cheapens the first impression. "
                "Compare to Corteiz's minimal homepage or Cole Buxton's editorial approach — both let the product speak."
            ),
            "recommendations": [
                "Simplify the homepage. Remove the multi-buy discount banner. Lead with a strong brand video or editorial image.",
                "Reduce announcement bar clutter. One clear message (e.g. 'Free Worldwide Shipping') instead of multiple competing offers.",
                "Add a 'Lookbook' or editorial section showing the clothes styled in context. Represent and Cole Buxton excel at this.",
                "Improve the About page — it's decent but could include founder story, brand origin, manufacturing process.",
                "Add a blog/journal section for brand storytelling, behind-the-scenes, and SEO value."
            ]
        },
        "social_media_strategy": {
            "current": "Instagram and Facebook links present. No visible TikTok presence on the site.",
            "critical_gap": (
                "TikTok is the #1 discovery platform for Gen Z streetwear. Every major competitor "
                "(Corteiz, Trapstar, Represent, Scuffers, Vicinity) has active TikTok. NEWGARMENTS "
                "not having TikTok linked on the site is a significant gap. The branded packaging and "
                "handwritten notes are perfect for TikTok unboxing content — this opportunity is being wasted."
            ),
            "recommendations": [
                "Create and actively maintain a TikTok account. Post: behind-the-scenes, fabric close-ups, packing orders, drop announcements.",
                "Seed product to 5-10 micro-influencers (5K-50K followers) in the streetwear niche for organic unboxing content.",
                "Use Instagram for curated brand imagery and TikTok for raw, authentic content.",
                "Create a branded hashtag for customers to use when posting their fits."
            ]
        },
        "competitive_positioning_summary": {
            "where_newgarments_wins": [
                "Free worldwide shipping (not all competitors offer this)",
                "Branded packaging + handwritten card (unique personal touch)",
                "Money-back guarantee clearly stated (many competitors don't)",
                "Size charts with cm/inches (better than most competitors)",
                "Affordable price point accessible to younger Gen Z buyers"
            ],
            "where_newgarments_loses": [
                "Permanent sitewide sales destroy premium perception (Corteiz, Trapstar never discount)",
                "No reviews/social proof (Represent, Vicinity have reviews)",
                "Multiple vendor names visible = perceived dropshipping (top competitors manufacture own)",
                "No TikTok presence (all top competitors are on TikTok)",
                "Generic product naming vs. distinctive brand-specific names",
                "No sold-out items visible = no proof of demand",
                "Too many products at discounted prices vs. small curated drops",
                "Missing cultural narrative/movement identity"
            ],
            "priority_actions": [
                "1. REMOVE all fake crossed-out prices and permanent sales. Set honest pricing.",
                "2. HIDE vendor names. Everything must appear as NEWGARMENTS brand.",
                "3. ADD customer reviews (install Judge.me or Loox).",
                "4. LAUNCH TikTok account and create unboxing-friendly content strategy.",
                "5. REDUCE product count and implement a proper drop model (small batches, sell out, archive).",
                "6. DEVELOP a stronger cultural narrative beyond 'quality basics'.",
                "7. ADD an Archive section showing past sold-out drops.",
                "8. SIMPLIFY homepage — remove multi-buy banners, lead with brand story."
            ]
        }
    }


def enrich_and_export():
    """Read existing data, add explanations, filter non-brands, export."""
    json_path = os.path.join(OUTPUT_DIR, "competitor_analysis.json")
    with open(json_path, "r", encoding="utf-8") as f:
        competitors = json.load(f)

    # Separate brands from non-brands
    brands = []
    non_brands = []
    for comp in competitors:
        if comp["name"] in NON_BRAND_NAMES:
            non_brands.append(comp)
        else:
            brands.append(comp)

    # Re-rank brands only
    for i, comp in enumerate(brands):
        comp["rank"] = i + 1
        comp["score_explanations"] = generate_score_explanations(comp)

    # Build NEWGARMENTS analysis
    ng_analysis = build_newgarments_analysis()

    # Export enriched JSON
    enriched = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "newgarments_store_analysis": ng_analysis,
        "total_brands_analyzed": len(brands),
        "filtered_non_brands": [n["name"] for n in non_brands],
        "competitors": brands,
    }

    enriched_path = os.path.join(OUTPUT_DIR, "competitor_analysis_enriched.json")
    with open(enriched_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False, default=str)
    print(f"Enriched JSON saved: {enriched_path}")

    # Export enriched Markdown report
    md_path = os.path.join(OUTPUT_DIR, "research_report_enriched.md")
    write_enriched_report(brands, ng_analysis, md_path)
    print(f"Enriched report saved: {md_path}")


def write_enriched_report(brands, ng, path):
    """Write the enriched markdown report."""
    L = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    L.append("# NEWGARMENTS Competitor Research Report (Enriched)")
    L.append(f"Generated: {now}\n")

    # ==================== NEWGARMENTS ANALYSIS ====================
    L.append("---")
    L.append("# PART 1: NEWGARMENTS.STORE ANALYSIS & OPTIMIZATIONS\n")
    L.append(f"**Store:** {ng['store_url']}")
    L.append(f"**Platform:** {ng['platform']}")
    L.append(f"**Currency:** {ng['currency']}\n")
    L.append(f"## Overall Assessment\n{ng['overall_assessment']}\n")

    # Brand Messaging
    bm = ng["brand_messaging"]
    L.append("## Brand Messaging\n")
    L.append(f"**Current tagline:** {bm['current']['tagline']}")
    L.append(f"**Hero text:** {bm['current']['hero']}")
    L.append(f"**About page:** {bm['current']['about']}\n")
    L.append(f"**Strengths:** {bm['strengths']}\n")
    L.append(f"**Weaknesses:** {bm['weaknesses']}\n")
    L.append("**Recommendations:**")
    for r in bm["recommendations"]:
        L.append(f"- {r}")
    L.append("")

    # Pricing
    pa = ng["pricing_analysis"]
    L.append("## Pricing Strategy (CRITICAL)\n")
    L.append(f"**Current range:** {pa['current_range']}\n")
    L.append("**Competitor price comparison:**")
    for brand, price in pa["competitor_comparison"].items():
        L.append(f"- **{brand}:** {price}")
    L.append(f"\n**CRITICAL ISSUE:** {pa['critical_issue']}\n")
    L.append("**Recommendations:**")
    for r in pa["recommendations"]:
        L.append(f"- {r}")
    L.append("")

    # Scarcity
    sc = ng["scarcity_and_urgency"]
    L.append("## Scarcity & Urgency\n")
    L.append("**Current signals:**")
    for s in sc["current_signals"]:
        L.append(f"- {s}")
    L.append(f"\n**Assessment:** {sc['assessment']}\n")
    L.append("**Recommendations:**")
    for r in sc["recommendations"]:
        L.append(f"- {r}")
    L.append("")

    # Trust
    ts = ng["trust_signals"]
    L.append("## Trust Signals\n")
    L.append("**Current:**")
    for t in ts["current"]:
        L.append(f"- {t}")
    L.append(f"\n**Strengths:** {ts['strengths']}\n")
    L.append(f"**Weaknesses:** {ts['weaknesses']}\n")
    L.append("**Recommendations:**")
    for r in ts["recommendations"]:
        L.append(f"- {r}")
    L.append("")

    # Products
    pp = ng["product_presentation"]
    L.append("## Product Presentation\n")
    L.append(f"**Products:** {pp['current_products']}")
    L.append(f"**Vendors detected:** {pp['vendors']}\n")
    L.append(f"**CRITICAL ISSUE:** {pp['critical_issue']}\n")
    L.append(f"**Product naming:** {pp['product_naming']}\n")
    L.append("**Recommendations:**")
    for r in pp["recommendations"]:
        L.append(f"- {r}")
    L.append("")

    # UX
    ux = ng["website_ux"]
    L.append("## Website UX\n")
    L.append(f"**Theme:** {ux['theme']}")
    L.append(f"**Design:** {ux['design']}\n")
    L.append(f"**Strengths:** {ux['strengths']}\n")
    L.append(f"**Weaknesses:** {ux['weaknesses']}\n")
    L.append("**Recommendations:**")
    for r in ux["recommendations"]:
        L.append(f"- {r}")
    L.append("")

    # Social
    sm = ng["social_media_strategy"]
    L.append("## Social Media Strategy\n")
    L.append(f"**Current:** {sm['current']}\n")
    L.append(f"**CRITICAL GAP:** {sm['critical_gap']}\n")
    L.append("**Recommendations:**")
    for r in sm["recommendations"]:
        L.append(f"- {r}")
    L.append("")

    # Summary
    cs = ng["competitive_positioning_summary"]
    L.append("## Competitive Positioning Summary\n")
    L.append("**Where NEWGARMENTS wins:**")
    for w in cs["where_newgarments_wins"]:
        L.append(f"- {w}")
    L.append("\n**Where NEWGARMENTS loses:**")
    for l in cs["where_newgarments_loses"]:
        L.append(f"- {l}")
    L.append("\n**Priority actions (in order):**")
    for a in cs["priority_actions"]:
        L.append(f"- {a}")
    L.append("")

    # ==================== COMPETITOR ANALYSIS ====================
    L.append("---")
    L.append("# PART 2: COMPETITOR RANKINGS (Brands Only)\n")
    L.append(f"**Total brands analyzed:** {len(brands)} (non-brand pages like blogs/magazines filtered out)\n")

    # Top table
    L.append("## Rankings\n")
    L.append("| Rank | Brand | Score | Website | IG | TikTok | Ads | Price Range |")
    L.append("|------|-------|-------|---------|-----|--------|-----|-------------|")
    for comp in brands[:25]:
        wa = comp.get("website_analysis", {})
        meta = comp.get("meta_ads", {})
        ads = "Yes" if meta.get("has_active_ads") else "No"
        L.append(
            f"| {comp['rank']} | {comp['name']} | {comp.get('relevance_score', 0)} | "
            f"[link]({comp.get('website', '')}) | "
            f"@{comp.get('instagram', '-')} | @{comp.get('tiktok', '-')} | "
            f"{ads} | {wa.get('price_range', '-')} |"
        )
    L.append("")

    # Detailed analysis with explanations
    L.append("## Detailed Analysis with Score Explanations\n")
    for comp in brands[:15]:
        wa = comp.get("website_analysis", {})
        meta = comp.get("meta_ads", {})
        scores = comp.get("scores", {})
        expl = comp.get("score_explanations", {})

        L.append(f"### {comp['rank']}. {comp['name']}")
        L.append(f"- **Website:** {comp.get('website', 'N/A')}")
        L.append(f"- **Instagram:** @{comp.get('instagram', 'N/A')}")
        L.append(f"- **TikTok:** @{comp.get('tiktok', 'N/A')}")
        L.append(f"- **Overall Score:** {comp.get('relevance_score', 0)}/10")
        L.append(f"- **Source:** {comp.get('source', 'N/A')}")
        L.append(f"- **Price Range:** {wa.get('price_range', 'N/A')}")
        L.append("")

        if wa.get("hero_messaging"):
            L.append(f"**Hero Messaging:** \"{wa['hero_messaging'][:200]}\"")
            L.append("")

        if wa.get("scarcity_signals"):
            L.append(f"**Scarcity Signals:** {', '.join(wa['scarcity_signals'])}")
        if wa.get("trust_signals"):
            L.append(f"**Trust Signals:** {', '.join(wa['trust_signals'])}")
        if wa.get("offer_signals"):
            L.append(f"**Offer Signals:** {', '.join(wa['offer_signals'])}")
        if wa.get("product_categories"):
            L.append(f"**Product Categories:** {', '.join(wa['product_categories'])}")
        L.append("")

        if meta.get("has_active_ads"):
            L.append(f"**Meta Ads:** Active (~{meta.get('approximate_ad_count', '?')} ads)")
            if meta.get("observed_themes"):
                L.append(f"**Ad Themes:** {', '.join(meta['observed_themes'])}")
        else:
            L.append("**Meta Ads:** No active ads found")
        L.append("")

        L.append("**Score Breakdown with Explanations:**\n")
        for key in ["audience_overlap", "aesthetic_similarity", "messaging_similarity",
                     "offer_similarity", "platform_presence", "ad_activity",
                     "website_quality", "confidence_level"]:
            val = scores.get(key, 0)
            explanation = expl.get(key, "No explanation available.")
            L.append(f"**{key.replace('_', ' ').title()}** ({val}/10)")
            L.append(f"> {explanation}\n")

        L.append("---\n")

    # Key observations
    L.append("## Key Observations\n")
    scarcity_count = sum(1 for c in brands if c.get("website_analysis", {}).get("scarcity_signals"))
    review_count = sum(1 for c in brands if c.get("website_analysis", {}).get("has_reviews"))
    size_count = sum(1 for c in brands if c.get("website_analysis", {}).get("has_size_guide"))
    ad_count = sum(1 for c in brands if c.get("meta_ads", {}).get("has_active_ads"))

    L.append(f"- **{scarcity_count}/{len(brands)}** competitors use scarcity messaging")
    L.append(f"- **{review_count}/{len(brands)}** have visible reviews on their site")
    L.append(f"- **{size_count}/{len(brands)}** have size guides")
    L.append(f"- **{ad_count}/{len(brands)}** are running Meta ads")
    L.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    enrich_and_export()
