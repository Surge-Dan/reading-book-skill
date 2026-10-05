/* Offline reading yearbook. Chart adapted from lieflat-charts Basics B2/F2;
 * PolyForm Noncommercial 1.0.0, full license retained in this document. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('reading-data').textContent);
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const serif = 'ReadingSerif, "Noto Serif SC", "SimSun", serif';
  const state = {query:'', status:'all', category:'', list:false, expanded:false, quote:0, busy:false, preview:'cover', ratio:'3:4', undo:[], selection:new Set(), composing:false};
  const bookMap = new Map(data.books.map(b => [b.book_id,b]));
  const highlights = data.books.flatMap(b => b.highlights.map(n => ({...n,book:b})));
  let toastTimer, searchTimer, previousFocus, originalHash='', dialogPushed=false, renderToken=0;
  const hours = v => v == null ? '未记录' : `${(v/3600).toFixed(1)}小时`;
  const duration = v => v == null ? '未记录' : `${Math.floor(v/3600)}小时${Math.floor(v%3600/60)}分钟`;
  const value = v => v == null ? '—' : String(v);
  const statusLabel = b => ({finished:'已读完',reading:'在读',unknown:'状态未记录'}[b.status]);
  const scope = data.coverage.complete ? `全年${data.books.length}本` : `已载入${data.books.length}本 · 年度记录${value(data.coverage.annual_books)}本`;
  function toast(text) {$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,2800);}
  $('#period').textContent = `${data.year}${data.as_of ? ` · 1—${Number(data.as_of.slice(5,7))}月` : ''}`;
  $('#modeNotice').textContent = data.source_mode==='sample' ? '示例数据 · 不代表真实阅读记录' : data.verification_status!=='live_verified' ? '数据尚未核验，供预览使用' : '';
  const time = data.summary.seconds;
  $('#stats').innerHTML = `<div class="metric lead"><strong>${time==null?'—':`${Math.floor(time/3600)}<em>小时</em>${Math.floor(time%3600/60)}<em>分钟</em>`}</strong><span>累计阅读时长</span></div>` + [[data.summary.read,'本读过'],[data.summary.finished,'本读完'],[data.summary.read_days,'天阅读'],[data.summary.notes,'条笔记']].map(([v,t])=>`<div class="metric"><strong>${esc(value(v))}</strong><span>${t}</span></div>`).join('');
  $('#distributionScope').textContent=`${scope} · 按主分类计数`;
  $('#shelfScope').textContent=scope;

  function drawChart() {
    const end = data.summary.complete_months;
    const months = data.summary.monthly.slice(0,end);
    $('#monthlyTable').innerHTML='<table><thead><tr><th>月份</th><th>时长</th></tr></thead><tbody>'+months.map((v,i)=>`<tr><td>${i+1}月</td><td>${esc(duration(v))}</td></tr>`).join('')+'</tbody></table>';
    if (!months.some(x=>x!=null)) {$('#chart').innerHTML='<p class="empty">暂无完整月份的阅读时长</p>';return;}
    // B2 skeleton: calendar floor, hairline path, individual dots, peak label.
    // Mapping uses unrounded seconds; null breaks a path, a measured zero stays on baseline.
    const mobile=matchMedia('(max-width:520px)').matches, W=Math.max(280,$('#chart').clientWidth),H=mobile?220:235;
    const left=37,right=W-15,base=H-37,max=Math.max(...months.filter(v=>v!=null).map(v=>v/3600),1);
    const top=Math.ceil(max/2)*2, x=i=>months.length===1?(left+right)/2:left+i*(right-left)/(months.length-1), y=v=>base-(v/3600)/top*(base-25);
    let svg=`<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="月度阅读时长，单位小时"><title>月度阅读时长</title>`;
    for (const tick of [0,top/2,top]) svg+=`<line x1="${left}" y1="${base-tick/top*(base-25)}" x2="${right}" y2="${base-tick/top*(base-25)}" stroke="#d5d3ca" stroke-width=".7" ${tick?'stroke-dasharray="2 4"':''}/><text x="${left-12}" y="${base-tick/top*(base-25)+4}" text-anchor="end" fill="#696962" font-size="12">${tick}</text>`;
    svg+='<text x="0" y="13" fill="#696962" font-size="11">小时</text>';
    let segment=[]; const paths=[];
    months.forEach((v,i)=>{if(v==null){if(segment.length)paths.push(segment);segment=[];}else segment.push([x(i),y(v)]);});if(segment.length)paths.push(segment);
    paths.forEach(points=>svg+=`<path d="${points.map((p,i)=>(i?'L':'M')+p.join(' ')).join(' ')}" fill="none" stroke="#ad3736" stroke-width="1.4"/>`);
    const peak=months.findIndex(v=>v!=null&&v===Math.max(...months.filter(v=>v!=null)));
    months.forEach((v,i)=>{svg+=`<line x1="${x(i)}" y1="${base}" x2="${x(i)}" y2="${base-7}" stroke="#bdbab0" stroke-width=".8"/><text x="${x(i)}" y="${base+24}" text-anchor="middle" fill="#696962" font-size="12">${i+1}月</text>`;
      if(v!=null) {svg+=`<circle data-chart-month="${i}" tabindex="0" role="button" aria-label="${i+1}月，${esc(duration(v))}" cx="${x(i)}" cy="${y(v)}" r="${i===peak?4.5:3}" fill="#ad3736"/><circle cx="${x(i)}" cy="${y(v)}" r="11" fill="transparent" data-chart-month="${i}" aria-hidden="true"/>`;
        if(i===peak)svg+=`<text x="${x(i)}" y="${y(v)-13}" text-anchor="middle" fill="#ad3736" font-size="13" style="paint-order:stroke;stroke:#faf8f2;stroke-width:4">${(v/3600).toFixed(1)}</text>`;}
    }); $('#chart').innerHTML=svg+'</svg>';
    $$('[data-chart-month]').forEach(el=>{const show=()=>$('#chartReadout').textContent=`${Number(el.dataset.chartMonth)+1}月 · ${duration(months[el.dataset.chartMonth])}`;el.addEventListener('mouseenter',show);el.addEventListener('focus',show);el.addEventListener('click',show);el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show();}});});
  }
  drawChart(); let resizeFrame;addEventListener('resize',()=>{cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(drawChart);});

  const categories = [...new Set(data.books.map(b=>b.category))];
  const categoryPalette=['#b65a54','#60829a','#b08b3d','#63806e'];
  const categoryCounts = categories.map(c=>({name:c,count:data.books.filter(b=>b.category===c).length})).sort((a,b)=>b.count-a.count);
  $('#distribution').innerHTML=categoryCounts.length?categoryCounts.map((c,i)=>`<button class="category-row" data-category="${esc(c.name)}" aria-pressed="false"><span>${esc(c.name)}</span><span class="category-track"><i class="category-bar" style="width:${c.count/data.books.length*100}%;background:${categoryPalette[i%4]}"></i></span><span class="category-count">${c.count}本</span></button>`).join(''):'<p class="empty">暂无可统计书目</p>';
  $$('[data-category]').forEach(button=>button.onclick=()=>{state.category=state.category===button.dataset.category?'':button.dataset.category;drawBooks();$('#shelf').scrollIntoView({block:'start'});});
  const events=[]; const seenEvents=new Set();
  data.books.forEach(b=>{for(const [type,list] of [['划线',b.highlights],['笔记',b.thoughts]])list.forEach(n=>{if(n.created_at){const key=`${b.book_id}|${type}|${n.source_id||n.text+'|'+n.created_at}`;if(!seenEvents.has(key)){seenEvents.add(key);events.push({date:n.created_at,type,book:b,text:n.text});}}});
    for(const [type,date] of [['开始阅读',b.start_date],['读完',b.finish_date]])if(date&&Number(date.slice(0,4))===data.year)events.push({date,type,book:b});});
  events.sort((a,b)=>a.date.localeCompare(b.date));
  const eventHtml = e=>`<div class="timeline-row"><time datetime="${esc(e.date)}">${e.date.slice(5).replace('-','.')}</time><button class="timeline-book" data-open-book="${esc(e.book.book_id)}">${esc(e.book.title)}</button><span class="event-type">${e.type}</span></div>`;
  const groups=[...new Set(events.map(e=>e.date.slice(0,7)))];
  const previewEvents=[],previewBooks=new Set();
  for(const e of [...events].reverse())if(!previewBooks.has(e.book.book_id)&&previewEvents.length<4){previewBooks.add(e.book.book_id);previewEvents.push(e);}
  previewEvents.sort((a,b)=>a.date.localeCompare(b.date));
  const remainingEvents=events.filter(e=>!previewEvents.includes(e));
  $('#timeline').innerHTML=events.length?previewEvents.map(eventHtml).join('')+(remainingEvents.length?`<details><summary>展开其余${remainingEvents.length}条记录</summary>${groups.map(m=>{const rows=remainingEvents.filter(e=>e.date.startsWith(m));return rows.length?`<h3 class="timeline-month">${Number(m.slice(5))}月</h3>${rows.map(eventHtml).join('')}`:'';}).join('')}</details>`:''):'<p class="empty">暂无带日期的阅读记录</p>';

  function fallbackCover(b){return `<span class="cover-fallback"><span>${esc(b.title)}</span><small>${esc(b.author)}</small></span>`;}
  function coverMarkup(b) {return b.cover?`<img data-cover-book="${esc(b.book_id)}" src="${esc(b.cover)}" alt="《${esc(b.title)}》书封" loading="lazy">`:fallbackCover(b);}
  document.addEventListener('error',e=>{if(e.target instanceof HTMLImageElement&&e.target.dataset.coverBook){const b=bookMap.get(e.target.dataset.coverBook);if(b){const holder=document.createElement('span');holder.innerHTML=fallbackCover(b);e.target.replaceWith(holder.firstElementChild);}}},true);
  function visibleBooks(){const q=state.query.toLocaleLowerCase();return data.books.filter(b=>(state.status==='all'||b.status===state.status)&&(!state.category||b.category===state.category)&&(!q||(b.title+' '+b.author).toLocaleLowerCase().includes(q)));}
  function drawBooks(printing=false) {
    const all=visibleBooks(), filtered=!!state.query||!!state.category||state.status!=='all', collapsed=!printing&&!filtered&&!state.expanded&&all.length>4;
    const picked=all.filter(b=>b.selected), rows=collapsed?(picked.length?picked:all).slice(0,4):all;
    $('#expandShelf').hidden=filtered||printing||all.length<=4;$('#expandShelf').setAttribute('aria-expanded',String(state.expanded));$('#expandShelf').textContent=state.expanded?'收起书目 ↑':`展开全部${all.length}本 →`;
    $('#books').classList.toggle('list',state.list);
    $('#books').innerHTML=rows.length?rows.map(b=>`<article class="book-entry"><button class="book" data-open-book="${esc(b.book_id)}"><span class="cover-wrap">${coverMarkup(b)}</span><h3>${esc(b.title)}</h3><p class="author">${esc(b.author)}</p><p class="book-meta">${esc(statusLabel(b))}${b.progress==null?'':` · ${b.progress}%`}</p></button><div class="book-actions"><button class="text-button" data-open-book="${esc(b.book_id)}">书评与笔记 ↗</button><button class="text-button" data-share-book="${esc(b.book_id)}">加入分享</button></div></article>`).join(''):'<p class="empty">没有找到对应的书。可以换个关键词，或清除筛选。</p>';
    $('#resultCount').textContent=`${collapsed?'精选':'显示'}${rows.length}／${data.books.length}本${state.category?' · '+state.category:''}`;
    $('#clearFilters').hidden=!state.query&&!state.category&&state.status==='all';
    $$('[data-status]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.status===state.status)));
    $$('[data-category]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.category===state.category)));
  }
  drawBooks();
  $('#expandShelf').onclick=()=>{state.expanded=!state.expanded;drawBooks();};
  $$('[data-status]').forEach(b=>b.onclick=()=>{state.status=b.dataset.status;drawBooks();});
  $('#clearFilters').onclick=()=>{clearTimeout(searchTimer);state.query='';state.status='all';state.category='';$('#search').value='';drawBooks();};
  const updateSearch=()=>{state.query=$('#search').value.trim();drawBooks();};
  $('#search').addEventListener('compositionstart',()=>{state.composing=true;clearTimeout(searchTimer);});
  $('#search').addEventListener('compositionend',()=>{state.composing=false;updateSearch();});
  $('#search').addEventListener('input',e=>{if(state.composing||e.isComposing)return;clearTimeout(searchTimer);searchTimer=setTimeout(updateSearch,180);});
  $('#viewSwitch').onclick=()=>{state.list=!state.list;$('#viewSwitch').setAttribute('aria-pressed',String(state.list));$('#viewSwitch').textContent=state.list?'封面视图':'列表视图';drawBooks();};

  function noteHtml(n,b,index,type){return `<div class="detail-note">${esc(n.text)}<small>${esc(n.created_at||'日期未记录')}${n.chapter?' · 章节 '+esc(n.chapter):''}</small>${type==='划线'?`<button class="text-button" data-add-quote="${esc(b.book_id)}" data-index="${index}">选这条加入分享</button>`:''}</div>`;}
  function openBook(id,fromHash=false) {
    const b=bookMap.get(id);if(!b)return;
    if(!$('#detail').open){previousFocus=document.activeElement;originalHash=location.hash;}
    $('#detailContent').innerHTML=`<div class="detail-identity"><div>${coverMarkup(b)}</div><div><h2 id="detailTitle">${esc(b.title)}</h2><p>${esc(b.author)}</p><p>${esc(statusLabel(b))} · ${esc(b.category)}${b.reading_seconds==null?'':' · 年内'+duration(b.reading_seconds)}</p></div></div><section class="detail-section"><h3>全书书评</h3>${b.review.status==='verified'?`<p>${esc(b.review.body)}</p><p class="review-source">正文来源：${esc(b.review.source)}\n版本：${esc(b.review.version)}\n章节依据：${esc(b.review.citations.join('；'))}</p>`:'<p class="muted">尚未取得并核验完整正文，暂不生成全书书评。</p>'}</section>${b.intro?`<details class="detail-section"><summary>书籍简介</summary><p>${esc(b.intro)}</p></details>`:''}<section class="detail-section"><h3>划线 · ${b.highlights.length}条</h3>${b.highlights.map((n,i)=>noteHtml(n,b,i,'划线')).join('')||'<p class="muted">这本书尚未载入划线。</p>'}</section><section class="detail-section"><h3>我的笔记 · ${b.thoughts.length}条</h3>${b.thoughts.map((n,i)=>noteHtml(n,b,i,'笔记')).join('')||'<p class="muted">这本书尚未载入个人笔记。</p>'}</section>`;
    if(!$('#detail').open)$('#detail').showModal();$('#detail').scrollTop=0;
    if(!fromHash){history.pushState(null,'','#book='+encodeURIComponent(id));dialogPushed=true;}
  }
  function closeBook(){if(!$('#detail').open)return;$('#detail').close();if(dialogPushed&&location.hash.startsWith('#book=')){history.back();}else if(location.hash.startsWith('#book=')){history.replaceState(null,'',originalHash.startsWith('#book=')?'#shelf':originalHash||'#shelf');}dialogPushed=false;previousFocus?.isConnected&&previousFocus.focus({preventScroll:true});}
  $('#detail .close').onclick=closeBook;
  $('#detail').addEventListener('cancel',e=>{e.preventDefault();closeBook();});
  addEventListener('hashchange',()=>{if(location.hash.startsWith('#book=')){try{openBook(decodeURIComponent(location.hash.slice(6)),true);}catch{toast('书籍链接无效');}}else if($('#detail').open){$('#detail').close();dialogPushed=false;previousFocus?.isConnected&&previousFocus.focus({preventScroll:true});}});
  if(location.hash.startsWith('#book=')){try{openBook(decodeURIComponent(location.hash.slice(6)),true);}catch{}}
  document.addEventListener('click',e=>{const open=e.target.closest('[data-open-book]');if(open)openBook(open.dataset.openBook);const add=e.target.closest('[data-share-book]');if(add)addBookShare(add.dataset.shareBook);const quote=e.target.closest('[data-add-quote]');if(quote){const b=bookMap.get(quote.dataset.addQuote);addBookShare(b.book_id,b.highlights[Number(quote.dataset.index)]?.text);toast('已加入分享，可在分享区预览');}});
  $('#sourcesDialog .close').onclick=()=>$('#sourcesDialog').close();
  $('#openSources').onclick=()=>{$('#sourcesContent').innerHTML=`<p>统计年份：${data.year}${data.as_of?'；采集日期：'+esc(data.as_of):''}</p><p>书目范围：${esc(scope)}。</p><p>模式：${esc(data.source_mode)}；核验状态：${esc(data.verification_status)}。</p><p>分布按已载入书籍的主分类计数；未知状态不归入“在读”。月度图只展示完整月份，缺失值不当作零。</p><p>时间线只展示有日期的事件。书介、原文划线、个人笔记和全书书评分别呈现。</p><p>字体优先使用本机Noto Serif SC／Noto Sans SC，无该字体时使用系统中文字体。文件不依赖在线字体或CDN。</p>`;$('#sourcesDialog').showModal();};

  async function copyText(text){try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text);}else{const t=document.createElement('textarea');t.value=text;document.body.append(t);t.select();if(!document.execCommand('copy'))throw Error('clipboard');t.remove();}toast('已复制');}catch{toast('复制失败，可选中文字后手动复制');}}
  function drawQuote(){if(!highlights.length){$('#quote').innerHTML='<p class="empty">暂无已载入的划线。</p>';$('#quotePosition').textContent='0／0';$('#previousQuote').disabled=$('#nextQuote').disabled=true;return;}
    const n=highlights[state.quote];$('#quotePosition').textContent=`${state.quote+1}／${highlights.length}`;
    $('#previousQuote').disabled=state.quote===0;$('#nextQuote').disabled=state.quote===highlights.length-1;
    $('#quote').innerHTML=`<div class="quote-body"><blockquote>${esc(n.text)}</blockquote><p class="attribution">—《${esc(n.book.title)}》</p><div class="quote-actions"><button id="copyQuote" class="text-button">复制</button><button id="shareQuote" class="text-button">加入分享</button></div></div>`;
    $('#copyQuote').onclick=()=>copyText(n.text);$('#shareQuote').onclick=()=>addBookShare(n.book.book_id,n.text);
  }drawQuote();$('#previousQuote').onclick=()=>{state.quote--;drawQuote();};$('#nextQuote').onclick=()=>{state.quote++;drawQuote();};

  const pages=[{id:'cover',title:'封面',kind:'cover'},{id:'stats',title:'阅读统计',kind:'stats'}];
  if(data.books.length)pages.push({id:'distribution',title:'阅读分布',kind:'distribution'});
  if(events.length)pages.push({id:'timeline',title:'阅读时间线',kind:'timeline'});
  data.books.filter(b=>b.selected).forEach(b=>pages.push({id:'book-'+b.book_id,title:b.title,kind:'book',book:b,quote:b.highlights[0]?.text||''}));
  state.selection=new Set(pages.filter(p=>p.id==='cover'||p.id==='stats'||p.kind==='book').map(p=>p.id));
  function recordUndo(){state.undo.push({ids:[...state.selection],preview:state.preview,quotes:pages.filter(p=>p.kind==='book').map(p=>[p.id,p.quote])});if(state.undo.length>10)state.undo.shift();}
  function addBookShare(id,quote){if(state.busy){toast('导出中，请稍后再调整');return;}const b=bookMap.get(id);if(!b)return;recordUndo();let p=pages.find(p=>p.id==='book-'+id);if(!p){p={id:'book-'+id,title:b.title,kind:'book',book:b,quote:quote||b.highlights[0]?.text||''};pages.push(p);}if(quote!==undefined)p.quote=quote;state.selection.add(p.id);state.preview=p.id;drawShare();toast('已加入分享');}
  function drawShare(){ $('#sharePages').innerHTML=pages.map(p=>`<div class="share-page"><label><input type="checkbox" data-page="${esc(p.id)}" ${state.selection.has(p.id)?'checked':''} ${state.busy?'disabled':''}><span>${esc(p.title)}</span></label><button data-preview="${esc(p.id)}" aria-pressed="${state.preview===p.id}">预览</button></div>`).join('');
    $('#selectedCount').textContent=`已选${state.selection.size}页`;$('#undoSelection').disabled=!state.undo.length||state.busy;$('#exportGroup').disabled=!state.selection.size||state.busy;$('#exportOne').disabled=state.busy;
    $$('[data-page]').forEach(el=>el.onchange=()=>{if(state.busy)return;recordUndo();el.checked?state.selection.add(el.dataset.page):state.selection.delete(el.dataset.page);drawShare();});
    $$('[data-preview]').forEach(el=>el.onclick=()=>{if(state.busy)return;state.preview=el.dataset.preview;drawShare();});updatePreview();
  }
  $('#undoSelection').onclick=()=>{const old=state.undo.pop();if(!old||state.busy)return;state.selection=new Set(old.ids);state.preview=old.preview;for(const [id,q]of old.quotes){const p=pages.find(p=>p.id===id);if(p)p.quote=q;}drawShare();};
  $('#ratio').onchange=()=>{if(state.busy)return;state.ratio=$('#ratio').value;updatePreview();};
  function dimensions(ratio){return [900,ratio==='1:1'?900:ratio==='4:5'?1125:1200];}
  const images=new Map();
  function loadImage(src){if(!images.has(src))images.set(src,new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('书封加载失败'));im.src=src;}));return images.get(src);}
  function wrap(ctx,text,x,y,width,lineHeight,maxLines=20){let line='',lines=[];for(const ch of String(text)){if(ch==='\n'){lines.push(line);line='';continue;}if(ctx.measureText(line+ch).width>width&&line){lines.push(line);line=ch;}else line+=ch;}if(line)lines.push(line);const cut=lines.length>maxLines;lines=lines.slice(0,maxLines);if(cut){let last=lines.at(-1)||'';while(ctx.measureText(last+'…').width>width)last=last.slice(0,-1);lines[lines.length-1]=last+'…';}lines.forEach((l,i)=>ctx.fillText(l,x,y+i*lineHeight));return y+lines.length*lineHeight;}
  async function canvasPage(p,ratio){
    await document.fonts.ready;const [W,H]=dimensions(ratio),cv=document.createElement('canvas');cv.width=W;cv.height=H;const c=cv.getContext('2d');if(!c)throw Error('浏览器不支持Canvas');
    const red='#ad3736',ink='#272723',muted='#696962',blue='#54768a',paper='#faf8f2';c.fillStyle=paper;c.fillRect(0,0,W,H);c.strokeStyle='#c8a87a';c.lineWidth=1;c.strokeRect(20,20,W-40,H-40);
    c.fillStyle=ink;c.font=`600 27px ${serif}`;c.fillText('年年阅',65,80);c.fillStyle=muted;c.font=`18px ReadingSans, sans-serif`;c.textAlign='right';c.fillText(`${data.year}${data.source_mode==='sample'?' · 示例':''}`,W-65,80);c.textAlign='left';
    c.font=`600 42px ${serif}`;c.fillStyle=ink;let y=wrap(c,p.kind==='cover'?'我的阅读年鉴':p.title,65,175,W-130,58,p.kind==='book'?3:2);
    c.strokeStyle='#d5d3ca';c.beginPath();c.moveTo(65,y+12);c.lineTo(W-65,y+12);c.stroke();y+=75;
    if(p.kind==='cover'){
      c.fillStyle=blue;c.font='italic 34px Georgia';c.fillText('Reading, at my own pace.',65,y);y+=95;
      c.fillStyle=red;c.font=`600 75px ${serif}`;c.fillText(String(data.summary.read),65,y);c.font=`26px ${serif}`;c.fillStyle=ink;c.fillText('本读过',195,y);y+=65;c.font=`26px ${serif}`;c.fillText(duration(data.summary.seconds),65,y);y+=60;
      const covers=data.books.filter(b=>b.selected).slice(0,4);const gap=20,cw=(W-130-gap*3)/4,ch=Math.min(220,H-y-140);
      for(let i=0;i<covers.length;i++){const b=covers[i],x=65+i*(cw+gap);if(b.cover){const im=await loadImage(b.cover);const scale=Math.min(cw/im.width,ch/im.height);c.drawImage(im,x,y+ch-im.height*scale,im.width*scale,im.height*scale);}else{c.fillStyle='#e6e3d8';c.fillRect(x,y,cw,ch);c.fillStyle=ink;c.font=`19px ${serif}`;wrap(c,b.title,x+12,y+32,cw-24,28,Math.max(1,Math.floor((ch-40)/28)));}}
    } else if(p.kind==='stats'){
      c.fillStyle=red;c.font=`500 49px ${serif}`;c.fillText(duration(data.summary.seconds),65,y);y+=62;c.fillStyle=muted;c.font='22px ReadingSans, sans-serif';c.fillText(`${value(data.summary.read)}本读过  ·  ${value(data.summary.finished)}本读完`,65,y);y+=45;c.fillText(`${value(data.summary.read_days)}天阅读  ·  ${value(data.summary.notes)}条笔记`,65,y);y+=65;
      const vals=data.summary.monthly.slice(0,data.summary.complete_months),top=Math.ceil(Math.max(...vals.filter(x=>x!=null).map(x=>x/3600),1)/2)*2,base=H-180,upper=y,left=100,right=W-75;
      for(const t of [0,top/2,top]){const yy=base-t/top*(base-upper);c.strokeStyle='#d5d3ca';c.beginPath();c.moveTo(left,yy);c.lineTo(right,yy);c.stroke();c.fillStyle=muted;c.font='18px ReadingSans, sans-serif';c.fillText(String(t),65,yy+5);}
      c.fillText('小时',65,upper-22);let active=false;c.strokeStyle=red;c.beginPath();vals.forEach((v,i)=>{if(v==null){active=false;return;}const x=vals.length===1?(left+right)/2:left+i*(right-left)/(vals.length-1),yy=base-v/3600/top*(base-upper);active?c.lineTo(x,yy):c.moveTo(x,yy);active=true;});c.lineWidth=2;c.stroke();
      vals.forEach((v,i)=>{const x=vals.length===1?(left+right)/2:left+i*(right-left)/(vals.length-1);c.fillStyle=muted;c.font='17px ReadingSans, sans-serif';c.textAlign='center';c.fillText(`${i+1}月`,x,base+32);if(v!=null){c.fillStyle=red;c.beginPath();c.arc(x,base-v/3600/top*(base-upper),4,0,2*Math.PI);c.fill();}});c.textAlign='left';
    } else if(p.kind==='distribution'){
      c.fillStyle=muted;c.font='21px ReadingSans, sans-serif';c.fillText(scope,65,y);y+=65;const rows=categoryCounts.slice(0,8);for(const [i,row]of rows.entries()){c.fillStyle=ink;c.font=`25px ${serif}`;wrap(c,row.name,65,y,290,35,2);c.fillStyle=categoryPalette[i%4];c.fillRect(365,y-22,row.count/Math.max(data.books.length,1)*360,12);c.fillStyle=muted;c.font='22px ReadingSans, sans-serif';c.fillText(`${row.count}本`,755,y);y+=Math.min(80,(H-y-100)/(rows.length-i));}if(categoryCounts.length>8){c.fillStyle=muted;c.fillText('更多分类见HTML年鉴',65,H-125);}
    } else if(p.kind==='timeline'){
      c.fillStyle=muted;c.font='21px ReadingSans, sans-serif';c.fillText('有日期的阅读与笔记记录',65,y);y+=65;
      const visible=events.slice(0,Math.max(1,Math.min(6,Math.floor((H-y-100)/115))));for(const e of visible){c.fillStyle=blue;c.beginPath();c.arc(75,y-8,5,0,2*Math.PI);c.fill();c.fillStyle=muted;c.font='20px ReadingSans, sans-serif';c.fillText(e.date.slice(5).replace('-','.'),105,y);c.fillStyle=ink;c.font=`24px ${serif}`;wrap(c,e.book.title,225,y,W-300,34,2);c.fillStyle=muted;c.font='18px ReadingSans, sans-serif';c.fillText(e.type,225,y+65);y+=115;}if(events.length>visible.length)c.fillText('更多记录见HTML年鉴',65,H-100);
    } else {
      const b=p.book;c.fillStyle=muted;c.font='21px ReadingSans, sans-serif';y=wrap(c,b.author,65,y,W-130,32,2)+25;
      const ch=Math.min(300,H*.26);if(b.cover){const im=await loadImage(b.cover);const sc=Math.min(220/im.width,ch/im.height);c.drawImage(im,65,y,im.width*sc,im.height*sc);}else{c.fillStyle='#e6e3d8';c.fillRect(65,y,190,ch);c.fillStyle=ink;c.font=`22px ${serif}`;wrap(c,b.title,82,y+38,155,33,5);}c.fillStyle=blue;c.font=`22px ${serif}`;wrap(c,b.category,330,y+40,W-395,36,3);c.fillStyle=muted;c.font='20px ReadingSans, sans-serif';c.fillText(statusLabel(b),330,y+160);y+=ch+65;
      c.fillStyle=red;c.font='45px Georgia';c.fillText('“',65,y);c.fillStyle=ink;c.font=`27px ${serif}`;wrap(c,p.quote||'这本书暂未载入划线。',100,y,W-165,44,Math.max(1,Math.floor((H-y-100)/44)));
    }
    c.fillStyle=muted;c.font='16px ReadingSans, sans-serif';c.fillText(data.as_of?`${data.year} · 数据采集于${data.as_of}`:String(data.year),65,H-55);c.textAlign='right';c.fillText(p.kind==='book'?'原文摘录':'阅读年鉴',W-65,H-55);return cv;
  }
  async function updatePreview(){const token=++renderToken,p=pages.find(p=>p.id===state.preview)||pages[0];try{const cv=await canvasPage(p,state.ratio);if(token!==renderToken)return;const target=$('#previewCanvas');target.width=cv.width;target.height=cv.height;target.getContext('2d').drawImage(cv,0,0);$('#previewTitle').textContent=p.title;}catch(e){if(token===renderToken){$('#previewTitle').textContent='预览失败：'+e.message;}}}
  const blobCanvas = cv=>new Promise((resolve,reject)=>cv.toBlob(b=>b?resolve(b):reject(Error('无法生成PNG')),'image/png'));
  function download(blob,name){const link=document.createElement('a'),url=URL.createObjectURL(blob);link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);}
  const filename = p => `${data.year}-${String(pages.indexOf(p)+1).padStart(2,'0')}-${p.id.replace(/[^a-zA-Z0-9_-]/g,'-').slice(0,80)||'page'}.png`;
  async function runExport(task){if(state.busy)return;state.busy=true;$('#ratio').disabled=true;drawShare();$('#exportStatus').textContent='正在准备字体、书封与分享画布…';try{await task();$('#exportStatus').textContent='下载已发起，请查看浏览器下载记录。';}catch(e){$('#exportStatus').textContent='导出失败：'+e.message+'。已保留选择，可以重试。';}finally{state.busy=false;$('#ratio').disabled=false;drawShare();}}
  $('#exportOne').onclick=()=>runExport(async()=>{const p=pages.find(p=>p.id===state.preview);const cv=await canvasPage(p,state.ratio);download(await blobCanvas(cv),filename(p));});
  // Dependency-free stored ZIP. CRC32 + UTF8 filenames; tested against Python zipfile.
  function crc32(bytes){let c=0xffffffff;for(const b of bytes){c^=b;for(let i=0;i<8;i++)c=(c>>>1)^((c&1)?0xedb88320:0);}return(c^0xffffffff)>>>0;}
  async function zip(files){const enc=new TextEncoder(),chunks=[],central=[];let offset=0;const u16=(view,pos,v)=>view.setUint16(pos,v,true),u32=(view,pos,v)=>view.setUint32(pos,v,true);
    for(const f of files){const name=enc.encode(f.name),bytes=new Uint8Array(await f.blob.arrayBuffer()),crc=crc32(bytes),local=new Uint8Array(30+name.length),l=new DataView(local.buffer);u32(l,0,0x04034b50);u16(l,4,20);u16(l,6,0x800);u32(l,14,crc);u32(l,18,bytes.length);u32(l,22,bytes.length);u16(l,26,name.length);local.set(name,30);chunks.push(local,bytes);
      const entry=new Uint8Array(46+name.length),v=new DataView(entry.buffer);u32(v,0,0x02014b50);u16(v,4,20);u16(v,6,20);u16(v,8,0x800);u32(v,16,crc);u32(v,20,bytes.length);u32(v,24,bytes.length);u16(v,28,name.length);u32(v,42,offset);entry.set(name,46);central.push(entry);offset+=local.length+bytes.length;}
    const size=central.reduce((n,x)=>n+x.length,0),end=new Uint8Array(22),v=new DataView(end.buffer);u32(v,0,0x06054b50);u16(v,8,files.length);u16(v,10,files.length);u32(v,12,size);u32(v,16,offset);return new Blob([...chunks,...central,end],{type:'application/zip'});
  }
  $('#exportGroup').onclick=()=>runExport(async()=>{const chosen=pages.filter(p=>state.selection.has(p.id)),ratio=state.ratio,files=[];for(const [i,p] of chosen.entries()){$('#exportStatus').textContent=`正在生成第${i+1}／${chosen.length}页…`;files.push({name:filename(p),blob:await blobCanvas(await canvasPage(p,ratio))});}download(await zip(files),`${data.year}-reading-share.zip`);});
  function markdown(){const lines=[`# ${data.year}阅读年鉴`,'',`范围：${scope}${data.as_of?'；采集日期：'+data.as_of:''}`,'',`阅读时长：${duration(data.summary.seconds)}`,`读过：${value(data.summary.read)}本；读完：${value(data.summary.finished)}本`,''];for(const b of data.books){lines.push(`## ${b.title}`,'',`作者：${b.author}`,'','### 全书书评','',b.review.status==='verified'?b.review.body:'尚未取得并核验完整正文。','');if(b.review.status==='verified')lines.push(`正文来源：${b.review.source}`,`版本：${b.review.version}`,`章节依据：${b.review.citations.join('；')}`,'');for(const [title,rows] of [['划线',b.highlights],['个人笔记',b.thoughts]]){lines.push(`### ${title}`,'');for(const n of rows)lines.push(n.text,'',`来源：${b.title} · ${n.created_at||'日期未记录'} · ${n.source_id||'未记录来源ID'}`,'');if(!rows.length)lines.push('尚未载入。','');}}return lines.join('\n');}
  $('#exportMd').onclick=()=>download(new Blob([markdown()],{type:'text/markdown;charset=utf-8'}),`${data.year}-reading.md`);
  $('#exportJson').onclick=()=>{const copy=JSON.parse(JSON.stringify(data));copy.books.forEach(b=>delete b.cover);download(new Blob([JSON.stringify(copy,null,2)],{type:'application/json;charset=utf-8'}),`${data.year}-reading.json`);};
  $('#exportPdf').onclick=()=>{if(state.query||state.category||state.status!=='all')toast('PDF将使用当前筛选的书架范围');window.print();};
  addEventListener('beforeprint',()=>{drawBooks(true);$$('#timeline details').forEach(el=>{el.dataset.wasOpen=String(el.open);el.open=true;});$('#printDetails').innerHTML=visibleBooks().map(b=>`<article><h2>${esc(b.title)}</h2><p>${esc(b.author)}</p><h3>全书书评</h3><p>${esc(b.review.status==='verified'?b.review.body:'尚未取得并核验完整正文。')}</p>${b.review.status==='verified'?`<p class="review-source">来源：${esc(b.review.source)}；版本：${esc(b.review.version)}；章节依据：${esc(b.review.citations.join('；'))}</p>`:''}<h3>划线</h3>${b.highlights.map(n=>`<div class="detail-note">${esc(n.text)}<small>${esc(n.created_at||'日期未记录')}</small></div>`).join('')||'<p>尚未载入。</p>'}<h3>个人笔记</h3>${b.thoughts.map(n=>`<div class="detail-note">${esc(n.text)}<small>${esc(n.created_at||'日期未记录')}</small></div>`).join('')||'<p>尚未载入。</p>'}</article>`).join('');});
  addEventListener('afterprint',()=>{$('#printDetails').replaceChildren();$$('#timeline details').forEach(el=>el.open=el.dataset.wasOpen==='true');drawBooks();});
  // Keep chapter indicator aligned to the currently visible section.
  if('IntersectionObserver'in window){const observer=new IntersectionObserver(entries=>{const active=entries.filter(e=>e.isIntersecting).sort((a,b)=>a.boundingClientRect.top-b.boundingClientRect.top)[0];if(active){$$('nav a').forEach(a=>a.getAttribute('href')==='#'+active.target.id?a.setAttribute('aria-current','location'):a.removeAttribute('aria-current'));}},{rootMargin:'-15% 0px -60% 0px'});['overview','shelf','quotes','share'].forEach(id=>observer.observe($('#'+id)));}
  drawShare();
})();
