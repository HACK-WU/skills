#!/usr/bin/env node
/**
 * archify-export-cdp — headless export that REUSES the Viewer's own code.
 *
 * The generated artifact already ships a complete export pipeline and exposes
 * it globally:
 *
 *     Archify.exportMenu = { ..., run: runExport, shareCard: rasterizeShareCard }
 *
 * `runExport(format)` is the exact entry point the Export menu buttons use, so
 * calling it reproduces the official artifact byte-for-byte — no
 * reimplementation of serializeSvg()/rasterize() and no re-derivation of theme
 * variables, cleanup rules, or filenames.
 *
 * This script only supplies the missing piece: a browser to run it in.
 *
 * Usage:
 *   node archify-export-cdp.mjs <artifact.html> <format> [outdir]
 *
 *   format: svg | png | jpeg | webp | webm | share-card
 *
 * Environment:
 *   ARCHIFY_CHROME  path to Chrome/Chromium (required)
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const FORMATS = ['svg', 'png', 'jpeg', 'webp', 'webm', 'share-card'];

/** Locate the archify skill, or null when it is not installed. */
function archifyHomeOrNull() {
  const candidates = [
    process.env.ARCHIFY_HOME,
    path.join(os.homedir(), '.codebuddy', 'skills', 'archify'),
  ].filter(Boolean);
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, 'bin', 'archify.mjs'))) return c;
  }
  return null;
}

function archifyHome() {
  const home = archifyHomeOrNull();
  if (home) return home;
  throw new Error(
    'archify skill not found (needs bin/archify.mjs). Set ARCHIFY_HOME to its directory.'
  );
}

const ARCHIFY_INSTALL_HINT =
  '  curl -fsSL https://raw.githubusercontent.com/HACK-WU/skills/master/scripts/skill-install.sh | \\\n'
  + '    bash -s -- --repo tt-a1i/archify';

/** Accept a delivered HTML, or a spec JSON rendered to a temp HTML first. */
function resolveHtml(input, tmpdir) {
  if (!/\.json$/i.test(input)) return { htmlPath: input, rendered: false };

  let spec;
  try {
    spec = JSON.parse(fs.readFileSync(input, 'utf8'));
  } catch {
    throw new Error(`not a valid spec JSON: ${input}`);
  }
  const type = spec.diagram_type;
  if (!type) throw new Error('spec JSON is missing "diagram_type"');

  const out = path.join(tmpdir, 'rendered.html');
  const res = spawnSync(process.execPath, [
    path.join(archifyHome(), 'bin', 'archify.mjs'), 'render', type, input, out,
  ], { encoding: 'utf8' });
  if (res.status !== 0 || !fs.existsSync(out)) {
    throw new Error(`archify render failed:\n${res.stderr || res.stdout || '(no output)'}`);
  }
  return { htmlPath: out, rendered: true };
}

function resolveChrome() {
  // An explicitly configured path is a commitment: if it is wrong, say so
  // instead of silently falling back to some other browser.
  const configured = process.env.ARCHIFY_CHROME;
  if (configured) {
    if (fs.existsSync(configured)) return configured;
    throw new Error(`ARCHIFY_CHROME points to a missing file: ${configured}`);
  }
  const candidates = [
    '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium', '/usr/bin/chromium-browser',
  ];
  for (const c of candidates) if (fs.existsSync(c)) return c;
  throw new Error('Chrome/Chromium not found. Set ARCHIFY_CHROME to its executable path.');
}

/** Does this file actually hold the format we asked for? Guards against
 *  picking an unrelated new file, and against reading a half-written one. */
