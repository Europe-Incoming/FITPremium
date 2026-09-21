#!/usr/bin/env python3
"""
Renders one branded PDF per (product, travel style) for the UK & Ireland
Metro pages, using Playwright against the site's own package.html + print
stylesheet. Run after generate_metro_uk_ireland.py.

Output: multi-country/uk-ireland/pdfs/{slug}-{style}.pdf

This subfolder is deliberately NOT the top level of multi-country/uk-ireland/,
so rebuild_site.py's os.listdir(folder)-based legacy PDF auto-discovery never
picks these up (bugfix: keep generated PDFs out of legacy auto-discovery).
"""
import http.server
import json
import socket
import threading
from contextlib import closing
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path('/home/user/FITPremium')
OUT_DIR = REPO_ROOT / 'multi-country' / 'uk-ireland'
PDF_DIR = OUT_DIR / 'pdfs'
CHROMIUM_PATH = '/opt/pw-browsers/chromium'


def free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def serve(root, port):
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(root), **kw)
    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def main():
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    index = json.loads((OUT_DIR / 'products' / 'index.json').read_text())
    products = index['products']

    port = free_port()
    httpd = serve(REPO_ROOT, port)
    base = f'http://127.0.0.1:{port}/multi-country/uk-ireland'

    generated = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM_PATH)
        page = browser.new_page(viewport={'width': 1200, 'height': 1600})

        for prod_meta in products:
            slug = prod_meta['id']
            product_json = json.loads((OUT_DIR / 'products' / f'{slug}.json').read_text())
            styles = list(product_json['styles'].keys())

            for style in styles:
                url = f'{base}/package.html?product=products/{slug}.json&style={style}'
                page.goto(url, wait_until='networkidle')
                page.wait_for_selector('#rates-container .rates-table, #rates-container', timeout=10000)
                page.wait_for_timeout(300)

                out_path = PDF_DIR / f'{slug}-{style}.pdf'
                page.emulate_media(media='print')
                page.pdf(
                    path=str(out_path),
                    format='A4',
                    print_background=True,
                    margin={'top': '14mm', 'bottom': '14mm', 'left': '12mm', 'right': '12mm'},
                )
                generated.append(out_path.name)
                print(f'  ✓ pdfs/{out_path.name}')

        browser.close()
    httpd.shutdown()

    print(f'\nGenerated {len(generated)} PDFs in {PDF_DIR}')


if __name__ == '__main__':
    main()
