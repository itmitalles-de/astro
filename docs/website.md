# Astro website

The project website is the static `site/` directory. It uses the existing Astro artwork, self-hosted Chivo and IBM Plex Mono, native HTML controls and dependency-free JavaScript. There is no framework, bundler, analytics, external font service or browser terminal emulator. The pane playground explains the native layout behavior; it never executes commands.

## Local preview and checks

From the repository root:

```sh
python3 -m http.server 8080 --bind 127.0.0.1 --directory site
```

Open `http://127.0.0.1:8080/`. HTTP is required for JavaScript modules; opening `index.html` through `file://` is not supported. If port 8080 is already in use, choose a free port rather than replacing another service.

```sh
python3 .github/check-site.py
python3 -m unittest discover -s tests -p test_site.py -v
node --test tests/site/*.test.mjs
```

The artifact checker verifies local assets and imports, anchors, image dimensions, domain metadata, the CSP, and a 2 MiB site-size budget. Node's built-in test runner covers both languages, locale and theme defaults, and immutable normal/full-span layout operations with a six-pane diagram limit. No package install is needed for these checks.

For browser QA, use Node 22+ and a **dedicated** headless Chromium/Brave profile, never a user's normal browser debugging endpoint. Pass that instance's CDP origin to:

```sh
node tools/check_site_browser.mjs \
  --url http://127.0.0.1:8080/ \
  --cdp http://127.0.0.1:9223 \
  --output /absolute/path/to/qa \
  --axe /absolute/path/to/axe.min.js
```

The CDP port above is an example; allocate an unused port for the dedicated browser. The optional axe-core script is a QA-only dependency and is not shipped. The tool tests both themes/languages at 320, 390, 768, 1024 and 1440 CSS pixels, layout actions, keyboard input, persistence, unavailable storage, reduced motion, installation-copy success/denial, resource requests and readable no-JavaScript content. Copy tests use an isolated browser clipboard stub and **do not** verify or replace the desktop clipboard. Automated accessibility checks do not establish full WCAG conformance or replace manual screen-reader and real-device testing. Reports and actual browser screenshots are written into the requested output directory.

## Product capture and licenses

`site/assets/workspace.png` is a native, unmodified Kitty/Xvfb capture. Its example project is deliberately labeled and contains no personal workspace, private user paths or real agent sessions. A simplified three-pane layout illustrates the controls; it is **not** the bundled default session. The installation section describes the bundled agent workspace and its side effects.

Recreate the capture on a machine with Kitty, Xvfb and Pillow with XCB support:

```sh
python3 tools/capture_site.py --kitty /path/to/kitty --xvfb /path/to/Xvfb \
  --evidence /absolute/path/to/private-capture-evidence.json
```

The script uses private HOME/XDG directories, a private X display and a socket-only Kitty connection. It runs actual `cat README.md`, Git status and Astro's Zoomies preview, then stops only its own processes. It never launches agent CLIs or touches the owner's running terminal. The default capture is 1440 × 760; keep the HTML dimensions and CSS aspect ratio aligned if changing it. Keep the evidence JSON outside the public artifact because it includes local paths.

The logo files are unchanged copies of `assets/astro.svg` and `assets/astro-128.png`. Astro's only open eye stays on the viewer's right. Keep those copies in sync when intentionally updating the canonical brand. Font provenance and OFL licenses are included in `site/assets/fonts/`.

## Preferences and progressive enhancement

- `astro-site.language`: valid `en`/`de` choices override the first browser locale. Otherwise German locales select German; all others select English.
- `astro-site.theme`: `light`/`dark` override the OS; `system` follows live OS changes. Early bootstrap avoids the wrong initial language/theme.
- Storage access is guarded; language/theme still work for the current page if persistence is blocked.
- Without JavaScript the English content, product evidence, installation commands and native FAQ remain readable. Language/theme controls, copy and the layout diagram require JavaScript.
- The web theme does not recolor the actual terminal screenshot. Reduced motion disables smooth scrolling. There are no autoplay videos or decorative entrance animations.

## Publication

`.github/workflows/pages.yml` validates the artifact and runs the Node tests on pull requests, main pushes and manual dispatches. Only main can deploy, and pull requests cannot deploy. The build job has read-only repository permissions; only the deployment job receives Pages and OIDC write permissions. Action references are pinned to verified release commits. Only `site/` is uploaded, not the repository, tests or review artifacts.

Publication and DNS changes require owner approval. Enable GitHub Pages with GitHub Actions as its build source and set `astro.wutz.io` as the repository's custom domain **before** adding DNS. The checked-in `CNAME` records the intended domain but does not configure it for a custom Actions deployment. Point the exact subdomain CNAME at `itmitalles-de.github.io` (DNS-only), not a repository path. Verify the Pages deployment, DNS, certificate, enforced HTTPS, redirects, assets and actual page before describing it as live.

Do not publish unrelated pending commits or uncommitted user changes implicitly. If the publication branch includes earlier app commits, disclose the full outgoing range in the owner's approval. Keep private review decisions, browser profiles, API credentials and capture logs outside `site/`.
