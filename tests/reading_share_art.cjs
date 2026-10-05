/* Actual offline PNGs and layout/data checks for the editorial renderer. */
const {chromium}=require('playwright'),{pathToFileURL}=require('url'),fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const real=path.resolve(process.argv[2]),fixtures=path.resolve(process.argv[3]),out=path.resolve(process.argv[4]||'demo-output/share-art');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'}),context=await browser.newContext({acceptDownloads:true});await context.setOffline(true);const page=await context.newPage(),errors=[],requests=[],checks=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
 const go=async file=>{await page.goto(pathToFileURL(file).href);await page.evaluate(()=>document.fonts.ready);};
 async function render(kind,ratio,variant,index=0){return page.evaluate(async({kind,ratio,variant,index})=>{
   const data=JSON.parse(document.querySelector('#reading-data').textContent),art=JSON.parse(document.querySelector('#reading-art').textContent);
   const images=new Map(),loadImage=src=>{if(!images.has(src))images.set(src,new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('image'));im.src=src;}));return images.get(src);};
   const b=variant==='empty'?data.books.find(b=>!b.highlights.length&&!b.thoughts.length)||data.books[0]:variant==='long'?[...data.books].sort((a,b)=>b.title.length-a.title.length)[0]:data.books[index];
   if(variant==='empty'){b.highlights=[];b.thoughts=[];}
   if(variant==='missing'){b.highlights=[];b.thoughts=[];b.intro='';b.note_coverage={highlights:'unverified',thoughts:'unverified'};}
   if(variant==='note-only'){b.highlights=[];b.thoughts=[{text:'这段话是个人想法，和原文划线分开。'}];b.note_coverage={highlights:'complete',thoughts:'complete'};}
   if(variant==='long-quote')b.highlights=[{text:'阅读的时候，记下值得回头看的句子。'.repeat(24)}];
   if(variant==='large'){data.summary.read=1234;data.summary.finished=999;data.summary.notes=9876;data.summary.read_days=365;data.summary.seconds=9999*3600+59*60;}
   if(variant==='full-year'){data.summary.complete_months=12;data.summary.monthly=Array.from({length:12},(_,i)=>i%4===0?null:(i+1)*3600);}
   const p=kind==='book'?{id:'book-'+b.book_id,title:b.title,kind,book:b,quote:b.highlights[0]?.text||b.thoughts[0]?.text||'',textKind:b.highlights.length?'highlight':'thought'}:{id:kind,kind};
   const cv=await window.ReadingShareArtwork.create({data,art,loadImage}).render(p,ratio);
   return {png:cv.toDataURL(),layout:cv.readingLayout,books:data.books.length,summary:data.summary};
 },{kind,ratio,variant,index});}
 function validate(r,label){
   fs.writeFileSync(path.join(out,label+'.png'),Buffer.from(r.png.split(',')[1],'base64'));
   assert.equal(r.layout.width,900);
   for(const t of r.layout.text){assert(t.x>=20&&t.x+t.w<=881,`${label}: horizontal overflow ${JSON.stringify(t)}`);assert(t.y>=20&&t.y+t.h<=r.layout.height-20,`${label}: vertical overflow ${JSON.stringify(t)}`);if(t.role!=='footer')assert(t.y+t.h<=r.layout.footerTop-12,`${label}: text reaches footer ${t.text}`);}
   for(let i=0;i<r.layout.text.length;i++)for(let j=i+1;j<r.layout.text.length;j++){const a=r.layout.text[i],b=r.layout.text[j],dx=Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x),dy=Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y);assert(!(dx>2&&dy>2),`${label}: text collision ${a.text} / ${b.text}`);}
   for(const gap of r.layout.spacing)assert(gap.gap>=14,`${label}: number and label too close: ${gap.gap}`);
   for(const im of r.layout.images){assert(im.x>=30&&im.x+im.w<=870,`${label}: image exceeds frame`);assert(im.y+im.h<=r.layout.footerTop-16,`${label}: rotated image reaches footer`);}
   const chart=r.layout.charts.find(c=>c.kind==='monthly');if(chart)for(const p of chart.points.filter(Boolean)){assert.equal(p.value,r.summary.monthly[p.month-1]);assert(Math.abs(p.y-(chart.base-p.value/3600/chart.top*(chart.base-chart.upper)))<1e-7);}
   const categories=r.layout.charts.filter(c=>c.kind==='category');if(categories.length)assert.equal(categories.reduce((n,c)=>n+c.count,0),r.books);
   checks.push(label+' geometry, spacing and data');
 }
 await go(real);
 await page.evaluate(()=>{for(const [id,family,weight]of [['serif','ReadingSerif',600],['sans','ReadingSans',400]]){const s=document.createElement('span');s.id='share-font-'+id;s.textContent='阅读年鉴，书页之间。2026';s.style.cssText=`font-family:${family};font-weight:${weight};font-size:40px;position:fixed;top:${id==='serif'?0:60}px;left:0;z-index:99;background:white`;document.body.append(s);}});
 await page.evaluate(()=>document.fonts.ready);await page.locator('#share-font-serif').screenshot();
 const client=await context.newCDPSession(page);await client.send('DOM.enable');await client.send('CSS.enable');const doc=await client.send('DOM.getDocument'),fonts={};
 for(const id of ['serif','sans']){const node=await client.send('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#share-font-'+id});fonts[id]=(await client.send('CSS.getPlatformFontsForNode',{nodeId:node.nodeId})).fonts;assert(fonts[id].some(f=>f.glyphCount>0));}
 await page.evaluate(()=>document.querySelectorAll('[id^="share-font-"]').forEach(n=>n.remove()));
 fs.writeFileSync(path.join(out,'fonts.json'),JSON.stringify(fonts,null,2));
 for(const ratio of ['3:4','1:1','4:5'])for(const kind of ['cover','stats','distribution','timeline','book']){
   const r=await render(kind,ratio),label=kind+'-'+ratio.replace(':','-');validate(r,label);
   assert.equal(r.layout.height,ratio==='1:1'?900:ratio==='4:5'?1125:1200);
 }
 const N=await page.locator('#reading-data').evaluate(n=>JSON.parse(n.textContent).books.length);
 for(let index=1;index<N;index++)for(const ratio of ['3:4','1:1','4:5'])validate(await render('book',ratio,null,index),'book-'+index+'-'+ratio.replace(':','-'));
 for(const variant of ['missing','note-only','long-quote'])for(const ratio of ['3:4','1:1','4:5']){
   const r=await render('book',ratio,variant);validate(r,variant+'-'+ratio.replace(':','-'));
   if(variant==='long-quote')assert(r.layout.material.excerpted&&r.layout.text.some(t=>t.text.includes('节选')));
   if(variant==='note-only')assert.equal(r.layout.material.kind,'个人笔记');
   if(variant==='missing')assert(!r.layout.text.some(t=>t.text==='条划线'||t.text==='条个人笔记'));
 }
 for(const variant of ['large','full-year'])for(const ratio of ['3:4','1:1','4:5'])for(const kind of ['cover','stats'])validate(await render(kind,ratio,variant),kind+'-'+variant+'-'+ratio.replace(':','-'));
 const empty=await render('book','3:4','empty');fs.writeFileSync(path.join(out,'book-no-notes.png'),Buffer.from(empty.png.split(',')[1],'base64'));assert.equal(empty.layout.material.kind,'book-info');checks.push('book with no excerpts remains exportable');
 await page.locator('[data-preview="stats"]').click();await page.waitForFunction(()=>document.querySelector('#previewTitle').textContent==='阅读统计');
 const before=await page.locator('#previewCanvas').evaluate(c=>c.toDataURL()),[download]=await Promise.all([page.waitForEvent('download'),page.locator('#exportOne').click()]);const png=path.join(out,'actual-stats-download.png');await download.saveAs(png);assert.equal(fs.readFileSync(png).toString('base64'),before.split(',')[1]);checks.push('browser preview and actual PNG are byte-identical');
 for(const file of ['empty','long','many']){await go(path.join(fixtures,file+'.html'));for(const ratio of ['3:4','1:1','4:5'])for(const kind of file==='empty'?['cover','stats','distribution','timeline']:['book','distribution'])validate(await render(kind,ratio,file==='long'?'long':null),file+'-'+kind+'-'+ratio.replace(':','-'));}
 // Font availability varies by user; layout must also hold with system fallback fonts.
 await go(real);
 const fallback=fs.readFileSync(path.join(__dirname,'../reading-yearbook-skill/assets/reading-share-art.js'),'utf8').replace(/const SERIF=.*?;/,'const SERIF="SimSun,serif";').replace(/const SANS=.*?;/,'const SANS="Microsoft YaHei,sans-serif";');
 await page.addScriptTag({content:fallback});
 for(const ratio of ['3:4','1:1','4:5'])for(const kind of ['cover','stats','distribution','timeline','book'])validate(await render(kind,ratio),'fallback-'+kind+'-'+ratio.replace(':','-'));
 assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);checks.push('offline with no script errors');
 await browser.close();fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({status:'pass',checks},null,2));console.log(JSON.stringify({status:'pass',checks:checks.length,out}));
})().catch(e=>{console.error(e);process.exit(1)});
