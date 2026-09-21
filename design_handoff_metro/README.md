# Handoff: Metro-styled FIT Destinations Index & Package Page

## Overview
Two screens for Europe Incoming's B2B FIT catalogue: a **Destinations Index** listing FIT packages for a region, and a **Package Page** showing one package day-by-day with switchable travel style, hotel category and season pricing. The visual treatment is a **Windows Metro** interpretation (flat, zero-radius, no shadows, light typography) rendered in Europe Incoming's brand colours — navy `#0B1733`, gold `#F2B91D`, white.

This was one of four design-language explorations (Material Design, Apple HIG, Metro, Fluent). Metro was selected because flat surfaces, square corners and reserved colour are closest to EI's own brand logic.

## About the Design Files
The files in this bundle are **design references created in HTML** — prototypes showing intended look and behaviour, **not production code to copy directly**. They use a bespoke streaming-template runtime (`support.js`, `<x-dc>`, `{{ }}` holes, `<sc-for>`, `<sc-if>`) that exists only in the authoring environment. Do not port that runtime.

The task is to **recreate these designs in the target codebase's existing environment** (React, Next.js, Vue, etc.) using its established component patterns, routing and data layer. If no environment exists yet, choose the framework most appropriate for the project and implement the designs there. Read the HTML for exact values; rebuild the structure idiomatically.

## Fidelity
**High-fidelity.** Colours, typography, spacing, states and copy are final. Recreate the UI faithfully using the codebase's existing libraries. The one thing deliberately left open is the Metro-vs-production question: EI's production styling uses 6px radii and soft navy-tinted shadows, while this mockup uses 0px radii and no shadows. Build what's specified here unless the team decides otherwise.

---

## Screens / Views

### 1. Destinations Index
**File:** `Destinations Index - Metro Design Mockup.dc.html`
**Purpose:** A trade user scans FIT packages for a region and clicks through to one package.

**Layout**
- Full-width, white page. No max-width container; horizontal padding `40px` throughout.
- Top to bottom: exploration banner → header row → page title block → intro line → card grid.
- Header row: `display:flex; align-items:center; gap:28px; padding:26px 40px 0`.
- Title block: `padding:36px 40px 22px; display:flex; align-items:flex-end; gap:20px; flex-wrap:wrap`.
- Intro line: `padding:0 40px 30px; max-width:640px`.
- Card grid: `display:grid; grid-template-columns:repeat(auto-fill,minmax(440px,1fr)); gap:12px; padding:0 40px 80px`.

**Components**

*Exploration banner* — remove in production. `background:#F2B91D; color:#0B1733; font-size:11px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; padding:7px 40px`.

*Logo* — `assets/logo-europe-incoming.png`, `height:32px; width:auto; display:block`. No filters — the real brand colours must show.

*Search input* — wrapper `flex:1; max-width:360px`. Input: full width, `padding:9px 14px`, `font-size:13px`, `border:2px solid #D8DAE1`, `border-radius:0`, `background:#FFFFFF`, `color:#1A1D2E`, `outline:none`, `box-sizing:border-box`. Placeholder `search packages` (lowercase, intentional). Filters cards live on each keystroke against package title and region, case-insensitive.

*Trade enquiries link* — `margin-left:auto`, `font-size:12px; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:#0B1733; text-decoration:none`. `mailto:fitsales@europeincoming.com`.

*Page title* — `UK & Ireland`. `font-weight:300; font-size:64px; letter-spacing:-0.02em; line-height:1; color:#0B1733; margin:0`. The light weight at large size is the Metro signature.

*Title eyebrow* — `Multi-country · FIT`. `font-size:13px; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:#F2B91D; padding-bottom:12px` (baseline-aligns with the h1).

*Intro line* — `FIT packages across the UK and Ireland — self drive, rail and private coach.` `font-weight:300; font-size:19px; color:#6B7080`.

*Package tile* (anchor) — `display:flex; align-items:stretch; text-decoration:none; color:inherit; min-height:240px; border-radius:0; transition:opacity 180ms linear`. Hover: `opacity:.86`. No shadow, no border, no lift.

Alternating tile colour by grid position, `index % 3 === 1` gets the gold variant:

