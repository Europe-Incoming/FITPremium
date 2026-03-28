"""
rebuild_site.py — v11
Fixes:
- City break pricing: handles 4-column table (Single/Twin/Triple/Child)
  with Extension night rows correctly skipped
- City extraction: handles both "Overnight in X" and "Overnight X" patterns
- Everything from v10 preserved
"""

import os, re, json, urllib.request, urllib.parse, time
from datetime import datetime
import fitz

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
COORDS_CACHE_PATH = os.path.join(REPO_ROOT, "city_coords_cache.json")

FOLDER_CONFIG = {
    "city-break": {"title": "City Breaks Packages", "breadcrumb": "City Breaks", "region": "City Break", "depth": 1},
    "multi-country/italy": {"title": "Italy", "breadcrumb": "Italy", "region": "Italy", "depth": 2},
    "multi-country/eastern-europe": {"title": "Eastern Europe", "breadcrumb": "Eastern Europe", "region": "Eastern Europe", "depth": 2},
    "multi-country/france": {"title": "France", "breadcrumb": "France", "region": "France", "depth": 2},
    "multi-country/scandinavia-iceland": {"title": "Scandinavia & Iceland", "breadcrumb": "Scandinavia & Iceland", "region": "Scandinavia & Iceland", "depth": 2},
    "multi-country/spain-portugal": {"title": "Spain & Portugal", "breadcrumb": "Spain & Portugal", "region": "Spain & Portugal", "depth": 2},
    "multi-country/switzerland": {"title": "Switzerland", "breadcrumb": "Switzerland", "region": "Switzerland", "depth": 2},
    "multi-country/uk-ireland": {"title": "UK & Ireland", "breadcrumb": "UK & Ireland", "region": "UK & Ireland", "depth": 2},
    "multi-country/western-central-europe": {"title": "Western & Central Europe", "breadcrumb": "Western & Central Europe", "region": "Western & Central Europe", "depth": 2},
}

REGION_DISPLAY = {
    "italy": "Italy", "eastern-europe": "Eastern Europe", "france": "France",
    "scandinavia-iceland": "Scandinavia & Iceland", "spain-portugal": "Spain & Portugal",
    "switzerland": "Switzerland", "uk-ireland": "UK & Ireland",
    "western-central-europe": "Western & Central Europe",
}

