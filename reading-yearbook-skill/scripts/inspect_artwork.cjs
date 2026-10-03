// Technical artwork inspection; composition and meaning still require a visual review.
async function inspectArtwork(page, context, planned) {
  if (!planned.artwork) return null; // Existing archives keep their original contract.
  const selector = `[id=${JSON.stringify(planned.id)}]`;
  await page.locator(selector).scrollIntoViewIfNeeded();
  const report = await page.evaluate(({ id, plan }) => {
    const card = document.getElementById(id), frame = card.getBoundingClientRect();
    const errors = [], warnings = [], images = [];
    const layers = [...card.querySelectorAll('[data-layer]')];
    const dependencies = el => {
      const urls = new Set();
      for (const child of [el, ...el.querySelectorAll('*')]) {
        if (child.matches('img,svg image')) {
          const source = child.currentSrc || child.getAttribute('src') || child.getAttribute('href') || child.getAttribute('xlink:href');
          if (source) urls.add(new URL(source, document.baseURI).href);
        }
        for (const pseudo of [null, '::before', '::after']) {
          const css = getComputedStyle(child, pseudo);
          for (const value of [css.backgroundImage, css.maskImage, css.borderImageSource, css.content])
            for (const match of (value || '').matchAll(/url\((?:"([^"]*)"|'([^']*)'|([^)]*))\)/g)) urls.add(new URL(match[1] || match[2] || match[3], document.baseURI).href);
        }
      }
      return urls;
    };
    const used = dependencies(card);
    for (const asset of plan.primary.asset_paths || [])
      if (!used.has(new URL(asset, document.baseURI).href)) errors.push({ problem: 'primary_asset_missing', asset });
    const expected = new Map(plan.layers.map(l => [l.id, l]));
    if (layers.length !== expected.size || new Set(layers.map(l => l.dataset.layer)).size !== layers.length || layers.some(l => !expected.has(l.dataset.layer)))
      errors.push({ problem: 'artwork_layer_mismatch' });
    for (const el of layers) {
      const layer = expected.get(el.dataset.layer);
      if (!layer) continue;
      const rect = el.getBoundingClientRect();
      const out = rect.left < frame.left-.5 || rect.top < frame.top-.5 || rect.right > frame.right+.5 || rect.bottom > frame.bottom+.5;
      if (out && !layer.allow_bleed) errors.push({ problem: 'unplanned_layer_bleed', layer: layer.id });
      const layerAssets = dependencies(el);
      for (const asset of layer.asset_paths || [])
        if (!layerAssets.has(new URL(asset, document.baseURI).href)) errors.push({ problem: 'layer_asset_missing', layer: layer.id, asset });
      for (const bid of layer.block_ids || []) {
        if (![...el.querySelectorAll('[data-block]'), ...(el.matches('[data-block]') ? [el] : [])].some(b => b.dataset.block === bid))
          errors.push({ problem: 'artwork_block_binding', layer: layer.id, block: bid });
      }
      if (layer.allow_bleed && (el.matches('[data-block],[data-graphic],text') || el.querySelector('[data-block],[data-graphic],text')))
        errors.push({ problem: 'text_or_data_in_bleed_layer', layer: layer.id });
    }
    for (const img of card.querySelectorAll('img')) {
      const r = img.getBoundingClientRect();
      images.push({ source: img.getAttribute('src'), natural: [img.naturalWidth, img.naturalHeight], displayed: [r.width, r.height] });
      if (Math.max(r.width / img.naturalWidth, r.height / img.naturalHeight) > 1.5 && !/\.svg(?:$|[?#])/i.test(img.src))
        warnings.push({ problem: 'image_upscale', source: img.getAttribute('src') });
    }
    // Hit testing is sampled at actual character centres. Override pointer-events
    // only during inspection so decorative images cannot evade the check.
    const targets = [...card.querySelectorAll('img,[data-layer]')];
    const saved = targets.map(el => [el, el.getAttribute('style')]);
    const canvases = new Map(), uncertain = new Set();
    const markUncertain = el => { uncertain.add(el.dataset.layer || el.tagName); return false; };
    const opaqueAt = (el, x, y) => {
      let opacity = 1;
      for (let p = el; p && p !== card; p = p.parentElement) opacity *= Number(getComputedStyle(p).opacity);
      if (opacity < .15) return false;
      const css = getComputedStyle(el);
      if (css.maskImage !== 'none' || css.clipPath !== 'none' || css.transform !== 'none') return markUncertain(el);
      if (el.tagName === 'IMG') {
        if (!['fill', 'cover', 'contain'].includes(css.objectFit) || css.objectPosition !== '50% 50%' || [css.paddingLeft, css.paddingTop, css.borderLeftWidth, css.borderTopWidth].some(v => parseFloat(v))) return markUncertain(el);
        try {
          if (!canvases.has(el)) {
            const c = document.createElement('canvas'); c.width = el.naturalWidth; c.height = el.naturalHeight;
            const ctx = c.getContext('2d', { willReadFrequently: true }); ctx.drawImage(el, 0, 0); canvases.set(el, ctx);
          }
          const r = el.getBoundingClientRect();
          const scale = css.objectFit === 'cover' ? Math.max(r.width/el.naturalWidth, r.height/el.naturalHeight) : Math.min(r.width/el.naturalWidth, r.height/el.naturalHeight);
          const w = css.objectFit === 'fill' ? r.width : el.naturalWidth*scale, h = css.objectFit === 'fill' ? r.height : el.naturalHeight*scale;
          const px = Math.floor((x-r.left-(r.width-w)/2)*el.naturalWidth/w), py = Math.floor((y-r.top-(r.height-h)/2)*el.naturalHeight/h);
          if (px < 0 || py < 0 || px >= el.naturalWidth || py >= el.naturalHeight) return false;
          return canvases.get(el).getImageData(px, py, 1, 1).data[3] / 255 * opacity > .6;
        } catch { return markUncertain(el); }
      }
      if (css.backgroundImage !== 'none' || el instanceof SVGElement) return markUncertain(el);
      const rgba = css.backgroundColor.match(/[\d.]+/g);
      return !!rgba && (rgba.length === 3 ? 1 : Number(rgba[3])) * opacity > .6;
    };
    try {
      for (const el of targets) el.style.setProperty('pointer-events', 'auto', 'important');
      for (const block of card.querySelectorAll('[data-block]')) {
        const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
        let samples = 0, hits = 0;
        while (walker.nextNode()) {
          const node = walker.currentNode;
          // At most 80 codepoints per block, distributed through its text.
          const step = Math.max(1, Math.ceil(node.length / 80));
          for (let i = 0; i < node.length && samples < 80; i += step) {
            if (!node.textContent[i].trim()) continue;
            const range = document.createRange(); range.setStart(node, i); range.setEnd(node, Math.min(i+1, node.length));
            const r = range.getBoundingClientRect();
            if (!r.width || !r.height) continue;
            const x = r.left+r.width/2, y = r.top+r.height/2;
            if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) continue;
            samples++;
            for (const el of document.elementsFromPoint(x, y)) {
              if (el === block || block.contains(el)) break;
              if (!card.contains(el) || el.contains(block)) continue;
              if ((el.matches('img,[data-layer]')) && opaqueAt(el, x, y)) { hits++; break; }
            }
          }
        }
        if (hits) errors.push({ problem: 'text_occluded', block: block.dataset.block, hit_samples: hits, samples });
      }
    } finally {
      for (const [el, style] of saved) { if (style === null) el.removeAttribute('style'); else el.setAttribute('style', style); }
    }
    if (uncertain.size) warnings.push({ problem: 'occlusion_needs_visual_review', layers: [...uncertain], reason: 'SVG, transformed, masked or background-image material needs inspection in the actual PNG.' });
    return { errors, warnings, images };
  }, { id: planned.id, plan: planned.artwork });
  const cdp = await context.newCDPSession(page);
  report.fonts = [];
  try {
    await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
    const { root } = await cdp.send('DOM.getDocument');
    const normalize = s => s.toLowerCase().replace(/[\s"'-]/g, '');
    for (const font of planned.artwork.fonts) for (const bid of font.block_ids) {
      const { nodeId } = await cdp.send('DOM.querySelector', { nodeId: root.nodeId, selector: `${selector} [data-block=${JSON.stringify(bid)}]` });
      if (!nodeId) { report.errors.push({ problem: 'font_block_missing', block: bid }); continue; }
      const descendants = await cdp.send('DOM.querySelectorAll', { nodeId, selector: '*' });
      const found = new Map();
      for (const n of [nodeId, ...descendants.nodeIds]) {
        const { fonts } = await cdp.send('CSS.getPlatformFontsForNode', { nodeId: n });
        for (const actual of fonts.filter(f => f.glyphCount > 0)) found.set(actual.familyName, actual);
      }
      const actual = [...found.values()];
      report.fonts.push({ block: bid, expected: font.family, actual });
      const allowed = [font.family, ...(font.fallbacks || [])].map(normalize);
      if (!actual.length || actual.some(f => !allowed.includes(normalize(f.familyName))))
        report.errors.push({ problem: 'font_fallback_unapproved', block: bid, expected: [font.family, ...(font.fallbacks || [])], actual: actual.map(f => f.familyName) });
    }
  } finally { await cdp.detach(); }
  return report;
}
module.exports = { inspectArtwork };