| Variant | Background | Title / price | Body | Meta |
|---|---|---|---|---|
| Navy (default) | `#132347` | `#FFFFFF` | `rgba(255,255,255,0.72)` | `#F2B91D` |
| Gold (every 3rd, offset 1) | `#F2B91D` | `#0B1733` | `rgba(11,23,51,0.8)` | `rgba(11,23,51,0.65)` |

Tile left column — `flex:1; min-width:0; padding:22px 24px; display:flex; flex-direction:column; gap:8px`:
1. Meta line `{nights} · {season}` — `font-size:11px; font-weight:700; letter-spacing:.14em; text-transform:uppercase`.
2. Title — `font-weight:300; font-size:30px; line-height:1.1`.
3. Blurb — `font-size:13px; line-height:1.55; margin:0`.
4. Route line, stops joined with ` · ` — `font-size:11px; letter-spacing:.06em; text-transform:uppercase`.
5. Price row, `margin-top:auto; padding-top:10px; display:flex; align-items:baseline; gap:8px` — `From` label (11px/700/.12em/uppercase), amount (`font-weight:300; font-size:34px; line-height:1`), price note (11px).
6. Validity line — `font-size:10px; font-weight:700; letter-spacing:.12em; text-transform:uppercase`. Prints the validity string verbatim; **do not prepend "Valid"** — the source string already carries it.

Tile right column — `width:190px; flex-shrink:0; position:relative; background:#F5F5F3`, holds an absolutely-positioned route map filling the cell.

*Route mini-map* — Leaflet, CARTO `light_all` tiles, `maxZoom:13`. Non-interactive: `zoomControl:false, scrollWheelZoom:false, dragging:false, attributionControl:false`. Bounds fit to all points with `0.35` degrees padding plus `[10,10]` px. Route drawn as `L.polyline`, `color:#0B1733`, `weight:1.5`, `dashArray:'4,4'`; closes the loop when the product's `map.closeLoop` is true. Overnight stops: **square** `10×10px` `#F2B91D` div markers. Pass-through stops: **square** `6×6px` `#6B7080`. Squares, not pins — Metro has no rounded geometry. Every marker carries a permanent label tooltip.

*Map label tooltip* (`.city-tip`) — transparent background, no border, no shadow, no arrow. `font-size:9px; font-weight:600; color:#0B1733`, four-way 1px white text-shadow for legibility over tiles.

*Empty state* — `padding:80px 0; color:#6B7080; font-weight:300; font-size:22px`, text `No packages match this search yet.` Shows only when products loaded and the filter matched nothing.

---

### 2. Package Page
**File:** `Package Page - Metro Design Mockup.dc.html`
**Purpose:** A trade user reads one package in full, switches travel style / hotel category / season, checks rates, and downloads a PDF or emails for a quote.

**Layout**
- White page, `40px` horizontal padding. Two-column body: content column `flex:1; min-width:0`, sidebar `width:300px; flex-shrink:0; position:sticky; top:20px`, `gap:40px`.
- Hero row: image block `flex:1; min-width:320px; min-height:380px` beside a `280px` navy facts panel, `gap:0` (blocks touch — Metro tiles abut).
- Print: `.no-print` hidden, `.print-block` becomes `display:block`, `.print-full` gets `padding:24px 0`.

**Components**

*Header* — logo (`height:24px`), back link, trade enquiries link, Download PDF button. Back link: circular `26px` outline glyph `←` (`border:2px solid #0B1733; border-radius:50%`) plus `All packages` in 11px/700/.12em/uppercase — the only circle on the page, as a navigational affordance. Navigates to the index.

*Download PDF button* — `background:#0B1733; color:#FFFFFF; border:none; border-radius:0; padding:10px 18px; font-size:11px; font-weight:700; letter-spacing:.12em; text-transform:uppercase`. Hover: `background:#F2B91D; color:#0B1733`. Opens Terms & conditions, then fires the browser print dialog after 150ms.

*Title block* — eyebrow (11px/700/.14em/uppercase/`#F2B91D`) above `h1` at `font-weight:300; font-size:56px; letter-spacing:-0.02em`, baseline-aligned.

