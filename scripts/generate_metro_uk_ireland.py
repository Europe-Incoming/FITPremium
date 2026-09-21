#!/usr/bin/env python3
"""
Generate Metro-design UK & Ireland package pages from Excel pricing + PDF brochures.
Outputs:
  multi-country/uk-ireland/products/{slug}.json
  multi-country/uk-ireland/prices/{slug}.json
  multi-country/uk-ireland/products/index.json
  multi-country/uk-ireland/index.html        (Metro card grid)
  multi-country/uk-ireland/package.html      (Metro package detail template)
"""

import os, re, json, sys
from datetime import datetime
from pathlib import Path

try:
    import fitz
except ImportError:
    import pymupdf as fitz

try:
    import openpyxl
except ImportError:
    print("pip install openpyxl pymupdf"); sys.exit(1)

EXCEL = Path('/root/.claude/uploads/2f514f63-9d8f-551c-b5b8-bd8293070bf9/fd7bfc7d-packages_2026-27.xlsx')
OUT_DIR = Path('/home/user/FITPremium/multi-country/uk-ireland')
# Source brochure PDFs live in a subfolder (not the top level of OUT_DIR) so
# rebuild_site.py's legacy os.listdir(folder)-based PDF auto-discovery never
# sees them and never overwrites this folder's Metro index.html/package.html.
PDF_DIR = OUT_DIR / 'source-pdfs'

wb = openpyxl.load_workbook(str(EXCEL), data_only=True)

# ─── Hardcoded coordinates for UK/Ireland cities ─────────────────────────────
CITY_COORDS = {
    'London':     {'lat': 51.5074,  'lng': -0.1278},
    'Manchester': {'lat': 53.4808,  'lng': -2.2426},
    'Edinburgh':  {'lat': 55.9533,  'lng': -3.1883},
    'Glasgow':    {'lat': 55.8642,  'lng': -4.2518},
    'Inverness':  {'lat': 57.4778,  'lng': -4.2247},
    'Fort William':{'lat': 56.8201, 'lng': -5.1057},
    'Dublin':     {'lat': 53.3498,  'lng': -6.2603},
    'Limerick':   {'lat': 52.6638,  'lng': -8.6267},
    'Bath':       {'lat': 51.3781,  'lng': -2.3597},
    'Cheltenham': {'lat': 51.8994,  'lng': -2.0783},
    'Exeter':     {'lat': 50.7184,  'lng': -3.5339},
    'Plymouth':   {'lat': 50.3755,  'lng': -4.1427},
    'Truro':      {'lat': 50.2632,  'lng': -5.0510},
    'Barnstaple': {'lat': 51.0826,  'lng': -4.0586},
    'Bournemouth':{'lat': 50.7192,  'lng': -1.8808},
    'Cliffs of Moher':{'lat': 52.9715,'lng': -9.4262},
    'Killarney':  {'lat': 52.0599,  'lng': -9.5044},
    'Kilkenny':   {'lat': 52.6541,  'lng': -7.2448},
}

# ─── Excel extraction ─────────────────────────────────────────────────────────

def read_rows(ws, max_row=130):
    rows = []
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=max_row, values_only=True), 1):
        rows.append((i, list(row)))
    return rows

def fmt_date(v):
    if isinstance(v, datetime): return v.strftime('%d %b %Y')
    return str(v) if v else ''

def safe_round(v):
    try: return round(float(v)) if v is not None else None
    except: return None

def has_marker(vals, marker):
    return any(isinstance(v, str) and marker in v for v in vals)

def extract_season_block(rows, start_idx, end_idx):
    start_col = header_idx = None
    for k in range(start_idx, min(end_idx, len(rows))):
        vals = rows[k][1]
        for ci, v in enumerate(vals):
            if isinstance(v, str) and v.strip() == 'Start':
                start_col, header_idx = ci, k
                break
        if header_idx is not None: break
    if header_idx is None: return []
    results = []
    for k in range(header_idx+1, min(end_idx, len(rows))):
        vals = rows[k][1]
        s = vals[start_col] if start_col < len(vals) else None
        if not isinstance(s, datetime): continue
        row = {
            'start': fmt_date(s),
            'end': fmt_date(vals[start_col+1] if start_col+1 < len(vals) else None),
            's3': safe_round(vals[start_col+2] if start_col+2 < len(vals) else None),
            't3': safe_round(vals[start_col+3] if start_col+3 < len(vals) else None),
            'c3': safe_round(vals[start_col+4] if start_col+4 < len(vals) else None),
            's4': safe_round(vals[start_col+5] if start_col+5 < len(vals) else None),
            't4': safe_round(vals[start_col+6] if start_col+6 < len(vals) else None),
            'c4': safe_round(vals[start_col+7] if start_col+7 < len(vals) else None),
        }
        if row['t3'] and row['t3'] > 0: results.append(row)
    return results

def extract_minpax_block(rows, start_idx, end_idx):
    pax_col = header_idx = None
    for k in range(start_idx, min(end_idx, len(rows))):
        vals = rows[k][1]
        for ci, v in enumerate(vals):
            if isinstance(v, str) and v.strip() == 'Min Pax':
                pax_col, header_idx = ci, k
                break
        if header_idx is not None: break
    if header_idx is None: return []
    results = []
    for k in range(header_idx+1, min(end_idx, len(rows))):
        vals = rows[k][1]
        pax = vals[pax_col] if pax_col < len(vals) else None
        if not isinstance(pax, (int, float)): continue
        row = {
            'pax': int(pax),
            'w3': safe_round(vals[pax_col+1] if pax_col+1 < len(vals) else None),
            'w4': safe_round(vals[pax_col+2] if pax_col+2 < len(vals) else None),
            's3': safe_round(vals[pax_col+3] if pax_col+3 < len(vals) else None),
            's4': safe_round(vals[pax_col+4] if pax_col+4 < len(vals) else None),
        }
        if row['w3'] and row['w3'] > 0: results.append(row)
    return results

def extract_excel_hotels(ws_name):
    """Extract hotel names from the Component - Hotels section."""
    ws = wb[ws_name]
    rows = read_rows(ws, max_row=20)
    hotels = []
    for rnum, vals in rows:
        b = vals[1] if len(vals) > 1 else None
        if not isinstance(b, str): continue
        if 'Component - Hotels' in b: continue
        # Format: "N nights City - H3 | H4"
        m = re.match(r'(\d+)\s*nights?\s+([^-,]+?)\s*[,–-]\s*(.+)', b, re.IGNORECASE)
        if m:
            nights_n = int(m.group(1))
            city = m.group(2).strip()
            hotels_raw = m.group(3).strip()
            parts = [p.strip() for p in hotels_raw.split('|') if p.strip()]
            h3 = parts[0] if len(parts) > 0 else hotels_raw
            h4 = parts[1] if len(parts) > 1 else ''
            hotels.append({'city': city, 'nights': f'{nights_n} Night{"s" if nights_n != 1 else ""}', 'h3': h3, 'h4': h4})
    return hotels

def extract_optional_tours_excel(ws_name):
    """Extract optional tours from Excel sheet."""
    ws = wb[ws_name]
    rows = read_rows(ws, max_row=60)
    tours = []
    in_optional = False
    for rnum, vals in rows:
        b = vals[1] if len(vals) > 1 else None
        c = vals[2] if len(vals) > 2 else None
        if isinstance(b, str) and b.strip() == 'Optional': in_optional = True; continue
        if in_optional and isinstance(b, str) and b.strip() and isinstance(c, (int, float)):
            tours.append({'name': b.strip(), 'price': round(float(c), 2)})
    return tours

def extract_premium_pricing(ws_name, genuine_styles):
    """Extract Premium Market rates for specified styles."""
    ws = wb[ws_name]
    rows = read_rows(ws, max_row=130)
    n = len(rows)

    currency = 'EUR'
    for _, vals in rows[:15]:
        for v in vals:
            if isinstance(v, str) and v.strip() == 'GBP': currency = 'GBP'

    result = {'currency': currency}

    # Build boundary map
    boundaries = []
    for idx, (rnum, vals) in enumerate(rows):
        row_str = ' '.join(str(v) for v in vals if v is not None)
        if 'Component - Regular FIT' in row_str: boundaries.append((idx, 'regular_header'))
        if 'Component - Private tour' in row_str: boundaries.append((idx, 'private_header'))
        if 'Component - Self Drive' in row_str: boundaries.append((idx, 'selfdrive_header'))
        if 'PREMIUM MARKET' in row_str and 'STANDARD MARKET' not in row_str:
            boundaries.append((idx, 'premium'))
        if 'STANDARD MARKET' in row_str and 'PREMIUM MARKET' not in row_str:
            boundaries.append((idx, 'standard'))
        if 'PREMIUM MARKET' in row_str and 'STANDARD MARKET' in row_str:
            boundaries.append((idx, 'private_both'))

    # Regular FIT
    if 'regular' in genuine_styles:
        reg_p = reg_s = None
        for idx, label in boundaries:
            if label == 'premium' and reg_p is None:
                nb = next((b for b in boundaries if b[0] > idx), None)
                if nb and nb[1] == 'regular_header': reg_p = idx
            if label == 'standard' and reg_p is not None and reg_s is None: reg_s = idx
        if reg_p is not None:
            end = reg_s if reg_s else reg_p + 15
            result['regular'] = extract_season_block(rows, reg_p, end)

    # Private (Min-Pax)
    if 'private' in genuine_styles:
        pb = next((idx for idx, label in boundaries if label == 'private_both'), None)
        if pb is not None:
            ns = next((idx for idx, label in boundaries if idx > pb and label in ('premium', 'selfdrive_header')), n)
            result['private'] = extract_minpax_block(rows, pb, ns)

    # Self Drive
    if 'selfdrive' in genuine_styles:
        sd = next((idx for idx, label in boundaries if label == 'selfdrive_header'), None)
        if sd is not None:
            sds = next((idx for idx, label in boundaries if idx > sd and label == 'standard'), n)
            result['selfdrive'] = extract_season_block(rows, sd, sds)

    return result

