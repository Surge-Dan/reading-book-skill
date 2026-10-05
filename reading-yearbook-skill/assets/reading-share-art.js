/* Editorial share artwork. Data-driven layouts; no external requests.
 * Chart encodings reuse the yearbook's lieflat line / rung / tick vocabulary.
 * Each canvas carries a local layout manifest for export regression checks. */
window.ReadingShareArtwork = (() => {
  'use strict';
  const C={paper:'#f7f2e5',ink:'#242822',muted:'#686c61',red:'#b84432',blue:'#305c78',gold:'#cba74e',green:'#607765',line:'#c9c4b3',cream:'#eee6d2'};
  const SERIF='ReadingSerif,"Noto Serif SC","Songti SC",SimSun,serif';
  const SANS='ReadingSans,"Noto Sans SC","Microsoft YaHei",sans-serif';
  const NUM='Georgia,"Noto Serif",serif';
  const palette=[C.blue,C.red,C.green,C.gold,'#97768b','#7a8875','#bd8261'];
  const known=n=>typeof n==='number'&&Number.isFinite(n);
  const amount=n=>known(n)?String(n):'—';
  const duration=n=>!known(n)?'未记录':n>=3600?`${Math.floor(n/3600)}小时${Math.floor(n%3600/60)}分钟`:`${Math.floor(n/60)}分钟`;
  const status=b=>b.progress==null?'进度未记录':b.progress>=100?'已读完':'在读';
  function create({data,art,loadImage}){
    const fonts=Promise.all([document.fonts.load('800 48px ReadingSerif'),document.fonts.load('400 32px ReadingSerif'),document.fonts.load('400 28px ReadingSans')]);
    const categories=new Map();for(const b of data.books)categories.set(b.category,(categories.get(b.category)||0)+1);
    const counts=[...categories].map(([name,count])=>({name,count})).sort((a,b)=>b.count-a.count||a.name.localeCompare(b.name,'zh'));
    const colors=new Map(counts.map((r,i)=>[r.name,palette[i%palette.length]]));
    const bookAccents=new Map(),bookColor=b=>bookAccents.get(b.book_id)||colors.get(b.category)||C.blue;
    async function coverAccent(b){
      if(!b.cover||bookAccents.has(b.book_id))return;
      const im=await loadImage(b.cover),cv=document.createElement('canvas');cv.width=cv.height=24;const c=cv.getContext('2d');c.drawImage(im,0,0,24,24);
      // Quantize colored cover pixels into legible ink hues. White / neutral paper
      // has no vote, and category-chart colors keep their own stable semantics.
      const inks=[C.red,C.blue,C.green,'#8a6825','#79596d','#675b40'],rgb=inks.map(h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16))),votes=inks.map(()=>0),pixels=c.getImageData(0,0,24,24).data;
      for(let i=0;i<pixels.length;i+=4){const p=[pixels[i],pixels[i+1],pixels[i+2]],sat=Math.max(...p)-Math.min(...p);if(pixels[i+3]<180||sat<35||Math.min(...p)>210)continue;let best=0,dist=Infinity;rgb.forEach((r,k)=>{const v=r.reduce((s,a,j)=>s+(a-p[j])**2,0);if(v<dist){best=k;dist=v;}});votes[best]+=sat;}
      if(Math.max(...votes)>0)bookAccents.set(b.book_id,inks[votes.indexOf(Math.max(...votes))]);
    }
    const events=[],seenEvents=new Set();for(const b of data.books){
      if(b.start_date?.startsWith(String(data.year)))events.push({date:b.start_date.slice(0,10),type:'开始阅读',book:b});
      if(b.finish_date?.startsWith(String(data.year)))events.push({date:b.finish_date.slice(0,10),type:'读完',book:b});
      for(const [kind,rows]of [['划线',b.highlights],['笔记',b.thoughts]])for(const n of rows)if(n.created_at?.startsWith(String(data.year))){const key=`${b.book_id}|${kind}|${n.source_id||n.text+'|'+n.created_at}`;if(!seenEvents.has(key)){seenEvents.add(key);events.push({date:n.created_at.slice(0,10),type:kind,book:b});}}
    }
    events.sort((a,b)=>a.date.localeCompare(b.date)||a.book.book_id.localeCompare(b.book.book_id));
    const months=data.summary.monthly.slice(0,data.summary.complete_months);
    function drawing(cv,p){
      const ctx=cv.getContext('2d'),W=cv.width,H=cv.height,M=56,R=W-M;
      const manifest={version:'editorial-1',page:p.id,width:W,height:H,text:[],charts:[],images:[]};cv.readingLayout=manifest;
      function text(str,x,y,{size=30,weight=400,font=SERIF,color=C.ink,align='left',italic=false}={}){
        ctx.font=`${italic?'italic ':''}${weight} ${size}px ${font}`;ctx.fillStyle=color;ctx.textAlign=align;
        ctx.fillText(String(str),x,y);const metric=ctx.measureText(String(str)),w=metric.width;
        manifest.text.push({text:String(str),x:align==='right'?x-w:align==='center'?x-w/2:x,y:y-(metric.actualBoundingBoxAscent||size),w,h:(metric.actualBoundingBoxAscent||size)+(metric.actualBoundingBoxDescent||0),size});ctx.textAlign='left';
      }
      function lines(str,width,style){
        ctx.font=`${style.weight||400} ${style.size||30}px ${style.font||SERIF}`;const out=[];let line='';
        for(const ch of String(str).replace(/\r/g,'')){
          if(ch==='\n'){out.push(line);line='';continue;}
          if(ctx.measureText(line+ch).width>width&&line){
            if(/[，。！？；：、）》】”’]/.test(ch)){out.push(line+ch);line='';}
            else if(/[（《【“‘]$/.test(line)){out.push(line.slice(0,-1));line=line.slice(-1)+ch;}
            else{out.push(line);line=ch;}
          }else line+=ch;
        }if(line)out.push(line);return out;
      }
      function block(str,x,y,w,h,{size=36,min=32,weight=400,font=SERIF,color=C.ink,leading=1.5}={}){
        let ls=[];while(size>=min){ls=lines(str,w-8,{size,weight,font});if(ls.length*size*leading<=h)break;if(size===min)break;size=Math.max(min,size-2);}
        const step=size*leading,max=Math.max(1,Math.floor(h/step)),cut=ls.length>max;ls=ls.slice(0,max);
        if(cut){let last=ls.at(-1);ctx.font=`${weight} ${size}px ${font}`;while(last&&ctx.measureText(last+'…').width>w-8)last=last.slice(0,-1);ls[ls.length-1]=last+'…';}
        ls.forEach((s,i)=>text(s,x,y+size+i*step,{size,weight,font,color}));return {bottom:y+ls.length*step,lines:ls.length,cut};
      }
      function rect(x,y,w,h,fill,stroke){ctx.fillStyle=fill;ctx.fillRect(x,y,w,h);if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=1;ctx.strokeRect(x,y,w,h);}}
      function line(x1,y1,x2,y2,color=C.line,width=1){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();}
      function dot(x,y,r,color){ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();}
      function section(label,x,y,w,no){line(x,y-12,x+w,y-12);text(no||'',x,y+22,{font:NUM,size:27,color:C.red,italic:true});text(label,x+(no?45:0),y+22,{size:27,weight:600,font:SANS});return y+48;}
      function scribble(x,y,w,color=C.red){ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();for(let i=0;i<=30;i++){const xx=x+w*i/30,yy=y+Math.sin(i*.85)*1.5+i*.05;i?ctx.lineTo(xx,yy):ctx.moveTo(xx,yy);}ctx.stroke();}
      function star(x,y,r,color=C.gold){for(let i=0;i<4;i++){const a=i*Math.PI/4;line(x-Math.cos(a)*r,y-Math.sin(a)*r,x+Math.cos(a)*r,y+Math.sin(a)*r,color,1.5);}}
      async function image(src,x,y,w,h,{angle=0,shadow=false,fit='contain'}={}){
        const im=await loadImage(src),s=fit==='contain'?Math.min(w/im.width,h/im.height):Math.max(w/im.width,h/im.height),iw=im.width*s,ih=im.height*s;
        ctx.save();ctx.translate(x+w/2,y+h/2);ctx.rotate(angle*Math.PI/180);if(shadow){ctx.shadowColor='#31312630';ctx.shadowBlur=16;ctx.shadowOffsetX=5;ctx.shadowOffsetY=10;}
        if(fit==='cover'){ctx.beginPath();ctx.rect(-w/2,-h/2,w,h);ctx.clip();}ctx.drawImage(im,-iw/2,-ih/2,iw,ih);ctx.restore();manifest.images.push({x,y,w,h,angle});
      }
      async function cover(b,x,y,w,h,opts={}){if(b.cover)await image(b.cover,x,y,w,h,opts);else{rect(x,y,w,h,C.cream);block(b.title,x+18,y+22,w-36,h-44,{size:34,min:28,weight:600});}}
      function metric(n,label,x,y,w,{size=64,color=C.ink}={}){
        const s=amount(n);let fs=size;ctx.font=`400 ${fs}px ${NUM}`;while(ctx.measureText(s).width>w&&fs>32){fs-=2;ctx.font=`400 ${fs}px ${NUM}`;}
        text(s,x,y,{size:fs,font:NUM,color});text(label,x,y+44,{size:26,font:SANS,color:C.muted});
      }
      function progress(b,x,y,w){
        if(!known(b.progress))return;const v=Math.max(0,Math.min(100,b.progress));text('当前进度',x,y,{size:26,font:SANS,color:C.muted});text(`${v}%`,x+w,y,{size:30,font:NUM,align:'right',color:bookColor(b)});
        rect(x,y+18,w,8,C.cream);rect(x,y+18,w*v/100,8,bookColor(b));manifest.charts.push({kind:'progress',value:v,width:w*v/100,totalWidth:w});
      }
      function trend(x,y,w,h,{small=false}={}){
        const vals=months,valid=vals.map((v,i)=>({v,i})).filter(r=>known(r.v));
        if(!valid.length){block('暂无月度阅读时长记录。',x,y+35,w,h,{size:32,min:30,color:C.muted});return;}
        const top=Math.ceil(Math.max(...valid.map(r=>r.v/3600),1)/2)*2,left=x+(small?8:42),right=x+w-16,base=y+h-44,upper=y+26;
        if(!small)for(const v of [0,top/2,top]){const yy=base-v/top*(base-upper);line(left,yy,right,yy);text(String(v),x,yy+8,{size:25,font:NUM,color:C.muted});}
        const points=vals.map((v,i)=>known(v)?{value:v,month:i+1,x:vals.length===1?(left+right)/2:left+i*(right-left)/(vals.length-1),y:base-v/3600/top*(base-upper)}:null);
        ctx.strokeStyle=C.red;ctx.lineWidth=small?2:3;ctx.beginPath();let active=false;for(const pt of points){if(!pt){active=false;continue;}active?ctx.lineTo(pt.x,pt.y):ctx.moveTo(pt.x,pt.y);active=true;}ctx.stroke();
        const peak=valid.reduce((a,b)=>b.v>a.v?b:a);for(const pt of points)if(pt)dot(pt.x,pt.y,small?3:5,pt.month===peak.i+1?C.blue:C.red);
        if(!small){for(let i=0;i<vals.length;i++){const xx=vals.length===1?(left+right)/2:left+i*(right-left)/(vals.length-1);if(vals.length<=9||i%2===0||i===vals.length-1)text(`${i+1}月`,xx,base+35,{size:25,font:SANS,color:C.muted,align:'center'});}text('小时',x,y+5,{size:23,font:SANS,color:C.muted});}
        manifest.charts.push({kind:'monthly',points,top,base,upper});
      }
      function tickRow(v,max,x,y,w,color=C.blue){
        const n=32,unit=max/n;for(let k=0;k<n;k++)line(x+k*w/n,y,x+k*w/n,y-13,C.line,1);
        if(unit>0)for(let k=0;k<Math.ceil(v/unit);k++)line(x+k*w/n,y,x+k*w/n,y-13*Math.min(1,(v-k*unit)/unit),color,3);
        manifest.charts.push({kind:'ticks',value:v,max,unit});
      }
      function base(){
        rect(0,0,W,H,C.paper);for(const [x,y,color]of [[W,0,'#e0bf65'],[0,H,'#90b5c7'],[W,H*.7,'#dda18e']]){const g=ctx.createRadialGradient(x,y,0,x,y,420);g.addColorStop(0,color+'38');g.addColorStop(1,color+'00');ctx.fillStyle=g;ctx.fillRect(0,0,W,H);}
        let seed=281;ctx.fillStyle='#635237';ctx.globalAlpha=.045;for(let i=0;i<3600;i++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;const x=seed%W;seed=(Math.imul(seed,1664525)+1013904223)>>>0;ctx.fillRect(x,seed%H,1,1);}ctx.globalAlpha=1;
        ctx.strokeStyle=C.line;ctx.lineWidth=1;ctx.strokeRect(22,22,W-44,H-44);text('年年阅',M,72,{size:30,weight:750});
        const labels={cover:'阅读年鉴',stats:'阅读的节奏',distribution:'阅读分布',timeline:'阅读时间线',book:'书页之间'};
        text(labels[p.kind],W/2,71,{font:SANS,size:24,align:'center',color:C.muted});text(`${data.year}${data.source_mode==='sample'?' · 示例':''}`,R,72,{font:NUM,size:27,align:'right'});line(M,95,R,95);
        const idx=p.kind==='book'?5+data.books.findIndex(b=>b.book_id===p.book.book_id):['cover','stats','distribution','timeline'].indexOf(p.kind)+1;
        text(`${String(idx).padStart(2,'0')} / ${String(4+data.books.length).padStart(2,'0')}`,M,H-44,{font:NUM,size:24,color:C.muted});
        text(p.kind==='book'?(p.quote?(p.textKind==='thought'?'个人笔记与阅读记录':'原文摘录与阅读记录'):'阅读记录'):'我的阅读年鉴',R,H-44,{size:23,font:SANS,align:'right',color:C.muted});
      }
      return {ctx,W,H,M,R,text,block,rect,line,dot,section,scribble,star,image,cover,metric,progress,trend,tickRow,base,manifest};
    }
    async function render(p,ratio){
      await fonts;await document.fonts.ready;const cv=document.createElement('canvas');cv.width=900;cv.height=ratio==='1:1'?900:ratio==='4:5'?1125:1200;
      const D=drawing(cv,p);if(!D.ctx)throw Error('浏览器不支持Canvas');D.base();
      if(p.kind==='cover')await coverPage(D);
      else if(p.kind==='stats')await statsPage(D);
      else if(p.kind==='distribution')await distributionPage(D);
      else if(p.kind==='timeline')await timelinePage(D);
      else{await coverAccent(p.book);await bookPage(D,p);}
      return cv;
    }
    async function coverPage(d){
      const {H,M,R,text,block,rect,line,image,cover,metric,trend,star}=d,square=H===900;
      text(String(data.year),M,250,{font:NUM,size:155,color:C.red,italic:true});
      await image(art.reading,566,123,267,145);
      text('这一年，',M,square?316:342,{size:65,weight:750});text('读了这些书',M,square?399:432,{size:80,weight:800});
      d.scribble(M, square?416:453,362,C.blue);star(798,342,18);
      const shelfTop=square?446:494,shelfHeight=square?226:H-865;
      const chosen=[...data.books.filter(b=>b.selected),...data.books.filter(b=>!b.selected)].slice(0,Math.min(5,data.books.length));
      rect(M,shelfTop+22,R-M,shelfHeight-8,'#d9dfd266');
      if(chosen.length){const cw=chosen.length<=2?190:Math.min(183,(R-M-30)/(chosen.length*.78+.22)),gap=cw*.78,total=cw+(chosen.length-1)*gap,left=(900-total)/2;
        for(const [i,b]of chosen.entries()){const yy=shelfTop+(i%2?24:0),angle=[-7,4,-3,6,-4][i];await cover(b,left+i*gap,yy,cw,shelfHeight-30,{angle,shadow:true});}
      }else{await image(art.hero,180,shelfTop-5,530,shelfHeight);block(data.coverage.complete?'这一年，还没有读书记录。':'阅读记录尚未取得。',M,shelfTop+shelfHeight-35,R-M,50,{size:30,min:28,color:C.muted});}
      line(M,shelfTop+shelfHeight+12,R,shelfTop+shelfHeight+12,C.ink,1);
      const my=square?748:H-256,w=(R-M)/4;
      for(const [i,[v,label]]of [[data.summary.read,'本读过'],[data.summary.finished,'本读完'],[data.summary.read_days,'天阅读'],[data.summary.notes,'条笔记']].entries())metric(v,label,M+i*w,my,w-24,{size:square?57:70,color:i===0?C.red:C.ink});
      if(!square){text(duration(data.summary.seconds),M,H-135,{font:NUM,size:37,color:C.blue});text('阅读时长',M,H-97,{font:SANS,size:25,color:C.muted});trend(460,H-177,375,83,{small:true});}
    }
    async function statsPage(d){
      const {H,M,R,text,block,rect,line,metric,trend,section,tickRow}=d,square=H===900;
      text('今年，花在书上的时间',M,179,{size:62,weight:750});
      const total=data.summary.seconds;rect(M,211,R-M,138,'#e7deca70');
      if(known(total)){metric(Math.floor(total/3600),'小时',M+20,299,285,{size:92,color:C.red});metric(Math.floor(total%3600/60),'分钟',M+366,299,260,{size:79,color:C.blue});}else text('阅读时长未记录',M+22,300,{size:46,color:C.muted});
      const w=(R-M)/4;for(const [i,[v,label]]of [[data.summary.read,'本读过'],[data.summary.finished,'本读完'],[data.summary.read_days,'天阅读'],[data.summary.notes,'条笔记']].entries())metric(v,label,M+i*w,427,w-20,{size:55});
      const chartY=section('每月的阅读节奏',M,501,R-M,'01');trend(M,chartY+9,R-M,square?224:H-870);
      const valid=months.map((v,i)=>({v,i})).filter(r=>known(r.v));const bottom=square?813:H-245;
      if(valid.length){const peak=valid.reduce((a,b)=>b.v>a.v?b:a);text(`${peak.i+1}月读得最久`,M,bottom,{size:31,weight:650,color:C.blue});text(duration(peak.v),R,bottom,{size:30,font:SANS,align:'right'});}
      if(!square){const ranked=data.books.filter(b=>known(b.reading_seconds)&&b.reading_seconds>0).sort((a,b)=>b.reading_seconds-a.reading_seconds).slice(0,2);
        if(ranked.length){section('时间花在哪本书上',M,H-199,R-M,'02');const max=ranked[0].reading_seconds;for(const [i,b]of ranked.entries()){const y=H-139+i*51;block(b.title,M,y-27,365,42,{size:28,min:26,weight:600,leading:1.15});tickRow(b.reading_seconds,max,446,y,238,bookColor(b));text(duration(b.reading_seconds),R,y,{size:24,font:SANS,align:'right',color:C.muted});}}
        else{section('这一年的阅读记录',M,H-199,R-M,'02');block('每一本书，都在书架里留下了位置。',M,H-146,R-M,67,{size:34,min:32,color:C.muted});}}
    }
    async function distributionPage(d){
      const {H,M,R,text,block,rect,line,cover,section}=d,square=H===900;
      text('今年读得最多的是哪些',M,179,{size:60,weight:750});
      text(`${data.books.length}`,M,282,{font:NUM,size:88,color:C.red});text('本已载入书籍',M+157,274,{size:30,font:SANS,color:C.muted});text(`${counts.length}个分类`,R,275,{size:31,align:'right',font:SANS});
      if(!counts.length){block(data.coverage.complete?'这一年没有可统计的阅读书目。':'暂未取得书目，暂无法展示分类分布。',M,355,R-M,155,{size:38,min:34});await d.image(art.hero,170,520,540,H-610);return;}
      const limit=square?4:6,rows=counts.slice(0,counts.length>limit?limit-1:limit);if(counts.length>limit)rows.push({name:'其他分类',count:counts.slice(limit-1).reduce((s,r)=>s+r.count,0),other:true});
      const max=Math.max(...rows.map(r=>r.count)),unit=Math.max(1,Math.ceil(max/60));
      const y0=section(`分类书架 · 一档${unit===1?'一':unit}本`,M,331,R-M,'01'),bottom=square?650:H-340,rh=(bottom-y0)/rows.length;
      for(const [i,r]of rows.entries()){const y=y0+i*rh+13,color=colors.get(r.name)||C.green;block(r.name,M,y,185,rh-10,{size:32,min:27,weight:650});
        const x=270,w=450,step=w/max,marks=Math.ceil(r.count/unit);for(let k=0;k<marks;k++){const frac=Math.min(unit,r.count-k*unit)/unit;line(x+k*unit*step,y+43,x+k*unit*step+Math.max(1,step*unit-8)*frac,y+43,color,9);}
        text(String(r.count),R,y+40,{font:NUM,size:45,align:'right',color});d.manifest.charts.push({kind:'category',name:r.name,count:r.count,total:data.books.length,unit,marks});
      }
      const bottomY=square?710:H-272;section('从这些书，继续翻下去',M,bottomY,R-M,'02');const chosen=rows.filter(r=>!r.other).map(r=>data.books.find(b=>b.category===r.name)).slice(0,square?4:5),cw=92;
      for(const [i,b]of chosen.entries()){const x=M+i*(R-M)/chosen.length;await cover(b,x,bottomY+53,cw,square?90:110,{shadow:true});if(!square)block(b.title,x,bottomY+171,(R-M)/chosen.length-12,34,{size:25,min:24,leading:1.15});}
    }
    async function timelinePage(d){
      const {H,M,R,text,block,line,dot,cover,rect,section}=d,square=H===900;
      text('顺着这一年翻回去',M,179,{size:66,weight:750});text('有日期的阅读与笔记记录',M,230,{size:28,font:SANS,color:C.muted});
      if(!events.length){block('暂无带日期的阅读记录。',M,340,R-M,90,{size:39,min:34});await d.image(art.hero,135,445,630,H-560);return;}
      const buckets=new Map();for(const e of events){const k=e.date.slice(0,7);if(!buckets.has(k))buckets.set(k,[]);buckets.get(k).push(e);}
      const entries=[...buckets],limit=square?3:4,chosen=entries.length<=limit?entries:Array.from({length:limit},(_,i)=>entries[Math.round(i*(entries.length-1)/(limit-1))]);
      const by=H-164;section('月份里的书页',M,291,R-M,'01');const cy=350,rh=(by-cy)/chosen.length;line(194,cy+18,194,by-16,C.blue,2);
      for(const [i,[month,items]]of chosen.entries()){const y=cy+i*rh,representative=items.find(e=>e.type==='读完')||items.find(e=>e.type==='开始阅读')||items[0];
        text(month.slice(5)+'月',M,y+35,{font:NUM,size:43,color:C.blue});dot(194,y+23,7,C.red);rect(224,y-7,R-224,rh-15,i%2?'#dce3db66':'#e8dfcb66');
        await cover(representative.book,244,y+12,72,Math.min(105,rh-45),{shadow:false});block(representative.book.title,342,y+8,R-366,Math.min(91,rh-67),{size:32,min:28,weight:650,leading:1.28});text(`${representative.date.slice(5).replace('-','.')} · ${representative.type}`,342,y+Math.min(110,rh-39),{size:25,font:SANS,color:C.muted});text(`${items.length}条记录`,R-20,y+rh-31,{size:25,font:SANS,color:C.blue,align:'right'});
      }
      text(`展示${chosen.length}个有记录的月份，共${buckets.size}个月`,M,H-113,{size:26,font:SANS,color:C.muted});text(`${events.length}条日期记录`,R,H-113,{size:26,font:SANS,color:C.blue,align:'right'});
      d.manifest.charts.push({kind:'timeline',total:events.length,months:buckets.size,shown:chosen.map(([month,items])=>({month,count:items.length}))});
    }
    async function bookPage(d,p){
      const {H,M,R,text,block,rect,line,cover,section,progress,metric}=d,b=p.book,square=H===900,color=bookColor(b);
      const titleText=b.title.replace(/([：:])\s*/,'$1\n');
      const title=block(titleText,M,127,R-M,185,{size:67,min:46,weight:800,leading:1.23}),author=block(b.author,M,title.bottom+5,R-M,72,{size:28,min:26,font:SANS,color:C.muted,leading:1.25});
      const bodyY=Math.max(square?290:316,author.bottom+28),mainBottom=square?663:H-314,available=mainBottom-bodyY;
      const primary=p.quote||'',kind=p.textKind==='thought'?'个人笔记':'原文摘录';
      const rich=Boolean(primary),long=primary.length>110;
      const metricY=H-174;line(M,metricY-34,R,metricY-34,color,1.5);
      const hComplete=b.note_coverage?.highlights==='complete',tComplete=b.note_coverage?.thoughts==='complete';
      if(rich&&!long){
        rect(M,bodyY,R-M,available,'#e4e8df85');line(M,bodyY,M,bodyY+available,color,4);
        await cover(b,M+24,bodyY+26,220,Math.min(312,available-96),{angle:-4,shadow:true});
        const qx=M+290;section(kind,qx,bodyY+18,R-qx-24);text('“',qx-5,bodyY+127,{font:NUM,size:94,color});
        const q=block(primary,qx,bodyY+111,R-qx-27,Math.min(available-145,long?430:300),{size:42,min:36,leading:1.65});
        const secondary=b.thoughts.find(n=>n.text!==primary)||b.highlights.find(n=>n.text!==primary);
        const remaining=mainBottom-q.bottom-35;
        if(secondary&&remaining>=100){const sy=Math.max(q.bottom+24,bodyY+290);if(mainBottom-sy>=105){text(b.thoughts.includes(secondary)?'我的笔记':'另一处划线',qx,sy+20,{font:SANS,size:25,color});const s=block(secondary.text,qx,sy+36,R-qx-27,mainBottom-sy-51,{size:32,min:30,leading:1.45});
          const candidates=b.highlights.filter(n=>n.text!==primary&&n.text!==secondary.text),next=candidates.find(n=>n.text.length>=16&&n.text.length<=60)||candidates[0],ny=s.bottom+25;if(next&&mainBottom-ny>=123){text('另一处划线',qx,ny+20,{font:SANS,size:25,color});block(next.text,qx,ny+36,R-qx-27,mainBottom-ny-48,{size:32,min:30,leading:1.4});}}}
        if(!square&&available>450){section('书籍分类',M+22,mainBottom-137,225);block(b.category,M+22,mainBottom-93,220,70,{size:32,min:27,weight:600,color});}
      }else if(rich){
        await cover(b,R-145,bodyY-8,135,172,{angle:5,shadow:true});text(kind,M,bodyY+28,{font:SANS,size:27,color});
        rect(M,bodyY+61,56,4,color);block(primary,M,bodyY+85,R-M-180,available-92,{size:39,min:34,leading:1.6});
        if(!square){const sidebarX=R-151;block(b.category,sidebarX,bodyY+218,151,100,{size:30,min:26,weight:600,color});text('书页摘录',sidebarX,mainBottom-24,{size:24,font:SANS,color:C.muted});}
      }else if(b.intro){
        rect(M,bodyY,R-M,available,'#e0e5db70');const cw=260,ch=Math.min(390,available-68);await cover(b,M+24,bodyY+31,cw,ch,{angle:-5,shadow:true});
        const tx=M+330,tw=R-tx-25;section('内容简介',tx,bodyY+15,tw);block(b.intro,tx,bodyY+80,tw,available-160,{size:36,min:32,leading:1.55});
      }else{
        rect(M,bodyY,R-M,available,'#e0e5db70');await cover(b,M+42,bodyY+14,370,available-28,{angle:-4,shadow:true});
        const tx=M+455,tw=R-tx-24;
        if(known(b.progress)){rect(tx,bodyY+39,tw,135,'#e9dfc3');text('阅读状态',tx+15,bodyY+77,{size:26,font:SANS,color:C.muted});block(status(b),tx+15,bodyY+95,tw-30,65,{size:43,min:32,weight:650,color});}
        if(b.category&&b.category!=='未分类')block(b.category,tx,bodyY+212,tw,82,{size:36,min:30,color});
        if(available>=355)await d.image(art.hero,tx-15,mainBottom-210,tw+30,180);
      }
      const mx=M+295,mw=R-mx;
      const cols=[[known(b.reading_seconds)?`${Math.floor(b.reading_seconds/3600)}小时\n${Math.floor(b.reading_seconds%3600/60)}分钟`:null,'阅读时长'],[hComplete&&(rich||b.highlights.length)?String(b.highlights.length):null,'条划线'],[tComplete&&(rich||b.thoughts.length)?String(b.thoughts.length):null,'条个人笔记']].filter(([v])=>v!==null);
      if(known(b.progress))progress(b,M,metricY,cols.length?245:R-M);else if(cols.length)block(status(b),M,metricY-26,245,65,{size:30,min:28,color:C.muted});
      if(cols.length)for(const [i,[v,label]]of cols.entries()){const x=mx+i*mw/cols.length,w=mw/cols.length-17,isTime=label==='阅读时长';block(v,x,metricY-26,w,isTime?74:57,{size:isTime?29:45,min:26,font:isTime?SANS:NUM,weight:500,leading:1.1,color:i===0?color:C.ink});text(label,x,metricY+60,{font:SANS,size:24,color:C.muted});}
      if(!square)d.scribble(670,H-88,170,color);
      d.manifest.material={highlights:b.highlights.length,thoughts:b.thoughts.length,kind:rich?kind:'book-info',long};
    }
    return {render};
  }
  return {create};
})();
