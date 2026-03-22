"""Deep analysis: WHY people buy + cloneability scoring."""
import json
import os
import re

def has_word(text, words):
    """Check if any word appears as a whole word (not inside other words)."""
    for w in words:
        if re.search(r'\b' + re.escape(w) + r'\b', text):
            return True
    return False

OUTDIR = r"C:\Users\maxku\OneDrive\Bureaublad\competitor creative research (NEWG)\scout\output"

with open(os.path.join(OUTDIR, "apify_all_combined.json"), encoding="utf-8") as f:
    all_ads = json.load(f)

# Collect full text per brand for top brands
TOP_BRANDS = [
    "catbox", "Splendies", "Mrs. Quilty", "Elia Boutique", "SnackCrate",
    "SnackVerse", "My Volley Box", "PowerBuild", "Hooks & Needles",
    "Mystery Tackle Box", "My Cheerleading Box", "Magic of I.", "Wrist Mafia",
    "August. Period.", "Hey Harper", "FairyLoot", "Moonlight Book Box",
    "The Farmhouse", "Iron Decoy", "VetBox", "ScentBox.com",
    "Birdmoss", "Witch Casket", "ShieldBox", "DuraPaw",
    "Foxy Roxy's Supply Co.", "Charley's Boxes", "Forbidden Fiber Co.",
    "Cords Club", "Vettsy"
]

brands = {}
for ad in all_ads:
    sn = ad.get('snapshot', {})
    name = sn.get('page_name', '')
    if name not in TOP_BRANDS:
        continue

    body = sn.get('body', {})
    text = body.get('text', '') if isinstance(body, dict) else str(body) if body else ''
    cards = sn.get('cards', [])

    if name not in brands:
        brands[name] = {'texts': [], 'urls': set(), 'count': 0, 'ctas': []}
    brands[name]['count'] += 1
    if text:
        brands[name]['texts'].append(text)
    for c in cards:
        cap = c.get('caption', '')
        if cap and '.' in cap and 'fb.' not in cap:
            brands[name]['urls'].add(cap)
        cta = c.get('cta_text', '')
        if cta:
            brands[name]['ctas'].append(cta)

# Analyze each brand
print("=" * 120)
print("DEEP ANALYSIS: Top Subscription Brands — Why People Buy + Cloneability")
print("=" * 120)

analyses = []

for name in TOP_BRANDS:
    if name not in brands:
        continue
    data = brands[name]
    all_text = '\n'.join(data['texts']).lower()
    count = data['count']
    url = sorted(data['urls'])[0] if data['urls'] else '?'

    # Detect buying triggers
    triggers = []
    if 'free' in all_text: triggers.append('FREE offer')
    if 'discount' in all_text or '% off' in all_text or 'save' in all_text: triggers.append('Discount/savings')
    if 'exclusive' in all_text: triggers.append('Exclusivity')
    if 'mystery' in all_text or 'surprise' in all_text: triggers.append('Mystery/surprise')
    if 'cancel anytime' in all_text or 'no commitment' in all_text: triggers.append('Low risk')
    if any(w in all_text for w in ['review', 'rated', 'stars', '5/5', '4.7']): triggers.append('Social proof')
    if any(w in all_text for w in ['limited', 'sell out', 'only', 'last chance']): triggers.append('Scarcity/FOMO')
    if 'community' in all_text or 'club' in all_text or 'join' in all_text: triggers.append('Community/belonging')
    if 'gift' in all_text or 'treat' in all_text: triggers.append('Gift/self-treat')
    if 'curated' in all_text or 'handpicked' in all_text: triggers.append('Curated/personalized')
    if 'delivered' in all_text or 'door' in all_text: triggers.append('Convenience')

    # Detect niche type (specific niches first, generic last; use word boundaries)
    niche = "General"
    if has_word(all_text, ['quilt', 'quilting', 'yarn', 'knit', 'knitting', 'crochet', 'stitch', 'sewing', 'needlework', 'fiber']): niche = "Crafts/Hobby"
    elif has_word(all_text, ['fishing', 'tackle', 'lure', 'angling', 'bass', 'trout']): niche = "Fishing"
    elif has_word(all_text, ['decoy', 'hunting', 'hunter', 'outdoor gear']): niche = "Hunting/Outdoor"
    elif has_word(all_text, ['cheerleading', 'cheer', 'volleyball', 'volley']): niche = "Sports"
    elif has_word(all_text, ['undies', 'underwear', 'lingerie', 'panties', 'bra', 'intimates']): niche = "Fashion/Apparel"
    elif has_word(all_text, ['fashion', 'clothing', 'outfit', 'streetwear', 'apparel', 'wardrobe']): niche = "Fashion/Apparel"
    elif has_word(all_text, ['jewelry', 'bracelet', 'necklace', 'earring', 'ring', 'accessory', 'accessories']): niche = "Jewelry/Accessories"
    elif has_word(all_text, ['fragrance', 'perfume', 'scent', 'cologne', 'eau de']): niche = "Fragrance"
    elif has_word(all_text, ['crystal', 'spiritual', 'witch', 'witchcraft', 'moon', 'tarot', 'ritual']): niche = "Spiritual/Wellness"
    elif has_word(all_text, ['dog', 'puppy', 'pet', 'paw', 'chew', 'kitten', 'feline', 'cats', 'cat box']): niche = "Pets"
    elif has_word(all_text, ['snack', 'candy', 'chocolate', 'yum', 'taste', 'food box', 'international snack']): niche = "Food/Snacks"
    elif has_word(all_text, ['book', 'reading', 'novel', 'fantasy', 'romantasy', 'author']): niche = "Books"
    elif has_word(all_text, ['gaming', 'gamer', 'console', 'controller', 'esports']): niche = "Gaming"
    elif has_word(all_text, ['building', 'brick', 'lego', 'model kit', 'construct']): niche = "Building/Collectibles"
    elif has_word(all_text, ['farmhouse', 'home decor', 'seasonal decor', 'rustic']): niche = "Home Decor"
    elif has_word(all_text, ['grooming', 'beard', 'shave', 'barber']): niche = "Grooming"
    elif has_word(all_text, ['period', 'menstrual', 'tampon', 'pad']): niche = "Period Care"
    elif has_word(all_text, ['nail', 'manicure', 'nail art', 'gel polish']): niche = "Nails/Beauty"
    elif has_word(all_text, ['baby', 'toddler', 'kid', 'child']): niche = "Kids/Baby"
    elif has_word(all_text, ['tactical', 'law enforcement', 'police']): niche = "Tactical/LEO"

    # Cloneability score (1-10)
    clone_score = 5  # base
    # Easy to source products?
    if niche in ["Pets", "Jewelry/Accessories", "Spiritual/Wellness", "Home Decor", "Grooming"]:
        clone_score += 2  # cheap sourcing from China
    if niche in ["Food/Snacks", "Books"]:
        clone_score += 1  # moderate sourcing
    if niche in ["Fashion/Apparel"]:
        clone_score += 2  # bulk fashion is cheap
    if niche in ["Crafts/Hobby", "Sports"]:
        clone_score += 1
    if niche in ["Tactical/LEO", "Period Care"]:
        clone_score -= 1  # harder/regulated

    # Is the model simple?
    if 'mystery' in all_text or 'surprise' in all_text:
        clone_score += 1  # mystery = no need for exact products
    if count >= 10:
        clone_score += 1  # proven demand

    # Low barrier to entry?
    if any(w in all_text for w in ['handmade', 'artisan', 'craft']):
        clone_score -= 1  # harder to replicate quality

    clone_score = min(10, max(1, clone_score))

    # Why people buy (narrative)
    sample = data['texts'][0][:250].encode('ascii', 'replace').decode().replace('\n', ' ') if data['texts'] else ''

    analyses.append({
        'name': name,
        'url': url,
        'niche': niche,
        'num_ads': count,
        'triggers': triggers,
        'clone_score': clone_score,
        'sample': sample,
    })