# ─── PDF extraction ───────────────────────────────────────────────────────────

FOOTER_BOILERPLATE_RE = re.compile(
    r'Turnham Green Terrace Mews|FITsales@europeincoming\.com|'
    r'^Web:\s*www\.europeincoming\.com|Please review general T&C',
    re.IGNORECASE,
)

BULLET_CHARS = ('•', '·', '●', '○', '-')


def merge_bulleted_lines(section_lines):
    """The PDF text extracts each bullet marker as its own line, with the
    item's text wrapping across the following lines until the next bullet
    marker. Reassemble those into one string per bullet item."""
    items = []
    for line in section_lines:
        if FOOTER_BOILERPLATE_RE.search(line):
            continue
        if line in BULLET_CHARS:
            items.append('')
            continue
        stripped = line
        starts_new = False
        for ch in BULLET_CHARS:
            if stripped.startswith(ch + ' ') or stripped == ch:
                stripped = stripped[len(ch):].strip()
                starts_new = True
                break
        if starts_new or not items:
            items.append(stripped)
        else:
            items[-1] = f'{items[-1]} {stripped}'.strip()
    return [i.strip() for i in items if i.strip() and len(i.strip()) > 3]


def extract_pdf_full(pdf_path):
    """Extract day-by-day, includes, hotels, terms, optional tours from PDF."""
    doc = fitz.open(str(pdf_path))
    txt = "\n".join(p.get_text() for p in doc)
    lines = [l.strip() for l in txt.split('\n') if l.strip()]

    days = []
    includes = []
    sample_tours = []
    hotels = []
    terms = []

    # ── Day-by-day ──
    day_pat = re.compile(r'^Day\s+(\d+)[,\.\s]+(.+)$', re.IGNORECASE)
    overnight_pat = re.compile(r'Overnight(?:\s+in)?\s+([\w\s\-]+?)(?:\.|$)', re.IGNORECASE)
    optional_pat = re.compile(r'^Optional:\s*(.+)$', re.IGNORECASE)

    current_num = current_title = None
    current_body = []
    in_days = False

    def flush_day():
        if current_num is None: return
        body = ' '.join(current_body)
        ov_m = overnight_pat.search(body)
        overnight_city = ov_m.group(1).strip() if ov_m else ''
        # Remove the "Overnight in X." line from desc
        desc = re.sub(r'\s*Overnight(?:\s+in)?\s+[\w\s\-]+?\.?\s*$', '', body).strip()
        opt_m = optional_pat.search(desc)
        optional_text = opt_m.group(1).strip() if opt_m else ''
        if opt_m:
            desc = desc[:opt_m.start()].strip()
        days.append({
            'num': int(current_num),
            'title': current_title,
            'overnight': f'Overnight: {overnight_city}' if overnight_city else 'Departure day',
            'desc': desc,
            'optional': optional_text,
        })

    for line in lines:
        m = day_pat.match(line)
        if m:
            flush_day()
            current_num, current_title = m.group(1), m.group(2).strip()
            current_body = []
            in_days = True
        elif in_days:
            if re.match(r'^This package price includes', line, re.IGNORECASE):
                flush_day()
                current_num = None
                in_days = False
                # Start collecting includes
                section = 'includes'
            elif current_num:
                current_body.append(line)

    # ── Package includes ──
    in_includes = False
    includes_raw = []
    for line in lines:
        if re.match(r'^This package price includes', line, re.IGNORECASE):
            in_includes = True; continue
        if in_includes:
            if re.match(r'^(Sample Tours|Pricing is|Terms|Sample Hotels)', line, re.IGNORECASE):
                break
            includes_raw.append(line)
    includes = merge_bulleted_lines(includes_raw)

    # ── Sample Tours ──
    in_tours = False
    for line in lines:
        if re.match(r'^Sample Tours', line, re.IGNORECASE):
            in_tours = True; continue
        if in_tours:
            if re.match(r'^(Pricing|Sample Hotels|Terms|3 Star|4 Star)', line, re.IGNORECASE):
                break
            # Look for "Name   £/€ price" or just "Name\tprice"
            pm = re.search(r'[€£]\s*([\d,]+)', line)
            if pm:
                name = re.sub(r'\s*[€£].*$', '', line).strip()
                price = float(pm.group(1).replace(',',''))
                if name and price > 0: sample_tours.append({'name': name, 'price': price})

    # ── Sample Hotels ──
    in_hotels = False
    hotel_header_seen = False
    for line in lines:
        if re.match(r'^Sample Hotels', line, re.IGNORECASE):
            in_hotels = True; continue
        if in_hotels:
            if re.match(r'^(Terms|Pricing)', line, re.IGNORECASE): break
            if re.match(r'^(City|The hotels)', line, re.IGNORECASE): hotel_header_seen = True; continue
            if not hotel_header_seen: continue
            # Lines after header: "City   3*hotel   4*hotel" – but PDF extracts as separate lines
            # Pattern varies; try to find city + 2 hotel names across multiple lines
            if line in CITY_COORDS or any(line.startswith(c) for c in CITY_COORDS):
                hotels.append({'city': line, 'h3': '', 'h4': '', 'nights': ''})
            elif hotels and not hotels[-1]['h3']:
                hotels[-1]['h3'] = line
            elif hotels and hotels[-1]['h3'] and not hotels[-1]['h4']:
                hotels[-1]['h4'] = line

    # ── Terms ──
    in_terms = False
    terms_raw = []
    for line in lines:
        if re.match(r'^Terms\s*[&\n]', line, re.IGNORECASE): in_terms = True; continue
        if in_terms:
            terms_raw.append(line)
    terms = [t for t in merge_bulleted_lines(terms_raw) if len(t) > 10]

    return {
        'days': days,
        'includes': includes,
        'optional_tours': sample_tours,
        'hotels': hotels,
        'terms': terms,
    }

# ─── Product definitions ──────────────────────────────────────────────────────
# Maps product slug → {excel_sheet, genuine_styles, pdfs, title, route_cities, nights, blurb}

