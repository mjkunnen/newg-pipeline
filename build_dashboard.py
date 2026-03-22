"""Build a self-contained HTML dashboard with processed ad data."""
import json
from pathlib import Path

data = json.load(open(Path(__file__).parent / "pipiads_data" / "pipiads_FILTERED_EUUS.json", encoding="utf-8"))
ads = [a for a in data["api_captured_ads"] if a.get("ad_id") and a.get("desc")]

# Process into minimal clean records
clean = []
sw_kw = ["streetwear","hoodie","oversized","heavyweight","baggy","archive","drop",
         "limited","tee","crewneck","cargo","fashion","brand"]

for a in ads:
    text = f"{a.get('desc','')} {a.get('ai_analysis_main_hook','')} {a.get('ai_analysis_script','')}".lower()
    is_sw = any(k in text for k in sw_kw)
    views = int(a.get("play_count") or 0)
    likes = int(a.get("digg_count") or 0)
    comments = int(a.get("comment_count") or 0)
    shares = int(a.get("share_count") or 0)
    days = int(a.get("put_days") or 0)
    cpm = float(a.get("min_cpm") or 0)
    import re
    regions = re.findall(r"'(\w{2})'", str(a.get("fetch_region","")))

    clean.append({
        "id": a.get("ad_id",""),
        "vid": a.get("video_id",""),
        "name": a.get("unique_id") or a.get("app_name") or "Unknown",
        "desc": (a.get("desc") or "")[:250],
        "hook": a.get("ai_analysis_main_hook") or "",
        "script": (a.get("ai_analysis_script") or "")[:350],
        "tags": a.get("ai_analysis_tags") or "",
        "cta": a.get("button_text") or "",
        "cover": a.get("cover") or "",
        "video": a.get("video_url") or "",
        "shop": a.get("shop_type") or "",
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "days": days,
        "cpm": round(cpm),
        "regions": regions,
        "sw": is_sw,
        "human": a.get("ai_analysis_human_presenter") or "",
        "dur": int(a.get("duration") or 0),
    })

js_data = json.dumps(clean, ensure_ascii=True)
print(f"Processed {len(clean)} ads, data size: {len(js_data)//1024}KB")

# Read HTML template and inject data
html_path = Path(__file__).parent / "pipiads-dashboard.html"
html_template = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>NEWGARMENTS - Competitor Intel Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#09090b;--card:#141416;--card2:#1a1a1e;--brd:#252529;--txt:#e4e4e7;--dim:#71717a;--grn:#22c55e;--blu:#3b82f6;--prp:#a855f7;--org:#f59e0b;--red:#ef4444;--cyan:#06b6d4}
body{background:var(--bg);color:var(--txt);font-family:-apple-system,Inter,sans-serif;font-size:14px}
a{color:var(--blu);text-decoration:none}a:hover{text-decoration:underline}