# Sort by clone_score * num_ads
analyses.sort(key=lambda x: (x['clone_score'], x['num_ads']), reverse=True)

for i, a in enumerate(analyses, 1):
    triggers_str = ', '.join(a['triggers'][:5])
    print(f"\n{'='*100}")
    print(f"#{i} {a['name']} | {a['niche']} | {a['num_ads']} ads | Cloneability: {'*' * a['clone_score']} ({a['clone_score']}/10)")
    print(f"   Website: {a['url']}")
    print(f"   Buy triggers: {triggers_str}")
    print(f"   Sample ad: {a['sample'][:200]}")

    # WHY people buy
    why = []
    if 'Mystery/surprise' in a['triggers']:
        why.append("DOPAMINE: Mystery/surprise element creates excitement & anticipation")
    if 'Exclusivity' in a['triggers']:
        why.append("STATUS: Exclusive items not available elsewhere")
    if 'Community/belonging' in a['triggers']:
        why.append("BELONGING: Part of a club/community")
    if 'Convenience' in a['triggers']:
        why.append("LAZY TAX: Products delivered without effort")
    if 'FREE offer' in a['triggers']:
        why.append("RISK REMOVAL: Free first box lowers barrier")
    if 'Gift/self-treat' in a['triggers']:
        why.append("SELF-CARE: Treat yourself mentality")
    if 'Curated/personalized' in a['triggers']:
        why.append("TRUST: Expert picks > own choice paralysis")
    if not why:
        why.append("CONVENIENCE + DISCOVERY: Regular delivery of new products")

    for w in why:
        print(f"   >> {w}")

    # How to clone
    if a['clone_score'] >= 8:
        print(f"   CLONE: EASY - Source products from AliExpress/1688, brand it, ship it")
    elif a['clone_score'] >= 6:
        print(f"   CLONE: MODERATE - Need some product knowledge/curation but doable")
    else:
        print(f"   CLONE: HARDER - Requires specific expertise or regulated products")

# Save analysis
with open(os.path.join(OUTDIR, "deep_analysis_20260322.json"), "w", encoding="utf-8") as f:
    json.dump(analyses, f, indent=2, ensure_ascii=False)

print(f"\n\n{'='*100}")
print("SUMMARY: Easiest to clone + highest scaling potential")
print("="*100)
easy = [a for a in analyses if a['clone_score'] >= 7]
for a in easy:
    print(f"  {a['clone_score']}/10 | {a['num_ads']:>3} ads | {a['name']:<30} | {a['niche']}")
