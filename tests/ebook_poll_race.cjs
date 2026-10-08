const {chromium}=require('playwright'),assert=require('assert'),http=require('http'),{html}=require('./fixtures/ebook-ui.cjs');

const running=(id,filename,message)=>({id,filename,state:'running',stage:'stage0-map',message,completed:0,total:4});
async function fixture(browser){
  const context=await browser.newContext(),page=await context.newPage(),errors=[],held=[],posts=[];
  page.on('pageerror',e=>errors.push(e.message));
  let job=null,nextId=0,holdState=false,holdUpload=false;
  const send=(res,payload,status=200)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(payload));};
  const server=http.createServer(async(req,res)=>{
    if(req.url==='/'){res.writeHead(200,{'Content-Type':'text/html'});res.end(html({token:'fixture-token'},null));return;}
    if(req.url==='/api/state'){const payload={runner:{available:true,name:'fixture'},jobs:job?[{...job}]:[]};if(holdState)held.push({res,payload,url:req.url});else send(res,payload);return;}
    if(req.method==='POST'){
      posts.push(req.url);for await(const chunk of req){}
      if(req.url.startsWith('/api/jobs?')){if(holdUpload)await new Promise(resolve=>held.push({res,url:'/api/jobs',resume:resolve}));const filename=new URL(req.url,'http://fixture').searchParams.get('name');job=running('j'+(++nextId),filename,'处理 '+filename);send(res,{job},202);return;}
      if(req.url.endsWith('/cancel'))job={...job,state:'cancelled',message:'当前已取消'};
      if(req.url.endsWith('/retry'))job={...job,state:'running',message:'当前重试中'};
      send(res,{job});return;
    }
    if(req.url.startsWith('/api/jobs/')){held.push({res,snapshot:{...job},url:req.url});return;}
    send(res,{error:'missing'},404);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  await page.goto('http://127.0.0.1:'+server.address().port);
  await page.locator('#ebookConnection').getByText('已检测',{exact:false}).waitFor();
  return {page,posts,held,errors,setJob:current=>job=current,holdState:()=>holdState=true,holdUpload:()=>holdUpload=true,
    async upload(filename){await page.locator('#ebookFile').setInputFiles({name:filename,mimeType:'text/plain',buffer:Buffer.from('正文')});await page.waitForFunction(name=>document.querySelector('#ebookFilename').textContent===name,filename);},
    async pending(){const deadline=Date.now()+5000;while(!held.length&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,20));assert(held.length,'request never reached fixture');return held.shift();},
    async release(request,payload=request.payload||{job:request.snapshot},status=200){const response=page.waitForResponse(r=>new URL(r.url()).pathname===request.url);if(request.resume)request.resume();else send(request.res,payload,status);await (await response).finished();await page.waitForTimeout(100);},
    async close(){await context.close();for(const request of held)request.res.destroy();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
  };
}

(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'}),failures=[];
  const cases={
    async 'cancel preserves terminal state against its old running poll'(f){await f.upload('first.txt');const old=await f.pending();await f.page.locator('#ebookCancel').click();await f.page.getByText('当前已取消',{exact:true}).waitFor();await f.release(old);assert.equal(await f.page.locator('#ebookStatus').textContent(),'当前已取消');assert(await f.page.locator('#ebookCancel').isHidden());},
    async 'new upload preserves filename and cancel target against an old job poll'(f){await f.upload('first.txt');const old=await f.pending();await f.page.locator('#ebookCancel').click();await f.page.getByText('当前已取消',{exact:true}).waitFor();await f.upload('second.txt');await f.release(old);assert.equal(await f.page.locator('#ebookFilename').textContent(),'second.txt');await f.page.locator('#ebookCancel').click();await f.page.getByText('当前已取消',{exact:true}).waitFor();assert.equal(f.posts.at(-1),'/api/jobs/j2/cancel');},
    async 'retry accepts current result and discards previous attempt poll'(f){await f.upload('first.txt');const old=await f.pending();await f.page.locator('#ebookCancel').click();await f.page.getByText('当前已取消',{exact:true}).waitFor();await f.page.locator('#ebookRetry').click();await f.page.getByText('当前重试中',{exact:true}).waitFor();await f.release(old);assert.equal(await f.page.locator('#ebookStatus').textContent(),'当前重试中');const current=await f.pending();assert.equal(current.url,'/api/jobs/j1');await f.release(current,{job:{...current.snapshot,message:'重试新进度'}});await f.page.getByText('重试新进度',{exact:true}).waitFor();},
    async 'reconnect accepts latest job and maintains one current poll chain'(f){await f.upload('first.txt');const old=await f.pending();f.setJob(running('j2','second.txt','重新连接的新进度'));await f.page.locator('#ebookReconnect').click();await f.page.getByText('重新连接的新进度',{exact:true}).waitFor();await f.release(old);assert.equal(await f.page.locator('#ebookFilename').textContent(),'second.txt');const current=await f.pending();assert.equal(current.url,'/api/jobs/j2');await f.page.waitForTimeout(1100);assert.equal(f.held.length,0,'a pending current poll must not spawn another poll');await f.release(current,{job:{...current.snapshot,message:'新任务正常更新'}});await f.page.getByText('新任务正常更新',{exact:true}).waitFor();},
    async 'stale poll failure cannot disconnect a new upload'(f){await f.upload('first.txt');const old=await f.pending();await f.page.locator('#ebookCancel').click();await f.page.getByText('当前已取消',{exact:true}).waitFor();await f.upload('second.txt');await f.release(old,{error:'obsolete failure'},503);assert((await f.page.locator('#ebookConnection').textContent()).includes('已检测'));assert.equal(await f.page.locator('#ebookStatus').textContent(),'处理 second.txt');},
    async 'a pending reconnect response cannot replace a subsequent upload'(f){await f.upload('first.txt');await f.page.locator('#ebookCancel').click();await f.page.getByText('当前已取消',{exact:true}).waitFor();f.holdState();await f.page.locator('#ebookReconnect').click();const old=await f.pending();assert.equal(old.url,'/api/state');await f.upload('second.txt');await f.release(old);assert.equal(await f.page.locator('#ebookFilename').textContent(),'second.txt');assert.equal(await f.page.locator('#ebookStatus').textContent(),'处理 second.txt');},
    async 'current poll rejects a different job identity'(f){await f.upload('first.txt');const current=await f.pending();await f.release(current,{job:running('j999','other.txt','错误任务')});assert.equal(await f.page.locator('#ebookFilename').textContent(),'first.txt');},
    async 'reconnect during a pending upload preserves its successful response'(f){f.holdUpload();await f.page.locator('#ebookFile').setInputFiles({name:'first.txt',mimeType:'text/plain',buffer:Buffer.from('正文')});const upload=await f.pending();await f.page.locator('#ebookReconnect').click();await f.page.waitForTimeout(100);await f.release(upload);assert.equal(await f.page.locator('#ebookFilename').textContent(),'first.txt');assert.equal(await f.page.locator('#ebookActionStatus').textContent(),'文件已接收，正在处理。');assert(!(await f.page.locator('#ebookTask').isHidden()));const poll=await f.pending();assert.equal(poll.url,'/api/jobs/j1');await f.release(poll,{job:{...poll.snapshot,message:'上传后正常更新'}});await f.page.getByText('上传后正常更新',{exact:true}).waitFor();}
  };
  try{for(const [name,test]of Object.entries(cases)){const f=await fixture(browser);try{await test(f);assert.deepEqual(f.errors,[]);console.log('PASS '+name);}catch(e){failures.push(name+': '+e.message);console.error('FAIL '+name+': '+e.message);}finally{await f.close();}}assert.deepEqual(failures,[]);}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
