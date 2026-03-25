"""Analyze Meta Ad Library streetwear data for winning products."""
import json
import urllib.request
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

TOKEN = os.getenv("APIFY_TOKEN")
if not TOKEN:
    raise RuntimeError("APIFY_TOKEN not set – add it to .env")
OUTDIR = r'C:\Users\maxku\OneDrive\Bureaublad\competitor creative research (NEWG)\scout\output'

# Check running status
for rid in ['l5kieXSXwKc3H5az7', 'TOHD8jH2u8YugGoZy']:
    url = f'https://api.apify.com/v2/actor-runs/{rid}?token={TOKEN}'
    d = json.loads(urllib.request.urlopen(url).read())['data']
    print(f'{rid}: {d["status"]} ds={d["defaultDatasetId"]}')

# Collect all succeeded datasets
DATASETS = ['ON7LX0ynbfgYAMq7V', '8vJPB3mDyUR84z3oA', 'eWbiOabBW50F8AhGZ', 'hq7dx3GwTWkPwsoGl']
for rid in ['l5kieXSXwKc3H5az7', 'TOHD8jH2u8YugGoZy']:
    d = json.loads(urllib.request.urlopen(f'https://api.apify.com/v2/actor-runs/{rid}?token={TOKEN}').read())['data']
    if d['status'] == 'SUCCEEDED':
        DATASETS.append(d['defaultDatasetId'])

all_ads = []
for ds in DATASETS:
    try:
        url = f'https://api.apify.com/v2/datasets/{ds}/items?token={TOKEN}&format=json'
        data = json.loads(urllib.request.urlopen(url).read())
        all_ads.extend(data)
        print(f'  {ds}: {len(data)} ads')
    except Exception as e:
        print(f'  {ds}: ERROR - {e}')

print(f'\nTotal ads: {len(all_ads)}')

# Big brands to exclude
BIG_BRANDS = [
    'nike', 'adidas', 'puma', 'stussy', 'supreme', 'carhartt', 'champion',
    'ralph lauren', 'tommy hilfiger', 'zara', 'shein', 'asos', 'uniqlo',
    'gap', 'primark', 'boohoo', 'fashion nova', 'prettylittlething',
    'north face', 'patagonia', 'columbia', 'under armour', 'new balance',
    'jordan', 'converse', 'vans', 'timberland', 'guess',
    'amazon', 'walmart', 'target', 'temu', 'wish',
    'gucci', 'balenciaga', 'louis vuitton', 'dior', 'versace', 'prada',
    'burberry', 'off-white', 'fear of god', 'essentials',
    'yeezy', 'palace', 'bape', 'kith', 'vlone', 'canada goose',
    'whatnot', 'stockx', 'grailed', 'depop', 'ebay',
    'foot locker', 'jd sports', 'finish line', 'snipes',
    'h&m', 'pull&bear', 'bershka', 'mango', 'cos',
    'levi', 'wrangler', 'lee jeans', 'diesel', 'g-star',
]

def safe(s):
    return s.encode('ascii', 'replace').decode().replace('\n', ' ')

sellers = {}
for ad in all_ads:
    sn = ad.get('snapshot', {})
    name = sn.get('page_name', 'Unknown')
    if any(b in name.lower() for b in BIG_BRANDS):
        continue

    body = sn.get('body', {})
    text = body.get('text', '') if isinstance(body, dict) else str(body) if body else ''
    cards = sn.get('cards', [])
    card_texts = []
    landing_urls = []
    has_video = False
    ctas = []
    for c in cards:
        card_texts.append(c.get('body', '') or '')
        card_texts.append(c.get('title', '') or '')
        cap = c.get('caption', '')
        if cap and '.' in cap and 'fb.' not in cap:
            landing_urls.append(cap)
        if c.get('video_hd_url') or c.get('video_sd_url'):
            has_video = True
        cta = c.get('cta_text', '')
        if cta:
            ctas.append(cta)

    all_text = (text + ' ' + ' '.join(filter(None, card_texts))).lower()

    if name not in sellers:
        sellers[name] = {
            'name': name, 'count': 0, 'texts': [], 'urls': set(),
            'has_video': False, 'products': set(), 'ctas': []
        }
    sellers[name]['count'] += 1
    if text:
        sellers[name]['texts'].append(text[:400])
    for u in landing_urls:
        sellers[name]['urls'].add(u)
    if has_video:
        sellers[name]['has_video'] = True
    sellers[name]['ctas'].extend(ctas)

    # Detect products
    for kw, prod in [
        ('cargo pants', 'Cargo Pants'), ('cargo', 'Cargo Pants'),
        ('hoodie', 'Hoodie'), ('hoodies', 'Hoodie'),
        ('oversized t', 'Oversized Tee'), ('oversized tee', 'Oversized Tee'),
        ('graphic tee', 'Graphic Tee'), ('graphic t-shirt', 'Graphic Tee'),
        ('jogger', 'Joggers'), ('tracksuit', 'Tracksuit'),
        ('windbreaker', 'Windbreaker'), ('sweatshirt', 'Sweatshirt'),
        ('crewneck', 'Crewneck'), ('jacket', 'Jacket'),
        ('bomber', 'Bomber Jacket'), ('shorts', 'Shorts'),
        ('jeans', 'Jeans'), ('denim', 'Denim'),
        ('jersey', 'Jersey'), ('polo', 'Polo'),
        ('vest', 'Vest'), ('tank top', 'Tank Top'),
    ]:
        if kw in all_text:
            sellers[name]['products'].add(prod)

