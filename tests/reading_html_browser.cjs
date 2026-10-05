/* Run with NODE_PATH pointing at an existing Playwright installation. No downloads. */
const {chromium}=require('playwright');
const {pathToFileURL}=require('url');
const fs=require('fs'),path=require('path'),assert=require('assert');
const input=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]||'demo-output/reading-html-browser');
fs.mkdirSync(out,{recursive:true});
const checks=[];const pass=(name,detail='')=>checks.push({name,status:'pass',detail});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const context=await browser.newContext({acceptDownloads:true});
 const page=await context.newPage();const errors=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('console',e=>{if(e.type()==='error')errors.push(e.text());});
 await context.route(/^https?:/,route=>{requests.push(route.request().url());return route.abort();});
 await context.setOffline(true);
 await page.goto(pathToFileURL(input).href);await page.evaluate(()=>document.fonts.ready);
 const ensurePreview=async id=>{if(id.startsWith('book-')){if(await page.locator('#bookShareMenu').isHidden())await page.locator('#bookShareTrigger').click();}else if(await page.locator('#bookShareMenu').isVisible())await page.locator('#closeShareBooks').click();};
 const original=await page.locator('.book-entry').count();assert(original>0);pass('offline single file loads',String(original));
 for(const width of [1440,768,390]){
  await page.setViewportSize({width,height:950});await page.waitForTimeout(230);
  const over=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);assert(!over,`horizontal overflow at ${width}`);
  await page.screenshot({path:path.join(out,`yearbook-${width}.png`),fullPage:true});pass(`layout ${width}px`);
 }
 await page.setViewportSize({width:1440,height:950});
 await page.locator('#search').fill('不存在的书xyz');await page.waitForTimeout(250);assert.equal(await page.locator('.book-entry').count(),0);assert(await page.locator('#books').textContent());
 await page.locator('#clearFilters').click();assert.equal(await page.locator('.book-entry').count(),original);pass('search empty state and reset');
 await page.locator('#search').evaluate(el=>{el.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true}));el.value='城市';el.dispatchEvent(new InputEvent('input',{bubbles:true,isComposing:true}));});await page.waitForTimeout(250);
 assert.equal(await page.locator('.book-entry').count(),original);
 await page.locator('#search').evaluate(el=>el.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true})));await page.waitForTimeout(30);assert.equal(await page.locator('.book-entry').count(),1);pass('Chinese IME does not filter mid composition');
 await page.locator('#clearFilters').click();
 await page.locator('[data-status="finished"]').click();assert.equal(await page.locator('.book-entry').count(),1);await page.locator('#clearFilters').click();
 await page.locator('[data-status="unknown"]').click();assert.equal(await page.locator('.book-entry').count(),1);await page.locator('#clearFilters').click();pass('finished and unknown status filters');
 await page.locator('[data-category]').first().click();assert((await page.locator('.book-entry').count())<original);await page.locator('#clearFilters').click();pass('distribution links to clearable shelf filter');
 await page.locator('#viewSwitch').click();assert(await page.locator('#books').evaluate(el=>el.classList.contains('list')));await page.locator('#viewSwitch').click();pass('cover and list views');
 await page.locator('.book').first().click();assert(await page.locator('#detail').evaluate(el=>el.open));assert(await page.locator('#detailContent').textContent().then(t=>!t.includes('全书书评')&&t.includes('原文摘录')));assert(page.url().includes('#book='));
 await page.keyboard.press('Escape');await page.waitForTimeout(150);assert(!(await page.locator('#detail').evaluate(el=>el.open)));pass('detail hash, actual notes without generated review, Escape');
 await page.locator('#chart circle[role=button]').first().focus();await page.keyboard.press('Enter');assert(await page.locator('#chartReadout').textContent().then(t=>t.includes('小时')));pass('keyboard chart exact readout');
 const geometry=await page.evaluate(()=>{const d=JSON.parse(document.querySelector('#reading-data').textContent),svg=document.querySelector('#chart svg'),H=svg.viewBox.baseVal.height,base=H-37,vals=d.summary.monthly.slice(0,d.summary.complete_months),top=Math.ceil(Math.max(...vals.filter(v=>v!=null).map(v=>v/3600),1)/2)*2;return [...svg.querySelectorAll('circle[role=button]')].every(dot=>Math.abs(Number(dot.getAttribute('cy'))-(base-vals[Number(dot.dataset.chartMonth)]/3600/top*(base-25)))<1e-7);});assert(geometry);assert.equal(await page.locator('#chart path').count(),2);pass('chart geometry, missing-month path break, true zero');
 await page.locator('#openSources').click();assert(await page.locator('#sourcesContent').textContent().then(t=>t.includes('缺失值')));await page.locator('#sourcesDialog .close').click();pass('source and missing data explanation');
 const count=await page.locator('[data-page]:checked').count();await page.locator('#bookShareTrigger').click();await page.locator('#bookShareRows [data-page]').first().uncheck();assert.equal(await page.locator('[data-page]:checked').count(),count-1);await page.locator('#closeShareBooks').click();await page.locator('#undoSelection').click();assert.equal(await page.locator('[data-page]:checked').count(),count);pass('share selection undo');
 const selected=await page.locator('#bookShareRows [data-page]:checked').evaluateAll(es=>es.map(e=>e.dataset.page));
 for(const id of selected){await ensurePreview(id);await page.locator(`[data-page="${id}"]`).uncheck();}assert.equal(await page.locator('[data-page]:checked').count(),4);assert(!(await page.locator('#exportGroup').isDisabled()));
 for(const id of selected){await ensurePreview(id);await page.locator(`[data-page="${id}"]`).check();}pass('clearing book selection retains four required overview pages');
 if(await page.locator('#bookShareMenu').isVisible())await page.locator('#closeShareBooks').click();
 await page.evaluate(()=>{window.savedToBlob=HTMLCanvasElement.prototype.toBlob;HTMLCanvasElement.prototype.toBlob=function(cb){cb(null);};});
 await page.locator('#exportOne').click();await page.waitForTimeout(100);assert(await page.locator('#exportStatus').textContent().then(t=>t.includes('导出失败')));assert.equal(await page.locator('[data-page]:checked').count(),count);assert(!(await page.locator('#exportOne').isDisabled()));await page.evaluate(()=>HTMLCanvasElement.prototype.toBlob=window.savedToBlob);pass('export failure preserves selection and unlocks retry');
 for(const ratio of ['3:4','1:1','4:5']){
  await page.locator('#ratio').selectOption(ratio,{force:true});await page.waitForTimeout(150);
  const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#exportOne').click()]);
  const name=`export-${ratio.replace(':','-')}.png`;await download.saveAs(path.join(out,name));const bytes=fs.readFileSync(path.join(out,name));assert.equal(bytes.readUInt32BE(16),900);assert.equal(bytes.readUInt32BE(20),ratio==='1:1'?900:ratio==='4:5'?1125:1200);pass(`actual PNG ${ratio}`);
 }
 await page.locator('#ratio').selectOption('3:4',{force:true});
 const [zip]=await Promise.all([page.waitForEvent('download'),page.locator('#exportGroup').click()]);await zip.saveAs(path.join(out,'reading-share.zip'));pass('actual group ZIP download',String(count));
 for(const [id,name]of [['#exportMd','reading.md'],['#exportJson','reading.json']]){const[d]=await Promise.all([page.waitForEvent('download'),page.locator(id).click()]);await d.saveAs(path.join(out,name));}
 const exported=JSON.parse(fs.readFileSync(path.join(out,'reading.json'),'utf8'));assert.equal(exported.books.length,original);assert(exported.books.every(b=>!('cover'in b)));assert(fs.readFileSync(path.join(out,'reading.md'),'utf8').includes('来源：'));pass('actual Markdown and JSON exports');
 await page.evaluate(()=>window.print=()=>window.dispatchEvent(new Event('beforeprint')));await page.locator('#exportPdf').click();assert.equal(await page.locator('#printDetails article').count(),original);assert(await page.locator('#printDetails').textContent().then(t=>t.includes('这是我的个人笔记')));await page.evaluate(()=>window.dispatchEvent(new Event('afterprint')));assert.equal(await page.locator('#printDetails article').count(),0);pass('print button includes full notes and restores reading view');
 await page.emulateMedia({media:'print'});assert(!(await page.locator('#share').isVisible()));await page.pdf({path:path.join(out,'reading.pdf'),format:'A4',printBackground:true});await page.emulateMedia({media:'screen'});pass('PDF print layout');
 await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior),'auto');pass('reduced motion');
 assert.equal(await page.evaluate(()=>window.PWNED||0),0);assert.deepEqual(requests,[]);assert.deepEqual(errors,[]);pass('no network, page errors, or injected scripts');
 await page.goto(pathToFileURL(input).href+'#book=three');assert(await page.locator('#detail').evaluate(el=>el.open));await page.locator('#detailContent details summary').click();assert.equal(await page.evaluate(()=>window.PWNED||0),0);assert.equal(await page.locator('#detailContent script').count(),0);await page.locator('#detail .close').click();assert(!(await page.locator('#detail').evaluate(el=>el.open)));pass('direct book link, malicious detail text, initial-link close');
 await browser.close();fs.writeFileSync(path.join(out,'browser-report.json'),JSON.stringify({status:'pass',checks},null,2));console.log(JSON.stringify({status:'pass',checks:checks.length,out}));
})().catch(e=>{console.error(e);process.exit(1);});
