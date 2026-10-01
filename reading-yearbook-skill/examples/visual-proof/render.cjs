// Bounded local proof renderer; no install, model calls, or account access.
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { createHash } = require('node:crypto');

async function main() {
  const args = process.argv.slice(2);
  function option(name) { const i = args.indexOf(name); return i < 0 ? undefined : args[i + 1]; }
  const packagePath = option('--playwright-path');
  const executablePath = option('--browser');
  const source = path.resolve(option('--source') || path.join(__dirname, 'deck.html'));
  if (!packagePath || !executablePath) throw new Error('Specify --playwright-path and --browser; no dependencies are installed automatically.');
  const { chromium } = require(packagePath);
  const out = path.join(path.dirname(source), 'images');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ executablePath, headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 980, height: 1280 }, deviceScaleFactor: 1 });
    await page.goto(pathToFileURL(source).href, { waitUntil: 'load' });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all(Array.from(document.images, img => img.decode()));
    });
    const result = await page.evaluate(() => Array.from(document.querySelectorAll('.page'), card => {
      const frame = card.getBoundingClientRect();
      const text = Array.from(card.querySelectorAll('[data-ink]'), el => {
        const rect = el.getBoundingClientRect();
        return { text: el.innerText, x: rect.x - frame.x, y: rect.y - frame.y, width: rect.width, height: rect.height,
          clipped: rect.left < frame.left || rect.top < frame.top || rect.right > frame.right + 0.5 || rect.bottom > frame.bottom + 0.5 || el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0 };
      });
      const overlaps = [];
      for (let i = 0; i < text.length; i++) for (let j = i + 1; j < text.length; j++) {
        const a = text[i], b = text[j];
        if (Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x) > 1 && Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y) > 1) overlaps.push([a.text, b.text]);
      }
      return { id: card.id, width: frame.width, height: frame.height, text, overlaps };
    }));
    const bad = result.filter(x => x.width !== 900 || x.height !== 1200 || x.text.some(t => t.clipped) || x.overlaps.length);
    const reportPath = path.join(path.dirname(source), 'validation-report.json');
    const report = { status: bad.length ? 'failed' : 'rendering', scope: 'sample-only', sourceSha256: createHash('sha256').update(fs.readFileSync(source)).digest('hex'), fonts: await page.evaluate(() => ({ serif: document.fonts.check('64px "Noto Serif SC"'), sans: document.fonts.check('34px "Noto Sans SC"') })), pages: result, visualReview: 'pending' };
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n');
    if (bad.length) throw new Error('Text bounds/overlap check failed; see validation-report.json.');
    for (const card of result) await page.locator(`[id="${card.id}"]`).screenshot({ path: path.join(out, `${card.id}.png`) });
    report.images = result.map(card => {
      const bytes = fs.readFileSync(path.join(out, `${card.id}.png`));
      const width = bytes.readUInt32BE(16), height = bytes.readUInt32BE(20);
      if (width !== 900 || height !== 1200) throw new Error(`Unexpected PNG dimensions: ${card.id}`);
      return { file: `${card.id}.png`, width, height, sha256: createHash('sha256').update(bytes).digest('hex') };
    });
    await page.addStyleTag({ content: 'body {padding:0!important; background:#d3d5d0} .page {zoom:0.4166666667;margin:0 0 20px!important}' });
    await page.setViewportSize({ width: 375, height: 1020 });
    await page.screenshot({ path: path.join(out, 'mobile-preview.png'), fullPage: true });
    report.status = 'pass';
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify({ status: 'pass', pages: result.length, dimensions: '900x1200', output: out }));
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