SEED_COORDS = {
    "Amsterdam": [52.3676, 4.9041], "Athens": [37.9838, 23.7275], "Barcelona": [41.3851, 2.1734],
    "Berlin": [52.5200, 13.4050], "Brussels": [50.8503, 4.3517], "Budapest": [47.4979, 19.0402],
    "Copenhagen": [55.6761, 12.5683], "Dublin": [53.3498, -6.2603], "Edinburgh": [55.9533, -3.1883],
    "Florence": [43.7696, 11.2558], "Frankfurt": [50.1109, 8.6821], "Geneva": [46.2044, 6.1432],
    "Glasgow": [55.8642, -4.2518], "Helsinki": [60.1699, 24.9384], "Innsbruck": [47.2692, 11.4041],
    "Interlaken": [46.6863, 7.8632], "Lisbon": [38.7223, -9.1393], "London": [51.5074, -0.1278],
    "Lucerne": [47.0502, 8.3093], "Madrid": [40.4168, -3.7038], "Milan": [45.4654, 9.1859],
    "Munich": [48.1351, 11.5820], "Nice": [43.7102, 7.2620], "Oslo": [59.9139, 10.7522],
    "Paris": [48.8566, 2.3522], "Prague": [50.0755, 14.4378], "Rome": [41.9028, 12.4964],
    "Salzburg": [47.8095, 13.0550], "Stockholm": [59.3293, 18.0686], "Venice": [45.4408, 12.3155],
    "Vienna": [48.2082, 16.3738], "Zurich": [47.3769, 8.5417], "Bergen": [60.3913, 5.3221],
    "Reykjavik": [64.1265, -21.8174], "Inverness": [57.4778, -4.2247], "Mykonos": [37.4467, 25.3289],
    "Santorini": [36.3932, 25.4615], "Manchester": [53.4808, -2.2426], "Fort William": [56.8198, -5.1052],
    "Limerick": [52.6638, -8.6267], "Galway": [53.2707, -9.0568], "Cork": [51.8985, -8.4756],
    "Bayeux": [49.2764, -0.7024], "Tours": [47.3941, 0.6848], "Lyon": [45.7640, 4.8357],
    "Bordeaux": [44.8378, -0.5792], "Strasbourg": [48.5734, 7.7521], "Marseille": [43.2965, 5.3698],
    "Avignon": [43.9493, 4.8055], "Montreux": [46.4312, 6.9107], "Zermatt": [46.0207, 7.7491],
    "Bern": [46.9480, 7.4474], "Naples": [40.8518, 14.2681], "Turin": [45.0703, 7.6869],
    "Bologna": [44.4949, 11.3426], "Pisa": [43.7228, 10.4017], "Siena": [43.3186, 11.3307],
    "Cagliari": [39.2238, 9.1217], "Cala Gonone": [40.2833, 9.6167], "Alghero": [40.5594, 8.3197],
    "Olbia": [40.9167, 9.5000], "Villasimius": [39.1333, 9.5167], "Bosa": [40.2981, 8.4983],
    "Ajaccio": [41.9192, 8.7386], "Corte": [42.3069, 9.1497], "Bonifacio": [41.3871, 9.1597],
    "Bastia": [42.7003, 9.4500], "Seville": [37.3891, -5.9845], "Granada": [37.1773, -3.5986],
    "Valencia": [39.4699, -0.3763], "Bilbao": [43.2627, -2.9253], "Porto": [41.1579, -8.6291],
    "Sintra": [38.7977, -9.3877], "Coimbra": [40.2033, -8.4103],
    "Cologne": [50.9333, 6.9500], "Hamburg": [53.5753, 10.0153], "Dresden": [51.0504, 13.7373],
    "Dusseldorf": [51.2217, 6.7762], "Nuremberg": [49.4521, 11.0767],
    "Krakow": [50.0647, 19.9450], "Warsaw": [52.2297, 21.0122], "Bratislava": [48.1486, 17.1077],
    "Ljubljana": [46.0569, 14.5058], "Dubrovnik": [42.6507, 18.0944], "Split": [43.5081, 16.4402],
    "Bruges": [51.2093, 3.2247], "Ghent": [51.0543, 3.7174], "Antwerp": [51.2194, 4.4025],
    "Rotterdam": [51.9244, 4.4777], "Luxembourg": [49.6117, 6.1319],
    "Gothenburg": [57.7089, 11.9746], "Tallinn": [59.4370, 24.7536],
    "Hallstatt": [47.5622, 13.6493], "Graz": [47.0707, 15.4395],
    "Amalfi": [40.6340, 14.6025], "Positano": [40.6281, 14.4850], "Pompeii": [40.7461, 14.5019],
    "Venice Mestre": [45.4847, 12.2386],
    "Tromso": [69.6489, 18.9551], "Kiruna": [67.8558, 20.2253], "Abisko": [68.3493, 18.8306],
    "Narvik": [68.4385, 17.4279], "Alta": [69.9689, 23.2716], "Rovaniemi": [66.5039, 25.7294],
    "Lofoten": [68.1566, 13.9989], "Flam": [60.8633, 7.1159], "Geiranger": [62.1008, 7.2050],
    "Trondheim": [63.4305, 10.3951],
    "Cheltenham": [51.8994, -2.0783], "Barnstaple": [51.0803, -4.0588], "Truro": [50.2632, -5.0510],
    "Plymouth": [50.3755, -4.1427], "Exeter": [50.7184, -3.5339], "Bournemouth": [50.7192, -1.8808],
    "Bristol": [51.4545, -2.5879], "Cambridge": [52.2053, 0.1218], "Oxford": [51.7520, -1.2577],
    "Bath": [51.3758, -2.3599], "York": [53.9600, -1.0873], "Cardiff": [51.4816, -3.1791],
    "Belfast": [54.5973, -5.9301], "Aberdeen": [57.1497, -2.0943], "Stirling": [56.1165, -3.9369],
    "Perth": [56.3950, -3.4310], "Dundee": [56.4620, -2.9707], "Oban": [56.4153, -5.4714],
    "Pitlochry": [56.7044, -3.7327], "St Andrews": [56.3398, -2.7967],
}

COMPOUND_NAMES = {
    'East Europe', 'Eastern Europe', 'Western Europe', 'Central Europe', 'Western Central Europe',
    'Costa Smeralda', 'Cala Gonone', 'Fort William', 'San Sebastian', 'Czech Republic',
    'Venice Mestre', 'Isle of Skye', 'Lake District', 'Stratford upon Avon',
}

GEO_BLOCK = """<script>
(async function(){try{const r=await fetch('https://api.country.is/');const d=await r.json();
if(!['US','CA','AU','NZ'].includes(d.country)){document.body.innerHTML='<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;background:#f5f5f5;text-align:center"><h1 style="font-size:48px">🌍</h1><h2>Service Not Available</h2><p style="color:#757575">This site is not available in your region.</p></div>';}
}catch(e){}}
)();</script>"""

GA = """<script async src="https://www.googletagmanager.com/gtag/js?id=G-04BZKH6574"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-04BZKH6574');</script>"""

LEAFLET_HEAD = """<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>"""