PRODUCTS = {
    'london-3n': {
        'sheet': '1.1',
        'genuine_styles': ['private'],
        'title': 'London City Break',
        'nights': '3 nights / 4 days',
        'eyebrow': 'UK & Ireland · FIT Packages · 2026–27',
        'season': 'All Year Round',
        'validity': 'Valid till Oct 2027',
        'blurb': 'Classic London — panoramic tour, Thames cruise, Stonehenge and Bath with a private vehicle.',
        'route_stops': ['London', 'Bath'],
        'pdfs': {
            'private': '3 nights 4 days London_Private.pdf',
        },
        'style_names': {'private': 'Private Exclusive Coach'},
        'style_blurbs': {'private': 'Private vehicle with driver — full city panoramic tour, Thames cruise, Stonehenge and Bath day trip.'},
        'style_routes': {'private': 'London (3N)'},
        'hero': 'https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?w=1600&q=80',
    },
    'england-scotland-10n': {
        'sheet': '1.2',
        'genuine_styles': ['regular', 'private'],
        'title': 'England & Scotland Grand Tour',
        'nights': '10 nights / 11 days',
        'eyebrow': 'UK & Ireland · FIT Packages · 2026–27',
        'season': 'All Year Round',
        'validity': 'Valid till Nov 2027',
        'blurb': "London to Glasgow — Peak District, Edinburgh's Old Town, Loch Ness and the Highland wilderness.",
        'route_stops': ['London', 'Manchester', 'Edinburgh', 'Inverness', 'Glasgow'],
        'pdfs': {
            'regular': '10 Nights 11 Days England-Scotland_ Regular.pdf',
            'private': '9 Nights 10 Days England-Scotland_ Private.pdf',
        },
        'style_names': {'regular': 'Regular FIT', 'private': 'Private Exclusive Coach'},
        'style_blurbs': {
            'regular': 'Trains and scheduled transfers between cities — the classic way to cross Britain.',
            'private': 'Private coach with driver from London to Glasgow — ideal for groups and families.',
        },
        'style_routes': {
            'regular': 'London (3N) → Manchester (2N) → Edinburgh (2N) → Inverness (2N) → Glasgow (1N)',
            'private': 'London (3N) → Manchester (2N) → Edinburgh (2N) → Inverness (1N) → Glasgow (1N)',
        },
        'hero': 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1600&q=80',
    },
    'london-scotland-8n': {
        'sheet': '1.3',
        'genuine_styles': ['regular'],
        'title': 'London & Scotland Highlights',
        'nights': '8 nights / 9 days',
        'eyebrow': 'UK & Ireland · FIT Packages · 2026–27',
        'season': 'All Year Round',
        'validity': 'Valid till Nov 2027',
        'blurb': 'London to Edinburgh via Glasgow — city sights, Highland wilderness and Loch Ness.',
        'route_stops': ['London', 'Glasgow', 'Inverness', 'Edinburgh'],
        'pdfs': {
            'regular': '8 Nights 9 Days London Scotland_Regular.pdf',
        },
        'style_names': {'regular': 'Regular FIT'},
        'style_blurbs': {'regular': 'Trains and scheduled transfers — London to Edinburgh via the Highlands.'},
        'style_routes': {'regular': 'London (3N) → Glasgow (1N) → Inverness (2N) → Edinburgh (2N)'},
        'hero': 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1600&q=80',
    },
    'scotland-6n': {
        'sheet': '1.4',
        'genuine_styles': ['regular', 'private', 'selfdrive'],
        'title': 'Scotland Discovery',
        'nights': '6 nights / 7 days',
        'eyebrow': 'UK & Ireland · FIT Packages · 2026–27',
        'season': 'All Year Round',
        'validity': 'Valid till Nov 2027',
        'blurb': 'Edinburgh, Inverness and Fort William — castles, lochs and Highland glens by train, coach or self-drive.',
        'route_stops': ['Edinburgh', 'Inverness', 'Fort William'],
        'pdfs': {
            'regular': '6 nights, 7 days Scotland_Regular.pdf',
            'private': '6 nights, 7 days Scotland_Private.pdf',
            'selfdrive': '6 nights, 7 days Scotland_Self Drive.pdf',
        },
        'style_names': {'regular': 'Regular FIT', 'private': 'Private Exclusive Coach', 'selfdrive': 'Self Drive'},
        'style_blurbs': {
            'regular': 'Trains and bus connections between cities — the classic Scottish rail adventure.',
            'private': 'Private coach with driver from Edinburgh to Fort William — photo stops at every loch.',
            'selfdrive': 'Rental car from Edinburgh — freedom to stop at any viewpoint on the Highland roads.',
        },
        'style_routes': {
            'regular': 'Edinburgh (2N) → Inverness (2N) → Fort William (1N) → Edinburgh (1N)',
            'private': 'Edinburgh (2N) → Inverness (2N) → Fort William (1N) → Edinburgh (1N)',
            'selfdrive': 'Edinburgh (2N) → Inverness (2N) → Fort William (1N) → Edinburgh (1N)',
        },
        'hero': 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=1600&q=80',
    },
    'ireland-6n': {
        'sheet': '1.5',
        'genuine_styles': ['regular', 'private', 'selfdrive'],
        'title': 'Ireland Discovery',
        'nights': '6 nights / 7 days',
        'eyebrow': 'UK & Ireland · FIT Packages · 2026–27',
        'season': 'All Year Round',
        'validity': 'Valid till Nov 2027',
        'blurb': 'Dublin, the Cliffs of Moher and Limerick — by train, private coach or self-drive.',
        'route_stops': ['Dublin', 'Cliffs of Moher', 'Limerick', 'Kilkenny'],
        'pdfs': {
            'regular': '6 nights, 7 days Ireland_Regular.pdf',
            'private': '6 nights, 7 days Ireland_Private.pdf',
            'selfdrive': '6 nights, 7 days Ireland_Self Drive.pdf',
        },
        'style_names': {'regular': 'Regular FIT', 'private': 'Private Exclusive Coach', 'selfdrive': 'Self Drive'},
        'style_blurbs': {
            'regular': 'Trains and coach tour — Dublin to Limerick by rail, Cliffs of Moher by scheduled coach.',
            'private': 'Private minivan with driver — Cliffs of Moher, Killarney and Kilkenny with photo stops.',
            'selfdrive': 'Rental car from Dublin airport — Cliffs of Moher, the Burren and Ring of Kerry at your pace.',
        },
        'style_routes': {
            'regular': 'Dublin (2N) → Limerick (3N) → Dublin (1N)',
            'private': 'Dublin (2N) → Limerick (3N) → Dublin (1N)',
            'selfdrive': 'Dublin (2N) → Limerick (3N) → Dublin (1N)',
        },
        'hero': 'https://images.unsplash.com/photo-1590089415225-401ed6f9db8e?w=1600&q=80',
    },
    'devon-cornwall-9n': {
        'sheet': '1.6',
        'genuine_styles': ['selfdrive'],
        'title': 'London, Devon & Cornwall',
        'nights': '9 nights / 10 days',
        'eyebrow': 'UK & Ireland · FIT Packages · 2026–27',
        'season': 'All Year Round',
        'validity': 'Valid till Nov 2027',
        'blurb': 'London to Land\'s End by rental car — Cotswolds, Tintagel, the Lizard Peninsula and Dartmoor.',
        'route_stops': ['London', 'Cheltenham', 'Barnstaple', 'Truro', 'Plymouth', 'Exeter', 'Bournemouth'],
        'pdfs': {
            'selfdrive': '9 nights, 10 days London with Devon & Cornwall_Self-drive.pdf',
        },
        'style_names': {'selfdrive': 'Self Drive'},
        'style_blurbs': {'selfdrive': 'Rental car from London — the slow route through England\'s Atlantic coast.'},
        'style_routes': {'selfdrive': 'London (2N) → Cheltenham (1N) → Barnstaple (1N) → Truro (2N) → Plymouth (1N) → Exeter (1N) → Bournemouth (1N)'},
        'hero': 'https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?w=1600&q=80',
    },
}

STYLE_LABEL = {'regular': 'Regular FIT', 'private': 'Private Tour', 'selfdrive': 'Self Drive'}

STANDARD_TERMS = [
    "All rates are net and per person for the package.",
    "Child rates apply for children aged 2 to 11 years old sharing a room with 2 adults.",
    "All rates are subject to availability at the time of booking.",
    "Rates are not applicable during trade fair periods, major European public holidays, and major events.",
    "City taxes are not included in the price.",
    "All bookings must be confirmed at least 60 working days prior to arrival.",
    "100% pre-payment required by bank transfer or credit card. All bank transfer charges covered by the Agent.",
    "Vouchers will be issued after receipt of full payment.",
]

# ─── Build prices JSON ────────────────────────────────────────────────────────

def build_prices_json(slug, product_def):
    pricing = extract_premium_pricing(product_def['sheet'], product_def['genuine_styles'])
    optional_tours = extract_optional_tours_excel(product_def['sheet'])
    # Also pull from PDFs if richer
    for style, pdf_name in product_def['pdfs'].items():
        pdf_path = PDF_DIR / pdf_name
        if pdf_path.exists():
            pdf_data = extract_pdf_full(pdf_path)
            if pdf_data['optional_tours']:
                optional_tours = pdf_data['optional_tours']
                break

    out = {
        'year': '2026-27',
        'currency': pricing['currency'],
        'validFrom': '01 Nov 2026',
        'validTo': '30 Nov 2027',
        'note': 'Premium market rates. Net, per person.',
        'variants': {},
        'optionalTours': optional_tours,
    }

    def season_rows_to_variants(rows):
        """Convert 2 season rows → {3: {summer:..., winter:...}, 4: {...}}"""
        # Identify which row is winter vs summer by month
        def is_winter(r):
            month = r['start'].split()[1] if r.get('start') else ''
            return month in ('Nov', 'Dec', 'Jan', 'Feb', 'Mar')
        if not rows: return {}
        v = {'3': {}, '4': {}}
        for r in rows:
            season = 'winter' if is_winter(r) else 'summer'
            if r.get('t3'): v['3'][season] = {'single': r['s3'], 'twin': r['t3'], 'child': r['c3']}
            if r.get('t4'): v['4'][season] = {'single': r['s4'], 'twin': r['t4'], 'child': r['c4']}
        return v

    if 'regular' in pricing:
        out['variants']['regular'] = season_rows_to_variants(pricing['regular'])
    if 'private' in pricing:
        out['variants']['private'] = {'minPax': pricing['private']}
    if 'selfdrive' in pricing:
        out['variants']['selfdrive'] = season_rows_to_variants(pricing['selfdrive'])

    return out

# ─── Build product JSON ───────────────────────────────────────────────────────

