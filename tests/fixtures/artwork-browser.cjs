const { chromium } = require(process.argv[2]);
const { inspectArtwork } = require('../../reading-yearbook-skill/scripts/inspect_artwork.cjs');
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.argv[3] });
  try {
    const context = await browser.newContext({ viewport: { width: 980, height: 1280 } });
    const page = await context.newPage();
    const plan = { id: 'card', artwork: { primary: { asset_paths: [] },
      layers: [{ id: 'words', block_ids: ['title'] }, { id: 'object', asset_paths: [] }],
      fonts: [{ family: 'Arial', block_ids: ['title'] }] } };
    const svg = encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="80"><rect width="12" height="80" fill="black"/></svg>');
    const html = object => `<html><head><style>*{box-sizing:border-box}body{margin:0}.page{width:900px;height:1200px;position:relative} [data-block]{font:40px Arial;margin:0;position:absolute;left:50px;top:50px} [data-layer="object"]{position:absolute;left:50px;top:45px;width:300px;height:80px;z-index:3;pointer-events:none}</style></head><body><article id="card" class="page"><div data-layer="words"><p data-block="title">Reading notes</p></div>${object}</article></body></html>`;
    const reports = {};
    const run = async (key, object, modify = () => {}) => {
      await page.setContent(html(object)); await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(img => img.decode())); });
      const input = JSON.parse(JSON.stringify(plan)); modify(input);
      reports[key] = await inspectArtwork(page, context, input);
    };
    await run('valid', '<div data-layer="object" style="top:300px"></div>');
    await run('fallback', '<div data-layer="object" style="top:300px"></div>', p => p.artwork.fonts[0].family = 'Missing font');
    await run('opaque', '<div data-layer="object" style="background:#000"></div>');
    reports.styles_restored = await page.locator('[data-layer="object"]').getAttribute('style') === 'background:#000';
    const solid = encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="80"><rect width="300" height="80" fill="black"/></svg>');
    await run('opaque_image', `<img data-layer="object" src="data:image/svg+xml,${solid}">`);
    await run('transparent', `<img data-layer="object" src="data:image/svg+xml,${svg}">`);
    await run('allowed_fallback', '<div data-layer="object" style="top:300px"></div>', p => { p.artwork.fonts[0].family = 'Requested alias'; p.artwork.fonts[0].fallbacks = ['Arial']; });
    await run('transformed', '<div data-layer="object" style="background:#000;transform:rotate(7deg)"></div>');
    await run('bleed', '<div data-layer="object" style="left:-10px;top:300px"></div>');
    await run('missing', '<div data-layer="object" style="top:300px"></div>', p => p.artwork.layers[1].asset_paths = ['https://example.com/missing.png']);
    process.stdout.write(JSON.stringify(reports));
  } finally { await browser.close(); }
})().catch(e => { process.stderr.write(e.stack); process.exitCode = 1; });
