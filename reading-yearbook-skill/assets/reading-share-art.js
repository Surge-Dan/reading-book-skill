/* Fixed reading plates, content-flow layout and one offline PNG pipeline. */
window.ReadingShareArtwork = (() => {
  'use strict';
  const VERSION='reading-plates-2', WIDTH=900;
  const ratios={'1:1':{height:900,categories:5,events:4,covers:4,trend:190},'3:4':{height:1200,categories:7,events:6,covers:5,trend:220},'4:5':{height:1125,categories:6,events:5,covers:5,trend:200}};
  const muted='#667085',blue='#0066cc',palette=[blue,'#387c91','#7864a2','#557d70','#78889d','#7185a3','#5e7c86'];
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const known=n=>typeof n==='number'&&Number.isFinite(n),value=n=>known(n)?String(n):'—';
  const txt=(s,cls='',tag='span')=>`<${tag} class="${cls}" data-rs-text>${esc(s)}</${tag}>`;
  const seconds=n=>!known(n)?'未记录':`${Math.floor(n/3600)}小时${Math.floor(n%3600/60)}分钟`;
  const short=(s,n)=>Array.from(String(s||'')).length>n?Array.from(String(s)).slice(0,n).join('')+'…':String(s||'');
  const time=n=>known(n)?`<div class="rs-time">${[[Math.floor(n/3600),'小时'],[Math.floor(n%3600/60),'分钟']].map(([v,u])=>`<div class="rs-value-line">${txt(v,'rs-value')}${txt(u,'rs-unit')}</div>`).join('')}</div>`:txt('未记录','rs-label');
  const metric=(v,label,{unit='',compact=false}={})=>`<div class="rs-metric ${compact?'rs-metric-compact':''}" data-rs-metric><div class="rs-value-line">${txt(value(v),'rs-value')}${unit?txt(unit,'rs-unit'):''}</div>${txt(label,'rs-label')}</div>`;
  const section=(label,aside='')=>`<div class="rs-section-title">${txt(label)}${aside?txt(aside,'rs-caption'):''}</div>`;
  const empty=message=>`<div class="rs-empty">${txt(message)}</div>`;

  function create({data,loadImage}){
    const books=data.books,summary=data.summary;
    const groups=new Map();for(const b of books)groups.set(b.category||'未分类',(groups.get(b.category||'未分类')||0)+1);
    const categories=[...groups].map(([name,count])=>({name,count})).sort((a,b)=>b.count-a.count||a.name.localeCompare(b.name,'zh'));
    const categoryColors=new Map(categories.map((r,i)=>[r.name,palette[i%palette.length]]));
    const months=summary.monthly.slice(0,summary.complete_months),events=[],seen=new Set();
    for(const b of books){
      for(const [field,kind]of [['start_date','开始阅读'],['finish_date','读完']])if(b[field]?.startsWith(String(data.year)))events.push({date:b[field].slice(0,10),kind,book:b});
      for(const [field,kind]of [['highlights','划线'],['thoughts','笔记']])for(const n of b[field]||[])if(n.created_at?.startsWith(String(data.year))){const key=b.book_id+'|'+kind+'|'+(n.source_id||n.text+'|'+n.created_at);if(!seen.has(key)){seen.add(key);events.push({date:n.created_at.slice(0,10),kind,book:b});}}
    }
    events.sort((a,b)=>a.date.localeCompare(b.date)||a.book.book_id.localeCompare(b.book.book_id));
    const cache=new Map();let queue=Promise.resolve();
    function cover(b,caption=false){
      const visual=b.cover?`<img src="${esc(b.cover)}" alt="">`:`<div class="rs-cover-fallback">${txt(short(b.title,24))}</div>`;
      return `<figure class="rs-cover-item">${visual}${caption?txt(short(b.title,8),'','figcaption'):''}</figure>`;
    }
    function shelf(rows,caption=true){return `<div class="rs-cover-shelf" style="grid-template-columns:repeat(${Math.max(1,rows.length)},minmax(0,1fr))">${rows.map(b=>cover(b,caption)).join('')}</div>`;}
    function totals(compact=false){return `<div class="rs-metrics">${[[summary.read,'读过的书'],[summary.finished,'读完的书'],[summary.read_days,'阅读天数'],[summary.notes,'笔记记录']].map(([v,l])=>metric(v,l,{compact})).join('')}</div>`;}
    function heading(title,subtitle=''){return `<div class="rs-heading">${txt(title,'rs-title','h1')}${subtitle?txt(subtitle,'rs-subtitle','p'):''}</div>`;}
    function trend(height,{mini=false}={}){
      const vals=months,valid=vals.map((v,i)=>({v,i})).filter(r=>known(r.v));
      if(!valid.length)return {html:mini?'':empty('暂无月度阅读时长记录'),chart:null};
      const W=mini?360:788,left=mini?8:44,right=W-(mini?8:18),base=height-(mini?10:43),upper=mini?10:24;
      const top=Math.max(2,Math.ceil(Math.max(...valid.map(r=>r.v/3600))/2)*2);
      const x=i=>vals.length===1?(left+right)/2:left+i*(right-left)/(vals.length-1),y=v=>base-v/3600/top*(base-upper);
      const points=vals.map((v,i)=>known(v)?{month:i+1,value:v,x:x(i),y:y(v)}:null);
      let svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${height}" aria-label="每月阅读时长，单位小时">`;
      if(!mini){
        for(const v of [0,top/2,top])svg+=`<line x1="${left}" y1="${y(v*3600)}" x2="${right}" y2="${y(v*3600)}" stroke="#e5e7eb"/><text x="0" y="${y(v*3600)+9}" fill="${muted}" font-size="28" data-rs-text>${v}</text>`;
        for(let i=0;i<vals.length;i++)if(vals.length<=10||i%2===0||i===vals.length-1)svg+=`<text x="${x(i)}" y="${height-3}" text-anchor="middle" fill="${muted}" font-size="28" data-rs-text>${i+1}月</text>`;
      }
      let path='',previous=false;for(const p of points){if(!p){previous=false;continue;}path+=`${previous?'L':'M'}${p.x},${p.y} `;previous=true;}
      svg+=`<path d="${path}" fill="none" stroke="${blue}" stroke-width="${mini?2.5:3}" stroke-linecap="round" stroke-linejoin="round"/>`;
      for(const p of points.filter(Boolean))svg+=`<circle cx="${p.x}" cy="${p.y}" r="${mini?3:4.5}" fill="${blue}"/>`;
      const peak=valid.reduce((a,b)=>b.v>a.v?b:a);
      const note=mini?'':`<div class="rs-trend-note">${txt(`${peak.i+1}月读得最久`,'','strong')}${txt(seconds(peak.v))}</div>`;
      return {html:`<div class="rs-chart-block">${mini?txt('每月阅读时长','rs-caption'):section('每月阅读时长','小时')}${svg}</svg>${note}</div>`,chart:{kind:'monthly',points,base,upper,top}};
    }
    function ranking(limit){
      const rows=books.filter(b=>known(b.reading_seconds)).sort((a,b)=>b.reading_seconds-a.reading_seconds).slice(0,limit);if(!rows.length)return '';
      const max=Math.max(...rows.map(b=>b.reading_seconds),1);
      return `<div class="rs-ranking" data-rs-optional>${section('时间花在哪些书上')}${rows.map(b=>`<div class="rs-rank-row">${txt(short(b.title,13),'rs-rank-name')}<div class="rs-rank-track"><div class="rs-rank-bar" style="width:${b.reading_seconds/max*100}%"></div></div>${txt(seconds(b.reading_seconds),'rs-rank-time')}</div>`).join('')}</div>`;
    }
    function coverPage(config,manifest){
      const chosen=[...books.filter(b=>b.selected),...books.filter(b=>!b.selected)].slice(0,config.covers),graph=trend(86,{mini:true});if(graph.chart)manifest.charts.push(graph.chart);
      return `<div class="rs-cover-heading"><div>${txt('我的阅读年鉴','rs-kicker','p')}<h1 class="rs-title" data-rs-text>这一年，<br>读了这些书</h1></div>${txt(data.year,'rs-year')}</div>`+
        (chosen.length?shelf(chosen):empty(data.coverage.complete?'这一年，还没有阅读记录':'阅读记录尚未取得'))+
        `<div class="rs-cover-data">${totals()}</div><div class="rs-cover-bottom" data-rs-optional><div>${time(summary.seconds)}${txt('累计阅读时长','rs-label')}</div>${graph.html}</div>`;
    }
    function statsPage(config,manifest){
      const graph=trend(config.trend);if(graph.chart)manifest.charts.push(graph.chart);
      return heading('花在书上的时间')+`<div class="rs-time-wrap">${time(summary.seconds)}${txt('累计阅读时长','rs-label')}</div>`+totals(true)+graph.html+(config.height===900?'':ranking(1));
    }
    function distributionPage(config,manifest){
      if(!books.length)return heading('今年读了些什么')+empty(data.coverage.complete?'还没有可统计的书籍':'书籍记录尚未取得');
      let rows=categories.slice();if(rows.length>config.categories){const unknown=rows.find(r=>r.name==='未分类'),named=rows.filter(r=>r!==unknown),slots=config.categories-(unknown?1:0)-1,shown=named.slice(0,slots),rest=named.slice(slots);rows=[...shown,...(unknown?[unknown]:[]),{name:'其他分类',count:rest.reduce((n,r)=>n+r.count,0),aggregated:true}];}
      const max=Math.max(...rows.map(r=>r.count),1);for(const row of rows)manifest.charts.push({kind:'category',...row,total:books.length});
      const representatives=rows.filter(r=>!r.aggregated).map(r=>books.find(b=>(b.category||'未分类')===r.name)).slice(0,5);
      return heading('今年读了些什么')+`<div class="rs-distribution-summary">${txt(books.length,'rs-value')}${txt('本已载入书籍','rs-caption')}${txt(`${categories.length}个分类`,'rs-caption')}</div>`+
        `<div class="rs-category-list">${rows.map(r=>`<div class="rs-category-row">${txt(short(r.name,12),'rs-category-name')}<div class="rs-category-track"><div class="rs-category-bar" style="width:${r.count/max*100}%;background:${categoryColors.get(r.name)||muted}"></div></div>${txt(r.count,'rs-category-count')}</div>`).join('')}</div>`+
        `<div class="rs-cover-index" data-rs-optional>${section('从这些书，继续翻下去')}${shelf(representatives)}</div>`;
    }
    function timelinePage(config,manifest){
      if(!events.length)return heading('顺着这一年翻回去')+empty('暂无带日期的阅读或笔记记录');
      const byMonth=new Map();for(const e of events){const month=e.date.slice(0,7);if(!byMonth.has(month))byMonth.set(month,[]);byMonth.get(month).push(e);}
      const rows=[...byMonth].slice(0,config.events).map(([month,list])=>({month,event:list.find(e=>e.kind==='读完')||list[0],count:list.length}));
      manifest.charts.push({kind:'timeline',events:events.length,months:byMonth.size,shown:rows.length});
      return heading('顺着这一年翻回去')+`<div class="rs-timeline">${rows.map(({month,event:e,count})=>`<div class="rs-event">${txt(`${Number(month.slice(5))}月`,'rs-event-date')}<div class="rs-event-mark"></div><div>${txt(short(e.book.title,24),'rs-event-title','p')}${txt(`${e.date.slice(5).replace('-','月')}日 · ${e.kind}${count>1?` · 本月${count}条记录`:''}`,'rs-event-kind','p')}</div>${e.book.cover?`<img src="${esc(e.book.cover)}" alt="">`:'<span></span>'}</div>`).join('')}</div>`+
        txt(`有日期的记录 · 展示${rows.length}／${byMonth.size}个月`,'rs-events-scope','p');
    }
    function material(label,text,limit,primary=false){
      const content=short(text,limit),cut=content!==text;
      return `<div class="rs-material">${txt(label,'rs-material-label','p')}${primary?`<blockquote class="rs-quote" data-rs-text data-rs-full="${esc(text)}">${esc(content)}</blockquote>`:txt(content,'rs-note','p')}${cut?txt('节选 · 完整记录见年鉴','rs-excerpt-tag','p'):''}</div>`;
    }
    function bookPage(p,config,manifest){
      const b=p.book,isSquare=config.height===900,primary=p.quote||b.highlights[0]?.text||b.thoughts[0]?.text||'',isThought=p.quote?p.textKind==='thought':!b.highlights.length;
      const longTitle=Array.from(b.title).length>24,stacked=!!primary&&primary.length>100&&!longTitle&&!isSquare;
      manifest.material={kind:primary?'reading-notes':b.intro?'intro':'book-info'};
      const bookTitle=`<div class="rs-book-heading ${longTitle?'rs-long-title':''}">${txt(b.title,'rs-title','h1')}${txt(b.author||'作者未记录','rs-subtitle','p')}</div>`;
      const object=`<div class="rs-book-object">${b.cover?`<img src="${esc(b.cover)}" alt="">`:`<div class="rs-cover-fallback">${txt(short(b.title,24))}</div>`}${txt(short(b.category||'未分类',20),'rs-book-category','p')}</div>`;
      let main='';
      if(primary){
        const limit=isSquare?(longTitle?36:primary.length>85?55:85):longTitle?100:stacked?(config.height===1200?100:80):155,second=(isThought?b.highlights:b.thoughts).find(n=>n.text!==primary);
        const third=b.highlights.find(n=>n.text!==primary&&n.text!==second?.text&&n.text.length>=12);
        main=`<div class="rs-book-main ${stacked?'rs-stacked':''}">${object}<div class="rs-materials">${material(isThought?'我的笔记':'原文摘录',primary,limit,true)}${second&&!longTitle&&!isSquare?`<div data-rs-optional>${material(isThought?'原文摘录':'我的笔记',second.text,65)}</div>`:''}${third&&!longTitle&&!isSquare&&!stacked?`<div data-rs-optional>${material('另一处划线',third.text,65)}</div>`:''}</div></div>`;
      }else{
        const state=known(b.progress)?b.progress>=100?'已经读完':'还在阅读':'阅读记录';
        main=`<div class="rs-book-main rs-book-info">${object}<div>${b.intro?material('内容简介',b.intro,isSquare?50:120):txt(state,'rs-info-heading','h2')+txt(b.note_coverage?.highlights==='complete'&&b.note_coverage?.thoughts==='complete'?'这本书还没有划线或笔记。':'划线或笔记暂未取得。','rs-info-copy','p')}</div></div>`;
      }
      const metrics=[];
      if(known(b.reading_seconds))metrics.push(`<div class="rs-metric rs-metric-compact">${time(b.reading_seconds)}${txt('阅读时长','rs-label')}</div>`);
      if(b.note_coverage?.highlights==='complete')metrics.push(metric(b.highlights.length,'划线',{compact:true}));
      if(b.note_coverage?.thoughts==='complete')metrics.push(metric(b.thoughts.length,'个人笔记',{compact:true}));
      if(metrics.length<3&&known(b.progress))metrics.push(metric(b.progress,'当前阅读进度',{compact:true,unit:'%'}));
      const progress=known(b.progress)?`<div class="rs-book-progress" data-rs-optional><div class="rs-progress-label">${txt('当前阅读进度')}${txt(b.progress+'%')}</div><div class="rs-progress"><span style="width:${Math.min(100,Math.max(0,b.progress))}%"></span></div></div>`:'';
      return bookTitle+main+(metrics.length?`<div class="rs-book-metrics" style="grid-template-columns:repeat(${metrics.length},minmax(0,1fr))">${metrics.join('')}</div>`:'')+progress;
    }
    function makePage(p,ratio){
      const config=ratios[ratio];if(!config)throw Error('不支持的图片比例');
      const manifest={version:VERSION,page:p.id,width:WIDTH,height:config.height,text:[],charts:[],images:[],spacing:[],removed:[]},titles={cover:'阅读年鉴',stats:'阅读统计',distribution:'阅读分布',timeline:'阅读时间线',book:'书页之间'};
      const index=p.kind==='book'?5+books.findIndex(b=>b.book_id===p.book.book_id):['cover','stats','distribution','timeline'].indexOf(p.kind)+1;
      const root=document.createElement('article');root.className='rs-page';root.dataset.ratio=ratio;root.dataset.kind=p.kind;root.style.height=config.height+'px';
      root.innerHTML=`<header class="rs-head">${txt('年年阅','rs-brand')}<div class="rs-head-right">${txt(titles[p.kind])}<i class="rs-dot"></i>${txt(data.year)}</div></header><div class="rs-content">${p.kind==='cover'?coverPage(config,manifest):p.kind==='stats'?statsPage(config,manifest):p.kind==='distribution'?distributionPage(config,manifest):p.kind==='timeline'?timelinePage(config,manifest):bookPage(p,config,manifest)}</div><footer class="rs-foot">${txt(String(index).padStart(2,'0')+' / '+String(4+books.length).padStart(2,'0'))}${txt(data.source_mode==='sample'?'示例数据':!data.coverage.complete?'已载入的阅读记录':p.kind==='book'?'原文与阅读记录':'我的阅读年鉴')}</footer>`;
      return {root,manifest};
    }
    function measure(root,manifest){
      const origin=root.getBoundingClientRect();
      let node=0;
      for(const n of root.querySelectorAll('[data-rs-text]')){node++;const range=document.createRange();range.selectNodeContents(n);const style=getComputedStyle(n),box=n.getBoundingClientRect();for(const r of range.getClientRects())if(r.width&&r.height){const right=style.overflow==='hidden'?Math.min(r.right,box.right):r.right;manifest.text.push({node,text:n.textContent,x:r.left-origin.left,y:r.top-origin.top,w:right-r.left,h:r.height,size:parseFloat(style.fontSize)});}}
      for(const n of root.querySelectorAll('img')){const r=n.getBoundingClientRect();manifest.images.push({x:r.left-origin.left,y:r.top-origin.top,w:r.width,h:r.height,angle:0});}
      for(const n of root.querySelectorAll('[data-rs-metric]')){const number=n.querySelector('.rs-value-line').getBoundingClientRect(),label=n.querySelector('.rs-label').getBoundingClientRect();manifest.spacing.push({kind:'metric-label',gap:label.top-number.bottom,minimum:16});}
      const labels=[...root.querySelectorAll('.rs-book-metrics>.rs-metric>.rs-label')].map(n=>n.getBoundingClientRect().top);
      manifest.metricLabelDeviation=labels.length?Math.max(...labels)-Math.min(...labels):0;
      if(manifest.metricLabelDeviation>.5)throw Error('指标说明未对齐，请调整数值行高度');
      const foot=root.querySelector('.rs-foot').getBoundingClientRect();
      if(manifest.text.some(t=>t.x<40||t.x+t.w>WIDTH-30||t.y<25||t.y+t.h>manifest.height-20)||[...root.querySelectorAll('.rs-content [data-rs-text],.rs-content img')].some(n=>{const r=n.getBoundingClientRect();return r.height&&r.width&&r.bottom>foot.top-18;}))throw Error('这页文字超出安全版面，请缩短次级材料或调整标题区');
      for(let i=0;i<manifest.text.length;i++)for(let j=i+1;j<manifest.text.length;j++){const a=manifest.text[i],b=manifest.text[j];if(a.node===b.node)continue;const dx=Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x),dy=Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y);if(dx>2&&dy>2)throw Error('文字区发生碰撞，请调整这一页的材料容量');}
      return manifest;
    }
    async function generate(p,ratio){
      await document.fonts.load('400 32px ReadingSans');await document.fonts.load('600 56px ReadingSans');await document.fonts.ready;
      const {root,manifest}=makePage(p,ratio),host=document.createElement('div');
      host.style.cssText='position:fixed;left:-12000px;top:0;width:900px;pointer-events:none;z-index:-1;';host.setAttribute('aria-hidden','true');host.append(root);document.body.append(host);
      try{
        await Promise.all([...root.querySelectorAll('img')].map(async im=>{if(loadImage)await loadImage(im.src);await im.decode();}));
        const fits=()=>{const content=root.querySelector('.rs-content'),foot=root.querySelector('.rs-foot');return content.scrollHeight<=content.clientHeight+1&&content.getBoundingClientRect().bottom<=foot.getBoundingClientRect().top-18;};
        for(const optional of [...root.querySelectorAll('[data-rs-optional]')].reverse()){if(fits())break;manifest.removed.push(optional.className||'secondary-material');optional.remove();}
        const timeline=root.querySelector('.rs-timeline');
        if(timeline){while(!fits()&&timeline.children.length>1)timeline.lastElementChild.remove();const chart=manifest.charts.find(c=>c.kind==='timeline');chart.shown=timeline.children.length;root.querySelector('.rs-events-scope').textContent=`有日期的记录 · 展示${chart.shown}／${chart.months}个月`;}
        // Actual line boxes decide the excerpt capacity, rather than guessing
        // that the same character count fits every font, title and proportion.
        const quote=root.querySelector('[data-rs-full]');
        if(quote){for(let pass=0;pass<3&&!fits();pass++){
          const content=root.querySelector('.rs-content'),lineHeight=parseFloat(getComputedStyle(quote).lineHeight),lines=Math.max(1,Math.round(quote.clientHeight/lineHeight)),tag=quote.parentElement.querySelector('.rs-excerpt-tag');
          const overflow=Math.max(0,content.scrollHeight-content.clientHeight)+(tag?0:52)+8,keep=lines-Math.ceil(overflow/lineHeight);
          if(keep<1)break;
          const length=Math.max(12,Math.floor(Array.from(quote.textContent).length*keep/lines)-2);quote.textContent=short(quote.dataset.rsFull,length);
          if(!tag){const note=document.createElement('p');note.className='rs-excerpt-tag';note.dataset.rsText='';note.textContent='节选 · 完整记录见年鉴';quote.after(note);}
        }quote.removeAttribute('data-rs-full');}
        if(!fits())throw Error('当前内容超出这一比例的容量，请调整标题或摘录后重试');
        if(!root.querySelector('.rs-chart-block svg')?.getClientRects().length)manifest.charts=manifest.charts.filter(c=>c.kind!=='monthly');
        measure(root,manifest);
        const cv=await window.htmlToImage.toCanvas(root,{width:WIDTH,height:manifest.height,pixelRatio:1,backgroundColor:'#fff',skipAutoScale:true,fontEmbedCSS:document.querySelector('#reading-fonts')?.textContent||''});
        cv.readingLayout=manifest;return cv;
      }finally{host.remove();}
    }
    function render(p,ratio){
      const key=JSON.stringify([VERSION,ratio,p.id,p.quote,p.textKind,p.book]);
      if(cache.has(key)){const cv=cache.get(key);cache.delete(key);cache.set(key,cv);return Promise.resolve(cv);}
      const work=queue.then(async()=>{if(cache.has(key))return cache.get(key);const cv=await generate(p,ratio);cache.set(key,cv);while(cache.size>5)cache.delete(cache.keys().next().value);return cv;});queue=work.catch(()=>{});return work;
    }
    return {render,version:VERSION};
  }
  return {create};
})();