BASE_CSS = """
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;background:#f0f2f5;color:#212121;line-height:1.6;padding-top:80px;}
.top-nav{position:fixed;top:0;left:0;right:0;background:white;box-shadow:0 1px 3px rgba(0,0,0,0.08);z-index:1000;padding:16px 0;}
.nav-container{max-width:1200px;margin:0 auto;padding:0 24px;display:flex;align-items:center;gap:32px;}
.logo{height:48px;width:auto;}.logo:hover{opacity:0.8;}
.header-right{display:flex;align-items:center;gap:32px;flex:1;justify-content:flex-end;}
.site-title-group{text-align:right;}
.site-title-main{font-size:1.1em;font-weight:600;color:#212121;}
.site-title-sub{font-size:0.9em;color:#757575;}
.contact-info{text-align:right;padding-left:32px;border-left:1px solid #e0e0e0;}
.contact-prompt{font-size:0.85em;color:#757575;margin-bottom:4px;}
.contact-email{font-size:0.9em;color:#2196F3;text-decoration:none;font-weight:500;}
.contact-email:hover{text-decoration:underline;}
.search-box{width:100%;max-width:350px;padding:10px 18px;font-size:0.95em;border:1px solid #e0e0e0;border-radius:24px;background:#fafafa;transition:all 0.2s;}
.search-box::placeholder{text-align:center;}
.search-box:focus{outline:none;border-color:#2196F3;background:white;box-shadow:0 2px 8px rgba(33,150,243,0.15);}
.breadcrumb{max-width:1200px;margin:0 auto;padding:24px 24px 0;font-size:0.9em;color:#757575;}
.breadcrumb a{color:#2196F3;text-decoration:none;}
.breadcrumb a:hover{text-decoration:underline;}
.container{max-width:1200px;margin:0 auto;padding:32px 24px 48px;}
h1{font-size:2.2em;font-weight:600;color:#212121;margin-bottom:32px;letter-spacing:-0.5px;}
footer{text-align:center;margin-top:60px;padding:32px 0;color:#9e9e9e;font-size:0.9em;border-top:1px solid #e8e8e8;}
@media(max-width:768px){body{padding-top:180px;}.nav-container{flex-wrap:wrap;gap:16px;}.header-right{width:100%;flex-direction:column;align-items:center;order:3;gap:16px;}.site-title-group{text-align:center;}.contact-info{text-align:center;border-left:none;border-top:1px solid #e0e0e0;padding-left:0;padding-top:16px;}.search-box{max-width:100%;}}
"""

BROCHURE_CSS = """
.brochures{display:grid;grid-template-columns:repeat(2,1fr);gap:20px;align-items:stretch;}
.brochure-card{background:white;border-radius:14px;box-shadow:0 1px 4px rgba(0,0,0,0.07);transition:all 0.3s cubic-bezier(0.4,0,0.2,1);text-decoration:none;color:inherit;display:flex;flex-direction:row;border:1px solid #ebebeb;overflow:hidden;min-height:210px;}
.brochure-card:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,0.11);border-color:#d0d0d0;}
.brochure-card.expired{opacity:0.75;border-color:#ffcc80;}
.card-info{flex:1;padding:20px 20px 16px;display:flex;flex-direction:column;gap:5px;min-width:0;}
.card-title{font-size:1.0em;font-weight:700;color:#1a1a1a;line-height:1.3;}
.tour-type{font-size:0.72em;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;color:#1565c0;}
.card-pills{display:flex;flex-wrap:wrap;gap:5px;margin-top:2px;}
.pill{font-size:0.71em;font-weight:600;padding:3px 9px;border-radius:20px;}
.pill-duration{background:#f3f3f3;color:#444;}
.pill-summer{background:#fff8e1;color:#e65100;}
.pill-winter{background:#e8f4fd;color:#0277bd;}
.pill-allyear{background:#e8f5e9;color:#2e7d32;}
.pill-valid{background:#e8f5e9;color:#2e7d32;}
.pill-expired{background:#fff3e0;color:#e65100;}
.card-description{font-size:0.81em;color:#666;font-style:italic;line-height:1.4;}
.cities-list{font-size:0.79em;color:#555;}
.price-tag{font-size:0.88em;color:#2e7d32;font-weight:700;margin-top:auto;padding-top:6px;}

.card-map{width:200px;min-width:200px;border-left:1px solid #ebebeb;position:relative;overflow:hidden;}
.map-inner{width:100%;height:100%;min-height:210px;}
.leaflet-tooltip.city-tip{background:transparent!important;border:none!important;box-shadow:none!important;font-size:9px;font-weight:700;color:#1a1a2e;white-space:nowrap;padding:0;text-shadow:-1px -1px 0 white,1px -1px 0 white,-1px 1px 0 white,1px 1px 0 white;}
.leaflet-tooltip.city-tip::before{display:none!important;}
@media(max-width:900px){.brochures{grid-template-columns:1fr;}.card-map{width:160px;min-width:160px;}}
@media(max-width:768px){.brochure-card{flex-direction:column;}.card-map{width:100%;min-width:100%;height:180px;border-left:none;border-top:1px solid #ebebeb;}.map-inner{min-height:180px;}}
"""

REGION_CSS = """
.categories{display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:24px;max-width:1000px;margin:0 auto;}
.category-card{background:white;padding:32px;border-radius:14px;box-shadow:0 1px 3px rgba(0,0,0,0.08);transition:all 0.3s cubic-bezier(0.4,0,0.2,1);text-decoration:none;color:inherit;display:block;border:1px solid #f5f5f5;}
.category-card:hover{transform:translateY(-4px);box-shadow:0 8px 24px rgba(0,0,0,0.12);border-color:#e0e0e0;}
.category-card h2{font-size:1.4em;color:#212121;margin-bottom:10px;font-weight:600;}
.category-meta{font-size:0.82em;color:#757575;margin-bottom:6px;}
.category-types{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;}
.type-tag{font-size:0.72em;font-weight:600;padding:2px 9px;border-radius:12px;background:#f0f4ff;color:#1565c0;}
.arrow{float:right;color:#2196F3;font-size:1.4em;transition:transform 0.2s;}
.category-card:hover .arrow{transform:translateX(4px);}
@media(max-width:768px){.categories{grid-template-columns:1fr;}}
"""