*Hero image* — `object-fit:cover`, fills its block, navy `#0B1733` behind while loading. Height driven by the `heroHeight` value, default `380px`.

*Facts panel* — `width:280px; background:#0B1733; color:#FFFFFF; padding:24px 26px; display:flex; flex-direction:column; gap:14px`. Duration (label 10px/700/.14em/uppercase/`#F2B91D`, value `font-weight:300; font-size:24px`), Route (13px, `rgba(255,255,255,0.78)`), then a gold `#F2B91D` price block pinned with `margin-top:auto` — `From` label, amount at `font-weight:300; font-size:34px`, `per person` at 11px/600/uppercase.

> **Known issue to resolve in implementation:** because the price block is pinned to the bottom, a tall hero leaves an empty gap between Route and From. Either fill it (validity + hotel category lines) or let the panel hug its content. Pick one and apply it consistently.

*Travel style switcher* — label `Travel style` (10px/700/.14em/uppercase/`#6B7080`) then one button per style, `gap:4px`. Metro button spec:

| State | Background | Text | Border |
|---|---|---|---|
| Selected | `#0B1733` | `#FFFFFF` | `2px solid #0B1733` |
| Unselected | `transparent` | `#0B1733` | `2px solid #D8DAE1` |

Shared: `border-radius:0; padding:8px 16px; font-size:10px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; cursor:pointer`. The active style's blurb sits to the right at 13px `#6B7080`. Same button spec is reused for hotel category (3 star / 4 star) and season (Apr–Oct / Nov–Mar).

*Section headings* — `font-weight:300; font-size:34px; color:#0B1733`, with a 10px/700/.14em/uppercase `#F2B91D` sub-label beneath naming the active travel style.

*Day-by-day rows* — `display:grid; grid-template-columns:64px 1fr; gap:20px; padding:22px 0; border-top:1px solid #E5E7EC`. Left: `Day` label (10px/700/uppercase/`#6B7080`) over the number at `font-weight:300; font-size:40px; line-height:1; color:#F2B91D`. Right: title (600/19px/`#0B1733`), overnight line (10px/700/.14em/uppercase/`#6B7080`), description (14px/1.7/`#3A3D4D`), then a `gap:6px` column of tagged lines.

Tag pills — square, `padding:4px 10px`, `font-size:10px; font-weight:700; letter-spacing:.1em; text-transform:uppercase`:

| Tag | Text | Background |
|---|---|---|
| Included | `#FFFFFF` | `#0B1733` |
| Local taste | `#0B1733` | `#F2B91D` |
| Local experience | `#0B1733` | `#EDEDEA` |
| Shopping | `#6B7080` | `#F5F5F3` |

`Included` shows the transport/inclusion string for that day number under the active travel style, falling back to the day's own fallback text, then `Day at leisure.`. `Local taste` is suppressed when food tips are switched off.

*Package includes* — two-column grid, `gap:0 32px`. Each row `padding:9px 0 9px 22px; border-bottom:1px solid #EFF0F3`, with an absolutely-positioned gold `✓` at `left:0`.

*Sample hotels* — three equal columns, `gap:8px`. Each `background:#F5F5F3; padding:18px 20px`: city (`font-weight:300; font-size:22px`), nights (10px/700/uppercase/`#6B7080`), then `3 STAR` / `4 STAR` gold labels each followed by the hotel name at 12.5px.

*Rates table* — full width, `border-collapse:collapse`. Header cells `background:#0B1733; color:#FFFFFF; padding:12px 16px; font-size:10px; font-weight:700; letter-spacing:.12em; text-transform:uppercase`; left-aligned `Occupancy`, right-aligned `Rate — {category} · {season}`. Body rows: label 13.5px, price `font-weight:300; font-size:22px` right-aligned, `border-bottom:1px solid #EFF0F3`. Three rows: Single, Twin / Double, Child (2–11). Footnote at 12px `#6B7080`: `All rates in €, net, per person. Twin/double occupancy unless stated. Child 2–11 yrs sharing with 2 adults.` While prices load, a single `Loading rates…` row shows.

