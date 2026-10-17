// SPDX-License-Identifier: GPL-3.0-or-later
// Real-browser QA. Connect only to a dedicated, task-owned Chromium CDP endpoint.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { checkAsciiScene } from './check_ascii_browser.mjs';

const options = Object.fromEntries(process.argv.slice(2).reduce((pairs, item, i, args) =>
  i % 2 === 0 ? [...pairs, [item.replace(/^--/, ''), args[i + 1]]] : pairs, []));
assert(options.url && options.cdp && options.output, 'Required: --url URL --cdp URL --output DIRECTORY [--axe FILE]');
const output = path.resolve(options.output);
await fs.mkdir(output, { recursive: true });
const checks = [];
const errors = [];
const failures = [];
const requests = new Set();
const accessibility = [];
const screenshots = [];
let target;
let animation;
let ws;
let commandId = 0;
let loadCount = 0;
const pending = new Map();
function check(name, condition, detail) {
  assert(condition, `${name}${detail ? ': ' + JSON.stringify(detail) : ''}`);
  checks.push(name);
}
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++commandId;
    const timer = setTimeout(() => { pending.delete(id); reject(Error(`CDP timeout: ${method}`)); }, 20000);
    pending.set(id, { resolve, reject, timer });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function until(expression) {
  const end = Date.now() + 15000;
  while (Date.now() < end) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw Error(`Page condition timed out: ${expression}`);
}
async function navigate(interactive = true) {
  const previous = loadCount;
  await send('Page.navigate', { url: options.url });
  const end = Date.now() + 15000;
  while (loadCount === previous && Date.now() < end) await new Promise(resolve => setTimeout(resolve, 25));
  assert(loadCount > previous, 'Navigation did not produce a fresh page load');
  await until(interactive ? 'document.readyState === "complete" && document.querySelectorAll("[data-pane]").length === 3' : 'document.readyState === "complete"');
  await evaluate('document.fonts.ready.then(() => true)');
}
async function screenshot(name, fullPage = true) {
  await evaluate('scrollTo({top:0,behavior:"instant"})');
  const params = { format: 'png', captureBeyondViewport: fullPage };
  if (fullPage) {
    const metrics = await send('Page.getLayoutMetrics');
    const size = metrics.cssContentSize || metrics.contentSize;
    params.clip = { x: 0, y: 0, width: Math.ceil(size.width), height: Math.ceil(size.height), scale: 1 };
  }
  const image = await send('Page.captureScreenshot', params);
  await fs.writeFile(path.join(output, name), Buffer.from(image.data, 'base64'));
  screenshots.push(name);
}
const click = selector => evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
const chooseTheme = theme => evaluate(`document.querySelector('#theme').value=${JSON.stringify(theme)}; document.querySelector('#theme').dispatchEvent(new Event('change',{bubbles:true}))`);
const paneCount = () => evaluate('document.querySelectorAll("[data-pane]").length');
const state = () => evaluate('({lang:document.documentElement.lang,theme:document.documentElement.dataset.theme})');

