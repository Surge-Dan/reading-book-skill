/* Public demo only: use the same renderer as the current web preview. */
const fs = require('fs'), path = require('path'), assert = require('assert');
const { chromium } = require('playwright');

(async () => {
  const out = path.join(__dirname, 'reading-html-demo');
  const html = fs.readFileSync(path.join(out, 'index.html'), 'utf8');
  const browser = await chromium.launch({ headless: true,
    executablePath: process.env.BROWSER_EXECUTABLE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' });
  try {
    const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1000 } });
    await context.setOffline(true);
    const page = await context.newPage(), errors = [], network = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => { if (/^https?:/.test(r.url())) network.push(r.url()); });
    await page.setContent(html, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForFunction(() => document.querySelector('#previewCanvas').width === 900);
    await page.waitForTimeout(1800);
    await page.screenshot({ path: path.join(out, 'web-preview.png') });
    const rows = await page.evaluate(async () => {
      const data = JSON.parse(document.querySelector('#reading-data').textContent);
      const art = JSON.parse(document.querySelector('#reading-art').textContent);
      const cache = new Map();
      const loadImage = src => {
        if (!cache.has(src)) cache.set(src, new Promise((resolve, reject) => {
          const image = new Image(); image.onload = () => resolve(image); image.onerror = reject; image.src = src;
        }));
        return cache.get(src);
      };
      const renderer = ReadingShareArtwork.create({ data, art, loadImage });
      const pages = ['cover', 'stats', 'distribution', 'timeline'].map(kind => ({ id: kind, kind }));
      pages.push(...data.books.map(book => ({ id: 'book-' + book.book_id, kind: 'book', book,
        quote: book.highlights[0]?.text || book.thoughts[0]?.text || '',
        textKind: book.highlights.length ? 'highlight' : 'thought' })));
      const rows = [];
      for (const [i, p] of pages.entries()) {
        const cv = await renderer.render(p, '3:4');
        rows.push({ id: p.id, title: p.book?.title || ({cover:'封面',stats:'阅读统计',distribution:'阅读分布',timeline:'阅读时间线'})[p.kind], filename: `${String(i+1).padStart(2,'0')}-${p.id}.png`,
          kind: p.kind, width: cv.width, height: cv.height, png: cv.toDataURL(), layout: cv.readingLayout });
      }
      return rows;
    });
    fs.mkdirSync(path.join(out, 'images'), { recursive: true });
    let maxPreviewDelta = 0;
    for (const row of rows) {
      assert.equal(row.width, 900); assert.equal(row.height, 1200);
      await page.locator(`[data-preview="${row.id}"]`).evaluate(el => el.click());
      await page.waitForFunction(title => document.querySelector('#previewTitle').textContent === title, row.title);
      const before = await page.locator('#previewCanvas').evaluate(cv => cv.toDataURL());
      const [download] = await Promise.all([page.waitForEvent('download'), page.locator('#exportOne').click()]);
      const stream = await download.createReadStream(), chunks = [];
      for await (const chunk of stream) chunks.push(chunk);
      const bytes = Buffer.concat(chunks);
      row.png = 'data:image/png;base64,' + bytes.toString('base64');
      const delta = await page.evaluate(async ([a, b]) => {
        async function pixels(src) {
          const image = new Image(); image.src = src; await image.decode();
          const cv = document.createElement('canvas'); cv.width = image.width; cv.height = image.height;
          const ctx = cv.getContext('2d'); ctx.drawImage(image, 0, 0);
          return ctx.getImageData(0, 0, cv.width, cv.height).data;
        }
        const x = await pixels(a), y = await pixels(b); let max = 0;
        for (let i = 0; i < x.length; i += 4) {
          max = Math.max(max, Math.abs(x[i+3]-y[i+3]));
          for (let j = 0; j < 3; j++) max = Math.max(max, Math.abs(x[i+j]*x[i+3]-y[i+j]*y[i+3])/255);
        }
        return max;
      }, [before, row.png]);
      // Canvas copy/PNG encoding may round premultiplied edges by one channel level.
      assert(delta <= 1, `preview/download pixel delta: ${delta}`);
      maxPreviewDelta = Math.max(maxPreviewDelta, delta);
      fs.writeFileSync(path.join(out, 'images', row.filename), bytes);
    }
    await page.setViewportSize({ width: 390, height: 900 });
    assert(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)));
    assert.deepEqual(errors, []); assert.deepEqual(network, []);
    const report = { status: 'pass', sample_data: true, ratio: '3:4', pages: rows.length,
      renderer: 'assets/reading-share-art.js', browser_png_matches_preview: true, max_premultiplied_channel_delta: maxPreviewDelta,
      css_matches_builder: true, no_network: true, mobile_overflow: false,
      images: rows.map(({ png, layout, ...row }) => row) };
    const selected = rows.slice(0, 6);
    await page.setViewportSize({ width: 1240, height: 2490 });
    await page.setContent(`<style>*{box-sizing:border-box}body{margin:0;padding:24px;background:#f3eee1;font:18px/1.6 "Microsoft YaHei",sans-serif;color:#494940}header{height:58px}.grid{display:grid;grid-template-columns:repeat(2,584px);gap:20px}.grid img{display:block;width:584px;height:auto}</style><header>当前网页导出的分享图 · 虚构数据与示意书封 · 3:4</header><div class="grid">${selected.map(r=>`<img src="${r.png}" alt="${r.kind}">`).join('')}</div>`, { waitUntil: 'load' });
    await page.screenshot({ path: path.join(out, 'share-overview.png'), fullPage: true });
    fs.writeFileSync(path.join(out, 'preview-manifest.json'), JSON.stringify(report, null, 2)+'\n');
    console.log(JSON.stringify({ status: 'pass', pages: rows.length, output: out }));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