NAV = """<nav class="top-nav"><div class="nav-container">
<a href="{lh}"><img src="{ls}" alt="Europe Incoming" class="logo"></a>
<input type="text" class="search-box" placeholder="Search packages - type city or country" id="searchBox">
<div class="header-right">
  <div class="site-title-group"><div class="site-title-main">Europe Incoming</div><div class="site-title-sub">FIT Packages</div></div>
  <div class="contact-info"><div class="contact-prompt">Can't find what you're looking for? Email us at:</div>
  <a href="mailto:fitsales@europeincoming.com" class="contact-email">fitsales@europeincoming.com</a></div>
</div></div></nav>"""


# ── COORDS CACHE ──────────────────────────────────────────────────────────────

def load_coords_cache():
    cache = dict(SEED_COORDS)
    if os.path.exists(COORDS_CACHE_PATH):
        with open(COORDS_CACHE_PATH, 'r') as f:
            cache.update(json.load(f))
    return cache

def save_coords_cache(cache):
    to_save = {k: v for k, v in cache.items() if k not in SEED_COORDS}
    with open(COORDS_CACHE_PATH, 'w') as f:
        json.dump(to_save, f, indent=2)

def geocode_city(city_name):
    for query in [city_name, f"{city_name} Europe"]:
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json&limit=1"
            req = urllib.request.Request(url, headers={
                "User-Agent": "EuropeIncomingFIT/1.0 (fitsales@europeincoming.com)"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                results = json.loads(resp.read())
                if results:
                    return [float(results[0]["lat"]), float(results[0]["lon"])]
            time.sleep(1)
        except Exception as e:
            print(f"    Geocode error {city_name}: {e}")
    return None

def get_coords(city_name, cache):
    if city_name in cache:
        return cache[city_name]
    city_lower = city_name.lower()
    for k, v in cache.items():
        if k.lower() == city_lower:
            return v
    for k, v in cache.items():
        if v and (city_lower in k.lower() or k.lower() in city_lower):
            return v
    print(f"    Geocoding: {city_name}...")
    coords = geocode_city(city_name)
    cache[city_name] = coords
    if coords:
        print(f"    Found: {city_name} -> {coords}")
    else:
        print(f"    Not found: {city_name}")
    time.sleep(1)
    return coords


# ── TITLE ─────────────────────────────────────────────────────────────────────

def smart_destination(words):
    if not words: return ""
    if len(words) == 1: return words[0]
    two = ' '.join(words[:2])
    if len(words) == 2:
        return two if two in COMPOUND_NAMES else f"{words[0]} & {words[1]}"
    if len(words) == 3:
        return f"{words[0]}, {words[1]} & {words[2]}"
    if len(words) == 4:
        return f"{words[0]}, {words[1]}, {words[2]} & {words[3]}"
    return f"{', '.join(words[:-1])} & {words[-1]}"

def make_title(filename):
    name = filename.replace('.pdf', '').replace('_', ' ')
    name = re.sub(r'\s+', ' ', name).strip()
    m = re.search(r'(\d+)\s*nights?,\s*(\d+)\s*days?\s+(.+)', name, re.IGNORECASE)
    if m:
        duration = f"{m.group(1)} nights, {m.group(2)} days"
        rest = m.group(3).strip()
    else:
        m2 = re.search(r'(\d+)\s*nights?\s*[/]?\s*(\d+)\s*days?', name, re.IGNORECASE)
        if m2:
            duration = f"{m2.group(1)} nights, {m2.group(2)} days"
            rest = name[m2.end():].strip()
        else:
            m3 = re.search(r'(\d+)\s*[Dd]ays?\s+(.+)', name, re.IGNORECASE)
            if m3:
                duration = f"{m3.group(1)} days"
                rest = m3.group(2).strip()
            else:
                return name
    rest = re.sub(r'\b(Private|Regular|Self.?[Dd]rive)\b', '', rest, flags=re.IGNORECASE)
    rest = re.sub(r'\d{4}-\d{2,4}', '', rest)
    rest = re.sub(r'Europe\s+Incoming', '', rest, flags=re.IGNORECASE)
    rest = re.sub(r'\s+', ' ', rest).strip().strip('-').strip()
    rest = re.sub(r'\s*&\s*', ' ', rest).strip()
    return f"{duration} {smart_destination(rest.split())}".strip()


# ── PDF EXTRACTION ────────────────────────────────────────────────────────────

def parse_date(d):
    for fmt in ['%d.%m.%Y', '%d.%m.%y', '%d/%m/%Y', '%d/%m/%y']:
        try:
            return datetime.strptime(d, fmt)
        except:
            pass
    return None

def detect_seasons(date_pairs):
    SUMMER = {4, 5, 6, 7, 8, 9, 10}
    WINTER = {11, 12, 1, 2, 3}
    hs = hw = False
    for s, e in date_pairs:
        sd = parse_date(s)
        ed = parse_date(e)
        if sd and ed:
            if sd.month in SUMMER or ed.month in SUMMER: hs = True
            if sd.month in WINTER or ed.month in WINTER: hw = True
    if hs and hw: return "all-year"
    elif hs: return "summer"
    elif hw: return "winter"
    return "all-year"

def extract_price(txt, lines):
    """
    Detect currency and extract lowest starting twin price.
    Handles three table formats:
    1. Private: Min Pax table
    2. Regular/Self Drive: Single/Twin/Child (3 cols)
    3. City Break: Single/Twin/Triple/Child (4 cols) with Extension night rows
    """
    currency = "£" if ("£" in txt and "€" not in txt) else "€"
    amt_pattern = r'[€£]\s*([\d,]+)'

    # Private — Min Pax table
    if re.search(r'Min\s*Pax', txt, re.IGNORECASE):
        section = re.search(r'Min\s*Pax.*?(?:Sample Hotels|Terms|Hotels\b)', txt, re.DOTALL|re.IGNORECASE)
        if section:
            amounts = re.findall(amt_pattern, section.group(0))
            prices = [int(a.replace(',', '')) for a in amounts if int(a.replace(',', '')) > 500]
            return (min(prices), currency) if prices else (None, currency)
        return (None, currency)

    ti = next((i for i, l in enumerate(lines) if 'Twin' in l and 'Do' in l), None)
    if not ti:
        return (None, currency)

    # Detect if table has Triple column (city break format)
    has_triple = any('Triple' in l for l in lines[max(0, ti-3):ti+3])

    ep = []
    skip_count = 0
    for l in lines[ti:ti + 50]:
        # Stop at new section headers
        if re.search(r'Pre.?Post|Sample Hotels|Sample Tours|Terms\b|Hotels\b', l, re.IGNORECASE):
            break
        if re.search(r'Extension', l, re.IGNORECASE):
            skip_count = 4 if has_triple else 3
            continue
        m = re.match(amt_pattern, l)
        if m:
            if skip_count > 0:
                skip_count -= 1
                continue
            val = int(m.group(1).replace(',', ''))
            if val >= 200:  # filter out pre/post night extras (69, 131 etc)
                ep.append(val)

    if has_triple:
        # 4 cols: Single=0, Twin=1, Triple=2, Child=3
        twins = ep[1::4] if len(ep) >= 4 else []
    else:
        # 3 cols: Single=0, Twin=1, Child=2
        twins = ep[1::3] if len(ep) >= 3 else ep[1:2] if len(ep) >= 2 else []

    return (min(twins), currency) if twins else (None, currency)

def extract_cities(txt):
    """
    Extract overnight cities. Handles:
    - "Overnight in Amsterdam"  (multi-country style)
    - "Overnight Amsterdam"     (city break style)
    """
    # Try "Overnight in X" first
    cities = re.findall(r'Overnight in ([A-Z][a-zA-Z\s]+?)[\.\n,]', txt)
    if not cities:
        # Fall back to "Overnight X"
        cities = re.findall(r'Overnight\s+([A-Z][a-zA-Z]+)', txt)
    return list(dict.fromkeys([c.strip() for c in cities]))[:6]

def extract_pdf_data(pdf_path, filename):
    r = {
        "duration": None, "tour_type": None, "cities": [],
        "price_twin": None, "currency": "€", "season": "all-year",
        "valid_till": None, "is_expired": False, "includes": []
    }
    name = filename.replace('_', ' ')
    dur = re.search(r'(\d+)\s*nights?\s*/?,?\s*(\d+)\s*days?', name, re.IGNORECASE)
    if dur:
        r["duration"] = f"{dur.group(1)} nights / {dur.group(2)} days"
    else:
        d = re.search(r'(\d+)\s*days?', name, re.IGNORECASE)
        if d: r["duration"] = f"{d.group(1)} days"
    t = re.search(r'(Self.?[Dd]rive|Private|Regular)', name)
    if t: r["tour_type"] = t.group(1).replace('-', ' ').title()

    try:
        doc = fitz.open(pdf_path)
        txt = "\n".join(p.get_text() for p in doc)
        lines = [l.strip() for l in txt.split('\n')]

        r["cities"] = extract_cities(txt)

        all_dates_raw = re.findall(r'\b(\d{2}[./]\d{2}[./]\d{2,4})\b', txt)
        valid_dates = []
        for d in all_dates_raw:
            parsed = parse_date(d)
            if parsed: valid_dates.append((d, parsed))
        if valid_dates:
            strs = [v[0] for v in valid_dates]
            objs = [v[1] for v in valid_dates]
            dp = [(strs[i], strs[i + 1]) for i in range(0, len(strs) - 1, 2)]
            if dp: r["season"] = detect_seasons(dp)
            latest = max(objs)
            r["valid_till"] = latest.strftime("%b %Y")
            r["is_expired"] = latest < datetime.now()

        price, currency = extract_price(txt, lines)
        r["price_twin"] = price
        r["currency"] = currency

        im = re.search(r'price includes:(.*?)(?:Sample Tours|Terms|Sample Hotels|Hotels\b)',
                       txt, re.DOTALL|re.IGNORECASE)
        if im:
            il = [l.strip().lstrip('•').strip() for l in im.group(1).split('\n')
                  if l.strip() and not l.strip().startswith('**') and len(l.strip()) > 5]
            r["includes"] = il[:3]

    except Exception as e:
        print(f"  WARNING {filename}: {e}")
    return r


# ── ITINERARY EXTRACTION ──────────────────────────────────────────────────────

def extract_itinerary(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        txt = "\n".join(p.get_text() for p in doc)
        m = re.search(
            r'(Day\s*1\s*[,:\-\s].+?)(?:This package price includes|Sample [Tt]ours|Terms\s*[&\n]|Sample Hotels|Hotels\b|$)',
            txt, re.DOTALL|re.IGNORECASE
        )
        if m:
            raw = m.group(1).strip()
            raw = re.sub(r'Optional:.*?(?=Day\s*\d|$)', '', raw, flags=re.DOTALL)
            raw = re.sub(r'\s+', ' ', raw).strip()
            return raw[:1500]
    except Exception as e:
        print(f"    Itinerary extract failed: {e}")
    return ""


# ── AI DESCRIPTION ────────────────────────────────────────────────────────────

def generate_description(cities, region, tour_type, season, pdf_path, cached_desc=None):
    FALLBACK_MARKERS = [
        "Curated", "The best of", "elegance meets", "unmissable stops",
        "handpicked experiences", "curated and ready"
    ]
    if cached_desc and not any(m in cached_desc for m in FALLBACK_MARKERS):
        print(f"    cached: {cached_desc}")
        return cached_desc

    itinerary = extract_itinerary(pdf_path)
    if not GITHUB_TOKEN or not itinerary:
        return _fallback_desc(cities, region, tour_type)

    season_hint = ""
    if season == "winter": season_hint = "This is a winter package. "
    elif season == "summer": season_hint = "This is a summer/warm season package. "

    prompt = (
        f"Tour itinerary:\n{itinerary}\n\n"
        f"Tour type: {tour_type or 'city break'}. {season_hint}"
        f"Write ONE punchy sentence (max 12 words) capturing the ESSENCE and VIBE of this specific tour. "
        f"Don't list city names. Don't say 'explore' or 'journey through'. "
        f"Be vivid and specific to what actually happens. Just the sentence, no quotes, no preamble."
    )
    payload = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": (
                "You write punchy one-sentence travel vibes capturing the soul of a tour. "
                "Specific, sensory, evocative. Never generic. Never list city names. "
                "Focus on what's unique about THIS itinerary. "
                "Good examples: "
                "'Canal cruises, Anne Frank's hideaway and golden-hour cycling.' "
                "'Acropolis at dawn, taverna nights and Aegean sea light.' "
                "'Baroque palaces, thermal baths and Danube bridge views.' "
                "'Cliffside drives, Bronze Age towers and hidden sea caves.'"
            )},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 80, "temperature": 0.9
    }).encode()

    try:
        req = urllib.request.Request(
            "https://models.inference.ai.azure.com/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {GITHUB_TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            desc = json.loads(resp.read())["choices"][0]["message"]["content"].strip().strip('"').strip("'")
            print(f"    AI: {desc}")
            time.sleep(2)
            return desc
    except Exception as e:
        print(f"    AI failed ({e}), fallback")
        return _fallback_desc(cities, region, tour_type)

def _fallback_desc(cities, region, tour_type):
    tt = (tour_type or "").lower()
    if not cities:
        if "self" in tt: return f"Self-drive freedom through {region} at your own pace."
        if "private" in tt: return f"Private guided {region} experience, tailored for your group."
        return f"Handpicked {region} itinerary with accommodation and transfers."
    if len(cities) == 1:
        if "self" in tt: return f"Self-drive city break in {cities[0]} — explore freely."
        if "private" in tt: return f"Private {cities[0]} experience with dedicated guide and transfers."
        return f"Two nights in {cities[0]} with sightseeing, canal cruise and transfers."
    elif len(cities) == 2:
        if "self" in tt: return f"Self-drive from {cities[0]} to {cities[1]} — roads, views, freedom."
        if "private" in tt: return f"Private tour: {cities[0]} to {cities[1]} with dedicated transport."
        return f"From {cities[0]} to {cities[1]} — history, culture and local highlights."
    else:
        stops = ', '.join(cities[:-1]) + ' and ' + cities[-1]
        if "self" in tt: return f"Self-drive through {stops} — your route, your pace."
        if "private" in tt: return f"Private guided tour through {stops}."
        return f"Trains, landmarks and local character through {stops}."


# ── MAP JS ────────────────────────────────────────────────────────────────────

def make_map_js(map_id, cities, coords_cache):
    points = []
    for city in cities:
        coords = get_coords(city, coords_cache)
        if coords:
            points.append([coords[0], coords[1], city])
    if not points: return ""
    coords_js = json.dumps(points)
    return f"""(function(){{
  var pts={coords_js};
  if(!pts.length) return;
  var lats=pts.map(function(p){{return p[0];}});
  var lngs=pts.map(function(p){{return p[1];}});
  var pad=0.6;
  var bounds=[[Math.min.apply(null,lats)-pad,Math.min.apply(null,lngs)-pad],[Math.max.apply(null,lats)+pad,Math.max.apply(null,lngs)+pad]];
  var map=L.map('{map_id}',{{zoomControl:false,scrollWheelZoom:false,dragging:false,touchZoom:false,doubleClickZoom:false,boxZoom:false,keyboard:false,attributionControl:false}});
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{maxZoom:19,attribution:''}}).addTo(map);
  map.fitBounds(bounds,{{padding:[20,20]}});
  if(pts.length>1){{var ll=pts.map(function(p){{return[p[0],p[1]];}});L.polyline(ll,{{color:'#2196F3',weight:2.5,dashArray:'6,4',opacity:0.85}}).addTo(map);}}
  pts.forEach(function(p,i){{
    var color=i===0?'#e53935':(i===pts.length-1?'#43a047':'#1565c0');
    L.circleMarker([p[0],p[1]],{{radius:5,fillColor:color,color:'white',weight:2,fillOpacity:1}}).addTo(map).bindTooltip(p[2],{{permanent:true,direction:'top',className:'city-tip',offset:[0,-5]}});
  }});
}})();"""


# ── BROCHURE CARD ─────────────────────────────────────────────────────────────

def make_brochure_card(pdf_filename, pdf_data, title, description, map_id, coords_cache):
    tt = pdf_data.get("tour_type", "")
    dur = pdf_data.get("duration", "")
    cities = pdf_data.get("cities", [])
    price = pdf_data.get("price_twin")
    currency = pdf_data.get("currency", "€")
    season = pdf_data.get("season", "all-year")
    valid_till = pdf_data.get("valid_till")
    is_expired = pdf_data.get("is_expired", False)
    is_private = tt.lower() == "private" if tt else False

    pills = ""
    if dur: pills += f'<span class="pill pill-duration">🕐 {dur}</span>'
    if season == "summer": pills += '<span class="pill pill-summer">☀️ Summer</span>'
    elif season == "winter": pills += '<span class="pill pill-winter">❄️ Winter</span>'
    else: pills += '<span class="pill pill-allyear">🌍 All Year Round</span>'
    if valid_till:
        if is_expired: pills += f'<span class="pill pill-expired">⚠️ Expired {valid_till}</span>'
        else: pills += f'<span class="pill pill-valid">✓ Valid till {valid_till}</span>'

    has_map = any(get_coords(c, coords_cache) for c in cities)
    map_html = f'<div class="card-map"><div id="{map_id}" class="map-inner"></div></div>' if has_map else ''
    expired_class = " expired" if is_expired else ""

    if price:
        if is_expired:
            price_html = '<div class="price-tag" style="color:#e65100;">Check availability</div>'
        elif is_private:
            price_html = f'<div class="price-tag">From {currency}{price:,} pp (group rate)</div>'
        else:
            price_html = f'<div class="price-tag">From {currency}{price:,} pp (twin)</div>'
    else:
        price_html = ""

    return f"""<a href="{pdf_filename}" class="brochure-card{expired_class}" target="_blank">
  <div class="card-info">
    <div class="card-title">{title}</div>
    {'<div class="tour-type">' + tt + '</div>' if tt else ''}
    <div class="card-pills">{pills}</div>
    {'<div class="card-description">' + description + '</div>' if description else ''}
    {'<div class="cities-list">📍 ' + ' · '.join(cities) + '</div>' if cities else ''}
    {price_html}
  </div>
  {map_html}
</a>"""


# ── REGION CARD ───────────────────────────────────────────────────────────────

def make_region_card(slug, display_name, pkg_count, tour_types):
    types_html = ''.join(f'<span class="type-tag">{t}</span>' for t in tour_types)
    pkg_label = f"{pkg_count} package{'s' if pkg_count != 1 else ''}"
    return f"""<a href="{slug}/" class="category-card">
  <span class="arrow">→</span>
  <h2>{display_name}</h2>
  <div class="category-meta">{pkg_label}</div>
  <div class="category-types">{types_html}</div>
</a>"""


# ── INDEX BUILDERS ────────────────────────────────────────────────────────────

def build_brochure_index(title, breadcrumb, cards_html, maps_js, logo_src, logo_href, search_js):
    nav = NAV.format(lh=logo_href, ls=logo_src)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | Europe Incoming</title>
<style>{BASE_CSS}{BROCHURE_CSS}</style>
{LEAFLET_HEAD}{GA}
</head>
<body>
{GEO_BLOCK}{nav}
<div class="breadcrumb">{breadcrumb}</div>
<div class="container">
<h1>{title}</h1>
<div class="brochures" id="brochuresList">
{cards_html}
</div>
<footer><p>All packages are available for download in PDF format</p></footer>
</div>
<script src="{search_js}"></script>
<script>window.addEventListener('load',function(){{{maps_js}}});</script>
</body></html>"""

def build_multicountry_index(region_cards_html, logo_href, search_js):
    nav = NAV.format(lh=logo_href, ls=logo_href + "logo.png")
    breadcrumb = f'<a href="{logo_href}">Home</a> › Multi-City & Country Packages'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Multi-City & Country Packages | Europe Incoming</title>
<style>{BASE_CSS}{REGION_CSS}</style>
{GA}
</head>
<body>
{GEO_BLOCK}{nav}
<div class="breadcrumb">{breadcrumb}</div>
<div class="container">
<h1>Multi-City & Country Packages</h1>
<div class="categories" id="categoriesList">
{region_cards_html}
</div>
<footer><p>All packages are available for download in PDF format</p></footer>
</div>
<script src="{search_js}"></script>
</body></html>"""


# ── PACKAGES JSON ─────────────────────────────────────────────────────────────

def load_existing_packages(packages_path):
    existing = {}
    if os.path.exists(packages_path):
        with open(packages_path, 'r') as f:
            for pkg in json.load(f).get("packages", []):
                existing[pkg.get("folder", "") + "/" + pkg.get("filename", "")] = pkg
    return existing

def update_packages_json(packages_path, all_found, desc_cache):
    existing = load_existing_packages(packages_path)
    new_pkgs = []
    for item in all_found:
        key = item["folder"] + "/" + item["filename"]
        if key in existing:
            pkg = existing[key].copy()
            pkg["description"] = desc_cache.get(key, pkg.get("description", ""))
            new_pkgs.append(pkg)
        else:
            pid = re.sub(r'[^a-z0-9]', '-', item["filename"].lower().replace('.pdf', ''))[:30]
            pd = item["pdf_data"]
            new_pkgs.append({
                "id": pid, "name": item["title"], "filename": item["filename"],
                "region": item["region"], "folder": item["folder"],
                "cities": pd.get("cities", []), "duration": pd.get("duration", ""),
                "type": pd.get("tour_type", ""), "season": pd.get("season", "all-year"),
                "price_twin": pd.get("price_twin"), "currency": pd.get("currency", "€"),
                "valid_till": pd.get("valid_till"),
                "description": desc_cache.get(key, ""),
                "tags": pd.get("cities", [])
            })
    with open(packages_path, 'w') as f:
        json.dump({"packages": new_pkgs}, f, indent=2)
    print(f"  packages.json: {len(new_pkgs)} entries")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    packages_path = os.path.join(REPO_ROOT, "packages.json")
    all_found = []
    region_stats = {}
    desc_cache = {}
    coords_cache = load_coords_cache()
    coords_cache_dirty = False
    existing_pkgs = load_existing_packages(packages_path)

    for folder_rel, config in FOLDER_CONFIG.items():
        folder_abs = os.path.join(REPO_ROOT, folder_rel)
        if not os.path.isdir(folder_abs): continue
        pdfs = sorted([f for f in os.listdir(folder_abs) if f.lower().endswith('.pdf')])
        if not pdfs: continue
        print(f"\n{folder_rel} — {len(pdfs)} PDFs")

        depth = config["depth"]
        logo_src = "../" * depth + "logo.png"
        logo_href = "../" * depth
        search_js = "../" * depth + "global-search.js"
        if depth == 1:
            breadcrumb = f'<a href="../">Home</a> › {config["breadcrumb"]}'
        else:
            breadcrumb = f'<a href="../../">Home</a> › <a href="../">Multi-Country</a> › {config["breadcrumb"]}'

        cards = []
        maps_js_parts = []
        tour_types_seen = []

        for idx, pdf in enumerate(pdfs):
            print(f"  {pdf}")
            pkg_key = folder_rel + "/" + pdf
            pdf_data = extract_pdf_data(os.path.join(folder_abs, pdf), pdf)
            title = make_title(pdf)
            cached_desc = existing_pkgs.get(pkg_key, {}).get("description", None)
            desc = generate_description(
                pdf_data.get("cities", []), config["region"],
                pdf_data.get("tour_type", ""), pdf_data.get("season", "all-year"),
                os.path.join(folder_abs, pdf), cached_desc
            )
            desc_cache[pkg_key] = desc

            for city in pdf_data.get("cities", []):
                was_missing = city not in coords_cache
                get_coords(city, coords_cache)
                if was_missing and city in coords_cache:
                    coords_cache_dirty = True

            map_id = f"map_{re.sub(r'[^a-z0-9]', '_', pdf.lower()[:18])}_{idx}"
            all_found.append({
                "filename": pdf, "title": title,
                "folder": folder_rel, "region": config["region"], "pdf_data": pdf_data
            })
            cards.append(make_brochure_card(pdf, pdf_data, title, desc, map_id, coords_cache))
            js = make_map_js(map_id, pdf_data.get("cities", []), coords_cache)
            if js: maps_js_parts.append(js)
            tt = pdf_data.get("tour_type", "")
            if tt and tt not in tour_types_seen:
                tour_types_seen.append(tt)

        html = build_brochure_index(
            config["title"], breadcrumb, "\n".join(cards),
            "\n".join(maps_js_parts), logo_src, logo_href, search_js
        )
        with open(os.path.join(folder_abs, "index.html"), 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  Rebuilt {folder_rel}/index.html")

        if depth == 2:
            slug = folder_rel.replace("multi-country/", "")
            region_stats[slug] = {"count": len(pdfs), "tour_types": tour_types_seen}

    if coords_cache_dirty:
        save_coords_cache(coords_cache)
        print(f"\n  Saved updated city_coords_cache.json")

    print("\nRebuilding multi-country/index.html...")
    mc_folder = os.path.join(REPO_ROOT, "multi-country")
    if os.path.isdir(mc_folder):
        region_cards = []
        for slug, display in REGION_DISPLAY.items():
            stats = region_stats.get(slug, {"count": 0, "tour_types": []})
            if stats["count"] > 0:
                region_cards.append(make_region_card(
                    slug, display, stats["count"], stats["tour_types"]
                ))
        mc_html = build_multicountry_index(
            "\n".join(region_cards), "../", "../global-search.js"
        )
        with open(os.path.join(mc_folder, "index.html"), 'w', encoding='utf-8') as f:
            f.write(mc_html)
        print("  Rebuilt multi-country/index.html")

    print(f"\nUpdating packages.json...")
    update_packages_json(packages_path, all_found, desc_cache)
    print("\nDone!")


if __name__ == "__main__":
    main()