*Optional tours & extras* — two-column grid, `gap:8px`. Each `background:#F5F5F3; padding:14px 18px; display:flex; justify-content:space-between; align-items:center`, name at 13px, price at `font-weight:300; font-size:22px` with a 10px uppercase `pp` suffix.

*Good to know* — two-column grid of navy `#0B1733` tiles, `padding:18px 20px`. Title 10px/700/.14em/uppercase/`#F2B91D`, body 13px `rgba(255,255,255,0.8)`. Filtered to entries with no style restriction or one matching the active travel style.

*Terms & conditions* — full-width collapsed button, `background:#F5F5F3; border:none; border-radius:0; padding:14px 18px`, label left / caret right, 10px/700/.12em/uppercase. Hover `background:#EDEDEA`. Caret `▼` closed, `▲` open. Expanded panel lists terms at 12.5px with a gold `·` marker and `1px solid #EFF0F3` dividers.

*Sidebar — About this tour* — `background:#F5F5F3; padding:20px`. Contains a `180px` route map (click to enlarge, `cursor:zoom-in`, `pointer-events:none` on the map itself so the click always lands), an `Enlarge` badge bottom-right (`background:#0B1733; color:#FFFFFF; font-size:10px; font-weight:700; letter-spacing:.12em; uppercase; padding:6px 12px`, square), then key/value rows separated by `1px solid #E5E7EC`: nights + route, then each about item.

*Sidebar — quote card* — `background:#F2B91D; color:#0B1733; padding:20px`. Heading `Ready to quote?` (10px/700/.14em/uppercase), body `Send us your dates and party size — we respond within one working day.` (13px), then a full-width navy button `Email the FIT team` (11px/700/.12em/uppercase, `background:#0B1733; color:#FFFFFF; padding:12px 0`), `mailto:fitsales@europeincoming.com`.

*Route map modal* — overlay `position:fixed; inset:0; z-index:1000; background:rgba(11,23,51,0.85); display:flex; align-items:center; justify-content:center; padding:40px`. Panel `background:#FFFFFF; width:min(960px,100%); height:min(640px,100%)`, square corners, no shadow. Title bar `background:#0B1733; padding:14px 20px` with the route title in 10px/700/.14em/uppercase white and a gold `✕` close button. The large map is interactive (zoom control, scroll wheel, drag). Overnight markers become `20px` gold squares with the night count in `#0B1733`; pass-through stops are `8px` navy squares. Closes on overlay click, on the ✕, and on `Escape`; the Leaflet instance is destroyed on close.

*Footer* — `background:#0B1733; color:rgba(255,255,255,0.55); padding:20px 40px; font-size:12px`, company line left, email (gold link) + `+44 208 994 5001` right.

---

## Interactions & Behavior

**Index → Package.** A tile click navigates to the package page with the product file as a query parameter: `Package Page - Metro Design Mockup.dc.html?product={encoded productFile}`. In the target app, replace with real routing (e.g. `/fit/{region}/{slug}`).

**Package page query parameters.** `product` selects the product JSON; optional `style` preselects a travel style when it exists on that product, otherwise the first style is used.

**Travel style switch.** Rewrites day-by-day inclusions, inclusions list, section sub-labels, hero duration/route, sidebar facts, rate lookups and the Good-to-know filter. No page reload.

**Hotel category / season switch.** Only re-reads the rates table and its heading.

**From price.** The minimum twin rate across every category and season for the active travel style — not a stored field.

**Map enlarge.** Sidebar map click opens the modal, drawing the large map ~50ms after mount so the container has dimensions. Escape and overlay clicks close it; inner clicks stop propagation.

**Download PDF.** Opens the Terms section, waits 150ms so it renders, then calls the browser print dialog. `.no-print` elements (banner, header, switchers, sidebar, modal) are hidden and the content column goes full width.

**Transitions.** Tiles fade opacity over `180ms linear`. Buttons and links change colour instantly. No transforms, no scale, no bounce, no spring — the brand's motion vocabulary is calm, and Metro reinforces it.

**Responsive.** Not addressed in the mockups; both pages assume desktop widths. The index grid already reflows via `auto-fill minmax(440px,1fr)`. Below ~900px the package page's two-column body and hero row need to stack — decide that behaviour during implementation.

## State Management

