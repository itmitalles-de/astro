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
python3 -m unittest discover -s tests -p test_site_validator.py -v
node --test tests/site/*.test.mjs
```

The artifact checker verifies local assets and imports (including dynamic imports and `.js` modules), anchors, PNG chunk framing/checksums, image dimensions, domain metadata, the exact self-hosted CSP, and a 2 MiB site-size budget. It rejects entries escaping the artifact and special files before reading their content. Structural PNG checks do not replace actual browser decoding. Node's built-in test runner covers both languages, locale/theme/variant defaults, immutable normal/full-span layout operations with a six-pane diagram limit, canonical ASCII cat geometry and positive-scale responsive artist poses. The full `python3 tools/check.py` suite also compares all ordinary diagram insertion sequences up to six panes with the installed Kitty layout, rather than assuming an abstract split always matches native insertion. No package install is needed for the Node checks.

For browser QA, use Node 22+ and a **dedicated** headless Chromium/Brave profile, never a user's normal browser debugging endpoint. Pass that instance's CDP origin to:

```sh
node tools/check_site_browser.mjs \
  --url http://127.0.0.1:8080/ \
  --cdp http://127.0.0.1:9223 \
  --output /absolute/path/to/qa \
  --axe /absolute/path/to/axe.min.js
```

The CDP port above is an example; allocate an unused port for the dedicated browser. The optional axe-core script is a QA-only dependency and is not shipped. The tool tests both themes/languages at 320, 390, 768, 1024 and 1440 CSS pixels, layout actions, keyboard input, persistence, unavailable storage, reduced motion, installation-copy success/denial, resource requests and readable no-JavaScript content. It also exercises real ASCII frame/pixel changes, keyboard pause, saved pause, a complete burst, offscreen/hidden suspension, reduced-motion stills, canvas failure and software frame timings. Run it once for each `?variant=orbit`, `?variant=zoomies` and `?variant=hyperraum` URL. Drawing-call observation preserves the native Canvas implementation; timing samples are taken after the observation wrapper is removed. Copy tests use an isolated browser clipboard stub and **do not** verify or replace the desktop clipboard. Automated accessibility checks do not establish full WCAG conformance or replace manual screen-reader and real-device testing. Reports and actual browser screenshots are written into the requested output directory.

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
- `astro-site.theme`: `light`/`dark` override the OS; `system` follows live OS changes. Early bootstrap applies the theme and variant; the application resolves language once while replacing English fallback content, so fallback text is never prematurely tagged German. A missing/partial bootstrap still honors valid saved choices.
- `astro-site.motion`: an explicit `paused` choice freezes the artwork on future loads; `auto` permits motion only while the system preference and visibility allow it.
- Storage access is guarded; language/theme still work for the current page if persistence is blocked.
- Without JavaScript the English content, product evidence, installation commands, native FAQ and static ASCII fallback remain readable. Language/theme controls, copy, live artwork and the layout diagram require JavaScript. Canvas failure leaves the same fallback and does not block the functional site.
- The web theme does not recolor the actual terminal screenshot or the terminal-colored ASCII artwork. Reduced motion disables smooth scrolling and composes a still, with no recurring artwork frame work; pointer input and the disabled burst cannot override it. There are no autoplay videos or section entrance effects.

## ASCII variants

The URL parameter `variant` accepts only `orbit`, `zoomies` or `hyperraum` (default: `orbit`). It is applied before CSS for stable hero composition; it does not persist a design choice or change the canonical site URL. All variants retain the real terminal capture and product content:

- **Orbit:** a wide canonical ASCII portrait with perspective orbital streams and an interactive star burst.
- **Zoomies:** a split hero and a front-facing running/jumping ASCII cat, articulated legs/tail, paw marks and momentum trails. Direction changes never mirror the head.
- **Hyperraum:** an immersive native-dark hero, copy-safe left column, right-hand portrait, layered ASCII corridor and hyperspace rush. Mobile stacks copy above a centered scene.

`ascii-model.mjs` samples the canonical silhouette and facial geometry from the source SVG. Only the shared head painter renders green, on the viewer-right eye. `ascii-scene.mjs` owns the single frame loop, local font use, DPR cap (1.5), responsive density, 24/18 fps ceilings, user pause, one-shot burst, lifecycle and visibility. It rearms a resolution query when DPR changes, redraws backing pixels without resuming paused motion, and starts at the inclusive 10% intersection threshold. Glyph font sizes are quantized to quarter pixels to bound font-cache churn without changing the artwork. The alternate artists are stateless ASCII drawing functions: they never schedule work or attach input handlers. Zoomies keeps its head/body connected even during the complete rush and direction-change cycle. Touch scrolling is not intercepted. The 18ms p95 QA budget measures software drawing on the test machine, not performance on physical phones.

The browser density check changes DPR without changing the CSS box. Chromium's CDP override updates resolution values without immediately dispatching media-query changes, so the harness requests native media reevaluation before checking the canvas; it does not inject DOM resize/change events. This is emulation, not a physical multi-monitor check.

The full-field particle assembly belongs to Orbit only. Zoomies and Hyperraum keep their heads coherent from the first frame while the body/trails or corridor animate; this preserves whole-head framing and Hyperraum's copy-safe region during the early intro, not just at rest. Hyperraum's opaque copy backing matches the terminal background and makes text contrast independently verifiable. Its no-canvas fallback uses the same right-hand safe region on desktop.

The three variants are alternatives for owner review; their presence in a local branch is not a publication or a design selection. Reviews, videos, browser profiles and decisions stay outside `site/`.

## Publication

`.github/workflows/pages.yml` validates the artifact and runs the Node tests on pull requests, main pushes and manual dispatches. Only main can deploy, and pull requests cannot deploy. The build job has read-only repository permissions; only the deployment job receives Pages and OIDC write permissions. Action references are pinned to verified release commits. Only `site/` is uploaded, not the repository, tests or review artifacts.

Publication and DNS changes require owner approval. Enable GitHub Pages with GitHub Actions as its build source and set `astro.wutz.io` as the repository's custom domain **before** adding DNS. The checked-in `CNAME` records the intended domain but does not configure it for a custom Actions deployment. Point the exact subdomain CNAME at `itmitalles-de.github.io` (DNS-only), not a repository path. Verify the Pages deployment, DNS, certificate, enforced HTTPS, redirects, assets and actual page before describing it as live.

Do not publish unrelated pending commits or uncommitted user changes implicitly. If the publication branch includes earlier app commits, disclose the full outgoing range in the owner's approval. Keep private review decisions, browser profiles, API credentials and capture logs outside `site/`.
