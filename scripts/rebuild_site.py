"""
rebuild_site.py — v12
Fixes from v11:
- Unicode city names (Tromsø, Malmö etc) now extracted correctly
- City extraction uses \w instead of [a-zA-Z] to handle non-ASCII
- packages.json descriptions cached properly — won't regenerate if already good
- Tromsø added to SEED_COORDS
- Date parsing handles 2026/2027 future dates correctly (not marked as expired)
- Swedish Lapland: Abisko detected as second city
- Generic fallback descriptions improved per tour type
"""

import os, re, json, urllib.request, urllib.parse, time, base64, html
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
    "Valencia": [39.4699, -0.3763], "Porto": [41.1579, -8.6291],
    "Cologne": [50.9333, 6.9500], "Hamburg": [53.5753, 10.0153], "Dresden": [51.0504, 13.7373],
    "Krakow": [50.0647, 19.9450], "Warsaw": [52.2297, 21.0122], "Bratislava": [48.1486, 17.1077],
    "Ljubljana": [46.0569, 14.5058], "Dubrovnik": [42.6507, 18.0944], "Split": [43.5081, 16.4402],
    "Bruges": [51.2093, 3.2247], "Ghent": [51.0543, 3.7174], "Antwerp": [51.2194, 4.4025],
    "Rotterdam": [51.9244, 4.4777], "Luxembourg": [49.6117, 6.1319],
    "Hallstatt": [47.5622, 13.6493], "Graz": [47.0707, 15.4395],
    "Amalfi": [40.6340, 14.6025], "Positano": [40.6281, 14.4850], "Pompeii": [40.7461, 14.5019],
    "Venice Mestre": [45.4847, 12.2386],
    # Arctic / Scandinavia — explicit Unicode and ASCII variants
    "Tromso": [69.6489, 18.9551],
    "Tromsø": [69.6489, 18.9551],
    "Kiruna": [67.8558, 20.2253],
    "Abisko": [68.3493, 18.8306],
    "Narvik": [68.4385, 17.4279],
    "Alta": [69.9689, 23.2716],
    "Rovaniemi": [66.5039, 25.7294],
    "Lofoten": [68.1566, 13.9989],
    "Flam": [60.8633, 7.1159],
    "Flåm": [60.8633, 7.1159],
    "Geiranger": [62.1008, 7.2050],
    "Trondheim": [63.4305, 10.3951],
    "Akureyri": [65.6826, -18.0913],
    "Hofn": [64.2533, -15.2080],
    "Vik": [63.4189, -18.9940],
    # UK
    "Cheltenham": [51.8994, -2.0783], "Barnstaple": [51.0803, -4.0588],
    "Truro": [50.2632, -5.0510], "Plymouth": [50.3755, -4.1427],
    "Exeter": [50.7184, -3.5339], "Bournemouth": [50.7192, -1.8808],
    "Bristol": [51.4545, -2.5879], "Bath": [51.3758, -2.3599],
    "Belfast": [54.5973, -5.9301], "Aberdeen": [57.1497, -2.0943],
    "Oban": [56.4153, -5.4714], "St Andrews": [56.3398, -2.7967],
    "Dusseldorf": [51.2217, 6.7762],
    "Aix en Provence": [43.5298, 5.4475],
    "Maastricht": [50.8514, 5.6910],
}

COMPOUND_NAMES = {
    'East Europe', 'Eastern Europe', 'Western Europe', 'Central Europe', 'Western Central Europe',
    'Costa Smeralda', 'Cala Gonone', 'Fort William', 'San Sebastian', 'Czech Republic',
    'Venice Mestre', 'Isle of Skye', 'Lake District', 'Stratford upon Avon',
    'Aix en Provence',
    'Swedish Lapland',
    'Norway Nutshell',
    'Nordic Capitals',
    'Bavarian Christmas Markets',
}

# Maps cleaned destination strings to exact final display strings, bypassing smart_destination.
# Use for abbreviations, spelling corrections, and destinations whose "&" was stripped by cleanup.
DESTINATION_FIXES = {
    'MADBCN': 'Madrid & Barcelona',
    'Tromso': 'Tromsø',
    'Bavarian Austrian Christmas Markets': 'Bavarian & Austrian Christmas Markets',
}

# Full title overrides keyed on "<duration> <dest>" — replace the entire generated title.
FULL_TITLE_OVERRIDES = {
    '6 nights, 7 days Italy':   '6 nights, 7 days Classic Italy',
    '10 nights, 11 days Italy': '10 nights, 11 days Italy with Naples',
    '7 nights, 8 days France':  '7 nights, 8 days Paris with Normandy & Loire Valley',
    '8 nights, 9 days France':  '8 nights, 9 days Paris with Provence & French Riviera',
    '4 nights, 5 days Rovaniemi': '4 nights, 5 days Finnish Lapland',
    '7 nights, 8 days Rovaniemi': '7 nights, 8 days Finnish Lapland',
    '4 nights, 5 days Tromsø':  '4 nights, 5 days Northern Norway, Arctic Gateway',
    '7 nights, 8 days Tromsø':  '7 nights, 8 days Northern Norway, Arctic Gateway',
    '4 nights, 5 days Kiruna':  '4 nights, 5 days Swedish Lapland',
}

