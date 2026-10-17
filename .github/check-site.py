#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate the dependency-free Pages artifact without network access."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import struct
import sys
from urllib.parse import unquote, urlsplit

DOMAIN = 'https://astro.wutz.io/'


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(site):
    site = site.resolve()
    html = (site / 'index.html').read_text()
    document = Document(html)
    ids = [attrs['id'] for _, attrs in document.elements if 'id' in attrs]
    require(len(ids) == len(set(ids)), 'Duplicate HTML id')
    checked = set()

    def local_asset(reference, base=site):
        url = urlsplit(reference)
        if url.scheme or url.netloc:
            require(url.scheme == 'https', f'Unexpected external asset URL: {reference}')
            return
        if not url.path:
            require(not url.fragment or url.fragment in ids, f'Missing anchor: {reference}')
            return
        path = ((site if url.path.startswith('/') else base) / unquote(url.path).lstrip('/')).resolve()
        require(path.is_relative_to(site), f'Asset escapes the artifact: {reference}')
        require(path.is_file(), f'Missing local asset: {reference}')
        checked.add(path)

    for tag, attrs in document.elements:
        if tag in ('img', 'script'):
            require('src' in attrs, f'{tag} must use an external local source')
            require(not urlsplit(attrs['src']).scheme, f'{tag} must be self-hosted')
            local_asset(attrs['src'])
        if tag == 'img':
            require('alt' in attrs, 'Image is missing alt text')
            require('width' in attrs and 'height' in attrs, 'Image dimensions are required')
        if tag in ('link', 'a') and 'href' in attrs:
            local_asset(attrs['href'])
    for css in site.rglob('*.css'):
        for reference in re.findall(r'url\([\'"]?([^\)\'"\s]+)', css.read_text()):
            local_asset(reference, css.parent)
    for script in site.rglob('*.mjs'):
        for reference in re.findall(r"(?:from\s*|import\s*)['\"]([^'\"]+)['\"]", script.read_text()):
            require(reference.startswith('./'), f'Unbundled external module: {reference}')
            local_asset(reference, script.parent)
    meta = {attrs.get('property', attrs.get('name', attrs.get('http-equiv'))): attrs.get('content', '')
            for tag, attrs in document.elements if tag == 'meta'}
    require(meta.get('viewport') == 'width=device-width,initial-scale=1', 'Missing responsive viewport')
    require(meta.get('og:url') == DOMAIN, 'Wrong Open Graph URL')
    require(any(tag == 'link' and attrs.get('rel') == 'canonical' and attrs.get('href') == DOMAIN
                for tag, attrs in document.elements), 'Wrong canonical URL')
    require(meta.get('og:image', '').startswith(DOMAIN), 'Open Graph image must belong to this site')
    local_asset(meta['og:image'].removeprefix(DOMAIN))
    csp = meta.get('Content-Security-Policy', '')
    for directive in ("default-src 'self'", "script-src 'self'", "object-src 'none'", "base-uri 'self'", "form-action 'none'"):
        require(directive in csp, f'Missing CSP directive: {directive}')
    require('unsafe-inline' not in csp and 'unsafe-eval' not in csp, 'CSP must not allow inline/eval scripts')
    require((site / 'CNAME').read_text().strip() == 'astro.wutz.io', 'Wrong Pages custom domain')
    require((site / '.nojekyll').is_file(), 'Missing .nojekyll')
    require(DOMAIN + 'sitemap.xml' in (site / 'robots.txt').read_text(), 'Wrong robots sitemap URL')
    require(f'<loc>{DOMAIN}</loc>' in (site / 'sitemap.xml').read_text(), 'Wrong sitemap URL')
    png = (site / 'assets/workspace.png').read_bytes()
    require(png[:8] == b'\x89PNG\r\n\x1a\n', 'Product capture must be a real PNG')
    dimensions = struct.unpack('>II', png[16:24])
    require(dimensions[0] >= 1000 and dimensions[1] >= 600, 'Product capture is too small')
    files = [path for path in site.rglob('*') if path.is_file()]
    total_bytes = sum(path.stat().st_size for path in files)
    require(total_bytes < 2 * 1024 * 1024, 'Static site exceeds the 2 MiB artifact budget')
    require(not any(path.name.startswith('.env') or path.suffix == '.log' for path in files), 'Private configuration/log in artifact')
    return {'files': len(files), 'bytes': total_bytes, 'local_references': len(checked), 'capture_dimensions': dimensions}


if __name__ == '__main__':
    try:
        print(json.dumps(check(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'site'), indent=2))
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from error