def build_product_json(slug, product_def):
    p = product_def

    # Extract data from each style's PDF
    style_data = {}
    for style, pdf_name in p['pdfs'].items():
        pdf_path = PDF_DIR / pdf_name
        if pdf_path.exists():
            style_data[style] = extract_pdf_full(pdf_path)
        else:
            print(f"  WARNING: PDF not found: {pdf_name}")

    # Use first available style's data for days/hotels/terms
    primary_style = p['genuine_styles'][0]
    primary_data = style_data.get(primary_style, {})
    days = primary_data.get('days', [])
    hotels_raw = primary_data.get('hotels', [])
    terms = primary_data.get('terms', STANDARD_TERMS) or STANDARD_TERMS

    # Build map points from route stops
    map_points = []
    for city in p['route_stops']:
        coords = CITY_COORDS.get(city, {'lat': 0, 'lng': 0})
        # Estimate nights: check if city appears in style route
        map_points.append({
            'lat': coords['lat'],
            'lng': coords['lng'],
            'label': city,
            'nights': 0,
        })

    # Build styles.
    # Note: we don't have clean, short transfer-only sentences per day (only
    # full itinerary paragraphs from the PDF), so 'transport' is left empty
    # and the day chip falls back to fallbackIncluded ("Day at leisure." or
    # an optional-tour note) instead of duplicating the day description.
    styles = {}
    for style in p['genuine_styles']:
        sd = style_data.get(style, {})
        styles[style] = {
            'name': p['style_names'][style],
            'blurb': p['style_blurbs'][style],
            'nights': p['nights'],
            'route': p['style_routes'][style],
            'aboutNights': p['nights'],
            'transport': {},
            'inclusions': sd.get('includes', []),
        }

    # Hotels — Excel Component-Hotels section is structured and reliable;
    # fall back to PDF-parsed hotels only if Excel yields nothing.
    hotels = extract_excel_hotels(p['sheet'])
    if not hotels:
        seen_cities = set()
        for h in hotels_raw:
            city = h.get('city', '')
            if city and city not in seen_cities:
                seen_cities.add(city)
                hotels.append({'city': city, 'nights': h.get('nights', ''), 'h3': h.get('h3', ''), 'h4': h.get('h4', '')})

    # Good to know — standard per style
    good_to_know = [
        {'title': 'Best season', 'body': 'April–September for long days and best weather; shoulder months quieter and often better value.'},
        {'title': 'Currency & documents', 'body': 'England/Scotland use £ GBP. Ireland uses € EUR. Both are Schengen-free — check your entry requirements.'},
        {'title': 'What to pack', 'body': 'Layers and a waterproof in any month. Comfortable shoes for cobbles and coastal paths.'},
    ]
    if 'selfdrive' in p['genuine_styles']:
        good_to_know.append({'title': 'Driving', 'body': 'Drive on the left. Rural roads can be narrow — allow extra time. Petrol stations sparse in Highland areas.', 'styles': ['selfdrive']})
    if 'regular' in p['genuine_styles']:
        good_to_know.append({'title': 'Rail travel', 'body': 'Seat reservations are included on inter-city trains. Arrive 10 minutes before departure.', 'styles': ['regular']})
    if 'private' in p['genuine_styles']:
        good_to_know.append({'title': 'Your vehicle', 'body': 'Driver hours are limited to 10 hrs/day by law. Luggage space fits one large case per guest.', 'styles': ['private']})

    # About items
    about = [
        {'title': 'Best season', 'body': 'May–September for long days; shoulder months quieter and better value'},
        {'title': 'Weather', 'body': 'Mild and changeable. 12–20°C in summer. Pack a rain layer year-round'},
    ]

    return {
        'id': slug,
        'title': p['title'],
        'eyebrow': p['eyebrow'],
        'heroImage': p['hero'],
        'pricesFile': f'prices/{slug}.json',
        'map': {'points': map_points, 'closeLoop': False},
        'styles': styles,
        'days': [{'num': d['num'], 'title': d['title'], 'overnight': d['overnight'],
                  'desc': d['desc'],
                  'fallbackIncluded': d.get('optional', '') or 'Day at leisure.'} for d in days],
        'hotels': hotels,
        'about': about,
        'goodToKnow': good_to_know,
        'terms': terms or STANDARD_TERMS,
    }

# ─── Build products/index.json ────────────────────────────────────────────────

def build_index_json(products_data):
    """Build the index.json for the Metro index page cards."""
    entries = []
    for slug, (prod, prices) in products_data.items():
        p_def = PRODUCTS[slug]
        # Minimum from price = lowest twin across all styles/seasons/star
        from_prices = []
        for style_key, style_rates in prices.get('variants', {}).items():
            if 'minPax' in style_rates:
                for row in style_rates['minPax']:
                    for v in [row.get('w3'), row.get('s3')]:
                        if v: from_prices.append(v)
            else:
                for star, seasons in style_rates.items():
                    for season, rates in seasons.items():
                        t = rates.get('twin')
                        if t: from_prices.append(t)

        from_price = min(from_prices) if from_prices else 0
        currency = prices.get('currency', '€')
        currency_sym = '£' if currency == 'GBP' else '€'

        entries.append({
            'id': slug,
            'productFile': f'products/{slug}.json',
            'title': p_def['title'],
            'region': 'UK & Ireland',
            'serviceLine': 'FIT',
            'map': {'points': prod['map']['points'], 'closeLoop': prod['map']['closeLoop']},
            'routeStops': p_def['route_stops'],
            'nights': p_def['nights'],
            'season': p_def['season'],
            'validity': p_def['validity'],
            'blurb': p_def['blurb'],
            'fromPrice': from_price,
            'currency': currency_sym,
            'priceNote': 'pp (twin)',
        })
    return {'products': entries}