try {
  const base = options.cdp.replace(/\/$/, '');
  target = await (await fetch(`${base}/json/new?about:blank`, { method: 'PUT' })).json();
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
  ws.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const promise = pending.get(message.id);
      if (!promise) return;
      pending.delete(message.id); clearTimeout(promise.timer);
      if (message.error) promise.reject(Error(JSON.stringify(message.error))); else promise.resolve(message.result);
    } else if (message.method === 'Page.loadEventFired') loadCount++;
    else if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails);
    else if (message.method === 'Log.entryAdded' && message.params.entry.level === 'error') errors.push(message.params.entry);
    else if (message.method === 'Network.responseReceived') {
      const response = message.params.response;
      requests.add(response.url);
      if (response.status >= 400) failures.push({ url: response.url, status: response.status });
    }
  });
  for (const domain of ['Page', 'Runtime', 'Network', 'Log']) await send(`${domain}.enable`);
  await send('Network.setCacheDisabled', { cacheDisabled: true });
  const version = await send('Browser.getVersion');
  await send('Network.setUserAgentOverride', { userAgent: version.userAgent, acceptLanguage: 'en-US,en;q=0.9', platform: 'Linux' });
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] });
  await send('Storage.clearDataForOrigin', { origin: new URL(options.url).origin, storageTypes: 'local_storage' });
  await navigate();
  check('English browser selects English and system dark', (await state()).lang === 'en' && (await state()).theme === 'dark');
  check('All real images load', await evaluate('[...document.images].every(img=>img.complete&&img.naturalWidth>0)'));
  await until('document.querySelector("#ascii-scene")?.dataset.ready==="true"');
  check('ASCII artwork initializes without replacing the real product capture', await evaluate('Boolean(document.querySelector("#ascii-scene[data-ready=true] canvas") && document.querySelector(".product img[data-alt=workspaceAlt]"))'));
  animation = await checkAsciiScene({send,evaluate,until,check,navigate,click,target});
  check('Desktop headline fits the intended two-line composition', await evaluate('document.querySelector("h1").getBoundingClientRect().height < 200'));
  check('Normal split adds one pane', (await click('#split-right'), await paneCount()) === 4);
  check('Normal split preserves the initial right-hand pair', await evaluate(`document.querySelector('[data-pane="2"]').parentElement.parentElement.querySelector('[data-pane="3"]') !== null`));
  await click('#reset-layout');
  await evaluate('document.querySelector("#whole-span").checked=true');
  await click('#split-below');
  check('Touch whole-span split wraps the full original tree', await evaluate('document.querySelector("#layout-diagram>.layout-split").classList.contains("rows") && document.querySelector("#layout-diagram>.layout-split>.layout-child:first-child").querySelectorAll("[data-pane]").length===3'));
  await click('#reset-layout');
  await evaluate('document.querySelector("#split-right").dispatchEvent(new MouseEvent("click",{bubbles:true,shiftKey:true}))');
  check('Shift-modified click adds a full-height column', await evaluate('document.querySelector("#layout-diagram>.layout-split>.layout-child:first-child").querySelectorAll("[data-pane]").length===3'));
  await click('#split-right'); await click('#split-right');
  check('Six-pane cap disables further splitting', (await paneCount()) === 6 && await evaluate('document.querySelector("#split-right").disabled&&document.querySelector("#split-below").disabled'));
  await click('#reset-layout');
  await click('[data-pane="2"]');
  check('Pane selection keeps keyboard focus', await evaluate('document.activeElement.dataset.pane==="2" && document.activeElement.getAttribute("aria-pressed")==="true"'));
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39 });
  check('Arrow key navigation moves selection and focus to the next pane', await evaluate('document.activeElement.dataset.pane==="3" && document.activeElement.getAttribute("aria-pressed")==="true"'));
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Home', code: 'Home', windowsVirtualKeyCode: 36 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Home', code: 'Home', windowsVirtualKeyCode: 36 });
  check('Home key returns selection and focus to the first pane', await evaluate('document.activeElement.dataset.pane==="1" && document.activeElement.getAttribute("aria-pressed")==="true"'));
  await click('#reset-layout');
  await evaluate('document.querySelector("#language-toggle").focus()');
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', text: '\r', unmodifiedText: '\r', windowsVirtualKeyCode: 13 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
  check('Keyboard language toggle translates labels and metadata', await evaluate('document.documentElement.lang==="de" && document.querySelector("[data-i18n=hero1]").textContent==="Dein Terminal." && document.title.includes("ruhige Gesellschaft")'));
  await chooseTheme('light');
  await navigate();
  check('Manual language and theme survive reload', (await state()).lang === 'de' && (await state()).theme === 'light');
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] });
  check('Explicit light mode overrides dark system mode', (await state()).theme === 'light');
  await chooseTheme('system');
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
  await until('document.documentElement.dataset.theme==="light"');
  check('System mode follows a live OS theme change', (await state()).theme === 'light');

  // Only stub the browser clipboard. Do not touch the owner's desktop selections.
  await evaluate('Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:async text=>{globalThis.__copied=text}}})');
  await click('#copy-install');
  await until('globalThis.__copied === document.querySelector("#install-commands").textContent');
  check('Copy handler passes the exact installation commands', await evaluate('globalThis.__copied.startsWith("git clone https://github.com/itmitalles-de/astro.git\\n") && document.querySelector("#copy-status").textContent.includes("kopiert")'));
  await click('#language-toggle');
  check('Language changes clear transient feedback from the previous locale', await evaluate('document.querySelector("#copy-status").textContent === ""'));
  await click('#language-toggle');
  await evaluate('navigator.clipboard.writeText=async()=>{throw new DOMException("Denied for QA","NotAllowedError")}');
  await click('#copy-install');
  await until('document.querySelector("#copy-status").textContent.includes("manuell")');
  check('Denied clipboard access selects commands with visible guidance', await evaluate('getSelection().toString()===document.querySelector("#install-commands").textContent && document.activeElement.id==="install-commands"'));
  check('A denied quick recopy cannot retain an obsolete success label', await evaluate('document.querySelector("#copy-install").textContent==="Befehle kopieren"&&!document.querySelector("#copy-install").hasAttribute("aria-busy")'));
  await evaluate('getSelection().removeAllRanges(); document.querySelector("#copy-status").textContent=""; document.querySelector("#copy-install").textContent=document.documentElement.lang==="de"?"Befehle kopieren":"Copy commands"');
  await click('details:first-child summary');
  check('Native disclosure opens via its own control', await evaluate('document.querySelector("details").open'));
  await click('details:first-child summary');
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }, { name: 'prefers-reduced-motion', value: 'reduce' }] });
  check('Reduced-motion preference disables smooth scroll', await evaluate('getComputedStyle(document.documentElement).scrollBehavior==="auto"'));

  const axeSource = options.axe ? await fs.readFile(options.axe, 'utf8') : null;
  for (const language of ['en', 'de']) {
    if ((await state()).lang !== language) await click('#language-toggle');
    for (const theme of ['dark', 'light']) {
      await chooseTheme(theme);
      for (const width of [1440, 1024, 768, 390, 320]) {
        await send('Emulation.setDeviceMetricsOverride', { width, height: width < 600 ? 844 : 1000, deviceScaleFactor: 1, mobile: width < 600 });
        check(`No horizontal page overflow: ${language}/${theme}/${width}`, await evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth'));
        check(`Heading and buttons retain content: ${language}/${theme}/${width}`, await evaluate('document.querySelector("h1").textContent.trim().length>15 && [...document.querySelectorAll("button:not(:disabled),select")].every(el=>el.getBoundingClientRect().width>0)'));
        if ((width === 1440 || width === 390) && axeSource) {
          await evaluate(axeSource);
          const result = await evaluate('axe.run(document,{runOnly:{type:"tag",values:["wcag2a","wcag2aa","wcag21a","wcag21aa","wcag22aa"]}}).then(r=>({version:r.testEngine.version,violations:r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary,checks:n.any,html:n.html}))})),incomplete:r.incomplete.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,html:n.html,checks:[...n.any,...n.all,...n.none]}))})),passes:r.passes.length}))');
          accessibility.push({ language, theme, width, ...result });
          check(`Axe WCAG A/AA: ${language}/${theme}/${width}`, result.violations.length === 0, result.violations);
          check(`Axe has no unresolved manual checks: ${language}/${theme}/${width}`, result.incomplete.length === 0, result.incomplete);
        }
        if ((language === 'en' && theme === 'dark' && width === 1440) || (language === 'de' && theme === 'light' && width === 1440) || (language === 'de' && theme === 'dark' && width === 390) || (language === 'en' && theme === 'light' && width === 390)) {
          await screenshot(`site-${language}-${theme}-${width}.png`);
          if (width === 1440) await screenshot(`site-${language}-${theme}-${width}-hero.png`, false);
        }
      }
    }
  }
  await send('Network.setUserAgentOverride', { userAgent: version.userAgent, acceptLanguage: 'de-DE,de;q=0.9,en;q=0.8', platform: 'Linux' });
  await evaluate('localStorage.clear()');
  await navigate();
  check('German browser selects German automatically', (await state()).lang === 'de');
  await send('Page.addScriptToEvaluateOnNewDocument', { source: 'Object.defineProperty(window,"localStorage",{get(){throw new DOMException("Blocked for QA","SecurityError")}})' });
  await navigate();
  check('Blocked storage does not break initialization', (await state()).lang === 'de' && (await paneCount()) === 3);
  await click('#language-toggle'); await chooseTheme('light');
  check('Language and theme still work without storage', (await state()).lang === 'en' && (await state()).theme === 'light');
  await send('Emulation.setScriptExecutionDisabled', { value: true });
  await navigate(false);
  check('Without JavaScript, real content and install commands remain available', await evaluate('document.querySelector("h1").textContent.includes("Your terminal")&&document.querySelector("noscript").textContent.includes("Enable JavaScript")&&document.querySelector("#install-commands").textContent.includes("./install.sh")'));
  check('All requests stay on the site origin', [...requests].every(url => new URL(url).origin === new URL(options.url).origin), [...requests]);
  check('No broken HTTP resources', failures.length === 0, failures);
  check('No browser errors or CSP violations', errors.length === 0, errors);
  console.log(JSON.stringify({ status: 'passed', assertions: checks.length, screenshots: screenshots.length, axe_scenarios: accessibility.length, animation }, null, 2));
} catch (error) {
  console.error(error.stack);
  process.exitCode = 1;
} finally {
  await fs.writeFile(path.join(output, 'browser-qa.json'), JSON.stringify({ status: process.exitCode ? 'failed' : 'passed', checks, errors, failures, requests: [...requests], accessibility, screenshots, animation }, null, 2));
  if (ws?.readyState === WebSocket.OPEN && target) {
    try { await send('Target.closeTarget', { targetId: target.id }); } catch {}
    ws.close();
  }
}
