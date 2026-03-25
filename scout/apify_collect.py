"""Collect and analyze Apify Meta Ad Library results."""
import json
import urllib.request
import os
import sys

TOKEN = os.getenv("APIFY_TOKEN")
if not TOKEN:
    raise RuntimeError("APIFY_TOKEN not set – add it to .env")
OUTDIR = r"C:\Users\maxku\OneDrive\Bureaublad\competitor creative research (NEWG)\scout\output"

# All run IDs (batch 1 + batch 2)
BATCH1_RUNS = ["hvvbUrq9VYgen9SZG", "Xe1hsS3OQ6d31BYHW", "CjeKNiqIVXL61VCJI", "JZx3jbu4YwUzZfvgF", "UVbausXovuj9oGjpc"]
BATCH2_RUNS = ["hHEiTY4hhorTIQgc8", "Vtq7X6bAcezVvYTT6", "yCs3bC4nNHe4ZIRSF", "PQ1gfh1Cuw2PM9ghH", "iC8XbF0UlhwXKHmeG",
               "hZTD522KpcvfRghGs", "ZaSEqZqHWGNVgSYZE", "pLpF7MBko904cypJM", "1ScxeQdC4tfuIdRVf", "oKwLwsPnsB49lB0x5"]

ALL_RUNS = BATCH1_RUNS + BATCH2_RUNS

def api_get(path):
    url = f"https://api.apify.com/v2/{path}?token={TOKEN}"
    return json.loads(urllib.request.urlopen(url).read())

def check_runs():
    """Check status of all runs."""
    print("=== RUN STATUS ===")
    total_cost = 0
    dataset_ids = []
    for rid in ALL_RUNS:
        try:
            d = api_get(f"actor-runs/{rid}")["data"]
            cost = d.get("usageTotalUsd", 0)
            total_cost += cost
            ds = d["defaultDatasetId"]
            dataset_ids.append(ds)
            print(f"  {rid}: {d['status']} | ${cost:.3f} | ds={ds}")
        except Exception as e:
            print(f"  {rid}: ERROR - {e}")
    print(f"\nTotal cost: ${total_cost:.3f}")
    return dataset_ids

