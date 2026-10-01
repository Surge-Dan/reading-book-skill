// Portable static-deck renderer. Uses an existing Playwright package; never installs one.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { pathToFileURL, fileURLToPath } = require('node:url');
const args = process.argv.slice(2);
function option(name, fallback) { const i = args.indexOf(name); return i < 0 ? fallback : args[i + 1]; }
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const normal = text => text.replace(/\s/gu, '');
const folder = path.resolve(option('--folder', '.'));
const output = path.resolve(option('--output', path.join(folder, '.render')));
const stage = option('--stage', 'preview');
const reportFile = path.join(output, 'render-report.json');
fs.mkdirSync(output, { recursive: true });
function fail(message, status = 'failed') { const e = new Error(message); e.status = status; throw e; }
function assetFile(url) {
  if (!url.startsWith('file:')) fail('图片与字体须为分享目录内的本地文件；先核对来源，不在导出时联网取素材。');
  const file = fileURLToPath(url);
  const relative = path.relative(folder, file);
  if (relative.startsWith('..') || path.isAbsolute(relative)) fail('资源超出分享目录。');
  return { file, relative: relative.replaceAll(path.sep, '/') };
}
function verifyPNG(file, expectedHash) {
  const bytes = fs.readFileSync(file);
  if (!bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) || bytes.readUInt32BE(16) !== 900 || bytes.readUInt32BE(20) !== 1200) return false;
  return !expectedHash || hash(bytes) === expectedHash;
}