ranked = sorted(sellers.values(), key=lambda x: x['count'], reverse=True)

print(f'\nSmall streetwear stores: {len(ranked)}')
print('=' * 120)
print(f'{"#":<3} {"Store":<32} {"Ads":>4} {"V":>2} {"Website":<32} Products')
print('-' * 120)

for i, s in enumerate(ranked[:35], 1):
    url = sorted(s['urls'])[0] if s['urls'] else '?'
    prods = ', '.join(sorted(s['products'])[:4]) if s['products'] else '?'
    vid = 'V' if s['has_video'] else ' '
    print(f'{i:<3} {safe(s["name"]):<32} {s["count"]:>4} {vid:>2} {safe(url):<32} {safe(prods)}')

# PRODUCT-LEVEL ANALYSIS
print('\n\n' + '=' * 120)
print('PRODUCT CATEGORIES being actively advertised by small stores')
print('=' * 120)

product_data = {}
for s in ranked:
    for txt in s['texts'][:5]:
        txt_lower = txt.lower()
        for pattern, category in [
            ('cargo pants', 'Cargo Pants'), ('cargo', 'Cargo Pants'),
            ('hoodie', 'Hoodie'), ('oversized hoodie', 'Oversized Hoodie'),
            ('oversized t', 'Oversized Tee'), ('graphic tee', 'Graphic Tee'),
            ('joggers', 'Joggers'), ('tracksuit', 'Tracksuit'),
            ('windbreaker', 'Windbreaker'), ('sweatshirt', 'Sweatshirt'),
            ('jacket', 'Jacket'), ('bomber jacket', 'Bomber Jacket'),
            ('shorts', 'Shorts'), ('jeans', 'Jeans'),
            ('jersey', 'Jersey'), ('polo', 'Polo'),
        ]:
            if pattern in txt_lower:
                if category not in product_data:
                    product_data[category] = {'mentions': 0, 'stores': set(), 'samples': []}
                product_data[category]['mentions'] += 1
                product_data[category]['stores'].add(s['name'])
                if len(product_data[category]['samples']) < 3:
                    product_data[category]['samples'].append(safe(txt[:200]))

print(f'\n{"Product":<25} {"Mentions":>9} {"Stores":>7}  Top Ad Text')
print('-' * 120)
for cat, data in sorted(product_data.items(), key=lambda x: x[1]['mentions'], reverse=True):
    sample = data['samples'][0][:80] if data['samples'] else ''
    print(f'{cat:<25} {data["mentions"]:>9} {len(data["stores"]):>7}  {sample}')

# WINNING PRODUCT EXTRACTION
print('\n\n' + '=' * 120)
print('WINNING PRODUCTS: Specific items being scaled by small dropshippers')
print('=' * 120)

for i, s in enumerate(ranked[:15], 1):
    if s['count'] < 2:
        continue
    url = sorted(s['urls'])[0] if s['urls'] else '?'
    prods = ', '.join(sorted(s['products'])[:4]) if s['products'] else '?'
    print(f'\n--- #{i} {safe(s["name"])} ({s["count"]} ads) | {safe(url)} ---')
    print(f'    Products: {safe(prods)}')
    print(f'    Video ads: {"Yes" if s["has_video"] else "No"}')
    for j, txt in enumerate(s['texts'][:3]):
        print(f'    Ad {j+1}: {safe(txt[:250])}')

# Save
output = {
    'total_ads': len(all_ads),
    'small_stores': len(ranked),
    'top_stores': [],
    'product_categories': {}
}
for s in ranked[:35]:
    output['top_stores'].append({
        'name': s['name'],
        'num_ads': s['count'],
        'website': sorted(s['urls'])[0] if s['urls'] else '',
        'products': sorted(s['products']),
        'has_video': s['has_video'],
        'sample_text': s['texts'][0][:300] if s['texts'] else ''
    })
for cat, data in product_data.items():
    output['product_categories'][cat] = {
        'mentions': data['mentions'],
        'num_stores': len(data['stores']),
        'sample': data['samples'][0][:200] if data['samples'] else ''
    }

outpath = os.path.join(OUTDIR, 'streetwear_meta_ads_20260322.json')
with open(outpath, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f'\nSaved to {outpath}')