def download_all(dataset_ids):
    """Download all datasets and combine."""
    all_ads = []
    # Also load existing batch 1 data
    existing = os.path.join(OUTDIR, "apify_raw_combined.json")
    if os.path.exists(existing):
        with open(existing, encoding="utf-8") as f:
            all_ads = json.load(f)
        print(f"Loaded {len(all_ads)} existing ads from batch 1")

    # Download batch 2 datasets
    for ds_id in dataset_ids[len(BATCH1_RUNS):]:  # Only new ones
        try:
            url = f"https://api.apify.com/v2/datasets/{ds_id}/items?token={TOKEN}&format=json"
            data = json.loads(urllib.request.urlopen(url).read())
            all_ads.extend(data)
            print(f"  Downloaded {len(data)} ads from {ds_id}")
        except Exception as e:
            print(f"  Error downloading {ds_id}: {e}")

    # Save combined
    outpath = os.path.join(OUTDIR, "apify_all_combined.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(all_ads, f, ensure_ascii=False)
    print(f"\nTotal: {len(all_ads)} ads saved to {outpath}")
    return all_ads

def analyze(all_ads):
    """Deep analysis of subscription brands."""
    from urllib.parse import urlparse

    sub_kw = ['subscri', 'monthly', 'membership', 'club', 'box', 'delivered every',
              'cancel anytime', 'first box', 'recurring', 'delivered to your door',
              'every month', 'auto-ship', 'replenish']

    excluded = ['supplement', 'vitamin', 'protein', 'probiotic', 'skincare', 'skin care',
                'anti-aging', 'serum', 'retinol', 'cbd', 'cannabis', 'pharma', 'medication',
                'weight loss', 'diet pill', 'fat burner', 'crypto', 'forex', 'trading',
                'gambling', 'casino', 'betting', 'insurance', 'mortgage', 'loan',
                'political', 'campaign', 'democrat', 'republican']

    brands = {}
    for ad in all_ads:
        sn = ad.get('snapshot', {})
        name = sn.get('page_name', 'Unknown')

        # Get all text
        body = sn.get('body', {})
        text = body.get('text', '') if isinstance(body, dict) else str(body) if body else ''
        cards = sn.get('cards', [])
        card_texts = []
        landing_urls = []
        for c in cards:
            card_texts.append(c.get('body', ''))
            card_texts.append(c.get('title', ''))
            card_texts.append(c.get('link_description', ''))
            cap = c.get('caption', '')
            if cap and '.' in cap and 'fb.' not in cap:
                landing_urls.append(cap)
            url = c.get('link_url', '')
            if url and 'facebook' not in url:
                try:
                    domain = urlparse(url).netloc
                    if domain.startswith('www.'): domain = domain[4:]
                    if domain: landing_urls.append(domain)
                except: pass

        all_text = (text + ' ' + ' '.join(filter(None, card_texts))).lower()

        # Skip excluded
        if any(ex in all_text for ex in excluded) or any(ex in name.lower() for ex in excluded):
            continue

        if name not in brands:
            brands[name] = {
                'name': name,
                'page_url': sn.get('page_profile_uri', ''),
                'ads': [],
                'all_texts': [],
                'landing_urls': set(),
                'sub_signals': 0,
                'media_types': {'video': 0, 'image': 0},
                'start_dates': [],
            }

        brands[name]['ads'].append(ad.get('ad_archive_id', ''))
        if text:
            brands[name]['all_texts'].append(text[:300])
        for u in landing_urls:
            brands[name]['landing_urls'].add(u)

        if any(kw in all_text for kw in sub_kw):
            brands[name]['sub_signals'] += 1

        # Check media type
        for c in cards:
            if c.get('video_hd_url') or c.get('video_sd_url'):
                brands[name]['media_types']['video'] += 1
            elif c.get('original_image_url'):
                brands[name]['media_types']['image'] += 1

        # Start date
        start = ad.get('start_date')
        if start:
            brands[name]['start_dates'].append(start)

    # Score and rank
    results = []
    for name, data in brands.items():
        num_ads = len(data['ads'])
        if num_ads < 2 or data['sub_signals'] == 0:
            continue

        sub_ratio = data['sub_signals'] / num_ads

        # SCORING
        score = 0
        # Ad volume (max 40) - THIS IS THE SCALING SIGNAL
        if num_ads >= 50: score += 40
        elif num_ads >= 20: score += 35
        elif num_ads >= 10: score += 30
        elif num_ads >= 5: score += 22
        elif num_ads >= 3: score += 15
        else: score += 8

        # Sub signal ratio (max 25)
        if sub_ratio >= 0.8: score += 25
        elif sub_ratio >= 0.5: score += 20
        elif sub_ratio >= 0.3: score += 15
        else: score += 10

        # Has website (max 15)
        if data['landing_urls']:
            score += 15

        # Not mega brand (max 10)
        mega = ['amazon', 'walmart', 'target', 'costco', 'nike', 'klarna', 'doordash']
        if not any(m in name.lower() for m in mega):
            score += 10

        # Video ads (scaling signal, max 10)
        if data['media_types']['video'] >= 3:
            score += 10
        elif data['media_types']['video'] >= 1:
            score += 5

        website = sorted(data['landing_urls'])[0] if data['landing_urls'] else ''

        results.append({
            'name': name,
            'website': website,
            'page_url': data['page_url'],
            'num_ads': num_ads,
            'sub_signals': data['sub_signals'],
            'sub_ratio': round(sub_ratio, 2),
            'score': score,
            'videos': data['media_types']['video'],
            'images': data['media_types']['image'],
            'sample_text': data['all_texts'][0][:300] if data['all_texts'] else '',
        })

    results.sort(key=lambda x: (x['score'], x['num_ads']), reverse=True)

    # Print results
    print("\n" + "="*110)
    print("TOP SCALING SUBSCRIPTION BRANDS — Ranked by ad volume + signals")
    print("="*110)
    print(f"{'#':<3} {'Brand':<30} {'Ads':>4} {'Sub%':>5} {'Vid':>4} {'Score':>5} | {'Website':<35} | Sample")
    print("-"*110)

    for i, r in enumerate(results[:40], 1):
        sample = r['sample_text'][:80].encode('ascii', 'replace').decode().replace('\n', ' ')
        print(f"{i:<3} {r['name']:<30} {r['num_ads']:>4} {r['sub_ratio']*100:>4.0f}% {r['videos']:>4} {r['score']:>5} | {r['website']:<35} | {sample}")

    # Save
    output = {
        'generated_at': '2026-03-22',
        'total_ads': len(all_ads),
        'unique_brands': len(brands),
        'subscription_brands': len(results),
        'top_opportunities': results[:40],
    }
    outpath = os.path.join(OUTDIR, "apify_ranked_20260322.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {outpath}")

    return results

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd in ("check", "all"):
        ds_ids = check_runs()

    if cmd in ("download", "all"):
        if cmd == "download":
            ds_ids = check_runs()
        all_ads = download_all(ds_ids)

    if cmd in ("analyze", "all"):
        if cmd == "analyze":
            path = os.path.join(OUTDIR, "apify_all_combined.json")
            with open(path, encoding="utf-8") as f:
                all_ads = json.load(f)
        analyze(all_ads)