# ─── Metro HTML: Index page ───────────────────────────────────────────────────

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>UK &amp; Ireland — FIT Packages | Europe Incoming</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root{--navy:#0B1733;--navy-tile:#132347;--gold:#F2B91D;--ink:#1A1D2E;--body-grey:#3A3D4D;--muted:#6B7080;--line:#E5E7EC;--line-light:#EFF0F3;--ctrl-border:#D8DAE1;--surface:#F5F5F3;--surface-hover:#EDEDEA;}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Open Sans','Segoe UI',sans-serif;background:#fff;color:var(--ink);}
/* Header */
.site-header{display:flex;align-items:center;gap:28px;padding:26px 40px 0;}
.site-header img{height:32px;width:auto;display:block;}
.search-wrap{flex:1;max-width:360px;}
.search-wrap input{width:100%;padding:9px 14px;font-size:13px;font-family:inherit;border:2px solid var(--ctrl-border);border-radius:0;background:#fff;color:var(--ink);outline:none;box-sizing:border-box;}
.search-wrap input::placeholder{color:var(--muted);}
.trade-link{margin-left:auto;font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--navy);text-decoration:none;}
/* Title block */
.page-title-block{padding:36px 40px 22px;display:flex;align-items:flex-end;gap:20px;flex-wrap:wrap;}
.page-eyebrow{font-size:13px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);padding-bottom:12px;}
.page-h1{font-weight:300;font-size:64px;letter-spacing:-0.02em;line-height:1;color:var(--navy);}
.intro-line{padding:0 40px 30px;max-width:640px;font-weight:300;font-size:19px;color:var(--muted);}
/* Card grid */
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:12px;padding:0 40px 80px;}
/* Package tile */
.pkg-tile{display:flex;align-items:stretch;text-decoration:none;color:inherit;min-height:240px;border-radius:0;transition:opacity 180ms linear;}
.pkg-tile:hover{opacity:.86;}
.pkg-tile.navy{background:var(--navy-tile);}
.pkg-tile.gold{background:var(--gold);}
.tile-left{flex:1;min-width:0;padding:22px 24px;display:flex;flex-direction:column;gap:8px;}
/* Navy tile text */
.navy .tile-meta{font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);}
.navy .tile-title{font-weight:300;font-size:30px;line-height:1.1;color:#fff;}
.navy .tile-blurb{font-size:13px;line-height:1.55;color:rgba(255,255,255,0.72);}
.navy .tile-route{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:rgba(255,255,255,0.72);}
.navy .tile-price-row{margin-top:auto;padding-top:10px;display:flex;align-items:baseline;gap:8px;}
.navy .tile-from{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#fff;}
.navy .tile-amount{font-weight:300;font-size:34px;line-height:1;color:#fff;}
.navy .tile-pnote{font-size:11px;color:rgba(255,255,255,0.72);}
.navy .tile-validity{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,0.6);}
/* Gold tile text */
.gold .tile-meta{font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--navy);}
.gold .tile-title{font-weight:300;font-size:30px;line-height:1.1;color:var(--navy);}
.gold .tile-blurb{font-size:13px;line-height:1.55;color:rgba(11,23,51,0.8);}
.gold .tile-route{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:rgba(11,23,51,0.8);}
.gold .tile-price-row{margin-top:auto;padding-top:10px;display:flex;align-items:baseline;gap:8px;}
.gold .tile-from{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--navy);}
.gold .tile-amount{font-weight:300;font-size:34px;line-height:1;color:var(--navy);}
.gold .tile-pnote{font-size:11px;color:rgba(11,23,51,0.65);}
.gold .tile-validity{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(11,23,51,0.65);}
/* Tile map column */
.tile-right{width:190px;flex-shrink:0;position:relative;background:var(--surface);}
.tile-map{position:absolute;inset:0;}
/* City-tip */
.city-tip{background:transparent!important;border:none!important;box-shadow:none!important;}
.city-tip .leaflet-tooltip-content{font-size:9px;font-weight:600;color:var(--navy);text-shadow:1px 0 0 #fff,-1px 0 0 #fff,0 1px 0 #fff,0 -1px 0 #fff;}
/* Empty state */
.empty-state{padding:80px 0;color:var(--muted);font-weight:300;font-size:22px;display:none;}
/* Footer */
footer{background:var(--navy);color:rgba(255,255,255,0.55);padding:20px 40px;font-size:12px;display:flex;justify-content:space-between;align-items:center;}
footer a{color:var(--gold);text-decoration:none;}
</style>
</head>
<body>

<header class="site-header">
  <a href="../../index.html"><img src="../../logo.png" alt="Europe Incoming"></a>
  <div class="search-wrap">
    <input type="search" id="search" placeholder="search packages" autocomplete="off">
  </div>
  <a class="trade-link" href="mailto:fitsales@europeincoming.com">Trade enquiries</a>
</header>

<div class="page-title-block">
  <div>
    <div class="page-eyebrow">Multi-country · FIT</div>
    <h1 class="page-h1">UK &amp; Ireland</h1>
  </div>
</div>
<p class="intro-line">FIT packages across Britain and Ireland — by train, self-drive or private coach.</p>

<div class="card-grid" id="grid"></div>
<p class="empty-state" id="empty">No packages match this search yet.</p>

<footer>
  <span>Europe Incoming Holdings Ltd · Unit 11-12 Turnham Green Terrace Mews, London W4 1QU</span>
  <span><a href="mailto:fitsales@europeincoming.com">fitsales@europeincoming.com</a> &nbsp;·&nbsp; +44 208 994 5001</span>
</footer>

<script>
const PRODUCTS_URL = 'products/index.json';
const maps = {};

function squareMarker(size, color) {
  return L.divIcon({
    className: '',
    html: `<div style="width:${size}px;height:${size}px;background:${color};"></div>`,
    iconSize: [size, size],
    iconAnchor: [size/2, size/2],
  });
}

function initMap(mapId, points, closeLoop) {
  if (maps[mapId]) return;
  const el = document.getElementById(mapId);
  if (!el) return;
  const map = L.map(el, {
    zoomControl: false, scrollWheelZoom: false,
    dragging: false, attributionControl: false,
  });
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {maxZoom: 13}).addTo(map);

  const latlngs = points.map(p => [p.lat, p.lng]);
  if (latlngs.length > 1) {
    const route = closeLoop ? [...latlngs, latlngs[0]] : latlngs;
    L.polyline(route, {color:'#0B1733', weight:1.5, dashArray:'4,4'}).addTo(map);
  }

  points.forEach(p => {
    const isOvernight = p.nights > 0;
    L.marker([p.lat, p.lng], {
      icon: squareMarker(isOvernight ? 10 : 6, isOvernight ? '#F2B91D' : '#6B7080'),
    }).addTo(map).bindTooltip(p.label, {
      permanent: true, direction: 'top', offset: [0, -8],
      className: 'city-tip',
    });
  });

  const bounds = L.latLngBounds(latlngs);
  map.fitBounds(bounds, {padding: [10, 10]});
  if (latlngs.length === 1) map.setZoom(8);
  maps[mapId] = map;
}

let allProducts = [];

fetch(PRODUCTS_URL)
  .then(r => r.json())
  .then(data => {
    allProducts = data.products || [];
    render(allProducts);
    document.getElementById('search').addEventListener('input', e => {
      const q = e.target.value.toLowerCase();
      const filtered = q
        ? allProducts.filter(p =>
            p.title.toLowerCase().includes(q) ||
            (p.region||'').toLowerCase().includes(q) ||
            (p.routeStops||[]).some(s => s.toLowerCase().includes(q))
          )
        : allProducts;
      render(filtered);
    });
  });