async function main() {
  const started = Date.now();
  let chromium;
  try { ({ chromium } = require(option('--playwright-package', 'playwright'))); }
  catch { fail('缺少 Node Playwright。保留 HTML，可传入现有包路径；不自动安装。', 'unavailable'); }
  const job = JSON.parse(fs.readFileSync(path.join(folder, 'share-job.json'), 'utf8'));
  const assetMap = new Map(job.assets.map(asset => [asset.path, asset]));
  function assetHash(url) {
    if (url.startsWith('data:')) return hash(url);
    const item = assetFile(url);
    const registered = assetMap.get(item.relative);
    if (!registered) fail(`资源未登记来源：${item.relative}`);
    const actual = hash(fs.readFileSync(item.file));
    if (actual !== registered.sha256) fail(`素材版本已变化：${item.relative}`);
    return actual;
  }
  const requested = stage === 'final' ? job.pages : job.pages.slice(0, Math.min(2, job.pages.length));
  let previous;
  try { previous = JSON.parse(fs.readFileSync(path.join(folder, 'validation-report.json'), 'utf8')); } catch { previous = null; }
  const executablePath = option('--browser');
  const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
  try {
    const context = await browser.newContext({ viewport: { width: 980, height: 1280 }, deviceScaleFactor: 1, colorScheme: 'light', serviceWorkers: 'block' });
    const page = await context.newPage();
    const globalResources = new Set();
    const blockedRequests = [];
    page.on('request', request => {
      if (['stylesheet', 'font'].includes(request.resourceType())) globalResources.add(request.url());
    });
    await page.route('**/*', route => {
      const url = route.request().url();
      if (url.startsWith('file:') || url.startsWith('data:')) return route.continue();
      blockedRequests.push(url.split('?')[0]);
      return route.abort();
    });
    await page.goto(pathToFileURL(path.join(folder, 'deck.html')).href, { waitUntil: 'load', timeout: 25000 });
    await page.evaluate(async () => {
      await Promise.race([
        (async () => { await document.fonts.ready; await Promise.all(Array.from(document.images, image => image.decode())); })(),
        new Promise((_, reject) => setTimeout(() => reject(new Error('字体或图片超过 20 秒未就绪。')), 20000)),
      ]);
    });
    if (blockedRequests.length) fail('HTML 引用了外部资源；请先转换为已登记的本地素材。');
    await page.addStyleTag({ content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}' });
    const inspected = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.page'));
      return {
        shared: document.head.innerHTML + '\n' + Array.from(document.body.attributes, a => a.name + '=' + a.value).join('|'),
        fonts: Array.from(document.fonts, font => ({ family: font.family, status: font.status })),
        pages: cards.map(card => {
          const frame = card.getBoundingClientRect();
          const cssImages = new Set();
          // Images in CSS are dependencies too: a background or mask can change
          // without changing HTML. Track them per card to keep repairs local.
          for (const el of [card, ...card.querySelectorAll('*')]) {
            for (const pseudo of [null, '::before', '::after']) {
              const style = getComputedStyle(el, pseudo);
              for (const value of [style.backgroundImage, style.maskImage, style.borderImageSource, style.listStyleImage, style.content]) {
                for (const match of (value || '').matchAll(/url\((?:"([^"]*)"|'([^']*)'|([^)]*))\)/g)) cssImages.add(new URL(match[1] || match[2] || match[3], document.baseURI).href);
              }
            }
          }
          const markers = Array.from(card.querySelectorAll('[data-ink],[data-block],[data-label],[data-status]')).filter(el => !el.parentElement.closest('[data-ink],[data-block],[data-label],[data-status]'));
          const text = markers.filter(el => el.textContent.trim()).map(el => {
            const rect = el.getBoundingClientRect(), style = getComputedStyle(el);
            let clipped = rect.left < frame.left - .5 || rect.top < frame.top - .5 || rect.right > frame.right + .5 || rect.bottom > frame.bottom + .5;
            // A Range includes lines hidden by a fixed-height wrapper; box dimensions alone do not.
            const range = document.createRange(); range.selectNodeContents(el);
            for (const line of range.getClientRects()) {
              if (line.left < frame.left - .5 || line.top < frame.top - .5 || line.right > frame.right + .5 || line.bottom > frame.bottom + .5) clipped = true;
              for (let parent = el; parent && parent !== card; parent = parent.parentElement) {
                const parentStyle = getComputedStyle(parent), box = parent.getBoundingClientRect();
                if (['hidden', 'clip', 'scroll', 'auto'].includes(parentStyle.overflowY) && (line.top < box.top - .5 || line.bottom > box.bottom + .5)) clipped = true;
                if (['hidden', 'clip', 'scroll', 'auto'].includes(parentStyle.overflowX) && (line.left < box.left - .5 || line.right > box.right + .5)) clipped = true;
              }
            }
            return { text: el.innerText, x: +(rect.x - frame.x).toFixed(2), y: +(rect.y - frame.y).toFixed(2), width: +rect.width.toFixed(2), height: +rect.height.toFixed(2),
              font: [style.fontFamily, style.fontSize, style.fontWeight, style.lineHeight, style.color], clipped,
              hidden: !rect.width || !rect.height || style.visibility === 'hidden' || Number(style.opacity) === 0 };
          });
          const overlaps = [];
          for (let i = 0; i < text.length; i++) for (let j = i + 1; j < text.length; j++) {
            const a = text[i], b = text[j];
            if (Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x) > 1 && Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y) > 1) overlaps.push([a.text.slice(0, 60), b.text.slice(0, 60)]);
          }
          return { id: card.id, width: frame.width, height: frame.height, html: card.outerHTML, text, overlaps,
            blocks: Array.from(card.querySelectorAll('[data-block]'), el => ({ id: el.dataset.block, text: el.innerText })),
            statusLabels: Array.from(card.querySelectorAll('[data-status]'), el => el.innerText),
            images: [...new Set([...Array.from(card.querySelectorAll('img'), el => el.currentSrc), ...cssImages])] };
        }),
      };
    });
    const actualIds = inspected.pages.map(card => card.id);
    if (new Set(actualIds).size !== actualIds.length || actualIds.some(id => !job.pages.some(p => p.id === id))) fail('HTML 的页面 ID 重复或不在任务计划中。');
    if (requested.some(p => !actualIds.includes(p.id))) fail('缺少当前阶段要求的页面；保留草稿。');
    if (stage === 'final' && (actualIds.length !== job.pages.length || actualIds.some((id, i) => id !== job.pages[i].id))) fail('完整 HTML 的页面数量或顺序与任务不一致。');
    const artHash = hash(JSON.stringify({ shared: inspected.shared, fonts: inspected.fonts, globalAssets: Array.from(globalResources).sort().map(url => [url, assetHash(url)]),
      environment: [process.platform, browser.version()], renderer: hash(fs.readFileSync(__filename)), width: 900, height: 1200 }));
    for (const card of inspected.pages) {
      const planned = job.pages.find(item => item.id === card.id);
      const expectedBlocks = new Map(planned.blocks.map(block => [block.id, block]));
      if (card.blocks.length !== expectedBlocks.size || new Set(card.blocks.map(b => b.id)).size !== card.blocks.length || card.blocks.some(block => !expectedBlocks.has(block.id) || normal(block.text) !== normal(expectedBlocks.get(block.id).text))) fail(`${card.id} 的可见内容与确认文本不一致。`);
      if (!card.statusLabels.length || (job.source_mode === 'sample' && !card.statusLabels.some(text => text.includes('样例')))) fail(`${card.id} 缺少诚实的数据模式标记。`);
      if (job.source_mode === 'live' && !job.period.complete && !card.statusLabels.some(text => text.includes('截至') && text.includes(job.period.as_of))) fail(`${card.id} 须注明记录截至日期。`);
      const dependencies = card.images.map(url => assetHash(url));
      card.fingerprint = hash(JSON.stringify({ artHash, html: card.html, text: card.text, assets: dependencies }));
    }
    if (stage === 'final') {
      const approval = job.approvals.visual;
      if (!approval || approval.art_hash !== artHash || Object.entries(approval.anchors).some(([id, fingerprint]) => inspected.pages.find(p => p.id === id)?.fingerprint !== fingerprint)) fail('封面或代表内页的视觉版本已变化；先预览当前图片再记录确认。');
    }
    const errors = requested.flatMap(planned => {
      const card = inspected.pages.find(p => p.id === planned.id);
      const issues = [];
      if (card.width !== 900 || card.height !== 1200) issues.push({ page: card.id, problem: 'dimensions' });
      if (card.text.some(t => t.clipped || t.hidden)) issues.push({ page: card.id, problem: 'text_clipped_or_hidden', text: card.text.filter(t => t.clipped || t.hidden).map(t => t.text.slice(0, 100)) });
      if (card.overlaps.length) issues.push({ page: card.id, problem: 'text_overlap', pairs: card.overlaps });
      return issues;
    });
    if (errors.length) {
      fs.writeFileSync(reportFile, JSON.stringify({ status: 'failed', errors }, null, 2));
      return false;
    }
    const imageDir = path.join(output, 'images');
    fs.mkdirSync(imageDir, { recursive: true });
    let rendered = 0, reused = 0;
    const images = [];
    for (const planned of requested) {
      const card = inspected.pages.find(p => p.id === planned.id);
      const filename = `${String(job.pages.indexOf(planned) + 1).padStart(2, '0')}-${planned.id}.png`;
      const target = path.join(imageDir, filename);
      const cached = previous?.images?.find(image => image.id === planned.id && image.fingerprint === card.fingerprint);
      let usable = false;
      if (cached) { try { usable = verifyPNG(path.join(folder, 'images', cached.file), cached.sha256); } catch { usable = false; } }
      if (usable) { fs.copyFileSync(path.join(folder, 'images', cached.file), target); reused++; }
      else { await page.locator(`[id="${planned.id}"]`).screenshot({ path: target, animations: 'disabled' }); rendered++; }
      if (!verifyPNG(target)) fail(`PNG 尺寸或格式异常：${planned.id}`);
      images.push({ id: planned.id, file: filename, width: 900, height: 1200, fingerprint: card.fingerprint, sha256: hash(fs.readFileSync(target)), reused: usable });
    }
    // A 375px-wide reading view of each requested page, arranged in two columns.
    await page.evaluate(ids => document.querySelectorAll('.page').forEach(card => { if (!ids.includes(card.id)) card.remove(); }), requested.map(p => p.id));
    await page.addStyleTag({ content: 'html{width:750px}body{width:750px;padding:0!important;margin:0!important;display:grid;grid-template-columns:375px 375px;gap:16px 0;background:#d6d6d3}.page{zoom:0.4166666667;margin:0!important}' });
    await page.setViewportSize({ width: 750, height: 500 });
    await page.screenshot({ path: path.join(output, 'overview.png'), fullPage: true });
    const pages = inspected.pages.map(({ html, ...card }) => card);
    fs.writeFileSync(reportFile, JSON.stringify({ status: 'pass', stage, art_hash: artHash, pages, requested_ids: requested.map(p => p.id), images, rendered, reused,
      elapsed_seconds: +((Date.now() - started) / 1000).toFixed(2), visual_review: 'pending', coverage: 'text boxes and registered assets; aesthetic judgment and editorial grounding remain human reviews' }, null, 2) + '\n');
    return true;
  } finally { await browser.close(); }
}
main().then(ok => { if (!ok) process.exitCode = 2; }).catch(error => {
  fs.writeFileSync(reportFile, JSON.stringify({ status: error.status || 'failed', reason: error.message.slice(0, 1200) }, null, 2) + '\n');
  process.exitCode = 2;
});
