"""Generate NEWGARMENTS competitor report from PiPiAds data."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = Path(__file__).parent / "pipiads_data"
data = json.load(open(DATA_DIR / "pipiads_v2_FINAL_20260312_0425.json", encoding="utf-8"))
ads = [a for a in data["api_captured_ads"] if a.get("ad_id") and a.get("desc")]
ads.sort(key=lambda a: int(a.get("play_count") or 0), reverse=True)

sw_kw = ["streetwear","hoodie","oversized","heavyweight","baggy","archive","drop",
         "limited","tee","crewneck","cargo","fashion","brand"]

def is_sw(a):
    text = f"{a.get('desc','')} {a.get('ai_analysis_main_hook','')} {a.get('ai_analysis_script','')}".lower()
    return any(k in text for k in sw_kw)

sw_ads = [a for a in ads if is_sw(a)]

def fmt(v):
    if v >= 1e6: return f"{v/1e6:.1f}M"
    if v >= 1e3: return f"{v/1e3:.0f}K"
    return str(v)

# Regions
regions = Counter()
for a in ads:
    for r in re.findall(r"'(\w{2})'", str(a.get("fetch_region",""))):
        regions[r] += 1

# CTAs
ctas = Counter(a.get("button_text","") for a in ads if a.get("button_text"))

# Shops
shops = Counter(str(a.get("shop_type","")) for a in ads if a.get("shop_type"))

# Hooks
hooks = [(a.get("ai_analysis_main_hook",""), a) for a in ads
         if a.get("ai_analysis_main_hook") and a.get("ai_analysis_main_hook") != "null"]
hooks.sort(key=lambda x: int(x[1].get("play_count") or 0), reverse=True)

categories = {
    "Scarcity/Urgency": ["limited","sold","last","hurry","gone","miss","only","drop"],
    "Quality/Material": ["heavy","quality","premium","thick","weight","fabric","built","gsm"],
    "Identity/Style": ["style","fit","look","outfit","wear","fashion","fire","hard"],
    "Question/Curiosity": ["how","why","what","would","know","secret","ever"],
    "Social Proof": ["everyone","trending","viral","best","favorite","popular"],
    "Price/Value": ["free","sale","discount","off","save","price","deal"],
}

proven = [a for a in sw_ads if int(a.get("put_days") or 0) > 30]
proven.sort(key=lambda a: int(a.get("put_days") or 0), reverse=True)

qual_count = len([h for h,a in hooks if any(k in h.lower() for k in ["heavy","quality","premium","thick","weight","fabric","built"])])
scar_count = len([h for h,a in hooks if any(k in h.lower() for k in ["limited","sold","last","hurry","gone","miss","drop"])])

# --- BUILD REPORT ---
R = []
R.append("# NEWGARMENTS - PiPiAds Competitor Research Report\n")
R.append(f"**Date:** 2026-03-12  ")
R.append(f"**Total Ads Analyzed:** {len(ads)}  ")
R.append(f"**Streetwear-Relevant Ads:** {len(sw_ads)}  ")
R.append(f"**Keywords Searched:** streetwear, oversized hoodie, heavyweight hoodie, streetwear brand, baggy jeans, archive fashion, oversized tee, streetwear drop, limited drop clothing, mens streetwear  ")
R.append(f"**Filters Applied:** TikTok, Dropshipping, Shopify\n")

# --- REGION ---
R.append("---\n\n## Region Breakdown\n")
for r, c in regions.most_common(15):
    R.append(f"- **{r}:** {c} ads")

# --- CTA ---
R.append("\n## CTA Buttons Used\n")
for ct, c in ctas.most_common(10):
    R.append(f"- **{ct}:** {c} ads ({c*100//len(ads)}%)")

# --- SHOP ---
R.append("\n## Shop Platforms\n")
for s, c in shops.most_common():
    R.append(f"- **{s}:** {c} ads")

# --- TOP 25 ---
R.append("\n---\n\n## Top 25 Streetwear Competitor Ads (by views)\n")
for i, a in enumerate(sw_ads[:25], 1):
    views = int(a.get("play_count") or 0)
    likes = int(a.get("digg_count") or 0)
    days = int(a.get("put_days") or 0)
    name = a.get("unique_id") or a.get("app_name") or "?"
    hook = a.get("ai_analysis_main_hook") or ""
    desc = (a.get("desc") or "")[:200]
    script = (a.get("ai_analysis_script") or "")[:300]
    cta_t = a.get("button_text") or ""
    video = a.get("video_url") or ""
    region_t = str(a.get("fetch_region",""))
    cpm = float(a.get("min_cpm") or 0)
    shop_t = a.get("shop_type") or ""

    R.append(f"### {i}. {name}")
    R.append(f"- **Views:** {fmt(views)} | **Likes:** {likes:,} | **Days Running:** {days} | **CTA:** {cta_t}")
    R.append(f"- **CPM:** ${cpm:.0f} | **Region:** {region_t} | **Platform:** {shop_t}")
    if hook and hook != "null":
        R.append(f"- **Hook:** {hook}")
    R.append(f"- **Caption:** {desc}")
    if script and script != "null":
        R.append(f"- **Script:** {script}")
    if video:
        R.append(f"- **Video:** {video}")
    R.append("")

# --- PROVEN WINNERS ---
R.append("---\n\n## Proven Winners (30+ days running = validated by ad spend)\n")
for i, a in enumerate(proven[:15], 1):
    name = a.get("unique_id") or a.get("app_name") or "?"
    days = int(a.get("put_days") or 0)
    views = int(a.get("play_count") or 0)
    hook = a.get("ai_analysis_main_hook") or a.get("desc","")
    if hook == "null": hook = a.get("desc","")
    R.append(f'{i}. **{name}** - {days} days, {fmt(views)} views - "{hook[:80]}"')
R.append("")

# --- HOOK ANALYSIS ---
R.append("---\n\n## Hook Analysis (AI-extracted)\n")
for cat, keywords in categories.items():
    matching = [(h,a) for h,a in hooks if any(k in h.lower() for k in keywords)]
    if matching:
        R.append(f"### {cat} ({len(matching)} hooks)\n")
        for h, a in matching[:5]:
            v = int(a.get("play_count") or 0)
            name = a.get("unique_id") or "?"
            R.append(f'- "{h}" - {name}, {fmt(v)} views')
        R.append("")

# --- NG INSIGHTS ---
R.append("---\n\n## NEWGARMENTS Strategic Insights\n")

R.append("### 1. HEAVYWEIGHT/QUALITY = OPEN WHITESPACE")
R.append(f"Only **{qual_count} out of {len(hooks)} hooks** lead with quality/material. Most competitors use identity/style hooks. NG should lead with fabric weight, GSM closeups, and \"built to last\" messaging. This is your biggest competitive gap.\n")

R.append("### 2. SCARCITY IS UNDERUSED")
R.append(f"Only **{scar_count} hooks** use scarcity/urgency. NG's real \"no restock\" model is a genuine differentiator vs competitors who fake it.\n")

R.append("### 3. REGION OPPORTUNITY")
R.append(f"US is saturated ({regions.get('US',0)} ads). **UK ({regions.get('GB',0)}), Germany ({regions.get('DE',0)}), France ({regions.get('FR',0)}), Netherlands ({regions.get('NL',0)})** have much less competition. Target EU harder.\n")

R.append("### 4. CTA DIFFERENTIATION")
R.append(f"\"Shop now\" dominates ({ctas.get('Shop now',0)} ads). NG should use urgency CTAs: **\"Cop before it's gone\"**, **\"Secure yours\"**, **\"Join the archive\"**.\n")

R.append("### 5. HOOKS TO ADAPT FOR NG")
R.append('- "the perfect blank hoodie under $100" -> **"the heavyweight hoodie they\'ll ask about"**')
R.append('- "POV: you found the HEAVYWEIGHT hoodie of your dreams" -> **"POV: archive streetwear that never restocks"**')
R.append('- "hardest tee in the market" -> **"hardest drop this year. 200 pieces. gone forever."**')
R.append('- "Would you wear this tee?" -> **"only 3% will cop this before it\'s gone"**\n')

R.append("### 6. PROVEN AD FORMATS")
R.append(f"**{len(proven)} streetwear ads** running 30+ days = validated by real spend. Study their video format, not just copy.\n")

R.append("### 7. VIDEO URLS")
R.append(f"All {len([a for a in ads if a.get('video_url')])} competitor video URLs are saved in `pipiads_data/` - download and study the top performers' creative formats.\n")

report = "\n".join(R)
out = Path(__file__).parent / "PIPIADS_COMPETITOR_REPORT.md"
out.write_text(report, encoding="utf-8")
print(f"Report written: {len(R)} lines -> {out.name}")