function render(products) {
  const grid = document.getElementById('grid');
  const empty = document.getElementById('empty');
  grid.innerHTML = '';
  if (!products.length) { empty.style.display = 'block'; return; }
  empty.style.display = 'none';

  products.forEach((prod, i) => {
    const variant = i % 3 === 1 ? 'gold' : 'navy';
    const currency = prod.currency || '€';
    const mapId = 'map_' + prod.id;
    const route = (prod.routeStops || []).join(' · ').toUpperCase();
    const nights = prod.nights || '';

    const tile = document.createElement('a');
    tile.className = `pkg-tile ${variant}`;
    tile.href = `package.html?product=${encodeURIComponent(prod.productFile)}`;
    tile.innerHTML = `
      <div class="tile-left">
        <div class="tile-meta">${nights} · ${prod.season || ''}</div>
        <div class="tile-title">${prod.title}</div>
        <div class="tile-blurb">${prod.blurb || ''}</div>
        <div class="tile-route">${route}</div>
        <div class="tile-price-row">
          <span class="tile-from">From</span>
          <span class="tile-amount">${currency}${prod.fromPrice ? prod.fromPrice.toLocaleString() : '—'}</span>
          <span class="tile-pnote">${prod.priceNote || 'pp (twin)'}</span>
        </div>
        <div class="tile-validity">${prod.validity || ''}</div>
      </div>
      <div class="tile-right"><div class="tile-map" id="${mapId}"></div></div>
    `;
    grid.appendChild(tile);

    // Init map after paint
    setTimeout(() => initMap(mapId, prod.map?.points || [], prod.map?.closeLoop || false), 50);
  });
}
</script>
</body>
</html>
"""

# ─── Metro HTML: Package detail template ─────────────────────────────────────

PACKAGE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title id="page-title">Package | Europe Incoming</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root{--navy:#0B1733;--navy-tile:#132347;--gold:#F2B91D;--ink:#1A1D2E;--body-grey:#3A3D4D;--muted:#6B7080;--line:#E5E7EC;--line-light:#EFF0F3;--ctrl-border:#D8DAE1;--surface:#F5F5F3;--surface-hover:#EDEDEA;}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Open Sans','Segoe UI',sans-serif;background:#fff;color:var(--ink);}

/* Header */
.site-header{display:flex;align-items:center;gap:20px;padding:20px 40px 0;no-print:true;}
.back-link{display:flex;align-items:center;gap:8px;text-decoration:none;color:var(--navy);}
.back-arrow{width:26px;height:26px;border:2px solid var(--navy);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;}
.back-label{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;}
.dl-btn{margin-left:auto;background:var(--navy);color:#fff;border:none;border-radius:0;padding:10px 18px;font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;cursor:pointer;font-family:inherit;}
.dl-btn:hover{background:var(--gold);color:var(--navy);}

/* Title block */
.title-block{padding:32px 40px 0;}
.title-eyebrow{font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);margin-bottom:8px;}
.page-h1{font-weight:300;font-size:56px;letter-spacing:-0.02em;color:var(--navy);line-height:1;}

/* Hero row */
.hero-row{display:flex;align-items:stretch;margin:24px 40px 0;gap:0;}
.hero-img{flex:1;min-width:320px;min-height:380px;background:var(--navy);overflow:hidden;}
.hero-img img{width:100%;height:100%;object-fit:cover;display:block;}
.facts-panel{width:280px;flex-shrink:0;background:var(--navy);color:#fff;padding:24px 26px;display:flex;flex-direction:column;gap:14px;}
.facts-label{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);}
.facts-value{font-weight:300;font-size:24px;margin-top:2px;}
.facts-route{font-size:13px;color:rgba(255,255,255,0.78);}
.facts-price-block{margin-top:auto;border-top:1px solid rgba(255,255,255,0.15);padding-top:14px;}
.facts-from{font-size:11px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--gold);}
.facts-amount{font-weight:300;font-size:34px;line-height:1;color:#fff;}
.facts-pp{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:rgba(255,255,255,0.7);}

/* Body layout */
.body-wrap{display:flex;gap:40px;padding:40px 40px 80px;align-items:flex-start;}
.content-col{flex:1;min-width:0;}
.sidebar-col{width:300px;flex-shrink:0;position:sticky;top:20px;}

/* Style switcher */
.switcher-row{margin-bottom:28px;}
.switcher-label{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:8px;}
.switcher-btns{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px;}
.sw-btn{border-radius:0;padding:8px 16px;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;cursor:pointer;font-family:inherit;border:2px solid var(--ctrl-border);background:transparent;color:var(--navy);}
.sw-btn.active{background:var(--navy);color:#fff;border-color:var(--navy);}
.sw-blurb{font-size:13px;color:var(--muted);}

/* Section heading */
.section-heading{font-weight:300;font-size:34px;color:var(--navy);margin-bottom:4px;}
.section-sub{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);margin-bottom:24px;}

/* Day rows */
.day-row{display:grid;grid-template-columns:64px 1fr;gap:20px;padding:22px 0;border-top:1px solid var(--line);}
.day-num-col{text-align:left;}
.day-label{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);}
.day-number{font-weight:300;font-size:40px;line-height:1;color:var(--gold);}
.day-title{font-size:19px;font-weight:600;color:var(--navy);margin-bottom:4px;}
.day-overnight{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:8px;}
.day-desc{font-size:14px;line-height:1.7;color:var(--body-grey);margin-bottom:8px;}
.day-tags{display:flex;flex-direction:column;gap:6px;}
.tag{display:inline-block;padding:4px 10px;font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;border-radius:0;}
.tag-included{background:var(--navy);color:#fff;}
.tag-taste{background:var(--gold);color:var(--navy);}
.tag-exp{background:#EDEDEA;color:var(--navy);}

/* Package includes */
.includes-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 32px;margin-bottom:40px;}
.include-row{position:relative;padding:9px 0 9px 22px;border-bottom:1px solid var(--line-light);font-size:13px;color:var(--body-grey);}
.include-row::before{content:'✓';position:absolute;left:0;color:var(--gold);font-weight:700;}

/* Hotels grid */
.hotels-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:40px;}
.hotel-card{background:var(--surface);padding:18px 20px;}
.hotel-city{font-weight:300;font-size:22px;color:var(--navy);}
.hotel-nights{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:10px;}
.hotel-star{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--gold);margin-top:6px;}
.hotel-name{font-size:12.5px;color:var(--body-grey);}

/* Rates table */
.rates-table{width:100%;border-collapse:collapse;margin-bottom:16px;}
.rates-table th{background:var(--navy);color:#fff;padding:12px 16px;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;}
.rates-table th:first-child{text-align:left;}
.rates-table th:not(:first-child){text-align:right;}
.rates-table td{padding:10px 16px;border-bottom:1px solid var(--line-light);}
.rates-table td:first-child{font-size:13.5px;}
.rates-table td:not(:first-child){font-weight:300;font-size:22px;text-align:right;}
.rates-footnote{font-size:12px;color:var(--muted);margin-top:8px;margin-bottom:40px;}

/* Min-pax table */
.minpax-table{width:100%;border-collapse:collapse;margin-bottom:16px;}
.minpax-table th{background:var(--navy);color:#fff;padding:10px 16px;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;text-align:right;}
.minpax-table th:first-child{text-align:left;}
.minpax-table td{padding:8px 16px;border-bottom:1px solid var(--line-light);font-size:13px;}
.minpax-table td:not(:first-child){font-weight:300;font-size:20px;text-align:right;}

/* Optional tours */
.optionals-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:40px;}
.optional-card{background:var(--surface);padding:14px 18px;display:flex;justify-content:space-between;align-items:center;}
.optional-name{font-size:13px;color:var(--body-grey);}
.optional-price{font-weight:300;font-size:22px;color:var(--navy);}
.optional-pp{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}

/* Good to know */
.gtk-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:40px;}
.gtk-card{background:var(--navy);padding:18px 20px;}
.gtk-title{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);margin-bottom:6px;}
.gtk-body{font-size:13px;color:rgba(255,255,255,0.8);line-height:1.55;}

/* T&C */
.tc-btn{width:100%;background:var(--surface);border:none;border-radius:0;padding:14px 18px;text-align:left;cursor:pointer;font-family:inherit;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;}
.tc-btn:hover{background:var(--surface-hover);}
.tc-body{background:var(--surface);padding:0 18px;max-height:0;overflow:hidden;transition:max-height 0.3s,padding 0.3s;}
.tc-body.open{max-height:1000px;padding:14px 18px;}
.tc-item{padding:9px 0 9px 16px;border-bottom:1px solid var(--line-light);font-size:12.5px;color:var(--body-grey);position:relative;}
.tc-item::before{content:'·';position:absolute;left:0;color:var(--gold);font-weight:700;}

/* Sidebar */
.sidebar-about{background:var(--surface);padding:20px;margin-bottom:12px;}
.sb-map-wrap{width:100%;height:180px;position:relative;cursor:zoom-in;margin-bottom:12px;}
.sb-map{width:100%;height:100%;}
.sb-enlarge{position:absolute;bottom:0;right:0;background:var(--navy);color:#fff;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;padding:6px 12px;border-radius:0;}
.sb-row{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--line);font-size:13px;}
.sb-key{color:var(--muted);font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;}
.sb-val{color:var(--ink);}
.quote-card{background:var(--gold);padding:20px;}
.quote-heading{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--navy);margin-bottom:8px;}
.quote-body{font-size:13px;color:var(--navy);line-height:1.55;margin-bottom:16px;}
.quote-btn{display:block;width:100%;text-align:center;background:var(--navy);color:#fff;text-decoration:none;padding:12px 0;font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;font-family:inherit;}

/* Map modal */
.modal-overlay{position:fixed;inset:0;z-index:1000;background:rgba(11,23,51,0.85);display:none;align-items:center;justify-content:center;padding:40px;}
.modal-overlay.open{display:flex;}
.modal-panel{background:#fff;width:min(960px,100%);height:min(640px,100%);display:flex;flex-direction:column;}
.modal-title-bar{background:var(--navy);padding:14px 20px;display:flex;align-items:center;justify-content:space-between;}
.modal-title{font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#fff;}
.modal-close{background:none;border:none;color:var(--gold);font-size:20px;cursor:pointer;line-height:1;}
.modal-map{flex:1;}

/* Footer */
footer{background:var(--navy);color:rgba(255,255,255,0.55);padding:20px 40px;font-size:12px;display:flex;justify-content:space-between;align-items:center;}
footer a{color:var(--gold);text-decoration:none;}

/* Season / star switchers */
.rate-controls{display:flex;gap:16px;margin-bottom:16px;flex-wrap:wrap;}
.rate-control-group{display:flex;flex-direction:column;gap:6px;}

/* Print styles */
@media print {
  *{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important;color-adjust:exact!important;}
  .site-header,.dl-btn,.switcher-row,.sidebar-col,.modal-overlay,.no-print{display:none!important;}
  .body-wrap{display:block;padding:0;}
  .content-col{width:100%;}
  .hero-row{margin:12px 0 0;}
  .hero-img{min-height:130px!important;height:130px!important;}
  .facts-panel{width:200px;}
  .page-h1{font-size:32px;}
  .section-heading{font-size:16px;}
  .day-number{font-size:24px;}
  .day-row{padding:12px 0;}
  .hotels-grid{grid-template-columns:repeat(3,1fr);}
  .rates-table td{font-size:16px;}
  .tc-body{max-height:none!important;padding:14px 18px!important;}
  .tc-btn .tc-caret{display:none;}
  .gtk-grid,.optionals-grid{grid-template-columns:1fr 1fr;}
  body{font-size:11px;}
  .includes-grid{grid-template-columns:1fr 1fr;}
  .package-includes-section{break-inside:avoid;}
}
</style>
</head>
<body>

<!-- Header -->
<header class="site-header no-print">
  <a href="../../logo.png" style="display:block">
    <img src="../../logo.png" alt="Europe Incoming" style="height:24px">
  </a>
  <a class="back-link" href="index.html">
    <span class="back-arrow">←</span>
    <span class="back-label">All packages</span>
  </a>
  <a class="dl-btn" id="dl-btn" href="#" download>Download PDF</a>
</header>

<!-- Title block -->
<div class="title-block">
  <div class="title-eyebrow" id="eyebrow"></div>
  <h1 class="page-h1" id="pkg-title">…</h1>
</div>

<!-- Hero row -->
<div class="hero-row">
  <div class="hero-img"><img id="hero-img" src="" alt=""></div>
  <div class="facts-panel">
    <div>
      <div class="facts-label">Duration</div>
      <div class="facts-value" id="facts-duration">…</div>
    </div>
    <div>
      <div class="facts-label">Route</div>
      <div class="facts-route" id="facts-route">…</div>
    </div>
    <div class="facts-price-block">
      <div class="facts-from">From</div>
      <div class="facts-amount" id="facts-price">…</div>
      <div class="facts-pp">per person</div>
    </div>
  </div>
</div>

<!-- Body -->
<div class="body-wrap">
  <div class="content-col">

    <!-- Style switcher -->
    <div class="switcher-row no-print">
      <div class="switcher-label">Travel style</div>
      <div class="switcher-btns" id="style-btns"></div>
      <div class="sw-blurb" id="style-blurb"></div>
    </div>

    <!-- Day by day -->
    <div class="section-heading" id="days-heading">Itinerary</div>
    <div class="section-sub" id="days-sub"></div>
    <div id="days-container"></div>

    <!-- Package includes -->
    <div class="package-includes-section">
      <div class="section-heading">Package includes</div>
      <div class="section-sub" id="includes-sub"></div>
      <div class="includes-grid" id="includes-container"></div>
    </div>

    <!-- Sample hotels -->
    <div class="section-heading">Sample hotels</div>
    <div class="section-sub">Representative hotels — subject to availability</div>
    <div class="hotels-grid" id="hotels-container"></div>

    <!-- Rates -->
    <div class="section-heading">Rates</div>
    <div class="section-sub" id="rates-sub"></div>
    <div id="rates-container"></div>
    <p class="rates-footnote" id="rates-footnote"></p>

    <!-- Optional tours -->
    <div id="optionals-section" style="display:none">
      <div class="section-heading">Optional tours &amp; extras</div>
      <div class="section-sub">Bookable at an additional cost</div>
      <div class="optionals-grid" id="optionals-container"></div>
    </div>

    <!-- Good to know -->
    <div id="gtk-section" style="display:none">
      <div class="section-heading">Good to know</div>
      <div class="section-sub" id="gtk-sub"></div>
      <div class="gtk-grid" id="gtk-container"></div>
    </div>

    <!-- T&C -->
    <button class="tc-btn" onclick="toggleTC()">
      <span>Terms &amp; Conditions</span>
      <span class="tc-caret" id="tc-caret">▼</span>
    </button>
    <div class="tc-body" id="tc-body"></div>

  </div><!-- .content-col -->

  <!-- Sidebar -->
  <aside class="sidebar-col no-print">
    <div class="sidebar-about">
      <div class="sb-map-wrap" onclick="openMapModal()">
        <div class="sb-map" id="sidebar-map" style="pointer-events:none"></div>
        <span class="sb-enlarge">Enlarge</span>
      </div>
      <div id="sb-rows"></div>
    </div>
    <div class="quote-card">
      <div class="quote-heading">Ready to quote?</div>
      <p class="quote-body">Send us your dates and party size — we respond within one working day.</p>
      <a class="quote-btn" href="mailto:fitsales@europeincoming.com">Email the FIT team</a>
    </div>
  </aside>
</div><!-- .body-wrap -->

<footer>
  <span>Europe Incoming Holdings Ltd · Unit 11-12 Turnham Green Terrace Mews, London W4 1QU</span>
  <span><a href="mailto:fitsales@europeincoming.com">fitsales@europeincoming.com</a> &nbsp;·&nbsp; +44 208 994 5001</span>
</footer>

<!-- Map modal -->
<div class="modal-overlay" id="map-modal">
  <div class="modal-panel">
    <div class="modal-title-bar">
      <span class="modal-title" id="modal-title"></span>
      <button class="modal-close" onclick="closeMapModal()">✕</button>
    </div>
    <div class="modal-map" id="modal-map"></div>
  </div>
</div>

<script>
// ── State ────────────────────────────────────────────────────────────────────
let PRODUCT = null, PRICES = null;
let activeStyle = null, activeCat = '3', activeSeason = 'summer';
let sidebarMap = null, modalMap = null;

// ── Boot ─────────────────────────────────────────────────────────────────────
const params = new URLSearchParams(location.search);
const productFile = params.get('product');
const productSlug = productFile ? productFile.replace(/^products\//, '').replace(/\.json$/, '') : '';
if (!productFile) {
  document.body.innerHTML = '<p style="padding:40px;color:#c00">No product specified.</p>';
} else {
  fetch(productFile)
    .then(r => r.json())
    .then(prod => {
      PRODUCT = prod;
      document.title = prod.title + ' | Europe Incoming';
      document.getElementById('page-title').textContent = prod.title;
      document.getElementById('eyebrow').textContent = prod.eyebrow || '';
      document.getElementById('pkg-title').textContent = prod.title;
      document.getElementById('hero-img').src = prod.heroImage || '';
      document.getElementById('hero-img').alt = prod.title;
      buildStyleSwitcher();
      const firstStyle = params.get('style') || Object.keys(prod.styles)[0];
      setStyle(firstStyle);
      buildHotels();
      buildTC();
      fetch(prod.pricesFile).then(r => r.json()).then(prices => {
        PRICES = prices;
        updateRates();
        updateFactsPrice();
      });
      setTimeout(buildSidebarMap, 100);
    });
}

// ── Style switcher ───────────────────────────────────────────────────────────
function buildStyleSwitcher() {
  const container = document.getElementById('style-btns');
  container.innerHTML = '';
  Object.entries(PRODUCT.styles).forEach(([key, s]) => {
    const btn = document.createElement('button');
    btn.className = 'sw-btn';
    btn.textContent = s.name;
    btn.dataset.style = key;
    btn.onclick = () => setStyle(key);
    container.appendChild(btn);
  });
}

function setStyle(styleKey) {
  if (!PRODUCT || !PRODUCT.styles[styleKey]) styleKey = Object.keys(PRODUCT.styles)[0];
  activeStyle = styleKey;
  const s = PRODUCT.styles[styleKey];
  document.querySelectorAll('.sw-btn').forEach(b => b.classList.toggle('active', b.dataset.style === styleKey));
  document.getElementById('style-blurb').textContent = s.blurb || '';
  document.getElementById('facts-duration').textContent = s.nights || '';
  document.getElementById('facts-route').textContent = s.route || '';
  document.getElementById('days-sub').textContent = s.name;
  document.getElementById('includes-sub').textContent = s.name;
  document.getElementById('rates-sub').textContent = s.name;
  document.getElementById('gtk-sub').textContent = s.name;
  const dlBtn = document.getElementById('dl-btn');
  if (dlBtn) dlBtn.href = `pdfs/${productSlug}-${styleKey}.pdf`;
  buildDays(styleKey);
  buildIncludes(styleKey);
  if (PRICES) { updateRates(); updateFactsPrice(); }
  updateGTK();
}

// ── Days ─────────────────────────────────────────────────────────────────────
function buildDays(styleKey) {
  const s = PRODUCT.styles[styleKey];
  const transport = s.transport || {};
  const container = document.getElementById('days-container');
  container.innerHTML = '';
  (PRODUCT.days || []).forEach(d => {
    const inc = transport[String(d.num)] || d.fallbackIncluded || '';
    const row = document.createElement('div');
    row.className = 'day-row';
    row.innerHTML = `
      <div class="day-num-col">
        <div class="day-label">Day</div>
        <div class="day-number">${d.num}</div>
      </div>
      <div>
        <div class="day-title">${d.title}</div>
        <div class="day-overnight">${d.overnight || ''}</div>
        <div class="day-desc">${d.desc || ''}</div>
        ${inc ? `<div class="day-tags"><span class="tag tag-included">${inc}</span></div>` : ''}
      </div>
    `;
    container.appendChild(row);
  });
}

// ── Includes ─────────────────────────────────────────────────────────────────
function buildIncludes(styleKey) {
  const s = PRODUCT.styles[styleKey];
  const items = s.inclusions || [];
  const container = document.getElementById('includes-container');
  container.innerHTML = items.map(i => `<div class="include-row">${i}</div>`).join('');
}

// ── Hotels ───────────────────────────────────────────────────────────────────
function buildHotels() {
  const container = document.getElementById('hotels-container');
  container.innerHTML = (PRODUCT.hotels || []).map(h => `
    <div class="hotel-card">
      <div class="hotel-city">${h.city}</div>
      <div class="hotel-nights">${h.nights}</div>
      ${h.h3 ? `<div class="hotel-star">3 STAR</div><div class="hotel-name">${h.h3}</div>` : ''}
      ${h.h4 ? `<div class="hotel-star">4 STAR</div><div class="hotel-name">${h.h4}</div>` : ''}
    </div>
  `).join('');
}

// ── Rates ────────────────────────────────────────────────────────────────────
function updateRates() {
  if (!PRICES || !activeStyle) return;
  const container = document.getElementById('rates-container');
  const variants = PRICES.variants || {};
  const styleRates = variants[activeStyle];
  const cur = PRICES.currency === 'GBP' ? '£' : '€';

  // Optionals
  const opts = PRICES.optionalTours || [];
  document.getElementById('optionals-section').style.display = opts.length ? '' : 'none';
  if (opts.length) {
    document.getElementById('optionals-container').innerHTML = opts.map(o =>
      `<div class="optional-card"><div class="optional-name">${o.name}</div><div><div class="optional-price">${cur}${o.price}</div><div class="optional-pp">pp</div></div></div>`
    ).join('');
  }

  if (!styleRates) { container.innerHTML = '<p style="color:var(--muted);font-size:13px">Rates not available for this travel style.</p>'; return; }

  // Min-Pax style (private)
  if (styleRates.minPax) {
    const rows = styleRates.minPax;
    container.innerHTML = `
      <table class="minpax-table">
        <thead><tr>
          <th style="text-align:left">Min Pax</th>
          <th>3★ Winter</th><th>4★ Winter</th>
          <th>3★ Summer</th><th>4★ Summer</th>
        </tr></thead>
        <tbody>
          ${rows.map(r => `<tr>
            <td>${r.pax}+ guests</td>
            <td>${r.w3 ? cur+r.w3 : '—'}</td>
            <td>${r.w4 ? cur+r.w4 : '—'}</td>
            <td>${r.s3 ? cur+r.s3 : '—'}</td>
            <td>${r.s4 ? cur+r.s4 : '—'}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    `;
    document.getElementById('rates-footnote').textContent =
      `All rates in ${cur}, net, per person per adult. Child (2–11 yrs) sharing with 2 adults — contact us for child rate.`;
    return;
  }

  // Season/star table — show ALL 4 combos for print
  const combos = [
    {star:'3', season:'winter', label:'3★ · Nov–Mar'},
    {star:'3', season:'summer', label:'3★ · Apr–Oct'},
    {star:'4', season:'winter', label:'4★ · Nov–Mar'},
    {star:'4', season:'summer', label:'4★ · Apr–Oct'},
  ];

  let html = '';
  combos.forEach(c => {
    const rates = (styleRates[c.star] || {})[c.season];
    if (!rates) return;
    html += `
      <div style="margin-bottom:20px">
        <table class="rates-table">
          <thead><tr>
            <th>Occupancy</th>
            <th colspan="1">Rate — ${c.label}</th>
          </tr></thead>
          <tbody>
            <tr><td>Single</td><td>${cur}${rates.single || '—'}</td></tr>
            <tr><td>Twin / Double</td><td>${cur}${rates.twin || '—'}</td></tr>
            <tr><td>Child (2–11)</td><td>${cur}${rates.child || '—'}</td></tr>
          </tbody>
        </table>
      </div>`;
  });
  container.innerHTML = html || '<p style="color:var(--muted);font-size:13px">No rates loaded.</p>';
  document.getElementById('rates-footnote').textContent =
    `All rates in ${cur}, net, per person. Twin/double occupancy unless stated. Child 2–11 yrs sharing with 2 adults.`;
}

function updateFactsPrice() {
  if (!PRICES || !activeStyle) return;
  const variants = PRICES.variants || {};
  const styleRates = variants[activeStyle];
  const cur = PRICES.currency === 'GBP' ? '£' : '€';
  let minPrice = Infinity;
  if (!styleRates) { document.getElementById('facts-price').textContent = '—'; return; }
  if (styleRates.minPax) {
    styleRates.minPax.forEach(r => {
      [r.w3, r.w4, r.s3, r.s4].forEach(v => { if (v && v < minPrice) minPrice = v; });
    });
  } else {
    ['3','4'].forEach(star => {
      ['summer','winter'].forEach(s => {
        const t = (styleRates[star] || {})[s]?.twin;
        if (t && t < minPrice) minPrice = t;
      });
    });
  }
  document.getElementById('facts-price').textContent = minPrice < Infinity ? cur + minPrice.toLocaleString() : '—';
}

// ── Good to know ─────────────────────────────────────────────────────────────
function updateGTK() {
  const items = (PRODUCT.goodToKnow || []).filter(g =>
    !g.styles || g.styles.includes(activeStyle)
  );
  const section = document.getElementById('gtk-section');
  section.style.display = items.length ? '' : 'none';
  document.getElementById('gtk-container').innerHTML = items.map(g =>
    `<div class="gtk-card"><div class="gtk-title">${g.title}</div><div class="gtk-body">${g.body}</div></div>`
  ).join('');
}

// ── Terms ────────────────────────────────────────────────────────────────────
function buildTC() {
  document.getElementById('tc-body').innerHTML = (PRODUCT.terms || [])
    .map(t => `<div class="tc-item">${t}</div>`).join('');
}
function toggleTC() {
  const body = document.getElementById('tc-body');
  const open = body.classList.toggle('open');
  document.getElementById('tc-caret').textContent = open ? '▲' : '▼';
}

// ── Sidebar map ──────────────────────────────────────────────────────────────
function squareMarker(size, color) {
  return L.divIcon({
    className: '', html: `<div style="width:${size}px;height:${size}px;background:${color}"></div>`,
    iconSize: [size, size], iconAnchor: [size/2, size/2],
  });
}
function buildSidebarMap() {
  const el = document.getElementById('sidebar-map');
  if (!el || !PRODUCT) return;
  const pts = PRODUCT.map?.points || [];
  sidebarMap = L.map(el, {zoomControl:false,scrollWheelZoom:false,dragging:false,attributionControl:false});
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',{maxZoom:13}).addTo(sidebarMap);
  if (pts.length > 1) {
    const lls = pts.map(p => [p.lat,p.lng]);
    const route = PRODUCT.map?.closeLoop ? [...lls,lls[0]] : lls;
    L.polyline(route,{color:'#0B1733',weight:1.5,dashArray:'4,4'}).addTo(sidebarMap);
  }
  pts.forEach(p => {
    L.marker([p.lat,p.lng],{icon:squareMarker(p.nights>0?10:6,p.nights>0?'#F2B91D':'#6B7080')}).addTo(sidebarMap)
      .bindTooltip(p.label,{permanent:true,direction:'top',offset:[0,-8],className:'city-tip'});
  });
  if (pts.length) {
    const b = L.latLngBounds(pts.map(p=>[p.lat,p.lng]));
    sidebarMap.fitBounds(b,{padding:[10,10]});
  }
  // Sidebar rows
  const s = PRODUCT.styles[activeStyle] || {};
  document.getElementById('sb-rows').innerHTML = `
    <div class="sb-row"><span class="sb-key">Nights</span><span class="sb-val">${s.nights||''}</span></div>
    <div class="sb-row"><span class="sb-key">Route</span><span class="sb-val">${s.route||''}</span></div>
    ${(PRODUCT.about||[]).map(a=>`<div class="sb-row"><span class="sb-key">${a.title}</span><span class="sb-val">${a.body}</span></div>`).join('')}
  `;
}

// ── Map modal ────────────────────────────────────────────────────────────────
function openMapModal() {
  document.getElementById('map-modal').classList.add('open');
  document.getElementById('modal-title').textContent = PRODUCT.title;
  setTimeout(() => {
    if (modalMap) { modalMap.invalidateSize(); return; }
    const el = document.getElementById('modal-map');
    const pts = PRODUCT.map?.points || [];
    modalMap = L.map(el,{zoomControl:true,scrollWheelZoom:true,dragging:true,attributionControl:false});
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',{maxZoom:15}).addTo(modalMap);
    if (pts.length > 1) {
      const lls = pts.map(p => [p.lat,p.lng]);
      L.polyline(PRODUCT.map?.closeLoop?[...lls,lls[0]]:lls,{color:'#0B1733',weight:2}).addTo(modalMap);
    }
    pts.forEach(p => {
      L.marker([p.lat,p.lng],{icon:squareMarker(p.nights>0?20:8,p.nights>0?'#F2B91D':'#0B1733')}).addTo(modalMap)
        .bindTooltip(`${p.label}${p.nights>0?' ('+p.nights+'N)':''}`,{permanent:true,direction:'top'});
    });
    if (pts.length) modalMap.fitBounds(L.latLngBounds(pts.map(p=>[p.lat,p.lng])),{padding:[30,30]});
  }, 50);
}
function closeMapModal() {
  document.getElementById('map-modal').classList.remove('open');
  if (modalMap) { modalMap.remove(); modalMap = null; }
}
document.getElementById('map-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeMapModal();
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMapModal(); });

</script>
</body>
</html>
"""

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    (OUT_DIR / 'products').mkdir(parents=True, exist_ok=True)
    (OUT_DIR / 'prices').mkdir(parents=True, exist_ok=True)

    all_products = {}
    for slug, p_def in PRODUCTS.items():
        print(f"\nProcessing {slug}...")
        try:
            prices = build_prices_json(slug, p_def)
            prod   = build_product_json(slug, p_def)

            prices_path = OUT_DIR / 'prices' / f'{slug}.json'
            prices_path.write_text(json.dumps(prices, indent=2))
            print(f"  ✓ prices/{slug}.json")

            prod_path = OUT_DIR / 'products' / f'{slug}.json'
            prod_path.write_text(json.dumps(prod, indent=2))
            print(f"  ✓ products/{slug}.json")

            all_products[slug] = (prod, prices)
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()

    # products/index.json
    idx = build_index_json(all_products)
    (OUT_DIR / 'products' / 'index.json').write_text(json.dumps(idx, indent=2))
    print("\n✓ products/index.json")

    # index.html
    (OUT_DIR / 'index.html').write_text(INDEX_HTML)
    print("✓ index.html")

    # package.html
    (OUT_DIR / 'package.html').write_text(PACKAGE_HTML)
    print("✓ package.html")

    print("\nDone.")

if __name__ == '__main__':
    main()
