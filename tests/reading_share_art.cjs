/* Offline PNG matrix, genuine webfonts, content boundaries and export identity. */
const {chromium}=require('playwright'),{pathToFileURL}=require('url'),fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const real=path.resolve(process.argv[2]),fixtures=path.resolve(process.argv[3]),out=path.resolve(process.argv[4]||'demo-output/share-art');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'}),context=await browser.newContext({acceptDownloads:true});await context.setOffline(true);const page=await context.newPage(),errors=[],requests=[],checks=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
 const go=async file=>{await page.goto(pathToFileURL(file).href);await page.evaluate(()=>document.fonts.ready);};
 async function render(kind,ratio,variant,index=0){return page.evaluate(async({kind,ratio,variant,index})=>{
   const data=JSON.parse(document.querySelector('#reading-data').textContent);
   if(variant==='one'){data.books=data.books.slice(0,1);data.summary.read=1;}
   const b=data.books[index];
   if(variant==='no-notes'){b.highlights=[];b.thoughts=[];b.intro='';b.note_coverage={highlights:'complete',thoughts:'complete'};}
   if(variant==='missing'){b.highlights=[];b.thoughts=[];b.intro='';b.note_coverage={highlights:'unverified',thoughts:'unverified'};}
   if(variant==='long-quote'){b.highlights=[{text:('这是一条用于检查控件的示例划线。').repeat(30)}];}
   if(variant==='title'){b.title='这是一本需要完整显示书名而且需要自动换行的阅读记录测试书籍中文长书名';b.author='示例作者';}
   if(variant==='overflow'){b.title='很长的中文书名'.repeat(50);}
   if(variant==='large'){data.summary.read=1234;data.summary.finished=999;data.summary.notes=9876;data.summary.seconds=9999*3600+59*60;}
   const p=kind==='book'?{id:'book-'+b.book_id,kind,book:b,quote:b.highlights[0]?.text||b.thoughts[0]?.text||'',textKind:b.highlights.length?'highlight':'thought'}:{id:kind,kind};
   const cv=await window.ReadingShareArtwork.create({data}).render(p,ratio);
   return {png:cv.toDataURL(),layout:cv.readingLayout,books:data.books.length,summary:data.summary};
 },{kind,ratio,variant,index});}
 function validate(r,label){
   const l=r.layout;assert.equal(l.width,900);assert([900,1125,1200].includes(l.height));
   for(const t of l.text)assert(t.x>=40&&t.x+t.w<=871&&t.y>=25&&t.y+t.h<=l.height-20,`${label}: overflow ${t.text}`);
   for(let i=0;i<l.text.length;i++)for(let j=i+1;j<l.text.length;j++){const a=l.text[i],b=l.text[j];if(a.node===b.node)continue;const dx=Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x),dy=Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y);assert(!(dx>2&&dy>2),`${label}: text collision ${a.text} / ${b.text}`);}
   for(const s of l.spacing)assert(s.gap>=s.minimum-.1,`${label}: spacing ${s.gap}`);
   assert(l.metricLabelDeviation<=.5,`${label}: misaligned metric labels`);
   for(const c of l.charts.filter(c=>c.kind==='monthly'))for(const p of c.points.filter(Boolean)){assert.equal(p.value,r.summary.monthly[p.month-1]);assert(Math.abs(p.y-(c.base-p.value/3600/c.top*(c.base-c.upper)))<1e-7);}
   const categories=l.charts.filter(c=>c.kind==='category');if(categories.length)assert.equal(categories.reduce((n,c)=>n+c.count,0),r.books);
   const bytes=Buffer.from(r.png.split(',')[1],'base64');assert.equal(bytes.readUInt32BE(16),900);assert.equal(bytes.readUInt32BE(20),l.height);assert(bytes.length>3000);
   fs.writeFileSync(path.join(out,label+'.png'),bytes);checks.push(label);
 }
 await go(real);
 // CDP distinguishes the embedded font from a coincidentally installed local font.
 await page.evaluate(()=>{const n=document.createElement('span');n.id='font-proof';n.textContent='阅读年鉴，书页之间。2026';n.style.cssText='font-family:ReadingSans;font-weight:600;font-size:40px';document.body.append(n);});
 await page.locator('#font-proof').screenshot();
 const client=await context.newCDPSession(page);await client.send('DOM.enable');await client.send('CSS.enable');const doc=await client.send('DOM.getDocument'),node=await client.send('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#font-proof'}),fonts=(await client.send('CSS.getPlatformFontsForNode',{nodeId:node.nodeId})).fonts;
 assert(fonts.length&&fonts.every(f=>f.isCustomFont),JSON.stringify(fonts));await page.evaluate(()=>document.querySelector('#font-proof').remove());checks.push('embedded font, not local fallback');fs.writeFileSync(path.join(out,'fonts.json'),JSON.stringify(fonts,null,2));
 for(const ratio of ['3:4','1:1','4:5'])for(const kind of ['cover','stats','distribution','timeline','book'])validate(await render(kind,ratio),kind+'-'+ratio.replace(':','-'));
 const count=await page.locator('#reading-data').evaluate(n=>JSON.parse(n.textContent).books.length);
 for(let i=1;i<count;i++)for(const ratio of ['3:4','1:1','4:5'])validate(await render('book',ratio,null,i),'book-'+i+'-'+ratio.replace(':','-'));
 for(const variant of ['no-notes','missing','long-quote','title'])for(const ratio of ['3:4','1:1','4:5']){
   const r=await render('book',ratio,variant);validate(r,variant+'-'+ratio.replace(':','-'));if(variant==='no-notes')assert.equal(r.layout.material.kind,'book-info');if(variant==='missing')assert(!r.layout.text.some(t=>['划线','个人笔记'].includes(t.text)));
 }
 for(const ratio of ['3:4','1:1','4:5'])for(const kind of ['cover','stats'])validate(await render(kind,ratio,'large'),kind+'-large-'+ratio.replace(':','-'));
 await assert.rejects(()=>render('book','1:1','overflow'),/容量|安全版面/);assert.equal(await page.locator('.rs-page').count(),0);checks.push('oversized primary content reports an error and releases its DOM');
 await page.locator('[data-preview="stats"]').click();await page.waitForFunction(()=>document.querySelector('#previewTitle').textContent==='阅读统计');
 const before=await page.locator('#previewCanvas').evaluate(c=>c.toDataURL()),[download]=await Promise.all([page.waitForEvent('download'),page.locator('#exportOne').click()]);const png=path.join(out,'actual-stats-download.png');await download.saveAs(png);assert.equal(fs.readFileSync(png).toString('base64'),before.split(',')[1]);checks.push('preview and actual PNG are byte-identical');
 await page.locator('#ratio').selectOption('1:1',{force:true});await page.locator('#ratio').selectOption('4:5',{force:true});await page.waitForFunction(()=>document.querySelector('#previewCanvas').dataset.rendered==='stats|4:5');assert.equal(await page.locator('#previewCanvas').evaluate(n=>n.height),1125);checks.push('rapid ratio switching retains only the newest preview');
 await page.locator('#exportGroup').click();await page.locator('#cancelExport').click();await page.waitForFunction(()=>document.querySelector('#exportStatus').textContent.includes('已取消'));assert(!(await page.locator('#exportOne').isDisabled()));checks.push('ZIP generation can be cancelled and controls recover');
 for(const file of ['empty','many','failed','none']){await go(path.join(fixtures,file+'.html'));for(const ratio of ['3:4','1:1','4:5'])for(const kind of file==='empty'?['cover','stats','distribution','timeline']:['book','distribution'])validate(await render(kind,ratio),file+'-'+kind+'-'+ratio.replace(':','-'));}
 await go(path.join(fixtures,'none.html'));for(const ratio of ['3:4','1:1','4:5'])validate(await render('cover',ratio,'one'),'one-cover-'+ratio.replace(':','-'));
 assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);checks.push('no network or script errors');assert.equal(await page.locator('.rs-page').count(),0);checks.push('no export DOM left mounted');
 await browser.close();fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({status:'pass',checks},null,2));console.log(JSON.stringify({status:'pass',checks:checks.length,out}));
})().catch(e=>{console.error(e);process.exit(1)});
