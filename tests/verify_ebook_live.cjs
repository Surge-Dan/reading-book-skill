/* Opt-in real-book acceptance. Uses installed Playwright/Edge; never logs tokens. */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
const [url,source,outArg,...flags]=process.argv.slice(2);
const out=path.resolve(outArg||'demo-output/ebook-live');
const verify=flags.includes('--verify');
const resumeId=flags.find(f=>f.startsWith('--resume='))?.slice('--resume='.length);
fs.mkdirSync(out,{recursive:true});
const reportFile=path.join(out,'live-report.json');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const context=await browser.newContext({acceptDownloads:true});
  await context.grantPermissions(['clipboard-read','clipboard-write'],{origin:new URL(url).origin});
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  try{
    await page.goto(url);await page.waitForLoadState('networkidle');
    await page.locator('#ebookFile').waitFor({state:'attached'});
    const state=()=>page.evaluate(async()=>{
      const c=window.EBOOK_CONFIG;
      const r=await fetch((c.apiBase||'')+'/api/state',{headers:{'X-Ebook-Token':c.token}});
      if(!r.ok)throw Error('state HTTP '+r.status);return r.json();
    });
    let job;
    if(!verify){
      const before=new Set((await state()).jobs.map(j=>j.id));
      await page.setViewportSize({width:375,height:850});
      await page.screenshot({path:path.join(out,'upload-375.png'),fullPage:true});
      if(resumeId){
        job=(await state()).jobs.find(j=>j.id===resumeId);
        assert(job&&['failed','cancelled','interrupted'].includes(job.state),'resume job is not retryable');
        await page.locator('#ebookRetry').click();
      }else await page.locator('#ebookFile').setInputFiles(path.resolve(source));
      const deadline=Date.now()+45*60*1000;let last='';
      while(Date.now()<deadline){
        job=(await state()).jobs.find(j=>resumeId?j.id===resumeId:!before.has(j.id));
        if(job){
          const status=[job.state,job.stage,job.completed,job.total].join(' ');
          if(status!==last){console.log(JSON.stringify({state:job.state,stage:job.stage,completed:job.completed,total:job.total}));last=status;}
          if(['completed','failed','needs_approval','cancelled','interrupted'].includes(job.state))break;
        }
        await page.waitForTimeout(3000);
      }
      assert(job,'upload did not create a job');
      if(['running','queued'].includes(job.state)){
        await page.locator('#ebookCancel').click();
        throw Error('Acceptance time budget reached; current task cancelled, valid stage cache retained');
      }
    }else{
      const saved=JSON.parse(fs.readFileSync(reportFile,'utf8'));
      job=(await state()).jobs.find(j=>j.id===saved.job_id);
    }
    if(job&&job.state!=='completed')fs.writeFileSync(reportFile,JSON.stringify({job_id:job.id,state:job.state,stage:job.stage,error:job.error},null,2));
    assert(job&&job.state==='completed',JSON.stringify({state:job?.state,error:job?.error,message:job?.message}));
    await page.locator('#ebookResult').waitFor({state:'visible'});
    await page.evaluate(()=>document.fonts.ready);
    assert((await page.locator('#ebookBookTitle').textContent()).includes(job.analysis.book.title));
    const report={job_id:job.id,state:job.state,quality:job.analysis.quality_status,
      title:job.analysis.book.title,coverage:job.analysis.coverage,
      counts:Object.fromEntries(['themes','methods','cases','counterexamples','glossary','references'].map(k=>[k,(job.analysis[k]||[]).length]))};
    fs.writeFileSync(reportFile,JSON.stringify(report,null,2));
    console.log(JSON.stringify({state:'completed',quality:report.quality,counts:report.counts}));
    if(!verify)return;
    for(const width of [1440,375]){
      await page.setViewportSize({width,height:950});await page.waitForTimeout(200);
      assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),`overflow ${width}`);
      await page.screenshot({path:path.join(out,`result-${width}.png`),fullPage:true});
    }
    await page.locator('#ebookCopyAll').click();
    assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),job.digest);
    for(const [selector,name] of [['#ebookDownloadMd','DIGEST.md'],['#ebookDownloadHtml','index.html']]){
      const [download]=await Promise.all([page.waitForEvent('download'),page.locator(selector).click()]);
      await download.saveAs(path.join(out,name));
    }
    assert.equal(fs.readFileSync(path.join(out,'DIGEST.md'),'utf8'),job.digest);
    const html=fs.readFileSync(path.join(out,'index.html'),'utf8');
    const token=await page.evaluate(()=>window.EBOOK_CONFIG.token);
    assert(!html.includes(token),'offline export contains service token');
    await page.locator('#ebookShareToggle').click();
    for(const ratio of ['1:1','3:4','4:5']){
      await page.locator('#ebookRatio').selectOption(ratio);await page.waitForTimeout(300);
      const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#ebookExportPng').click()]);
      const png=path.join(out,`share-${ratio.replace(':','-')}.png`);await download.saveAs(png);
      const bytes=fs.readFileSync(png),w=bytes.readUInt32BE(16),h=bytes.readUInt32BE(20);
      const [rw,rh]=ratio.split(':').map(Number);assert(Math.abs(w/h-rw/rh)<.002);
    }
    const [zip]=await Promise.all([page.waitForEvent('download',{timeout:120000}),page.locator('#ebookExportZip').click()]);
    await zip.saveAs(path.join(out,'share.zip'));
    assert.equal(fs.readFileSync(path.join(out,'share.zip')).readUInt32LE(0),0x04034b50);
    await page.reload();await page.waitForLoadState('networkidle');
    await page.locator('#ebookResult').waitFor({state:'visible'});
    assert((await page.locator('#ebookBookTitle').textContent()).includes(job.analysis.book.title));
    const offline=await context.newPage();
    const remote=[];await offline.route(/^https?:/,r=>{remote.push(r.request().url());return r.abort();});
    await offline.goto(pathToFileURL(path.join(out,'index.html')).href);await offline.waitForLoadState('networkidle');
    assert((await offline.locator('#ebookBookTitle').textContent()).includes(job.analysis.book.title));
    assert.equal(await offline.evaluate(()=>Boolean(window.EBOOK_CONFIG?.token)),false);
    assert.deepEqual(remote,[]);assert.deepEqual(errors,[]);
    report.browser_checks='copy, MD, offline HTML, PNG three ratios, ZIP, refresh, 375px';
    fs.writeFileSync(reportFile,JSON.stringify(report,null,2));
    console.log(JSON.stringify({status:'pass',browser_checks:report.browser_checks,out}));
  }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