.top{background:#111113;border-bottom:1px solid var(--brd);padding:14px 28px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.top h1{font-size:17px;letter-spacing:.5px}.top h1 b{color:var(--grn)}
.st{display:flex;gap:20px;font-size:12px;color:var(--dim)}.st strong{color:var(--txt);font-size:14px;display:block}

.tabs{display:flex;background:#111113;border-bottom:1px solid var(--brd);padding:0 28px;position:sticky;top:49px;z-index:99}
.tb{padding:11px 20px;font-size:12px;font-weight:600;cursor:pointer;color:var(--dim);border-bottom:2px solid transparent;transition:.15s}
.tb:hover{color:var(--txt)}.tb.on{color:var(--grn);border-color:var(--grn)}

.pnl{display:none;padding:20px 28px}.pnl.on{display:block}

.sg{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:20px}
.sc{background:var(--card);border:1px solid var(--brd);border-radius:10px;padding:16px}
.sc .l{font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--dim);margin-bottom:6px}
.sc .v{font-size:24px;font-weight:700}.sc .s{font-size:11px;color:var(--dim);margin-top:3px}

.fl{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;align-items:center}
.si{padding:7px 14px;border-radius:7px;border:1px solid var(--brd);background:var(--card);color:var(--txt);font-size:12px;outline:none;width:260px}
.si:focus{border-color:var(--grn)}
select.ss{padding:7px 10px;border-radius:7px;border:1px solid var(--brd);background:var(--card);color:var(--txt);font-size:11px;cursor:pointer;outline:none}
.fb{padding:7px 14px;border-radius:7px;border:1px solid var(--brd);background:var(--card);color:var(--dim);font-size:11px;cursor:pointer;transition:.15s}
.fb:hover,.fb.on{border-color:var(--grn);color:var(--grn);background:#0a1f0a}

.ag{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.ac{background:var(--card);border:1px solid var(--brd);border-radius:10px;overflow:hidden;transition:.15s}
.ac:hover{border-color:#444;transform:translateY(-1px);box-shadow:0 6px 20px #0005}
.ac img.th{width:100%;height:180px;object-fit:cover;background:#1a1a1a}
.ac .bd{padding:14px}
.ac .nm{font-size:12px;font-weight:600;color:var(--grn);margin-bottom:5px}
.ac .cp{font-size:11px;color:var(--dim);line-height:1.5;margin-bottom:10px;max-height:48px;overflow:hidden}
.ac .mt{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;text-align:center}
.ac .mt .n{font-size:13px;font-weight:700}.ac .mt .lb{font-size:9px;color:var(--dim);text-transform:uppercase}
.tg{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}
.t{padding:2px 7px;border-radius:3px;font-size:9px;font-weight:600}
.t-g{background:#052e16;color:#4ade80}.t-b{background:#0c1929;color:#60a5fa}.t-p{background:#1e0a3c;color:#c084fc}
.t-o{background:#2a1500;color:#fb923c}.t-r{background:#2a0000;color:#f87171}.t-c{background:#042f2e;color:#2dd4bf}
.lnk{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.lnk a{font-size:10px;padding:4px 10px;border-radius:5px;font-weight:600;transition:.15s}
.lnk a.pp{background:#1a2e1a;color:var(--grn)}
.lnk a.pp:hover{background:#2a4a2a;text-decoration:none}
.lnk a.vd{background:#1a1a2e;color:var(--blu)}
.lnk a.vd:hover{background:#2a2a4a;text-decoration:none}

table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;padding:9px 10px;font-size:10px;text-transform:uppercase;letter-spacing:.4px;color:var(--dim);border-bottom:1px solid var(--brd);background:#111;position:sticky;top:97px;z-index:10}
td{padding:9px 10px;border-bottom:1px solid var(--brd);vertical-align:top}
tr:hover td{background:var(--card2)}

.hc{background:var(--card);border:1px solid var(--brd);border-radius:10px;padding:16px;margin-bottom:10px;cursor:pointer;transition:.15s}
.hc:hover{border-color:#444}.hc .ht{font-size:14px;font-weight:500;line-height:1.5;margin-bottom:8px}
.hc .hm{font-size:11px;color:var(--dim);display:flex;gap:14px;flex-wrap:wrap;align-items:center}

.ib{background:linear-gradient(135deg,#0f1f0f,#111);border:1px solid #1a3a1a;border-radius:10px;padding:18px;margin-bottom:14px}
.ib h3{font-size:13px;color:var(--grn);margin-bottom:6px}.ib p{font-size:12px;color:var(--dim);line-height:1.6}
.ib ul{margin:8px 0 0 18px;color:var(--dim);font-size:12px;line-height:1.9}

.bc{display:flex;align-items:end;gap:5px;height:110px;margin:12px 0}
.bc .c{display:flex;flex-direction:column;align-items:center;flex:1}
.bc .b{width:100%;border-radius:3px 3px 0 0;min-height:3px}
.bc .bl{font-size:8px;color:var(--dim);margin-top:4px;text-align:center}.bc .bv{font-size:9px;font-weight:600;margin-bottom:3px}

.cnt{text-align:center;padding:14px;color:var(--dim);font-size:11px}
</style>
</head>
<body>

<div class="top">
  <h1>NEWGARMENTS <b>Competitor Intel</b></h1>
  <div class="st" id="topStats"></div>
</div>

<div class="tabs" id="tabs"></div>

<div class="pnl on" id="p-overview"></div>
<div class="pnl" id="p-ads"></div>
<div class="pnl" id="p-hooks"></div>
<div class="pnl" id="p-competitors"></div>
<div class="pnl" id="p-insights"></div>

<script>
const D=###DATA###;
const fmt=v=>v>=1e6?(v/1e6).toFixed(1)+'M':v>=1e3?(v/1e3).toFixed(1)+'K':v+'';
const esc=s=>{const d=document.createElement('div');d.textContent=s||'';return d.innerHTML};
const pipi=id=>`https://www.pipiads.com/ad-search/ad/detail/${id}`;

// Tabs
const tabNames=['overview','ads','hooks','competitors','insights'];
const tabLabels=['Overview','All Ads','Hook Analysis','Top Competitors','NG Insights'];
document.getElementById('tabs').innerHTML=tabNames.map((n,i)=>`<div class="tb${i===0?' on':''}" onclick="showTab('${n}')">${tabLabels[i]}</div>`).join('');
function showTab(id){
  document.querySelectorAll('.pnl').forEach(p=>p.classList.remove('on'));
  document.querySelectorAll('.tb').forEach(t=>t.classList.remove('on'));
  document.getElementById('p-'+id).classList.add('on');
  event.target.classList.add('on');
}

// Top stats
const totalViews=D.reduce((s,a)=>s+a.views,0);
const brands=[...new Set(D.map(a=>a.name))];
const swAds=D.filter(a=>a.sw);
document.getElementById('topStats').innerHTML=`
  <div><strong>${D.length}</strong>Ads</div>
  <div><strong>${brands.length}</strong>Brands</div>
  <div><strong>${fmt(totalViews)}</strong>Views</div>
  <div><strong>${swAds.length}</strong>Streetwear</div>`;

function adCard(a){
  const cat=hookCat(a.hook);
  return`<div class="ac">
    ${a.cover?`<img class="th" src="${a.cover}" loading="lazy" onerror="this.style.display='none'">`:'<div class="th" style="display:flex;align-items:center;justify-content:center;color:#333;font-size:12px">No preview</div>'}
    <div class="bd">
      <div class="nm">${esc(a.name)}</div>
      <div class="cp">${esc(a.desc)}</div>
      <div class="mt">
        <div><div class="n">${fmt(a.views)}</div><div class="lb">Views</div></div>
        <div><div class="n">${fmt(a.likes)}</div><div class="lb">Likes</div></div>
        <div><div class="n">${a.days}d</div><div class="lb">Running</div></div>
        <div><div class="n">${a.cpm?'$'+a.cpm:'\u2014'}</div><div class="lb">CPM</div></div>
      </div>
      ${a.hook&&a.hook!=='null'?`<div style="margin-top:8px;font-size:11px;color:var(--org)"><b>Hook:</b> ${esc(a.hook.substring(0,80))}</div>`:''}
      <div class="tg">
        ${a.sw?'<span class="t t-g">STREETWEAR</span>':''}
        ${a.days>30?'<span class="t t-o">PROVEN</span>':''}
        ${a.views>500000?'<span class="t t-p">VIRAL</span>':''}
        ${a.regions.map(r=>'<span class="t t-b">'+r+'</span>').join('')}
        ${a.cta?'<span class="t t-c">'+esc(a.cta)+'</span>':''}
        ${cat?'<span class="t t-r">'+cat+'</span>':''}
        ${a.shop?'<span class="t" style="background:#1a1a1a;color:#888">'+a.shop+'</span>':''}
      </div>
      <div class="lnk">
        <a class="pp" href="${pipi(a.id)}" target="_blank">Open in PiPiAds &#8599;</a>
        ${a.video?`<a class="vd" href="${a.video}" target="_blank">Watch Video &#9654;</a>`:''}
      </div>
    </div></div>`;
}

function hookCat(h){
  if(!h)return'';const l=h.toLowerCase();
  if(['limited','sold','last','hurry','gone','miss','only','drop'].some(k=>l.includes(k)))return'SCARCITY';
  if(['heavy','quality','premium','thick','weight','fabric','built'].some(k=>l.includes(k)))return'QUALITY';
  if(['style','fit','look','outfit','wear','fashion','fire','hard'].some(k=>l.includes(k)))return'IDENTITY';
  if(['how','why','what','would','know','secret'].some(k=>l.includes(k)))return'QUESTION';
  if(['everyone','trending','viral','best','favorite','popular'].some(k=>l.includes(k)))return'SOCIAL';
  return'';
}

// === OVERVIEW ===
function renderOverview(){
  const avgDays=Math.round(D.reduce((s,a)=>s+a.days,0)/D.length);
  const ctas={};D.forEach(a=>{if(a.cta)ctas[a.cta]=(ctas[a.cta]||0)+1});
  const topCta=Object.entries(ctas).sort((a,b)=>b[1]-a[1])[0];
  const regs={};D.forEach(a=>a.regions.forEach(r=>regs[r]=(regs[r]||0)+1));
  const topReg=Object.entries(regs).sort((a,b)=>b[1]-a[1])[0];
  const shopify=D.filter(a=>a.shop==='shopify').length;
  const top=[...D].sort((a,b)=>b.views-a.views).slice(0,12);

  document.getElementById('p-overview').innerHTML=`
    <div class="sg">
      <div class="sc"><div class="l">Avg Days Running</div><div class="v">${avgDays}</div></div>
      <div class="sc"><div class="l">Top CTA</div><div class="v">${topCta?topCta[0]:'-'}</div><div class="s">${topCta?topCta[1]:0} ads</div></div>
      <div class="sc"><div class="l">Top Region</div><div class="v">${topReg?topReg[0]:'-'}</div><div class="s">${topReg?topReg[1]:0} ads</div></div>
      <div class="sc"><div class="l">Shopify</div><div class="v">${shopify}</div><div class="s">of ${D.length}</div></div>
      <div class="sc"><div class="l">Streetwear</div><div class="v">${swAds.length}</div><div class="s">${Math.round(swAds.length/D.length*100)}%</div></div>
      <div class="sc"><div class="l">With Video</div><div class="v">${D.filter(a=>a.video).length}</div></div>
    </div>
    <h3 style="font-size:14px;margin-bottom:12px">Top 12 by Views</h3>
    <div class="ag">${top.map(a=>adCard(a)).join('')}</div>`;
}

// === ALL ADS ===
let swOnly=false;
function renderAds(){
  const regs={};const ctas={};
  D.forEach(a=>{a.regions.forEach(r=>regs[r]=(regs[r]||0)+1);if(a.cta)ctas[a.cta]=(ctas[a.cta]||0)+1});
  const regOpts=Object.entries(regs).sort((a,b)=>b[1]-a[1]).map(([r,c])=>`<option value="${r}">${r} (${c})</option>`).join('');
  const ctaOpts=Object.entries(ctas).sort((a,b)=>b[1]-a[1]).map(([c,n])=>`<option value="${esc(c)}">${esc(c)} (${n})</option>`).join('');

  document.getElementById('p-ads').innerHTML=`
    <div class="fl">
      <input class="si" id="q" placeholder="Search ads, brands, hooks..." oninput="filterAds()">
      <select class="ss" id="srt" onchange="filterAds()"><option value="views">Views</option><option value="likes">Likes</option><option value="days">Days</option><option value="cpm">CPM</option></select>
      <select class="ss" id="reg" onchange="filterAds()"><option value="all">All Regions</option>${regOpts}</select>
      <select class="ss" id="cta" onchange="filterAds()"><option value="all">All CTAs</option>${ctaOpts}</select>
      <div class="fb" id="swBtn" onclick="swOnly=!swOnly;this.classList.toggle('on');filterAds()">Streetwear Only</div>
    </div>
    <div class="ag" id="adsGrid"></div>
    <div class="cnt" id="adCnt"></div>`;
  filterAds();
}

function filterAds(){
  const q=(document.getElementById('q')?.value||'').toLowerCase();
  const srt=document.getElementById('srt')?.value||'views';
  const reg=document.getElementById('reg')?.value||'all';
  const cta=document.getElementById('cta')?.value||'all';
  let f=[...D];
  if(q)f=f.filter(a=>`${a.name} ${a.desc} ${a.hook} ${a.script} ${a.cta}`.toLowerCase().includes(q));
  if(swOnly)f=f.filter(a=>a.sw);
  if(reg!=='all')f=f.filter(a=>a.regions.includes(reg));
  if(cta!=='all')f=f.filter(a=>a.cta===cta);
  f.sort((a,b)=>b[srt]-a[srt]);
  document.getElementById('adsGrid').innerHTML=f.slice(0,80).map(a=>adCard(a)).join('');
  document.getElementById('adCnt').textContent=`Showing ${Math.min(f.length,80)} of ${f.length}`;
}

// === HOOKS ===
let hf='all';
function renderHooks(){
  const cats=['all','scarcity','quality','identity','question','social'];
  document.getElementById('p-hooks').innerHTML=`
    <h3 style="margin-bottom:14px">AI-Extracted Hooks from Competitor Ads</h3>
    <div class="fl">${cats.map(c=>`<div class="fb${c==='all'?' on':''}" onclick="hf='${c}';document.querySelectorAll('#p-hooks .fb').forEach(b=>b.classList.remove('on'));this.classList.add('on');drawHooks()">${c==='all'?'All':c.charAt(0).toUpperCase()+c.slice(1)}</div>`).join('')}</div>
    <div id="hooksList"></div>`;
  drawHooks();
}
function drawHooks(){
  let h=D.filter(a=>a.hook&&a.hook!=='null');
  if(hf!=='all')h=h.filter(a=>hookCat(a.hook).toLowerCase()===hf);
  h.sort((a,b)=>b.views-a.views);
  document.getElementById('hooksList').innerHTML=h.slice(0,50).map(a=>`
    <div class="hc">
      <div class="ht">"${esc(a.hook)}"</div>
      <div class="hm">
        <b>${esc(a.name)}</b>
        <span>${fmt(a.views)} views</span><span>${a.days}d</span><span>${esc(a.cta)}</span>
        ${hookCat(a.hook)?'<span class="t t-r">'+hookCat(a.hook)+'</span>':''}
        ${a.sw?'<span class="t t-g">STREETWEAR</span>':''}
        <a class="pp" href="${pipi(a.id)}" target="_blank" style="font-size:10px;padding:2px 8px;border-radius:4px;background:#1a2e1a;color:var(--grn)">PiPiAds &#8599;</a>
      </div>
    </div>`).join('');
}

// === COMPETITORS ===
function renderCompetitors(){
  const bm={};
  D.forEach(a=>{
    if(!bm[a.name])bm[a.name]={ads:[],tv:0,td:0,ctas:{},regs:new Set,hooks:[]};
    const b=bm[a.name];b.ads.push(a);b.tv+=a.views;b.td+=a.days;
    if(a.cta)b.ctas[a.cta]=(b.ctas[a.cta]||0)+1;
    a.regions.forEach(r=>b.regs.add(r));
    if(a.hook&&a.hook!=='null')b.hooks.push(a.hook);
  });
  const sorted=Object.entries(bm).sort((a,b)=>b[1].tv-a[1].tv);
  document.getElementById('p-competitors').innerHTML=`
    <h3 style="margin-bottom:14px">Top Competitor Brands</h3>
    <table><thead><tr><th>#</th><th>Brand</th><th>Ads</th><th>Total Views</th><th>Avg Days</th><th>CTA</th><th>Regions</th><th>Top Hook</th><th>Link</th></tr></thead>
    <tbody>${sorted.slice(0,40).map(([n,b],i)=>{
      const avgD=Math.round(b.td/b.ads.length);
      const tc=Object.entries(b.ctas).sort((a,b)=>b[1]-a[1])[0];
      const topAd=b.ads.sort((a,b)=>b.views-a.views)[0];
      return`<tr>
        <td>${i+1}</td><td><b>${esc(n)}</b></td><td>${b.ads.length}</td>
        <td>${fmt(b.tv)}</td><td>${avgD}d</td><td>${tc?esc(tc[0]):'-'}</td>
        <td>${[...b.regs].slice(0,4).join(', ')}</td>
        <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--dim)">${esc((b.hooks[0]||'').substring(0,60))}</td>
        <td><a href="${pipi(topAd.id)}" target="_blank" style="font-size:10px">PiPiAds &#8599;</a></td>
      </tr>`;
    }).join('')}</tbody></table>`;
}

// === INSIGHTS ===
function renderInsights(){
  const hooks=D.filter(a=>a.hook&&a.hook!=='null');
  const qCnt=hooks.filter(a=>hookCat(a.hook)==='QUALITY').length;
  const sCnt=hooks.filter(a=>hookCat(a.hook)==='SCARCITY').length;
  const regs={};D.forEach(a=>a.regions.forEach(r=>regs[r]=(regs[r]||0)+1));
  const rs=Object.entries(regs).sort((a,b)=>b[1]-a[1]);
  const mx=rs[0]?.[1]||1;
  const regBars=rs.slice(0,12).map(([r,c])=>`<div class="c"><div class="bv">${c}</div><div class="b" style="height:${c/mx*100}%;background:var(--blu)"></div><div class="bl">${r}</div></div>`).join('');

  const ctas={};D.forEach(a=>{if(a.cta)ctas[a.cta]=(ctas[a.cta]||0)+1});
  const cs=Object.entries(ctas).sort((a,b)=>b[1]-a[1]);
  const cm=cs[0]?.[1]||1;
  const ctaBars=cs.slice(0,8).map(([c,n])=>`<div class="c"><div class="bv">${n}</div><div class="b" style="height:${n/cm*100}%;background:var(--prp)"></div><div class="bl">${esc(c)}</div></div>`).join('');

  const proven=D.filter(a=>a.sw&&a.days>30).sort((a,b)=>b.views-a.views);

  document.getElementById('p-insights').innerHTML=`
    <h3 style="color:var(--grn);margin-bottom:14px">NEWGARMENTS Strategic Insights</h3>
    <div class="ib"><h3>1. HEAVYWEIGHT/QUALITY = YOUR WHITESPACE</h3><p>Only <b>${qCnt} of ${hooks.length} hooks</b> lead with quality/material. Most use identity/style. Lead with GSM weight, fabric closeups, "built to last".</p></div>
    <div class="ib"><h3>2. SCARCITY IS UNDERUSED</h3><p>Only <b>${sCnt} hooks</b> use scarcity. Your real "no restock" model beats competitors who fake it.</p></div>
    <div class="ib"><h3>3. REGION OPPORTUNITY</h3><div class="bc">${regBars}</div><p>US saturated (${regs['US']||0}). <b>UK (${regs['GB']||0}), DE (${regs['DE']||0}), FR (${regs['FR']||0}), NL (${regs['NL']||0})</b> = less competition.</p></div>
    <div class="ib"><h3>4. CTA STRATEGY</h3><div class="bc">${ctaBars}</div><p>"Shop now" dominates. Differentiate: <b>"Cop before it's gone"</b>, <b>"Secure yours"</b>, <b>"Join the archive"</b>.</p></div>
    <div class="ib"><h3>5. HOOKS TO ADAPT</h3><ul>
      <li>"the perfect blank hoodie under $100" → <b>"the heavyweight hoodie they'll ask about"</b></li>
      <li>"POV: you found the HEAVYWEIGHT hoodie" → <b>"POV: archive streetwear that never restocks"</b></li>
      <li>"hardest tee in the market" → <b>"hardest drop this year. 200 pieces. gone forever."</b></li>
      <li>"Would you wear this tee?" → <b>"only 3% will cop this before it's gone"</b></li></ul></div>
    <div class="ib"><h3>6. PROVEN WINNERS (30+ days)</h3><ul>${proven.slice(0,8).map(a=>
      `<li><b>${esc(a.name)}</b> - ${fmt(a.views)} views, ${a.days}d - <a href="${pipi(a.id)}" target="_blank">PiPiAds &#8599;</a></li>`
    ).join('')}</ul></div>
    <div class="ib"><h3>7. ALL VIDEO URLS SAVED</h3><p>${D.filter(a=>a.video).length} competitor videos captured. Click "Watch Video" on any card to study their creative.</p></div>`;
}

renderOverview();renderAds();renderHooks();renderCompetitors();renderInsights();
</script>
</body>
</html>"""

html_final = html_template.replace('###DATA###', js_data)
html_path.write_text(html_final, encoding='utf-8')
print(f"Dashboard written: {len(html_final)//1024}KB -> pipiads-dashboard.html")