Index:
- `search` — string, filter query.
- `products` — array, from `products/index.json`.
- A map-drawing registry keyed by DOM id so each mini-map initialises exactly once.

Package page:
- `product` — object, from the `product` query parameter.
- `prices` — object, from the `pricesFile` named on the product.
- `style` — active travel style key; defaults to the `style` query parameter when valid, else the first key.
- `cat` — `'3'` or `'4'`.
- `season` — `'summer'` or `'winter'`.
- `tcOpen` — boolean.
- `mapOpen` — boolean.

Data fetching: index loads `products/index.json` on mount. Package page loads the product JSON, then its `pricesFile`. Both render loading placeholders (`…`, `Loading rates…`) rather than blocking. The mockups poll for Leaflet and container readiness on a timer; in a real app, load Leaflet as a module dependency and initialise in an effect instead.

## Design Tokens

Colours
| Token | Hex | Use |
|---|---|---|
| Gold | `#F2B91D` | Accent, gold tiles, day numbers, map overnight markers, quote card |
| Gold hover | `#E5AC12` | Reserved (not used in Metro) |
| Navy | `#0B1733` | Structural fills, headings, primary button, footer |
| Navy tile | `#132347` | Default package tile background |
| Ink | `#1A1D2E` | Body text |
| Body grey | `#3A3D4D` | Day descriptions, list text |
| Muted | `#6B7080` | Labels, captions, secondary text |
| Line | `#E5E7EC` | Primary hairline |
| Line light | `#EFF0F3` | Table and list dividers |
| Control border | `#D8DAE1` | Unselected button / input border |
| Surface | `#F5F5F3` | Light panel fill |
| Surface hover | `#EDEDEA` | Panel hover |
| White | `#FFFFFF` | Page background |

Typography — `'Segoe UI', 'Open Sans', sans-serif`. Metro's identity is weight contrast: `300` for anything large, `600`/`700` for anything small and uppercase. Nothing between.

| Role | Size / weight / tracking |
|---|---|
| Page title (index) | 64px / 300 / -0.02em |
| Page title (package) | 56px / 300 / -0.02em |
| Section heading | 34px / 300 |
| Day number | 40px / 300 |
| Price large | 34px / 300 |
| Price medium | 22px / 300 |
| Tile title | 30px / 300 |
| Card city | 22px / 300 |
| Day title | 19px / 600 |
| Body | 14px / 400 / 1.7 line-height |
| Small body | 13px / 400 |
| Label | 10–11px / 700 / .12–.14em / uppercase |

Spacing — 4px grid. Page gutter `40px`; column gap `40px`; grid gaps `8px` and `12px`; panel padding `18–26px`; row padding `22px 0`.

Radius — `0` everywhere. The single exception is the `50%` back-arrow circle in the package header.

Shadow — none. Depth comes from colour blocks only.

Motion — `opacity 180ms linear` on tiles. Nothing else animates.

## Assets
- `assets/logo-europe-incoming.png` — Europe Incoming logo, used at 32px (index) and 24px (package) height. **Never apply CSS filters to it** — earlier explorations did and the wordmark became illegible. It must render in its own brand colours.
- Hero and package photography — referenced by `heroImage` in each product JSON. Source images from the brand's photo library; the design system calls for full-bleed landmark photography, natural colour, no duotone or heavy filtering.
- Leaflet 1.9.4 + CARTO `light_all` basemap tiles for route maps.
- Fonts: Segoe UI where available, Open Sans (Google Fonts, weights 300/400/600/700) as the loaded fallback.

## Data Shape

`products/index.json` → `{ products: [...] }`, each entry: `id`, `title`, `region`, `nights`, `season`, `validity`, `blurb`, `routeStops[]`, `currency`, `fromPrice`, `priceNote`, `productFile`, `map`.

Product JSON: `title`, `eyebrow`, `heroImage`, `pricesFile`, `map { points[{lat,lng,label,nights}], closeLoop }`, `days[{num,title,overnight,desc,taste,experience,shopping,fallbackIncluded}]`, `styles{ key: {name,blurb,nights,route,aboutNights,transport{dayNum:string},inclusions[]} }`, `hotels[{city,nights,h3,h4}]`, `about[{title,body}]`, `goodToKnow[{title,body,styles?}]`, `terms[]`.