GEO_BLOCK = """<script>
(async function(){try{const r=await fetch('https://api.country.is/');const d=await r.json();
if(['US','CA','AU','NZ'].includes(d.country)){document.body.innerHTML='<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;background:#f5f5f5;text-align:center"><h1 style="font-size:48px">🌍</h1><h2>Service Not Available</h2><p style="color:#757575">This site is not available in your region.</p></div>';}
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

# ── METRO DESTINATIONS INDEX (design_handoff_metro/) ─────────────────────────
# Flat, zero-radius, no shadows; navy/gold tiles alternating every 3rd card.
# Applied site-wide: every region-listing page (city-break and multi-country)
# uses this design, whether the card links to a rich package page or a PDF.
METRO_INDEX_CSS = """
:root{--navy:#0B1733;--navy-tile:#132347;--gold:#F2B91D;--ink:#1A1D2E;--muted:#6B7080;--control-border:#D8DAE1;}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Segoe UI','Open Sans',sans-serif;color:var(--ink);font-size:15px;line-height:1.5;background:#fff;padding-top:0;}
a{color:inherit;}
.metro-header{display:flex;align-items:center;gap:28px;padding:26px 40px 0;}
.metro-logo{height:32px;width:auto;display:block;}
.metro-back-link{display:flex;align-items:center;gap:9px;font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--navy);text-decoration:none;}
.metro-back-circle{width:26px;height:26px;border:2px solid var(--navy);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:400;}
.metro-back-link:hover{color:var(--gold);}
.metro-back-link:hover .metro-back-circle{border-color:var(--gold);}
.metro-search-wrap{flex:1;max-width:360px;}
.metro-search{width:100%;padding:9px 14px;font-size:13px;font-family:'Segoe UI','Open Sans',sans-serif;border:2px solid var(--control-border);border-radius:0;background:#fff;box-sizing:border-box;outline:none;color:var(--ink);}
.metro-search::placeholder{color:var(--muted);}
.metro-trade{margin-left:auto;font-size:12px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--navy);text-decoration:none;white-space:nowrap;}
.metro-trade:hover{color:var(--gold);}
.metro-title-row{padding:36px 40px 22px;display:flex;align-items:flex-end;gap:20px;flex-wrap:wrap;}
.metro-title-row h1{font-weight:300;font-size:64px;letter-spacing:-0.02em;line-height:1;color:var(--navy);margin:0;}
.metro-eyebrow{font-size:13px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);padding-bottom:12px;}
.metro-intro{padding:0 40px 30px;max-width:640px;font-weight:300;font-size:19px;color:var(--muted);}
.metro-grid-wrap{padding:0 40px 80px;}
.metro-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:12px;}
.metro-empty{padding:80px 0;color:var(--muted);font-weight:300;font-size:22px;}
.metro-tile{display:flex;align-items:stretch;text-decoration:none;color:inherit;min-height:240px;transition:opacity 180ms linear;}
.metro-tile:hover{opacity:.86;}
.metro-tile.navy{background:var(--navy-tile);}
.metro-tile.gold{background:var(--gold);}
.metro-tile-body{flex:1;min-width:0;padding:22px 24px;display:flex;flex-direction:column;gap:8px;}
.metro-tile-meta,.metro-tile-route,.metro-tile-from,.metro-tile-note,.metro-tile-validity{font-size:11px;font-weight:700;}
.metro-tile-meta,.metro-tile-route{letter-spacing:.14em;text-transform:uppercase;}
.metro-tile-route{letter-spacing:.06em;}
.metro-tile-from,.metro-tile-validity{letter-spacing:.12em;text-transform:uppercase;}
.metro-tile-validity{font-size:10px;}
.metro-tile-note{font-weight:400;}
.metro-tile.navy .metro-tile-meta,.metro-tile.navy .metro-tile-route,.metro-tile.navy .metro-tile-from,.metro-tile.navy .metro-tile-note,.metro-tile.navy .metro-tile-validity{color:var(--gold);}
.metro-tile.gold .metro-tile-meta,.metro-tile.gold .metro-tile-route,.metro-tile.gold .metro-tile-from,.metro-tile.gold .metro-tile-note,.metro-tile.gold .metro-tile-validity{color:rgba(11,23,51,.65);}
.metro-tile-title{font-weight:300;font-size:30px;line-height:1.1;}
.metro-tile.navy .metro-tile-title{color:#fff;}
.metro-tile.gold .metro-tile-title{color:var(--navy);}
.metro-tile-blurb{font-size:13px;line-height:1.55;margin:0;}
.metro-tile.navy .metro-tile-blurb{color:rgba(255,255,255,.72);}
.metro-tile.gold .metro-tile-blurb{color:rgba(11,23,51,.8);}
.metro-tile-price-row{margin-top:auto;padding-top:10px;display:flex;align-items:baseline;gap:8px;}
.metro-tile-amount{font-weight:300;font-size:34px;line-height:1;}
.metro-tile.navy .metro-tile-amount{color:#fff;}
.metro-tile.gold .metro-tile-amount{color:var(--navy);}
.metro-tile-map-col{width:190px;flex-shrink:0;position:relative;background:#F5F5F3;}
.metro-tile-map{position:absolute;inset:0;}
.leaflet-tooltip.city-tip{background:transparent!important;border:none!important;box-shadow:none!important;font-family:'Segoe UI','Open Sans',sans-serif;font-size:9px;font-weight:600;color:var(--navy);white-space:nowrap;padding:0;text-shadow:-1px -1px 0 #fff,1px -1px 0 #fff,-1px 1px 0 #fff,1px 1px 0 #fff;}
.leaflet-tooltip.city-tip::before{display:none!important;}
.metro-expired{opacity:0.6;}
@media(max-width:900px){.metro-grid{grid-template-columns:1fr;}.metro-header{flex-wrap:wrap;}.metro-search-wrap{order:3;max-width:100%;}}
"""

# ── PACKAGE PAGE (products/*.json + prices/*.json) ───────────────────────────
# Metro design language - flat, zero-radius, no shadows, weight-contrast type.
# Print layout per design_handoff_metro's PDF Export spec, refined further in
# TestFITSTD PRs #16-#18: full-bleed navy header (assets/logo-print.png), no
# route map at print, full 4-combination rate grid, forced-open T&Cs, and the
# max-width:960px phone breakpoint restored to multi-column for print widths.
PACKAGE_PAGE_CSS = """
:root{--navy:#0B1733;--navy-tile:#132347;--gold:#F2B91D;--gold-hover:#E5AC12;
--ink:#1A1D2E;--body:#3A3D4D;--muted:#6B7080;--line:#E5E7EC;--line-light:#EFF0F3;
--control-border:#D8DAE1;--surface:#F5F5F3;--surface-hover:#EDEDEA;
--taste-bg:#F2B91D;--exp-bg:#EDEDEA;--shop-bg:#F5F5F3;}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Segoe UI','Open Sans',sans-serif;color:var(--ink);background:#fff;line-height:1.55;padding-top:56px;}
a{color:inherit;}
.pkg-wrap{max-width:1200px;margin:0 auto;padding:0 40px;}
.pkg-topbar{position:fixed;top:0;left:0;right:0;height:56px;background:#fff;border-bottom:1px solid var(--line);z-index:300;}
.pkg-topbar-inner{max-width:1200px;margin:0 auto;height:100%;padding:0 40px;display:flex;align-items:center;justify-content:space-between;gap:24px;}
.pkg-topbar-left{display:flex;align-items:center;gap:20px;}
.pkg-logo{height:24px;width:auto;display:block;}
.pkg-back-link{display:flex;align-items:center;gap:9px;font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--navy);text-decoration:none;}
.pkg-back-link .pkg-back-circle{width:26px;height:26px;border:2px solid var(--navy);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:400;}
.pkg-back-link:hover{color:var(--gold);}
.pkg-back-link:hover .pkg-back-circle{border-color:var(--gold);}
.pkg-topbar-right{display:flex;align-items:center;gap:16px;}
.pkg-trade{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;}
.pkg-trade a{color:var(--navy);text-decoration:none;}
.pkg-trade a:hover{color:var(--gold);}
.pkg-dl-btn{background:var(--navy);color:#fff;border:none;border-radius:0;padding:10px 18px;font-family:'Segoe UI','Open Sans',sans-serif;font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;cursor:pointer;white-space:nowrap;}
.pkg-dl-btn:hover{background:var(--gold);color:var(--navy);}
.pkg-title-row{padding:26px 40px 0;display:flex;align-items:flex-end;gap:18px;flex-wrap:wrap;}
.pkg-eyebrow{font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);padding-bottom:10px;}
.pkg-hero-title{font-weight:300;font-size:56px;letter-spacing:-0.02em;line-height:1;margin:0;color:var(--navy);}
.pkg-hero{padding:14px 40px 0;display:flex;gap:0;flex-wrap:wrap;}
.pkg-hero-img{flex:1;min-width:320px;min-height:380px;background:var(--navy) center/cover no-repeat;position:relative;overflow:hidden;}
.pkg-hero-facts{width:280px;flex-shrink:0;background:var(--navy);color:#fff;padding:24px 26px;display:flex;flex-direction:column;gap:14px;box-sizing:border-box;}
.pkg-hero-fact-label{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);margin-bottom:4px;}
.pkg-hero-fact-value{font-weight:300;font-size:24px;line-height:1.1;}
.pkg-hero-fact-value.small{font-size:13px;font-weight:400;color:rgba(255,255,255,.78);line-height:1.5;}
.pkg-hero-price-block{margin-top:auto;background:var(--gold);color:var(--navy);padding:14px 16px;}
.pkg-hero-price-block .pkg-hero-fact-label{color:var(--navy);margin-bottom:2px;}
.pkg-hero-price{font-weight:300;font-size:34px;line-height:1;}
.pkg-hero-price-unit{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;}
.pkg-variantbar{position:sticky;top:56px;z-index:290;background:#fff;border-bottom:1px solid var(--line);}
.pkg-variantbar-inner{max-width:1200px;margin:0 auto;padding:14px 40px;display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap;}
.pkg-variantbar-left{display:flex;align-items:center;gap:14px;flex-wrap:wrap;}
.pkg-variant-label{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);}
.pkg-pills{display:flex;gap:4px;flex-wrap:wrap;}
.pkg-pill{font-family:'Segoe UI','Open Sans',sans-serif;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;padding:8px 16px;border-radius:0;border:2px solid var(--control-border);background:transparent;color:var(--navy);cursor:pointer;}
.pkg-pill.active{background:var(--navy);color:#fff;border-color:var(--navy);}
.pkg-variant-blurb{font-size:13px;color:var(--muted);text-align:right;}
.pkg-body{max-width:1200px;margin:0 auto;padding:32px 40px 0;display:flex;gap:40px;align-items:flex-start;box-sizing:border-box;}
.pkg-main{flex:1;min-width:0;}
.pkg-sidebar{width:300px;flex-shrink:0;position:sticky;top:76px;}
.pkg-section-label{font-weight:300;font-size:34px;color:var(--navy);margin:0 0 4px;}
.pkg-section-sub{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);margin-bottom:18px;}
.pkg-section{margin-bottom:36px;}
.pkg-day{display:grid;grid-template-columns:64px 1fr;gap:20px;padding:22px 0;border-top:1px solid var(--line);}
.pkg-day-num-lbl{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);}
.pkg-day-num{font-weight:300;font-size:40px;line-height:1;color:var(--gold);}
.pkg-day-title{font-weight:600;font-size:19px;color:var(--navy);margin-bottom:2px;}
.pkg-day-overnight{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:10px;}
.pkg-day-desc{font-size:14px;line-height:1.7;color:var(--body);margin-bottom:12px;}
.pkg-pill-row{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px;margin-top:6px;}
.pkg-tag{flex-shrink:0;font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;padding:4px 10px;white-space:nowrap;}
.pkg-tag-inc{background:var(--navy);color:#fff;}
.pkg-tag-taste{background:var(--taste-bg);color:var(--navy);}
.pkg-tag-exp{background:var(--exp-bg);color:var(--navy);}
.pkg-tag-shop{background:var(--shop-bg);color:var(--muted);}
.pkg-tag-text{flex:1 1 220px;min-width:0;font-size:13px;color:var(--body);}
.pkg-inc-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 32px;}
.pkg-inc-item{font-size:13.5px;color:var(--body);padding:9px 0 9px 22px;border-bottom:1px solid var(--line-light);position:relative;}
.pkg-check{position:absolute;left:0;color:var(--gold);font-weight:700;font-size:12px;}
.pkg-hotels-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;}
.pkg-hotel-card{background:var(--surface);padding:18px 20px;}
.pkg-hotel-city{font-weight:300;font-size:22px;color:var(--navy);line-height:1.1;}
.pkg-hotel-nights{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:12px;}
.pkg-hotel-cat{font-size:10px;font-weight:700;letter-spacing:.12em;color:var(--gold);}
.pkg-hotel-name{font-size:12.5px;color:var(--body);margin-bottom:8px;line-height:1.4;}
.pkg-rate-toggles{display:flex;gap:24px;margin-bottom:16px;flex-wrap:wrap;}
.pkg-seg-group-labeled{display:flex;align-items:center;gap:10px;}
.pkg-seg-label{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);}
.pkg-seg-group{display:inline-flex;gap:4px;}
.pkg-seg{font-family:'Segoe UI','Open Sans',sans-serif;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;padding:8px 16px;border-radius:0;border:2px solid var(--control-border);background:transparent;color:var(--navy);cursor:pointer;}
.pkg-seg.active{background:var(--navy);color:#fff;border-color:var(--navy);}
.pkg-rate-table{width:100%;border-collapse:collapse;margin-bottom:8px;}
.pkg-rate-table th{background:var(--navy);color:#fff;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;text-align:left;padding:12px 16px;}
.pkg-rate-table td{padding:12px 16px;font-size:13.5px;border-bottom:1px solid var(--line-light);color:var(--ink);}
.pkg-rate-table td:last-child{text-align:right;font-weight:300;font-size:22px;color:var(--navy);}
.pkg-pax-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:8px;}
.pkg-pax-season-label{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:8px;}
.pkg-pax-table{width:100%;border-collapse:collapse;}
.pkg-pax-table th{background:var(--navy);color:#fff;font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;text-align:left;padding:8px 12px;}
.pkg-pax-table td{padding:8px 12px;font-size:13px;border-bottom:1px solid var(--line-light);}
.pkg-pax-table td:not(:first-child){text-align:right;font-weight:600;color:var(--navy);}
.pkg-rate-note{font-size:12px;color:var(--muted);}
@media(max-width:960px){.pkg-pax-grid{grid-template-columns:1fr;}}
.pkg-opt-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.pkg-opt-item{display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:13px;padding:14px 18px;background:var(--surface);}
.pkg-opt-name{color:var(--body);}
.pkg-opt-price{font-weight:300;font-size:22px;color:var(--navy);white-space:nowrap;}
.pkg-opt-price .pkg-opt-pp{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
.pkg-gtk-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.pkg-gtk-card{background:var(--navy);color:#fff;padding:18px 20px;}
.pkg-gtk-title{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);margin-bottom:6px;}
.pkg-gtk-body{font-size:13px;color:rgba(255,255,255,.8);line-height:1.6;}
.pkg-tc-btn{width:100%;display:flex;justify-content:space-between;align-items:center;background:var(--surface);border:none;border-radius:0;padding:14px 18px;font-family:'Segoe UI','Open Sans',sans-serif;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--navy);cursor:pointer;}
.pkg-tc-btn:hover{background:var(--surface-hover);}
.pkg-tc-body{display:none;padding:16px 20px;}
.pkg-tc-body.open{display:block;}
.pkg-tc-body li{font-size:12.5px;color:var(--body);padding:7px 0 7px 16px;list-style:none;border-bottom:1px solid var(--line-light);position:relative;line-height:1.55;}
.pkg-tc-body li::before{content:'\\00b7';position:absolute;left:2px;color:var(--gold);}
.pkg-sb-card{background:var(--surface);padding:20px;margin-bottom:8px;}
.pkg-sb-title{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:12px;}
.pkg-map-box{position:relative;height:180px;overflow:hidden;margin-bottom:14px;background:var(--surface);cursor:zoom-in;}
.pkg-map-box #pkgMapSmall{pointer-events:none;height:100%;}
.pkg-map-enlarge{position:absolute;right:0;bottom:0;z-index:10;background:var(--navy);color:#fff;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;padding:6px 12px;border-radius:0;cursor:zoom-in;border:none;font-family:'Segoe UI','Open Sans',sans-serif;pointer-events:none;}
.pkg-fact-row{padding:9px 0;border-top:1px solid var(--line);}
.pkg-fact-title{font-size:13px;font-weight:600;color:var(--navy);}
.pkg-fact-body{font-size:12px;color:var(--muted);margin-top:2px;}
.pkg-sb-quote{background:var(--gold);color:var(--navy);}
.pkg-sb-quote .pkg-sb-title{color:var(--navy);}
.pkg-sb-quote-body{font-size:13px;color:rgba(11,23,51,.85);margin-bottom:14px;line-height:1.6;}
.pkg-sb-quote-btn{display:block;text-align:center;width:100%;background:var(--navy);color:#fff;font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;padding:12px 0;border-radius:0;text-decoration:none;}
.pkg-sb-footer{background:var(--navy);color:rgba(255,255,255,.55);font-size:12px;padding:20px 40px;text-align:left;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;}
.pkg-sb-footer a{color:var(--gold);text-decoration:none;}
.pkg-badge-icon{background:transparent;border:none;}
.pkg-badge{background:var(--gold);color:var(--navy);text-align:center;font-weight:700;box-sizing:border-box;}
.pkg-quiet-icon{background:transparent;border:none;}
.pkg-quiet-dot{background:var(--navy);box-sizing:border-box;}
.leaflet-tooltip.pkg-map-tip{background:transparent!important;border:none!important;box-shadow:none!important;font-family:'Segoe UI','Open Sans',sans-serif;font-size:9px;font-weight:600;color:var(--navy);white-space:nowrap;padding:0!important;text-shadow:-1px -1px 0 #fff,1px -1px 0 #fff,-1px 1px 0 #fff,1px 1px 0 #fff;}
.leaflet-tooltip.pkg-map-tip::before{display:none!important;}
.pkg-map-modal{display:none;position:fixed;inset:0;background:rgba(11,23,51,.85);z-index:1000;align-items:center;justify-content:center;padding:40px;}
.pkg-map-modal.open{display:flex;}
.pkg-map-modal-panel{background:#fff;border-radius:0;width:min(960px,100%);height:min(640px,100%);display:flex;flex-direction:column;overflow:hidden;}
.pkg-map-modal-header{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;background:var(--navy);}
.pkg-map-modal-header h3{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#fff;}
.pkg-map-modal-close{background:none;border:none;font-size:16px;color:var(--gold);cursor:pointer;line-height:1;padding:6px;}
.pkg-map-modal-canvas{flex:1;}
.print-only-block{display:none;}
.pkg-rate-print-wrap{display:none;}
.pkg-rate-print{width:100%;border-collapse:collapse;margin-bottom:8px;}
.pkg-rate-print th{background:var(--navy);color:#fff;font-weight:700;text-transform:uppercase;text-align:center;border-right:1px solid rgba(255,255,255,.25);}
.pkg-rate-print th:first-child{text-align:left;}
.pkg-rate-print th:last-child{border-right:none;}
.pkg-rate-print td{border-bottom:1px solid var(--line-light);border-right:1px solid var(--line-light);color:var(--ink);text-align:right;}
.pkg-rate-print td:first-child{text-align:left;color:var(--ink);}
.pkg-rate-print td:last-child{border-right:none;}
@media(max-width:960px){
  .pkg-body{flex-direction:column;}
  .pkg-sidebar{width:100%;position:static;}
  .pkg-hero-title{font-size:38px;}
  .pkg-inc-grid,.pkg-opt-grid,.pkg-gtk-grid,.pkg-hotels-grid{grid-template-columns:1fr;}
}
@page{margin:12mm 14mm;}
@media print{
  .no-print{display:none!important;}
  .print-only-block{display:block!important;}
  .pkg-rate-print-wrap.pkg-rate-print-active{display:block!important;}
  body{padding-top:0;font-size:13px;}
  .pkg-body{display:block;padding:0;max-width:none;}
  .pkg-print-header{background:var(--navy);padding:10px 14px;margin-bottom:10px;}
  .pkg-print-header img{height:32px;width:auto;display:block;}
  .pkg-title-row{padding:0 0 4px;}
  .pkg-hero-title{font-size:26px;}
  .pkg-hero{padding:6px 0 0;}
  #pkgHeroImg{display:none!important;}
  .pkg-hero-facts{width:100%;}
  .pkg-inc-grid,.pkg-opt-grid{grid-template-columns:1fr 1fr;}
  .pkg-hotels-grid{grid-template-columns:repeat(auto-fill,minmax(150px,1fr));}
  .pkg-section{margin-bottom:14px;}
  .pkg-section-label{font-size:16px;margin:10px 0 2px;page-break-after:avoid;break-after:avoid;}
  .pkg-section-sub{margin-bottom:6px;page-break-after:avoid;break-after:avoid;}
  .pkg-day{grid-template-columns:32px 1fr;gap:10px;padding:6px 0;page-break-inside:avoid;break-inside:avoid;}
  .pkg-day-num{font-size:16px;}
  .pkg-day-title{font-size:12px;margin-bottom:1px;}
  .pkg-day-overnight{margin-bottom:3px;}
  .pkg-day-desc{font-size:10px;line-height:1.35;margin-bottom:4px;}
  .pkg-tag{font-size:8px;padding:2px 6px;}
  .pkg-tag-text{font-size:9.5px;}
  .pkg-inc-item{font-size:10px;padding:4px 0 4px 16px;}
  .pkg-hotel-card{padding:8px 10px;page-break-inside:avoid;break-inside:avoid;}
  .pkg-hotel-city{font-size:14px;}
  .pkg-hotel-nights{margin-bottom:4px;}
  .pkg-hotel-cat{font-size:9px;}
  .pkg-hotel-name{font-size:9.5px;margin-bottom:4px;}
  #pkgRateTable{display:none!important;}
  .pkg-rate-note{font-size:9px;margin:0 0 10px;}
  .pkg-rate-print th,.pkg-rate-print td{padding:6px 10px;}
  .pkg-rate-print th{font-size:8px;}
  .pkg-rate-print td{font-size:10px;}
  .pkg-opt-item{padding:8px 10px;page-break-inside:avoid;break-inside:avoid;}
  .pkg-opt-name{font-size:10.5px;}
  .pkg-opt-price{font-size:14px;}
  .pkg-tc-body{display:block!important;padding:6px 0 0;}
  .pkg-tc-btn{pointer-events:none;background:none!important;padding:0!important;font-weight:300!important;text-transform:none!important;letter-spacing:0!important;color:var(--navy)!important;page-break-after:avoid;break-after:avoid;}
  #pkgTcArrow{display:none!important;}
  .pkg-tc-body li{font-size:9px;padding:4px 0 4px 14px;page-break-inside:avoid;break-inside:avoid;}
  .pkg-sb-footer{padding:8px 0;font-size:8.5px;margin-top:10px;}
}
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

# eyebrow shown on every Metro region page — names the product line the same
# way design_handoff_metro's mockup does.
METRO_EYEBROW = "FIT Packages"


# ── COORDS CACHE ──────────────────────────────────────────────────────────────

def load_coords_cache():
    cache = dict(SEED_COORDS)
    if os.path.exists(COORDS_CACHE_PATH):
        with open(COORDS_CACHE_PATH, 'r', encoding='utf-8') as f:
            cache.update(json.load(f))
    return cache

def save_coords_cache(cache):
    to_save = {k: v for k, v in cache.items() if k not in SEED_COORDS}
    with open(COORDS_CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(to_save, f, indent=2, ensure_ascii=False)

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
    # Case-insensitive match
    city_lower = city_name.lower()
    for k, v in cache.items():
        if k.lower() == city_lower:
            return v
    # Partial match
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
    full = ' '.join(words)
    if full in COMPOUND_NAMES: return full   # exact full-phrase match wins
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
    # Pattern 1: "6 nights, 7 days Destination" — comma optional, handles "6 Nights 7 Days …" too
    m = re.search(r'(\d+)\s*nights?,?\s+(\d+)\s*days?\s+(.+)', name, re.IGNORECASE)
    if m:
        duration = f"{m.group(1)} nights, {m.group(2)} days"
        rest = m.group(3).strip()
    else:
        # Pattern 2: "Destination 6 nights[,] 7 days" — destination before duration marker
        m2 = re.search(r'(\d+)\s*nights?,?\s*(\d+)\s*days?', name, re.IGNORECASE)
        if m2:
            duration = f"{m2.group(1)} nights, {m2.group(2)} days"
            before = name[:m2.start()].strip()
            after = name[m2.end():].strip()
            rest = (before + " " + after).strip()
        else:
            # Pattern 3: "X nights / Y days" with slash
            m2b = re.search(r'(\d+)\s*nights?\s*[/]\s*(\d+)\s*days?', name, re.IGNORECASE)
            if m2b:
                duration = f"{m2b.group(1)} nights, {m2b.group(2)} days"
                before = name[:m2b.start()].strip()
                after = name[m2b.end():].strip()
                rest = (before + " " + after).strip()
            else:
                # Pattern 4: "4N" shorthand — derive days as nights+1
                m2c = re.search(r'(\d+)\s*[Nn]\b', name)
                if m2c:
                    nights = int(m2c.group(1))
                    duration = f"{nights} nights, {nights+1} days"
                    rest = (name[:m2c.start()] + name[m2c.end():]).strip()
                else:
                    m3 = re.search(r'(\d+)\s*[Dd]ays?\s+(.+)', name, re.IGNORECASE)
                    if m3:
                        duration = f"{m3.group(1)} days"
                        rest = m3.group(2).strip()
                    else:
                        return name
    rest = re.sub(r'\b(Private|Regular|Self.?[Dd]rive)\b', '', rest, flags=re.IGNORECASE)
    rest = re.sub(r'\b(Winter|Summer)\b', '', rest, flags=re.IGNORECASE)
    rest = re.sub(r'\d{4}-\d{2,4}', '', rest)
    rest = re.sub(r'Europe\s+Incoming', '', rest, flags=re.IGNORECASE)
    rest = re.sub(r'\s*&\s*', ' ', rest)
    rest = re.sub(r'-', ' ', rest)             # "England-Scotland" → "England Scotland"
    rest = re.sub(r'\s+', ' ', rest).strip().strip('-').strip()
    fixed = DESTINATION_FIXES.get(rest)
    dest = fixed if fixed is not None else smart_destination(rest.split())
    base = f"{duration} {dest}".strip()
    # Apply curated title overrides for specific packages
    if base in FULL_TITLE_OVERRIDES:
        return FULL_TITLE_OVERRIDES[base]
    return base


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

    # Detect Triple column (city break format)
    has_triple = any('Triple' in l for l in lines[max(0, ti-3):ti+3])

    ep = []
    skip_count = 0
    for l in lines[ti:ti + 50]:
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
            if val >= 200:
                ep.append(val)

    if has_triple:
        twins = ep[1::4] if len(ep) >= 4 else []
    else:
        twins = ep[1::3] if len(ep) >= 3 else ep[1:2] if len(ep) >= 2 else []

    return (min(twins), currency) if twins else (None, currency)

def extract_cities(txt):
    """
    Extract overnight cities. Uses \w to handle non-ASCII chars like ø, å, ü etc.
    Tries 'Overnight in X' first (multi-country style),
    falls back to 'Overnight X' (city break style).
    """
    # Pattern 1: "Overnight in Tromsø" — \w handles Unicode
    cities = re.findall(r'Overnight in ([\w][\w\s\-]+?)[\.\n,]', txt)
    cities = [c.strip() for c in cities if len(c.strip()) > 1]
    if not cities:
        # Pattern 2: "Overnight Amsterdam" — single word only
        cities = re.findall(r'Overnight\s+([\w]+)', txt)
    return list(dict.fromkeys(cities))[:6]

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
        # Handle "4N" or "7N" style filenames — derive days as nights+1
        d = re.search(r'(\d+)\s*[Nn](?:ights?)?\b', name)
        if d:
            nights = int(d.group(1))
            r["duration"] = f"{nights} nights / {nights+1} days"
        else:
            d2 = re.search(r'(\d+)\s*days?', name, re.IGNORECASE)
            if d2: r["duration"] = f"{d2.group(1)} days"

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
        "handpicked experiences", "curated and ready",
        "Two nights in", "history, culture and local highlights",
        "Handpicked", "your route, your pace",
        "with sightseeing, canal cruise and transfers",
    ]
    if cached_desc and not any(m in cached_desc for m in FALLBACK_MARKERS):
        print(f"    cached: {cached_desc[:60]}...")
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
                "'Dog sleds, ice art suites and Aurora hunts deep in Swedish Lapland.' "
                "'Whale watching fjords, reindeer camp dinners and Northern Lights over the water.'"
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
    # Region-specific fallbacks
    if region == "Scandinavia & Iceland":
        if "tromso" in str(cities).lower() or "tromsø" in str(cities).lower():
            return "Northern Lights, whale watching and Sámi reindeer culture in Arctic Norway."
        if "kiruna" in str(cities).lower() and "abisko" in str(cities).lower():
            return "Dog sleds, ice art suites and the Aurora Sky Station across Swedish Lapland."
        if "kiruna" in str(cities).lower():
            return "Dog sledding, ICEHOTEL and a Northern Lights chase in Swedish Lapland."
        if "rovaniemi" in str(cities).lower():
            return "Reindeer safaris, husky experiences and guaranteed Northern Lights from Santa's hometown."
        if "reykjavik" in str(cities).lower():
            return "Golden Circle, black beaches and the Blue Lagoon on Iceland's ring road."
    if not cities:
        if "self" in tt: return f"Self-drive freedom through {region} at your own pace."
        if "private" in tt: return f"Private guided {region} experience, tailored for your group."
        return f"Handpicked {region} package with curated accommodation and transfers."
    if len(cities) == 1:
        if "self" in tt: return f"Self-drive city break in {cities[0]} — explore at your own pace."
        if "private" in tt: return f"Private {cities[0]} city experience with dedicated guide and transfers."
        return f"Three days in {cities[0]} — iconic sights, local food and a city tour included."
    elif len(cities) == 2:
        if "self" in tt: return f"Self-drive from {cities[0]} to {cities[1]} — roads, views, freedom."
        if "private" in tt: return f"Private guided tour: {cities[0]} to {cities[1]} with dedicated transport."
        return f"From {cities[0]} to {cities[1]} — landmarks, local character and curated transfers."
    else:
        stops = ', '.join(cities[:-1]) + ' and ' + cities[-1]
        if "self" in tt: return f"Self-drive through {stops} — your route, your pace."
        if "private" in tt: return f"Private guided tour through {stops}."
        return f"Trains, landmarks and local character through {stops}."


# ── MAP JS ────────────────────────────────────────────────────────────────────
# Metro tile mini-map: square markers, not pins — gold for overnight stops
# (with a night count when known), muted grey-navy for pass-through/unknown-
# duration stops. Matches design_handoff_metro's route-map spec and the same
# skin used by assets/package-page.js on the package detail pages. Tile
# provider: ESRI NatGeo (free, no API key), used site-wide for card maps.

def make_metro_map_js(map_id, points, close_loop=False):
    """points: list of dicts {lat, lng, label, nights} — nights is an int
    for a known-duration overnight stop, or None/0 for a plain waypoint."""
    if not points: return ""
    pts_json = json.dumps(points)
    close_js = "true" if close_loop else "false"
    return f"""(function(){{
  var pts={pts_json};
  if(!pts.length) return;
  var lats=pts.map(function(p){{return p.lat;}}), lngs=pts.map(function(p){{return p.lng;}});
  var latSpread=Math.max.apply(null,lats)-Math.min.apply(null,lats);
  var lngSpread=Math.max.apply(null,lngs)-Math.min.apply(null,lngs);
  var spread=Math.max(latSpread,lngSpread);
  var pad=spread>5?1.2:(spread>1?0.6:0.35);
  var map=L.map('{map_id}',{{zoomControl:false,scrollWheelZoom:false,dragging:false,touchZoom:false,doubleClickZoom:false,boxZoom:false,keyboard:false,attributionControl:false}});
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{{z}}/{{y}}/{{x}}',{{maxZoom:16,attribution:''}}).addTo(map);
  map.fitBounds([[Math.min.apply(null,lats)-pad,Math.min.apply(null,lngs)-pad],[Math.max.apply(null,lats)+pad,Math.max.apply(null,lngs)+pad]],{{padding:[10,10]}});
  var route=pts.map(function(p){{return [p.lat,p.lng];}});
  if({close_js} && route.length>1) route.push(route[0]);
  if(route.length>1) L.polyline(route,{{color:'#0B1733',weight:1.5,dashArray:'4,4'}}).addTo(map);
  pts.forEach(function(p){{
    if(p.nights){{
      L.marker([p.lat,p.lng],{{icon:L.divIcon({{className:'',iconSize:[18,18],iconAnchor:[9,9],
        html:'<div style="width:18px;height:18px;background:#F2B91D;color:#0B1733;font-size:9px;font-weight:700;line-height:18px;text-align:center;box-sizing:border-box">'+p.nights+'N</div>'}})}}).addTo(map)
       .bindTooltip(p.label,{{permanent:true,direction:'top',className:'city-tip',offset:[0,-10]}});
    }} else {{
      L.marker([p.lat,p.lng],{{icon:L.divIcon({{className:'',iconSize:[10,10],iconAnchor:[5,5],
        html:'<div style="width:10px;height:10px;background:#0B1733;box-sizing:border-box"></div>'}})}}).addTo(map)
       .bindTooltip(p.label,{{permanent:true,direction:'top',className:'city-tip',offset:[0,-6]}});
    }}
  }});
}})();"""


# ── BROCHURE CARD ─────────────────────────────────────────────────────────────

def make_metro_pdf_card(pdf_filename, pdf_data, title, description, map_id, index):
    """Metro tile for a PDF-only package (no products/*.json backing it) —
    links straight to the PDF. Same navy/gold alternating skin as
    make_metro_package_card so both card types sit consistently in one grid."""
    dur = pdf_data.get("duration", "")
    cities = pdf_data.get("cities", [])
    price = pdf_data.get("price_twin")
    currency = pdf_data.get("currency", "€")
    season = pdf_data.get("season", "all-year")
    valid_till = pdf_data.get("valid_till")
    is_expired = pdf_data.get("is_expired", False)
    tt = pdf_data.get("tour_type", "")
    is_private = tt.lower() == "private" if tt else False

    season_lbl = {"winter": "Winter", "summer": "Summer"}.get(season, "All Year Round")
    meta_line = " · ".join(x for x in (dur, season_lbl) if x)
    route_html = f'<div class="metro-tile-route">{" · ".join(cities)}</div>' if cities else ""
    blurb_html = f'<p class="metro-tile-blurb">{description}</p>' if description else ""
    map_html = f'<div id="{map_id}" class="metro-tile-map"></div>' if cities else ""

    if price and not is_expired:
        note = "pp (group rate)" if is_private else "pp (twin)"
        price_html = (f'<div class="metro-tile-price-row"><span class="metro-tile-from">From</span>'
                      f'<span class="metro-tile-amount">{currency}{price:,}</span>'
                      f'<span class="metro-tile-note">{note}</span></div>')
    else:
        price_html = ""
    if valid_till:
        validity_html = (f'<div class="metro-tile-validity">{"Check availability" if is_expired else "Valid till " + valid_till}</div>')
    else:
        validity_html = ""

    variant = "gold" if index % 3 == 1 else "navy"
    expired_cls = " metro-expired" if is_expired else ""

    return f"""<a href="{pdf_filename}" class="metro-tile {variant}{expired_cls}" target="_blank">
  <div class="metro-tile-body">
    <div class="metro-tile-meta">{meta_line}</div>
    <div class="metro-tile-title">{title}</div>
    {blurb_html}
    {route_html}
    {price_html}
    {validity_html}
  </div>
  <div class="metro-tile-map-col">{map_html}</div>
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


# ── PACKAGE PAGE HELPERS (products/*.json + prices/*.json) ──────────────────

PRODUCTS_DIR = os.path.join(REPO_ROOT, "products")
PRICES_DIR = os.path.join(REPO_ROOT, "prices")

# Rate year labels shown in the package-page switcher, mapped to the
# "<id>-<suffix>.json" filename suffix under prices/. Add an entry here
# (oldest first) whenever a new season's prices file is imported.
RATE_YEARS = [("2026-27", "2027")]

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_products():
    products = []
    if not os.path.isdir(PRODUCTS_DIR):
        return products
    for fname in sorted(os.listdir(PRODUCTS_DIR)):
        if not fname.endswith(".json"): continue
        products.append(load_json(os.path.join(PRODUCTS_DIR, fname)))
    return products

def load_year_prices(product):
    """id -> {year label: prices dict} for every RATE_YEARS file that exists."""
    pid = product.get("id", "")
    by_year = {}
    for label, suffix in RATE_YEARS:
        path = os.path.join(PRICES_DIR, f"{pid}-{suffix}.json")
        if os.path.exists(path):
            by_year[label] = load_json(path)
    return by_year

def _fmt_money(val, curr):
    if val is None: return "—"
    return f"{curr}{val:,.0f}"

def _cheapest_overall(prices):
    """Cheapest twin (or, for a Min-Pax-only style, cheapest 3-star) rate
    across every travel style — used for the tile's "From" price."""
    best = None
    best_is_twin = True
    for variant in (prices.get("variants") or {}).values():
        if "paxTiers" in variant:
            for tiers in variant["paxTiers"].values():
                for tier in tiers or []:
                    val = tier.get("3star")
                    if val is not None and (best is None or val < best):
                        best, best_is_twin = val, False
        else:
            for cat_rates in variant.values():
                if not isinstance(cat_rates, dict): continue
                for row in cat_rates.values():
                    if not isinstance(row, dict): continue
                    twin = row.get("twin")
                    if twin is not None and (best is None or twin < best):
                        best, best_is_twin = twin, True
    return best, best_is_twin

def _seasons_present(prices):
    seasons = set()
    for variant in (prices.get("variants") or {}).values():
        if "paxTiers" in variant:
            seasons.update(variant["paxTiers"].keys())
        else:
            for cat_rates in variant.values():
                if isinstance(cat_rates, dict):
                    seasons.update(cat_rates.keys())
    seasons.discard("validity")
    return seasons

def _season_label(prices):
    seasons = _seasons_present(prices)
    if seasons == {"summer"}: return "Summer"
    if seasons == {"winter"}: return "Winter"
    return "All Year Round"

def _format_validity(prices):
    valid_to = (prices.get("validTo") or "").strip()
    parts = valid_to.split()
    if len(parts) >= 2:
        return f"Valid till {parts[-2]} {parts[-1]}"
    return f"Valid till {valid_to}" if valid_to else ""

def _humanize_join(words):
    words = [w for w in words if w]
    if not words: return ""
    if len(words) == 1: return words[0]
    if len(words) == 2: return f"{words[0]} and {words[1]}"
    return ", ".join(words[:-1]) + " and " + words[-1]

STYLE_PHRASE = {"trains": "train", "selfdrive": "self-drive", "private": "private coach"}

def _style_phrase(style_keys):
    phrases = [STYLE_PHRASE.get(k, k) for k in style_keys]
    if not phrases: return ""
    if len(phrases) == 1: return phrases[0]
    return ", ".join(phrases[:-1]) + " or " + phrases[-1]

def _build_blurb(product):
    stops = [p.get("label") for p in (product.get("map") or {}).get("points", [])][:3]
    stops_txt = _humanize_join(stops)
    style_txt = _style_phrase(list(product.get("styles", {}).keys()))
    if stops_txt and style_txt:
        return f"{stops_txt} — by {style_txt}."
    return stops_txt or product.get("title", "")


def render_package_page(product, prices_by_year, default_year, depth, back_href):
    """Render one static package page. depth = folder depth for relative asset
    paths. prices_by_year holds every available rate-year's prices dict, keyed
    by the RATE_YEARS label; default_year is which one is preselected."""
    root_rel = "../" * depth
    logo_src = root_rel + "logo.png"
    # PDF/print gets its own logo — a full-bleed navy header bar, since the
    # on-screen navy-block logo would be a heavy floating rectangle at print.
    print_logo_src = root_rel + "assets/logo-print.png"
    js_src = root_rel + "assets/package-page.js"
    title = product.get("title", "")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} | Europe Incoming FIT Packages</title>
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>{PACKAGE_PAGE_CSS}</style>
{LEAFLET_HEAD}{GA}
</head>
<body>
{GEO_BLOCK}
<div class="pkg-print-header print-only-block"><img src="{print_logo_src}" alt="Europe Incoming"></div>
<div class="pkg-topbar no-print"><div class="pkg-topbar-inner">
  <div class="pkg-topbar-left">
    <a href="{root_rel}"><img class="pkg-logo" src="{logo_src}" alt="Europe Incoming"></a>
    <a class="pkg-back-link" href="{back_href}"><span class="pkg-back-circle">←</span> All packages</a>
  </div>
  <div class="pkg-topbar-right">
    <div class="pkg-trade"><a href="mailto:fitsales@europeincoming.com">Trade enquiries</a></div>
    <button class="pkg-dl-btn" id="pkgDownloadBtn">Download PDF</button>
  </div>
</div></div>

<div class="pkg-title-row">
  <h1 class="pkg-hero-title" id="pkgHeroTitle"></h1>
  <div class="pkg-eyebrow" id="pkgEyebrow"></div>
</div>

<div class="pkg-hero">
  <div class="pkg-hero-img" id="pkgHeroImg"></div>
  <div class="pkg-hero-facts">
    <div>
      <div class="pkg-hero-fact-label">Duration</div>
      <div class="pkg-hero-fact-value" id="pkgHeroNights"></div>
    </div>
    <div>
      <div class="pkg-hero-fact-label">Route</div>
      <div class="pkg-hero-fact-value small" id="pkgHeroRoute"></div>
    </div>
    <div class="pkg-hero-price-block">
      <div class="pkg-hero-fact-label">From</div>
      <div class="pkg-hero-price" id="pkgHeroPrice"></div>
      <div class="pkg-hero-price-unit">per person</div>
    </div>
  </div>
</div>

<div class="pkg-variantbar no-print"><div class="pkg-variantbar-inner">
  <div class="pkg-variantbar-left">
    <div class="pkg-variant-label">Travel style</div>
    <div class="pkg-pills" id="pkgVariantPills"></div>
  </div>
  <div class="pkg-variant-blurb" id="pkgVariantBlurb"></div>
</div></div>

<div class="pkg-body">
  <div class="pkg-main">
    <div class="pkg-section">
      <div class="pkg-section-label">Day by day</div>
      <div class="pkg-section-sub" id="pkgDaySub"></div>
      <div id="pkgDays"></div>
    </div>
    <div class="pkg-section">
      <div class="pkg-section-label">Package includes</div>
      <div class="pkg-section-sub" id="pkgIncludesSub"></div>
      <div class="pkg-inc-grid" id="pkgIncludes"></div>
    </div>
    <div class="pkg-section">
      <div class="pkg-section-label" style="margin-bottom:14px">Sample hotels</div>
      <div class="pkg-hotels-grid" id="pkgHotels"></div>
    </div>
    <div class="pkg-section">
      <div class="pkg-section-label">Package rates</div>
      <div class="pkg-section-sub" id="pkgRateSub"></div>
      <div class="pkg-rate-toggles no-print">
        <div class="pkg-seg-group-labeled">
          <div class="pkg-seg-label">Rate year</div>
          <div class="pkg-seg-group" id="pkgYearToggle"></div>
        </div>
      </div>
      <div class="pkg-rate-toggles no-print" id="pkgRateToggles">
        <div class="pkg-seg-group" id="pkgCatToggle"></div>
        <div class="pkg-seg-group" id="pkgSeasonToggle"></div>
      </div>
      <table class="pkg-rate-table" id="pkgRateTable">
        <thead><tr><th>Occupancy</th><th style="text-align:right" id="pkgRateColHeading"></th></tr></thead>
        <tbody id="pkgRatesBody"></tbody>
      </table>
      <div class="pkg-pax-grid" id="pkgPaxRates"></div>
      <div class="pkg-rate-print-wrap" id="pkgRateTablePrintWrap">
        <table class="pkg-rate-print">
          <thead>
            <tr>
              <th rowspan="2">Occupancy</th>
              <th colspan="2">3 star</th>
              <th colspan="2">4 star</th>
            </tr>
            <tr><th>Apr–Oct</th><th>Nov–Mar</th><th>Apr–Oct</th><th>Nov–Mar</th></tr>
          </thead>
          <tbody id="pkgRatesPrintBody"></tbody>
        </table>
      </div>
      <div class="pkg-rate-note" id="pkgRateNote"></div>
    </div>
    <div class="pkg-section">
      <div class="pkg-section-label" style="margin-bottom:14px">Optional tours &amp; extras</div>
      <div class="pkg-opt-grid" id="pkgOptionals"></div>
    </div>
    <div class="pkg-section no-print">
      <div class="pkg-section-label" style="margin-bottom:14px">Good to know</div>
      <div class="pkg-gtk-grid" id="pkgGoodToKnow"></div>
    </div>
    <div class="pkg-section pkg-tc-wrap">
      <button class="pkg-tc-btn" id="pkgTcBtn"><span>Terms &amp; conditions</span><span id="pkgTcArrow">▼</span></button>
      <div class="pkg-tc-body" id="pkgTcBody"><ul id="pkgTerms"></ul></div>
    </div>
  </div>

  <div class="pkg-sidebar no-print">
    <div class="pkg-sb-card">
      <div class="pkg-sb-title">About this tour</div>
      <div class="pkg-map-box" id="pkgMapBox">
        <div id="pkgMapSmall" style="height:100%;"></div>
        <button class="pkg-map-enlarge" id="pkgMapEnlarge">⤢ ENLARGE</button>
      </div>
      <div class="pkg-fact-row">
        <div class="pkg-fact-title" id="pkgAboutDuration"></div>
        <div class="pkg-fact-body" id="pkgAboutRoute"></div>
      </div>
      <div id="pkgAboutFacts"></div>
    </div>
    <div class="pkg-sb-card pkg-sb-quote">
      <div class="pkg-sb-title">Ready to quote?</div>
      <div class="pkg-sb-quote-body">Get in touch with the FIT team for availability and a tailored quotation.</div>
      <a class="pkg-sb-quote-btn" href="mailto:fitsales@europeincoming.com?subject=Quote request — {title}">Email the FIT team</a>
    </div>
  </div>
</div>

<div class="pkg-sb-footer">Europe Incoming Holdings Ltd · Company Reg. England &amp; Wales 07053949 · <a href="mailto:fitsales@europeincoming.com" style="color:inherit">fitsales@europeincoming.com</a></div>

<div class="pkg-map-modal no-print" id="pkgMapModal">
  <div class="pkg-map-modal-panel">
    <div class="pkg-map-modal-header">
      <h3 id="pkgMapModalTitle"></h3>
      <button class="pkg-map-modal-close" id="pkgMapModalClose">✕</button>
    </div>
    <div class="pkg-map-modal-canvas" id="pkgMapModalCanvas"></div>
  </div>
</div>

<script>
window.PRODUCT = {json.dumps(product)};
window.PRICES_BY_YEAR = {json.dumps(prices_by_year)};
window.DEFAULT_RATE_YEAR = {json.dumps(default_year)};
</script>
<script src="{js_src}"></script>
</body></html>"""


def make_metro_package_card(product, prices, out_filename, index):
    """Metro tile for a products/*.json-backed package — links to its rich
    package detail page. Alternates navy/gold every 3rd card, per
    design_handoff_metro/README.md."""
    style_keys = list(product.get("styles", {}).keys())
    first_style = style_keys[0] if style_keys else ""
    style = product.get("styles", {}).get(first_style, {})
    price, is_twin = _cheapest_overall(prices)
    curr = prices.get("currency", "€")
    title = product.get("title", "").rstrip(".")
    points = (product.get("map") or {}).get("points", [])
    route_line = " · ".join(p.get("label", "") for p in points if p.get("label"))
    nights_label = style.get("nights", "") or ""
    season = _season_label(prices)
    validity = _format_validity(prices)
    blurb = _build_blurb(product)
    price_note = "pp (twin)" if is_twin else "pp"
    variant = "gold" if index % 3 == 1 else "navy"

    price_html = (f'<div class="metro-tile-price-row"><span class="metro-tile-from">From</span>'
                  f'<span class="metro-tile-amount">{_fmt_money(price, curr)}</span>'
                  f'<span class="metro-tile-note">{price_note}</span></div>') if price is not None else ""
    validity_html = f'<div class="metro-tile-validity">{validity}</div>' if validity else ""
    meta_line = " · ".join(x for x in (nights_label, season) if x)
    blurb_html = f'<p class="metro-tile-blurb">{blurb}</p>' if blurb else ""
    route_html = f'<div class="metro-tile-route">{route_line}</div>' if route_line else ""
    map_id = f'map_{product.get("id","").replace(".","_")}'
    map_html = f'<div id="{map_id}" class="metro-tile-map"></div>' if points else ""

    return f"""<a href="{out_filename}" class="metro-tile {variant}">
  <div class="metro-tile-body">
    <div class="metro-tile-meta">{meta_line}</div>
    <div class="metro-tile-title">{title}</div>
    {blurb_html}
    {route_html}
    {price_html}
    {validity_html}
  </div>
  <div class="metro-tile-map-col">{map_html}</div>
</a>"""


# ── INDEX BUILDERS ────────────────────────────────────────────────────────────

def build_metro_destinations_index(title, intro, cards_html, maps_js, logo_src, logo_href, hub_href, card_count):
    """Destinations Index page shell, per design_handoff_metro's mockup.
    Used site-wide for every region-listing page (city-break and each
    multi-country region), regardless of whether its cards link to a rich
    package page or straight to a PDF. hub_href points back one level up."""
    h1_title = title if not title.endswith(".") else title[:-1]
    empty_style = "display:none" if card_count else ""
    grid_style = "" if card_count else "display:none"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} | Europe Incoming FIT Packages</title>
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>{METRO_INDEX_CSS}</style>
{LEAFLET_HEAD}{GA}
</head>
<body>
{GEO_BLOCK}
<div class="metro-header">
  <a href="{logo_href}"><img class="metro-logo" src="{logo_src}" alt="Europe Incoming"></a>
  <a class="metro-back-link" href="{hub_href}"><span class="metro-back-circle">←</span> All regions</a>
  <div class="metro-search-wrap"><input type="text" class="metro-search" id="metroSearch" placeholder="search packages"></div>
  <a class="metro-trade" href="mailto:fitsales@europeincoming.com">Trade enquiries</a>
</div>

<div class="metro-title-row">
  <h1>{h1_title}</h1>
  <div class="metro-eyebrow">{METRO_EYEBROW}</div>
</div>
<div class="metro-intro">{intro}</div>

<div class="metro-grid-wrap">
  <div class="metro-grid" id="metroGrid" style="{grid_style}">{cards_html}</div>
  <div class="metro-empty" id="metroEmpty" style="{empty_style}">No packages match this search yet.</div>
</div>

<script>
(function(){{
  var input = document.getElementById('metroSearch');
  var grid = document.getElementById('metroGrid');
  var empty = document.getElementById('metroEmpty');
  var tiles = Array.prototype.slice.call(grid.querySelectorAll('.metro-tile'));
  input.addEventListener('input', function(){{
    var q = input.value.trim().toLowerCase();
    var shown = 0;
    tiles.forEach(function(t){{
      var match = !q || t.textContent.toLowerCase().indexOf(q) !== -1;
      t.style.display = match ? '' : 'none';
      if (match) shown++;
    }});
    grid.style.display = shown ? '' : 'none';
    empty.style.display = shown ? 'none' : '';
  }});
}})();
window.addEventListener('load',function(){{{maps_js}}});
</script>
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
        with open(packages_path, 'r', encoding='utf-8') as f:
            for pkg in json.load(f).get("packages", []):
                existing[pkg.get("folder", "") + "/" + pkg.get("filename", "")] = pkg
    return existing

def update_packages_json(packages_path, all_found, desc_cache, product_packages=None):
    existing = load_existing_packages(packages_path)
    new_pkgs = []
    for item in all_found:
        key = item["folder"] + "/" + item["filename"]
        if key in existing:
            pkg = existing[key].copy()
            pkg["name"] = item["title"]   # always recalculate from make_title() so fixes propagate
            pkg["description"] = desc_cache.get(key, pkg.get("description", ""))
            # Update cities/duration/price from fresh PDF extraction if they were empty
            pd = item["pdf_data"]
            if not pkg.get("cities") and pd.get("cities"):
                pkg["cities"] = pd["cities"]
            if not pkg.get("duration") and pd.get("duration"):
                pkg["duration"] = pd["duration"]
            if pd.get("price_twin") and not pkg.get("price_twin"):
                pkg["price_twin"] = pd["price_twin"]
                pkg["currency"] = pd.get("currency", "€")
            if pd.get("valid_till"):
                pkg["valid_till"] = pd["valid_till"]
                pkg["is_expired"] = pd.get("is_expired", False)
                pkg["season"] = pd.get("season", pkg.get("season", "all-year"))
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
                "valid_till": pd.get("valid_till"), "is_expired": pd.get("is_expired", False),
                "description": desc_cache.get(key, ""),
                "tags": pd.get("cities", [])
            })

    for pp in (product_packages or []):
        new_pkgs.append({
            "id": f'product-{pp["id"]}', "name": pp["name"], "filename": pp["filename"],
            "region": pp["region"], "folder": pp["folder"],
            "cities": pp["cities"], "duration": pp["duration"],
            "type": pp["type"], "season": pp["season"],
            "price_twin": pp["price_twin"], "currency": pp["currency"],
            "valid_till": pp["valid_till"], "is_expired": pp["is_expired"],
            "description": pp["description"], "tags": pp["tags"],
        })

    with open(packages_path, 'w', encoding='utf-8') as f:
        json.dump({"packages": new_pkgs}, f, indent=2, ensure_ascii=False)
    print(f"  packages.json: {len(new_pkgs)} entries")


# ── PDF ↔ PRODUCT MATCHING ────────────────────────────────────────────────────
# A products/*.json route can bundle several PDFs (Private/Regular/Self Drive
# variants of the same itinerary) under one rich package page. Match by
# (nights, primary city) rather than filename — duration alone collides
# within a region (e.g. scandinavia-iceland has three separate 4-night and
# three separate 7-night routes).

def _normalize_city(s):
    import unicodedata
    s = (s or '')
    # NFKD drops these Nordic letters entirely rather than folding them to
    # their nearest ASCII letter (e.g. "Tromsø" -> "Troms", not "Tromso").
    for a, b in (('ø','o'), ('Ø','O'), ('å','a'), ('Å','A'), ('æ','ae'), ('Æ','AE')):
        s = s.replace(a, b)
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower().strip()

def _normalize_nights(s):
    m = re.search(r'(\d+)\s*nights?', s or '', re.IGNORECASE)
    return m.group(1) if m else None

def _city_overlaps(a, b):
    """Fuzzy city match tolerant of labelling differences between the PDF's
    extraction and the product's map (e.g. PDF says "Venice Mestre", product
    map labels the stop just "Mestre")."""
    return a == b or a in b or b in a

def build_product_match_index(products, region_slug):
    """(nights) -> [(product, normalized_city_set), ...], for this region."""
    index = {}
    for product in products:
        if product.get("region") != region_slug: continue
        styles = product.get("styles", {})
        nights = None
        for style in styles.values():
            nights = _normalize_nights(style.get("nights", ""))
            if nights: break
        points = (product.get("map") or {}).get("points", [])
        if not nights or not points: continue
        city_set = [_normalize_city(p.get("label", "")) for p in points]
        index.setdefault(nights, []).append((product, city_set))
    return index

def match_pdf_to_product(pdf_data, match_index):
    """Same duration + at least one overlapping city (fuzzy-matched), picking
    the candidate with the most overlapping cities if more than one qualifies."""
    nights = _normalize_nights(pdf_data.get("duration", ""))
    pdf_cities = [_normalize_city(c) for c in pdf_data.get("cities", [])]
    if not nights or not pdf_cities: return None
    best, best_score = None, 0
    for product, city_set in match_index.get(nights, []):
        score = sum(1 for pc in pdf_cities if any(_city_overlaps(pc, cc) for cc in city_set))
        if score > best_score:
            best, best_score = product, score
    return best


# ── PDF EXPORT (products/*.json + prices/*.json → one Playwright-rendered
# PDF per travel style, matching DESIGN.md's brand spec) ─────────────────────

PDF_FOOTER_ADDRESS = "11 Turnham Green Terrace Mews, London W4 1QU, England"

PDF_SEASON_LABEL = {"summer": "APR–OCT", "winter": "NOV–MAR"}

PDF_CSS = """
:root{--navy:#0B1733;--gold:#F2B91D;--gold-50:#FEF7DC;--ink:#1A1D2E;--line:#E5E7EC;}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background:#fff;color:var(--ink);}
body{font-family:'Open Sans',sans-serif;font-size:10px;line-height:1.5;}
h1,h2,h3{margin:0;font-family:'Montserrat',sans-serif;}
.pdf-logo-band{width:100%;height:78px;background:var(--navy);display:flex;align-items:center;padding:0 32px;}
.pdf-logo-band img{height:56px;width:auto;display:block;}
.pdf-content{padding:24px 32px 32px;}
.pdf-masthead{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;}
.pdf-eyebrow{font-family:'Montserrat',sans-serif;font-weight:800;font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--navy);margin-bottom:4px;}
.pdf-title{font-weight:900;font-size:26px;letter-spacing:-0.01em;text-transform:uppercase;color:var(--navy);}
.pdf-chip{font-family:'Montserrat',sans-serif;font-weight:700;font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:#fff;background:var(--navy);padding:8px 16px;border-radius:4px;white-space:nowrap;}
.pdf-gold-rule{height:3px;background:var(--gold);margin:12px 0 16px;}
.pdf-facts{display:flex;gap:32px;margin-bottom:24px;}
.pdf-fact-label{font-family:'Montserrat',sans-serif;font-weight:800;font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink);opacity:.6;margin-bottom:4px;}
.pdf-fact-value{font-size:11px;font-weight:700;color:var(--ink);}
.pdf-section-label{font-family:'Montserrat',sans-serif;font-weight:800;font-size:16px;text-transform:uppercase;color:var(--navy);border-left:4px solid var(--gold);padding-left:12px;margin:0 0 16px;}
.pdf-subhead{font-family:'Montserrat',sans-serif;font-weight:800;font-size:13px;text-transform:uppercase;color:var(--navy);margin:0 0 12px;}
.pdf-includes-head{page-break-inside:avoid;break-inside:avoid;}
.pdf-card{background:#fff;border:1px solid var(--line);border-radius:6px;box-shadow:0 1px 2px rgba(11,23,51,.06),0 4px 10px rgba(11,23,51,.08);}
.pdf-day-columns{display:flex;gap:16px;margin-bottom:8px;}
.pdf-day-col{flex:1;display:flex;flex-direction:column;gap:16px;min-width:0;}
.pdf-day-card{padding:16px;page-break-inside:avoid;break-inside:avoid;}
.pdf-day-head{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:8px;}
.pdf-day-badge{font-family:'Montserrat',sans-serif;font-weight:800;font-size:14px;letter-spacing:.04em;color:var(--gold);text-transform:uppercase;white-space:nowrap;}
.pdf-day-title{font-family:'Montserrat',sans-serif;font-weight:700;font-size:14px;color:var(--navy);}
.pdf-day-overnight{display:inline-block;font-family:'Montserrat',sans-serif;font-weight:700;font-size:9px;letter-spacing:.06em;text-transform:uppercase;color:#fff;background:var(--navy);padding:4px 8px;border-radius:4px;margin-bottom:8px;}
.pdf-day-desc{font-size:10px;line-height:1.5;margin-bottom:8px;}
.pdf-callout{background:var(--gold-50);border-radius:4px;padding:8px 12px;font-size:10px;line-height:1.4;margin-bottom:8px;}
.pdf-callout:last-child{margin-bottom:0;}
.pdf-callout b{font-weight:700;}
.pdf-hotels-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px;}
.pdf-hotel-card{padding:12px;}
.pdf-hotel-city{font-family:'Montserrat',sans-serif;font-weight:800;font-size:11px;text-transform:uppercase;color:var(--navy);margin-bottom:2px;}
.pdf-hotel-nights{font-size:9px;color:var(--ink);opacity:.65;margin-bottom:8px;}
.pdf-hotel-tier{display:flex;gap:6px;align-items:baseline;padding-top:8px;border-top:1px solid var(--line);margin-top:8px;}
.pdf-hotel-tier:first-of-type{padding-top:0;border-top:none;margin-top:0;}
.pdf-hotel-stars{color:var(--gold);font-size:9px;white-space:nowrap;}
.pdf-hotel-name{font-weight:700;font-size:9.5px;color:var(--ink);}
.pdf-rate-note{font-size:9px;color:var(--ink);opacity:.7;margin-bottom:8px;}
.pdf-rate-table{width:100%;border-collapse:collapse;margin-bottom:16px;}
.pdf-rate-table th{background:var(--navy);color:#fff;font-family:'Montserrat',sans-serif;font-weight:700;font-size:9px;letter-spacing:.08em;text-transform:uppercase;text-align:left;padding:10px 14px;}
.pdf-rate-table td{font-size:10px;padding:10px 14px;border-bottom:1px solid var(--line);}
.pdf-rate-table tbody tr:nth-child(even){background:#FAFAFB;}
.pdf-pax-wrap{display:flex;gap:16px;}
.pdf-pax-col{flex:1;min-width:0;}
.pdf-pax-season{font-family:'Montserrat',sans-serif;font-weight:800;font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:var(--navy);margin-bottom:8px;}
.pdf-inc-row{display:flex;flex-wrap:wrap;gap:8px 32px;margin-bottom:24px;font-size:10px;}
.pdf-extras-card{padding:16px;display:flex;gap:24px;margin-bottom:24px;}
.pdf-extra-col{flex:1;min-width:0;display:flex;flex-direction:column;gap:16px;}
.pdf-extra-item{font-size:11px;line-height:1.4;}
.pdf-extra-item b{font-weight:700;}
.pdf-terms-grid{display:flex;gap:32px;margin-bottom:16px;}
.pdf-terms-col{flex:1;min-width:0;margin:0;padding-left:14px;font-size:9px;line-height:1.5;}
.pdf-terms-col li{margin-bottom:8px;page-break-inside:avoid;break-inside:avoid;}
.pdf-footer{border-top:3px solid var(--gold);padding-top:12px;}
.pdf-footer-row{display:flex;justify-content:space-between;font-size:9px;}
.pdf-footer-row a{color:inherit;}
.pdf-footer-address{text-align:center;font-size:9px;color:var(--ink);opacity:.65;margin-top:8px;}
"""


def _pdf_esc(s):
    return html.escape(str(s if s is not None else ""), quote=False)


def _pdf_split_half(items):
    half = len(items) // 2
    return items[:half], items[half:]


def _pdf_available_cats(variant):
    """Which of "3"/"4" star tiers have any real (non-null) rate anywhere -
    mirrors assets/package-page.js's availableCats() so the PDF never shows
    an unpriced tier."""
    cats = []
    for cat in ("3", "4"):
        row = variant.get(cat) or {}
        for season_row in row.values():
            if isinstance(season_row, dict) and any(v is not None for v in season_row.values()):
                cats.append(cat)
                break
    return cats


def _pdf_available_seasons(cat_row):
    return [s for s in ("summer", "winter")
            if isinstance(cat_row.get(s), dict) and any(v is not None for v in cat_row[s].values())]


def _pdf_priced_star_tiers(variant):
    """Which of "3"/"4" star tiers are actually priced for this variant,
    whichever shape it is (season/cat table, or Min-Pax paxTiers) - used to
    decide which hotel-tier rows to show, since a Min-Pax style has no "3"/"4"
    keys of its own."""
    if "paxTiers" in variant:
        all_tiers = [t for tiers in variant["paxTiers"].values() for t in tiers]
        cats = []
        if any(t.get("3star") is not None for t in all_tiers):
            cats.append("3")
        if any(t.get("4star") is not None for t in all_tiers):
            cats.append("4")
        return cats
    return _pdf_available_cats(variant)


def _pdf_validity_text(prices):
    return f"{prices.get('validFrom', '')} – {prices.get('validTo', '')}"


def _pdf_day_callouts(day, style):
    callouts = []
    transport = (style.get("transport") or {}).get(str(day.get("num")))
    if transport:
        callouts.append(("Included", transport))
    if day.get("taste"):
        callouts.append(("Local taste", day["taste"]))
    if day.get("experience"):
        callouts.append(("Local experience", day["experience"]))
    return callouts


def _pdf_day_card_html(day, style):
    callouts_html = "".join(
        f'<div class="pdf-callout"><b>{_pdf_esc(label)}</b> {_pdf_esc(text)}</div>'
        for label, text in _pdf_day_callouts(day, style)
    )
    return f"""<div class="pdf-card pdf-day-card">
<div class="pdf-day-head"><span class="pdf-day-badge">DAY {_pdf_esc(day.get('num'))}</span><span class="pdf-day-title">{_pdf_esc(day.get('title'))}</span></div>
<div class="pdf-day-overnight">{_pdf_esc(day.get('overnight', ''))}</div>
<div class="pdf-day-desc">{_pdf_esc(day.get('desc', ''))}</div>
{callouts_html}</div>"""


def _pdf_days_columns_html(product, style):
    left, right = _pdf_split_half(product.get("days", []))
    left_html = "".join(_pdf_day_card_html(d, style) for d in left)
    right_html = "".join(_pdf_day_card_html(d, style) for d in right)
    return f'<div class="pdf-day-columns"><div class="pdf-day-col">{left_html}</div><div class="pdf-day-col">{right_html}</div></div>'


def _pdf_hotel_tiers(hotel, variant):
    cats = _pdf_priced_star_tiers(variant)
    tiers = []
    if "3" in cats and hotel.get("h3"):
        tiers.append(("★★★", hotel["h3"]))
    if "4" in cats and hotel.get("h4"):
        tiers.append(("★★★★", hotel["h4"]))
    return tiers


def _pdf_hotels_grid_html(product, variant):
    cards = []
    for hotel in product.get("hotels", []):
        tiers = _pdf_hotel_tiers(hotel, variant)
        if not tiers:
            continue
        rows = "".join(
            f'<div class="pdf-hotel-tier"><span class="pdf-hotel-stars">{stars}</span><span class="pdf-hotel-name">{_pdf_esc(name)}</span></div>'
            for stars, name in tiers
        )
        cards.append(f"""<div class="pdf-card pdf-hotel-card">
<div class="pdf-hotel-city">{_pdf_esc(hotel.get('city', ''))}</div>
<div class="pdf-hotel-nights">{_pdf_esc(hotel.get('nights', ''))}</div>
{rows}</div>""")
    return "".join(cards)


def _pdf_season_rates_html(prices, style, variant):
    currency = prices.get("currency", "€")
    validity_text = _pdf_validity_text(prices)
    tables = []
    for cat in _pdf_available_cats(variant):
        cat_row = variant.get(cat, {})
        seasons = _pdf_available_seasons(cat_row)
        stars = "★" * int(cat)
        header_cols = "".join(f"<th>{PDF_SEASON_LABEL[s]}</th>" for s in seasons)

        def cell(occ, seasons=seasons, cat_row=cat_row):
            return "".join(f"<td>{_fmt_money(cat_row.get(s, {}).get(occ), currency)}</td>" for s in seasons)

        tables.append(f"""<div class="pdf-rate-note">Per person · {_pdf_esc(style.get('name', ''))} · {stars} accommodation · Valid {validity_text}</div>
<table class="pdf-rate-table">
<thead><tr><th>Occupancy</th>{header_cols}</tr></thead>
<tbody>
<tr><td>Single</td>{cell('single')}</tr>
<tr><td>Twin / Double</td>{cell('twin')}</tr>
<tr><td>Child (2–11)</td>{cell('child')}</tr>
</tbody></table>""")
    return "".join(tables)


def _pdf_paxtiers_rates_html(prices, style, variant):
    currency = prices.get("currency", "€")
    validity_text = _pdf_validity_text(prices)
    pax_tiers = variant.get("paxTiers", {})
    seasons = [s for s in ("winter", "summer") if pax_tiers.get(s)]
    all_tiers = [t for s in seasons for t in pax_tiers.get(s, [])]
    cols = [(key, label) for key, label in (("3star", "3★ per adult"), ("4star", "4★ per adult"))
            if any(t.get(key) is not None for t in all_tiers)]

    def season_table(season):
        header = "".join(f"<th>{label}</th>" for _, label in cols)
        rows = "".join(
            "<tr><td>{}</td>{}</tr>".format(
                t.get("pax"),
                "".join(f"<td>{_fmt_money(t.get(key), currency)}</td>" for key, _ in cols)
            )
            for t in pax_tiers.get(season, [])
        )
        return f'<div class="pdf-pax-col"><div class="pdf-pax-season">{PDF_SEASON_LABEL[season]}</div><table class="pdf-rate-table"><thead><tr><th>Min Pax</th>{header}</tr></thead><tbody>{rows}</tbody></table></div>'

    tables = "".join(season_table(s) for s in seasons)
    return f'<div class="pdf-rate-note">Per person · {_pdf_esc(style.get("name", ""))} · Valid {validity_text}</div><div class="pdf-pax-wrap">{tables}</div>'


def _pdf_rates_html(prices, style, variant):
    if "paxTiers" in variant:
        return _pdf_paxtiers_rates_html(prices, style, variant)
    return _pdf_season_rates_html(prices, style, variant)


def _load_logo_data_uri():
    path = os.path.join(REPO_ROOT, "assets", "logo-print.png")
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")


def build_pdf_html(product, prices, style_key, logo_data_uri):
    style = product["styles"][style_key]
    variant = (prices.get("variants") or {}).get(style_key, {})
    currency = prices.get("currency", "€")

    extras = prices.get("optionalTours") or []
    extras_section = ""
    if extras:
        left_extras, right_extras = _pdf_split_half(extras)

        def extra_item(e):
            return f'<div class="pdf-extra-item">{_pdf_esc(e.get("name", ""))} — <b>{_fmt_money(e.get("price"), currency)} pp</b></div>'

        extras_section = f"""<div class="pdf-section-label">OPTIONAL TOURS &amp; EXTRAS</div>
<div class="pdf-card pdf-extras-card">
<div class="pdf-extra-col">{"".join(extra_item(e) for e in left_extras)}</div>
<div class="pdf-extra-col">{"".join(extra_item(e) for e in right_extras)}</div>
</div>"""

    left_terms, right_terms = _pdf_split_half(product.get("terms") or [])
    inclusions_html = "".join(
        f'<div class="pdf-inc-item">✓ {_pdf_esc(t)}</div>' for t in style.get("inclusions", [])
    )

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800;900&family=Open+Sans:wght@400;700&display=swap" rel="stylesheet">
<style>{PDF_CSS}</style>
</head><body>
<div class="pdf-logo-band"><img src="{logo_data_uri}" alt="Europe Incoming"></div>
<div class="pdf-content">
<div class="pdf-masthead">
<div><div class="pdf-eyebrow">{_pdf_esc((product.get('eyebrow') or '').upper())}</div><h1 class="pdf-title">{_pdf_esc(product.get('title', ''))}</h1></div>
<div class="pdf-chip">{_pdf_esc(style.get('name', ''))}</div>
</div>
<div class="pdf-gold-rule"></div>
<div class="pdf-facts">
<div><div class="pdf-fact-label">Duration</div><div class="pdf-fact-value">{_pdf_esc(style.get('nights', ''))}</div></div>
<div><div class="pdf-fact-label">Route</div><div class="pdf-fact-value">{_pdf_esc(style.get('route', ''))}</div></div>
</div>

<div class="pdf-section-label">Day by Day</div>
{_pdf_days_columns_html(product, style)}

<div class="pdf-includes-head">
<div class="pdf-section-label">Package Includes — {_pdf_esc(style.get('name', '').upper())}</div>
<div class="pdf-subhead">Sample Hotels</div>
<div class="pdf-hotels-grid">{_pdf_hotels_grid_html(product, variant)}</div>
</div>

<div class="pdf-subhead">Package Rates</div>
{_pdf_rates_html(prices, style, variant)}
<div class="pdf-inc-row">{inclusions_html}</div>

{extras_section}
<div class="pdf-section-label">Terms &amp; Conditions</div>
<div class="pdf-terms-grid">
<ul class="pdf-terms-col">{"".join(f"<li>{_pdf_esc(t)}</li>" for t in left_terms)}</ul>
<ul class="pdf-terms-col">{"".join(f"<li>{_pdf_esc(t)}</li>" for t in right_terms)}</ul>
</div>

<div class="pdf-footer">
<div class="pdf-footer-row"><div>Europe Incoming Holdings Ltd · Company Reg. England &amp; Wales 07053949</div><div><a href="mailto:fitsales@europeincoming.com">fitsales@europeincoming.com</a></div></div>
<div class="pdf-footer-address">{PDF_FOOTER_ADDRESS}</div>
</div>
</div>
</body></html>"""


def generate_pdfs(jobs):
    """jobs: [(product, prices, style_key, out_path), ...]. One headless-Chromium
    launch shared across every package/style PDF for speed."""
    if not jobs:
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\nSkipping PDF export: playwright not installed (pip install playwright && playwright install chromium)")
        return

    logo_data_uri = _load_logo_data_uri()
    print(f"\nGenerating {len(jobs)} package PDFs...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            # Some sandboxes only ship the full "chromium" binary, not the
            # headless_shell variant Playwright launches by default.
            sandbox_chromium = "/opt/pw-browsers/chromium"
            if not os.path.exists(sandbox_chromium):
                raise
            browser = p.chromium.launch(executable_path=sandbox_chromium)
        page = browser.new_page()
        for product, prices, style_key, out_path in jobs:
            page.set_content(build_pdf_html(product, prices, style_key, logo_data_uri), wait_until="networkidle")
            page.pdf(path=out_path, format="Letter", print_background=True,
                     margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
            print(f"  ✓ {os.path.relpath(out_path, REPO_ROOT)}")
        browser.close()


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    packages_path = os.path.join(REPO_ROOT, "packages.json")
    all_found = []
    product_packages = []
    pdf_jobs = []
    region_stats = {}
    desc_cache = {}
    coords_cache = load_coords_cache()
    coords_cache_dirty = False
    existing_pkgs = load_existing_packages(packages_path)
    products = load_products()

    for folder_rel, config in FOLDER_CONFIG.items():
        folder_abs = os.path.join(REPO_ROOT, folder_rel)
        if not os.path.isdir(folder_abs): continue
        pdfs = sorted([f for f in os.listdir(folder_abs) if f.lower().endswith('.pdf')])

        depth = config["depth"]
        region_slug = folder_rel.replace("multi-country/", "") if depth == 2 else "city-break"
        match_index = build_product_match_index(products, region_slug)
        # A region with zero PDFs left (every route superseded by a product
        # page) still needs rebuilding — don't skip it.
        if not pdfs and not any(p.get("region") == region_slug for p in products):
            continue
        region_products = sorted(
            (p for p in products if p.get("region") == region_slug),
            key=lambda p: p.get("id", "")
        )
        covered_product_ids = set()

        print(f"\n{folder_rel} — {len(pdfs)} PDFs, {len(region_products)} products")

        logo_src = "../" * depth + "logo.png"
        logo_href = "../" * depth
        search_js = "../" * depth + "global-search.js"
        hub_href = "../" if depth == 2 else "../"
        if depth == 1:
            breadcrumb = f'<a href="../">Home</a> › {config["breadcrumb"]}'
        else:
            breadcrumb = f'<a href="../../">Home</a> › <a href="../">Multi-Country</a> › {config["breadcrumb"]}'

        pdf_cards = []
        maps_js_parts = []
        tour_types_seen = []

        for idx, pdf in enumerate(pdfs):
            print(f"  {pdf}")
            pkg_key = folder_rel + "/" + pdf
            pdf_data = extract_pdf_data(os.path.join(folder_abs, pdf), pdf)
            title = make_title(pdf)

            for city in pdf_data.get("cities", []):
                was_missing = city not in coords_cache
                get_coords(city, coords_cache)
                if was_missing and city in coords_cache:
                    coords_cache_dirty = True

            matched = match_pdf_to_product(pdf_data, match_index)
            if matched:
                # Superseded by a rich package page — no separate PDF card or
                # packages.json entry (that would duplicate the same route).
                covered_product_ids.add(matched.get("id"))
                tt = pdf_data.get("tour_type", "")
                if tt and tt not in tour_types_seen:
                    tour_types_seen.append(tt)
                continue

            cached_desc = existing_pkgs.get(pkg_key, {}).get("description", None)
            desc = generate_description(
                pdf_data.get("cities", []), config["region"],
                pdf_data.get("tour_type", ""), pdf_data.get("season", "all-year"),
                os.path.join(folder_abs, pdf), cached_desc
            )
            desc_cache[pkg_key] = desc

            map_id = f"map_{re.sub(r'[^a-z0-9]', '_', pdf.lower()[:18])}_{idx}"
            all_found.append({
                "filename": pdf, "title": title,
                "folder": folder_rel, "region": config["region"], "pdf_data": pdf_data
            })
            points = [{"lat": c[0], "lng": c[1], "label": city, "nights": None}
                      for city in pdf_data.get("cities", [])
                      for c in [get_coords(city, coords_cache)] if c]
            js = make_metro_map_js(map_id, points)
            if js: maps_js_parts.append(js)
            pdf_cards.append((title, pdf, pdf_data, desc, map_id))

            tt = pdf_data.get("tour_type", "")
            if tt and tt not in tour_types_seen:
                tour_types_seen.append(tt)

        # ── Package pages for products in this region ────────────────────────
        product_cards = []
        for product in region_products:
            prices_by_year = load_year_prices(product)
            if not prices_by_year:
                print(f"  WARNING: no prices file for product {product.get('id')}, skipping")
                continue
            default_year = RATE_YEARS[-1][0] if RATE_YEARS[-1][0] in prices_by_year else next(iter(prices_by_year))
            prices = prices_by_year[default_year]

            brochure_fname = f'{product.get("id")}_brochure.html'
            page_html = render_package_page(product, prices_by_year, default_year, depth, back_href="./")
            with open(os.path.join(folder_abs, brochure_fname), 'w', encoding='utf-8') as f:
                f.write(page_html)
            print(f"  ✓ {folder_rel}/{brochure_fname}")

            # Written to a "pdf/" subfolder, not next to the brochure HTML -
            # the legacy PDF-package auto-discovery below only scans folder_abs
            # itself, so a generated download PDF sitting there directly would
            # get mistaken for its own standalone PDF-brochure package (its
            # duration/cities can't be parsed out of this styled layout, so it
            # never matches back to the product it belongs to).
            pdf_dir = os.path.join(folder_abs, "pdf")
            os.makedirs(pdf_dir, exist_ok=True)
            for style_key in product.get("styles", {}):
                pdf_out = os.path.join(pdf_dir, f'{product.get("id")}-{style_key}.pdf')
                pdf_jobs.append((product, prices, style_key, pdf_out))

            product_cards.append((product, prices, brochure_fname))

            product_map = product.get("map") or {}
            map_id = f'map_{product.get("id","").replace(".","_")}'
            js = make_metro_map_js(map_id, product_map.get("points", []), product_map.get("closeLoop", False))
            if js: maps_js_parts.append(js)

            for style in product.get("styles", {}).values():
                name = style.get("name", "")
                if name and name not in tour_types_seen:
                    tour_types_seen.append(name)

            price, is_twin = _cheapest_overall(prices)
            points = product_map.get("points", [])
            product_packages.append({
                "id": product.get("id"), "name": product.get("title", "").rstrip("."),
                "filename": brochure_fname, "region": config["region"], "folder": folder_rel,
                "cities": [p.get("label") for p in points if p.get("label")],
                "duration": next((s.get("nights") for s in product.get("styles", {}).values()), ""),
                "type": "; ".join(s.get("name", "") for s in product.get("styles", {}).values()),
                "season": _season_label(prices),
                "price_twin": price, "currency": prices.get("currency", "€"),
                "valid_till": _format_validity(prices).replace("Valid till ", ""),
                "is_expired": False,
                "description": _build_blurb(product),
                "tags": [p.get("label") for p in points if p.get("label")],
            })

        # ── Combine cards into one Metro destinations index ──────────────────
        combined_cards = []
        index = 0
        for product, prices, brochure_fname in product_cards:
            combined_cards.append(make_metro_package_card(product, prices, brochure_fname, index))
            index += 1
        for title, pdf, pdf_data, desc, map_id in pdf_cards:
            combined_cards.append(make_metro_pdf_card(pdf, pdf_data, title, desc, map_id, index))
            index += 1

        intro = f"FIT packages across {config['region']} — self drive, rail and private coach."
        html = build_metro_destinations_index(
            config["title"], intro, "\n".join(combined_cards),
            "\n".join(maps_js_parts), logo_src, logo_href, hub_href, len(combined_cards)
        )
        with open(os.path.join(folder_abs, "index.html"), 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  Rebuilt {folder_rel}/index.html ({len(combined_cards)} packages)")

        if depth == 2:
            region_stats[region_slug] = {"count": len(combined_cards), "tour_types": tour_types_seen}

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
    update_packages_json(packages_path, all_found, desc_cache, product_packages)

    generate_pdfs(pdf_jobs)

    print("\nDone!")


if __name__ == "__main__":
    main()