function matchesFormat(file, format) {
  const kind = format === 'share-card' ? 'png' : format;
  let fd;
  try {
    fd = fs.openSync(file, 'r');
    const head = Buffer.alloc(512);
    const n = fs.readSync(fd, head, 0, 512, 0);
    const b = head.slice(0, n);
    if (kind === 'png') return b.slice(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
    if (kind === 'jpeg') return b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff;
    if (kind === 'webp') return b.slice(0, 4).toString('latin1') === 'RIFF' && b.slice(8, 12).toString('latin1') === 'WEBP';
    if (kind === 'webm') return b.slice(0, 4).equals(Buffer.from([0x1a, 0x45, 0xdf, 0xa3]));
    if (kind === 'svg') return /<svg[\s>]/.test(b.toString('utf8')) || b.slice(0, 5).toString('latin1') === '<?xml';
    return true;
  } catch {
    return false;
  } finally {
    if (fd !== undefined) { try { fs.closeSync(fd); } catch { /* ignore */ } }
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** stat that tolerates entries vanishing mid-scan (shared dirs like /tmp). */
const statOrNull = (p) => {
  try { return fs.statSync(p); } catch { return null; }
};

// ------------------------------------------------------------------ CDP ---

class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
    this.listeners = new Map();
    ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id != null && this.pending.has(msg.id)) {
        const slot = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? slot.reject(new Error(JSON.stringify(msg.error))) : slot.resolve(msg.result);
        return;
      }
      if (msg.method) {
        const set = this.listeners.get(msg.method);
        if (set) for (const cb of set) cb(msg.params);
      }
    });
    // A dropped connection must reject callers, not leave them hanging.
    // Otherwise Node drains its event loop and exits 0 — a silent false success.
    ws.addEventListener('close', () => {
      const err = new Error('Chrome closed the DevTools connection');
      for (const slot of this.pending.values()) slot.reject(err);
      this.pending.clear();
    });
  }

  on(method, cb) {
    if (!this.listeners.has(method)) this.listeners.set(method, new Set());
    this.listeners.get(method).add(cb);
  }

  send(method, params = {}, sessionId, timeoutMs = 60000) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP ${method} timed out after ${timeoutMs}ms`));
      }, timeoutMs);
      this.pending.set(id, {
        resolve: (v) => { clearTimeout(timer); resolve(v); },
        reject: (e) => { clearTimeout(timer); reject(e); },
      });
      this.ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
  }
}

/** Newest file in dir written at/after t0 (downloads overwrite, so mtime moves). */
function newestSince(dir, t0) {
  return fs.readdirSync(dir)
    .filter((f) => !f.endsWith('.crdownload'))
    .map((f) => path.join(dir, f))
    .map((p) => ({ p, st: statOrNull(p) }))
    .filter((e) => e.st && e.st.mtimeMs >= t0)
    .sort((a, b) => b.st.mtimeMs - a.st.mtimeMs)[0]?.p || null;
}

/** Launch Chrome and return a CDP connection to the browser target. */
async function launch(chrome, userDataDir) {
  const proc = spawn(chrome, [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--hide-scrollbars',
    '--remote-debugging-port=0',
    `--user-data-dir=${userDataDir}`,
    'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });

  const wsUrl = await new Promise((resolve, reject) => {
    let buf = '';
    const timer = setTimeout(() => reject(new Error('Chrome did not report a DevTools endpoint')), 30000);
    proc.stderr.on('data', (chunk) => {
      buf += chunk.toString();
      const m = /DevTools listening on (ws:\/\/\S+)/.exec(buf);
      if (m) { clearTimeout(timer); resolve(m[1]); }
    });
    proc.once('exit', (code) => { clearTimeout(timer); reject(new Error(`Chrome exited early (${code})`)); });
  });

  const ws = new WebSocket(wsUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true });
    ws.addEventListener('error', reject, { once: true });
  });
  return { proc, cdp: new Cdp(ws) };
}

// --------------------------------------------------------------- driver ---

async function main(argv) {
  const [artifact, format, outdirArg] = argv;
  if (!artifact || !format || !FORMATS.includes(format)) {
    console.error(`Usage: node export.mjs <artifact.html> <${FORMATS.join('|')}> [outdir|out.svg]`);
    return 2;
  }
  if (!fs.existsSync(artifact)) throw new Error(`artifact not found: ${artifact}`);

  // Preflight: this skill is meaningless without archify. Detect it and stop;
  // never install anything on the user's behalf.
  if (!archifyHomeOrNull()) {
    console.error('archify-svg-export: 未检测到 archify skill，本 skill 依赖它才能工作。');
    console.error('请自行安装（本 skill 不会自动安装）：');
    console.error(ARCHIFY_INSTALL_HINT);
    return 3;
  }

  // The third argument is normally an output DIRECTORY, because archify decides
  // the filename. For svg we also accept an explicit *.svg file path: Chrome
  // still writes archify's own name, so we rename afterwards.
  const explicitFile = format === 'svg' && outdirArg && /\.svg$/i.test(outdirArg)
    ? path.resolve(outdirArg)
    : null;

  const chrome = resolveChrome();
  const outdir = explicitFile
    ? path.dirname(explicitFile)
    : path.resolve(outdirArg || path.dirname(path.resolve(artifact)));
  // mkdirSync would only say EEXIST, which is cryptic when a *file* sits there.
  if (fs.existsSync(outdir) && !fs.statSync(outdir).isDirectory()) {
    throw new Error(`output path exists but is not a directory: ${outdir}`);
  }
  fs.mkdirSync(outdir, { recursive: true });
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'archify-cdp-'));
  // A spec JSON has to be rendered to HTML first; the Viewer only lives in the
  // delivered artifact.
  const renderDir = fs.mkdtempSync(path.join(os.tmpdir(), 'archify-render-'));
  let htmlPath;
  try {
    ({ htmlPath } = resolveHtml(artifact, renderDir));
  } catch (error) {
    // Render happens before the main try/finally, so clean up here too.
    try { fs.rmSync(renderDir, { recursive: true, force: true }); } catch { /* best effort */ }
    throw error;
  }

  const { proc, cdp } = await launch(chrome, userDataDir);
  try {
    // Route whatever the page's download() produces into outdir.
    await cdp.send('Browser.setDownloadBehavior', {
      behavior: 'allow', downloadPath: outdir, eventsEnabled: true,
    });

    const { targetId } = await cdp.send('Target.createTarget', {
      url: pathToFileURL(path.resolve(htmlPath)).href,
    });
    const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });

    const evaluate = (expression, awaitPromise = false, timeoutMs = 60000) =>
      cdp.send('Runtime.evaluate', {
        expression, awaitPromise, returnByValue: true,
      }, sessionId, timeoutMs).then((result) => {
        // A page-side throw arrives as exceptionDetails, not as a CDP error.
        if (result?.exceptionDetails) {
          const d = result.exceptionDetails;
          throw new Error(`page threw: ${d.exception?.description || d.text}`);
        }
        return result;
      });

    // Learn the real filename from CDP rather than diffing the directory:
    // the Viewer always writes the same name, so a re-export overwrites it.
    let suggested = null;
    cdp.on('Browser.downloadWillBegin', (p) => { suggested = p.suggestedFilename; });

    // The Viewer initialises asynchronously; wait for the official entry point.
    const ready = await (async () => {
      for (let i = 0; i < 60; i++) {
        const r = await evaluate('!!(window.Archify && window.Archify.exportMenu && window.Archify.exportMenu.run)');
        if (r.result?.value) return true;
        await sleep(250);
      }
      return false;
    })();
    if (!ready) throw new Error('Archify.exportMenu.run never became available in the artifact');

    // The one and only call: the Viewer's own export.
    const t0 = Date.now();
    await evaluate(`Archify.exportMenu.run(${JSON.stringify(format)})`, true, 180000);

    const err = await evaluate(
      "document.documentElement.getAttribute('data-last-export-error') || ''"
    );
    if (err.result?.value) throw new Error(`viewer reported: ${err.result.value}`);

    // Downloads land slightly after the promise resolves.
    //
    // Two hazards here, both observed:
    //   1. A same-named file from an earlier run is already present — matching
    //      on existence alone returns the STALE file and we then kill Chrome
    //      mid-download, so the real export never lands.
    //   2. Chrome may write the final name directly, so the file exists while
    //      still being written — reading it early yields truncated bytes.
    // Guards: the candidate must be touched at/after t0, have no .crdownload
    // sibling, and report the same size twice in a row.
    const pickCandidate = () => {
      const candidates = [];
      if (suggested) {
        // basename: the name originates from the page, never trust it as a path.
        const p = path.join(outdir, path.basename(suggested));
        const st = statOrNull(p);
        if (st && st.mtimeMs >= t0 && !statOrNull(`${p}.crdownload`)) candidates.push(p);
      }
      const newest = newestSince(outdir, t0);
      if (newest) candidates.push(newest);
      // Only accept a file that really is the requested format.
      return candidates.find((c) => matchesFormat(c, format)) || null;
    };

    let produced = null;
    let lastSize = -1;
    for (let i = 0; i < 120 && !produced; i++) {
      const candidate = pickCandidate();
      const st = candidate ? statOrNull(candidate) : null;
      if (candidate && st) {
        if (st.size > 0 && st.size === lastSize) produced = candidate;
        else lastSize = st.size;
      }
      if (!produced) await sleep(150);
    }
    if (!produced) {
      throw new Error(
        `export ran but no completed ${format} file appeared `
        + `(expected ${suggested || 'a new file'} in ${outdir})`
      );
    }

    // Honour an explicit output filename (svg only).
    if (explicitFile && path.resolve(produced) !== explicitFile) {
      fs.renameSync(produced, explicitFile);
      produced = explicitFile;
    }

    console.log(`${format.toUpperCase()}  ${produced}  ${fs.statSync(produced).size} bytes`);
    console.log(`     via Archify.exportMenu.run('${format}') in ${path.basename(chrome)}`);
    return 0;
  } finally {
    proc.kill('SIGKILL');
    // Chrome keeps flushing its profile after SIGKILL; removing the directory
    // immediately races and throws ENOTEMPTY, which would mask a successful
    // export as a failure. Wait for exit, then clean up best-effort.
    if (proc.exitCode === null && proc.signalCode === null) {
      await new Promise((resolve) => {
        const timer = setTimeout(resolve, 5000);
        proc.once('exit', () => { clearTimeout(timer); resolve(); });
      });
    }
    try { cdp.ws.close(); } catch { /* already closed */ }
    for (const dir of [userDataDir, renderDir]) {
      try { fs.rmSync(dir, { recursive: true, force: true }); } catch { /* best effort */ }
    }
  }
}

main(process.argv.slice(2))
  .then((code) => { process.exitCode = code; })
  .catch((err) => {
    console.error(`archify-svg-export: ${err.message}`);
    process.exitCode = 1;
  });