Prices JSON: `validFrom`, `validTo`, `variants{ styleKey: { '3'|'4': { summer|winter: {single,twin,child} } } }`, `optionalTours[{name,price}]`.

## Files
| File | What it is |
|---|---|
| `Destinations Index - Metro Design Mockup.dc.html` | Index screen reference |
| `Package Page - Metro Design Mockup.dc.html` | Package screen reference |
| `support.js` | Authoring-environment runtime. **Reference only — do not port.** |
| `products/index.json` | Package list data |
| `products/ireland-discovery.json` | Sample product |
| `prices/2026.json` | Sample rates |
| `assets/logo-europe-incoming.png` | Logo |

## PDF Export (Download PDF)

The mockup's "Download PDF" button drives the browser's native print (`window.print()`) with a dedicated print stylesheet — no separate PDF renderer. Recreate this as a **print stylesheet on the package page itself**, not a generated file, unless the target stack already has a PDF pipeline (e.g. Puppeteer/wkhtmltopdf) — if so, apply the same rules to that template instead.

**Rules for what prints:**
- Hide all interactive-only chrome: exploration banner, top nav, travel-style/hotel-category/season switchers, sidebar (About this tour + Ready to quote card), route map modal.
- Show a compact print-only header with just the Europe Incoming logo top-left (the interactive header's logo is hidden along with the rest of that row — add a separate small logo block that only renders at print).
- Hide the **Good to know** section and the **About this tour** sidebar entirely in the PDF — trade users don't need them in the printed doc.
- **Package rates**: regardless of which hotel category / season the user has selected on screen, the PDF must show a single grid with **all four combinations** — 3★ and 4★, Apr–Oct and Nov–Mar — for the currently loaded pricing year. Never print just the selected combination, and never print more than one year (only one price file is ever active at a time — there's no "compare years" requirement).
- **Terms & conditions**: force this section open before printing (don't rely on the on-screen collapsed state) and give it a plain, static heading — not the same clickable toggle button used on screen (remove pointer/hover affordance, hide the ▼/▲ caret, keep the label). Prevent individual term lines from breaking across a page (`break-inside: avoid` equivalent) and keep the heading attached to its content (`break-after: avoid`) so it never sits alone at the bottom of a page.
- Compact every section for print: smaller headings (section titles ~16px, not 34px), tighter row padding on day-by-day / hotel / tour cards, smaller day-number and pill text. The on-screen type scale is far too large for a printed A4/Letter page and leaves excessive white space — cut sizes and paddings by roughly half to two-thirds across the board rather than reusing the screen values.
- Reduce the hero image height for print (screen default 380px → roughly 130px is enough) and shrink the navy facts panel accordingly.
- Page numbers: there is no reliable cross-browser CSS mechanism to print true "Page X of Y" text from arbitrary page content — this comes from the browser's own print dialog ("Headers and footers" option in Chrome/Edge), which is a user-facing print setting, not something the page can force on. Leave normal page margins in place (don't zero out `@page` margins) so that native header/footer has room to render without colliding with content. If the target stack instead uses a server-side PDF renderer (e.g. headless Chrome/Puppeteer), that's the point where real page numbers can be added via that tool's header/footer template option.

See `Package Page - Metro Design Mockup.dc.html` for the exact print CSS (search for `@media print`) and the class names used to scope it (`no-print`, `print-only`, `print-only-block`, `print-hide`, and the `pp-*` compacting classes) — port the intent (what's hidden, what's compacted, the full rate grid, the fixed T&C heading) into whatever styling approach the target codebase uses; the class names themselves don't need to survive the port.

## Brand system note
Europe Incoming has a design system covering colour, type, voice and components. Where this handoff and that system disagree, the deliberate Metro departures are: **0px radii** (system says 6px) and **no shadows** (system defines a navy-tinted shadow scale). Everything else — gold as a reserved accent, navy as structural, white-dominant pages, calm motion with no bounce, UK English, uppercase labels — follows the system and must be preserved. Use the codebase's existing brand tokens where they exist rather than hard-coding these hex values.
