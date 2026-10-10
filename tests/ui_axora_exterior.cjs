/* Smoke-test da moldura externa ATRIA em Chromium.
   Carrega HTML e folhas reais sem credenciais ou chamadas de API.
   Medidas em viewport desktop, zoom de referência (90%) e smartphone.
*/
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const shots=path.join(root,'test-artifacts');
fs.mkdirSync(shots,{recursive:true});
const server=http.createServer((req,res)=>{
  const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  const filename=pathname==='/'?path.join(root,'static/index.html'):path.resolve(root,'.'+pathname);
  if(!filename.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
  if(!fs.existsSync(filename)||fs.statSync(filename).isDirectory()){res.writeHead(404);res.end();return;}
  let data=fs.readFileSync(filename);
  if(filename.endsWith('index.html')){
    // Desabilita APENAS a lógica JS: a geometria/CSS/DOM reais continuam.
    data=Buffer.from(data.toString('utf8').replace(/<script\s+src="[^"]+"\s+defer><\/script>/g,''));
  }
  const type=filename.endsWith('.css')?'text/css':filename.endsWith('.svg')?'image/svg+xml':
    filename.endsWith('.html')?'text/html':filename.endsWith('.js')?'text/javascript':'application/octet-stream';
  res.writeHead(200,{'Content-Type':type});res.end(data);
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin='http://127.0.0.1:'+server.address().port;
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  try{
    const desktop=await browser.newPage({viewport:{width:1440,height:900}});
    await desktop.goto(origin+'/',{waitUntil:'domcontentloaded'});
    await desktop.waitForFunction(()=>Boolean(document.querySelector('link[href*="atria-axora-exterior"]')?.sheet));
    let layout=await desktop.evaluate(()=>{
      const shell=document.querySelector('.shell'),side=document.querySelector('.sidebar'),
        workspace=document.querySelector('.workspace'),body=getComputedStyle(document.body);
      return {
        bodyBg:body.backgroundImage,shellWidth:shell.getBoundingClientRect().width,
        shellX:shell.getBoundingClientRect().x,
        sidebarX:side.getBoundingClientRect().x,
        sideRadius:getComputedStyle(side).borderTopLeftRadius,
        shellRadius:getComputedStyle(shell).borderTopLeftRadius,
        workspaceBg:getComputedStyle(workspace).backgroundImage,
        docWidth:document.documentElement.scrollWidth,
        winWidth:window.innerWidth
      };
    });
    assert.match(layout.bodyBg,/nexon-app-atmosphere\.svg/);
    assert.match(layout.workspaceBg,/linear-gradient/);
    assert.ok(layout.shellX>=8 && layout.shellX<=20,JSON.stringify(layout));
    assert.ok(parseFloat(layout.shellRadius)>=20);
    assert.ok(Math.abs(layout.shellX-layout.sidebarX)<=2);
    assert.ok(layout.docWidth<=layout.winWidth+2,JSON.stringify(layout));

    // Referência do usuário: browser em 90%, sem impor escala ao produto.
    await desktop.evaluate(()=>{document.body.style.zoom='90%';});
    const zoom=await desktop.evaluate(()=>({
      outer:document.querySelector('.shell').getBoundingClientRect().width,
      doc:document.documentElement.scrollWidth,win:window.innerWidth
    }));
    assert.ok(zoom.outer>600 && zoom.doc<=zoom.win+2,JSON.stringify(zoom));
    await desktop.screenshot({path:path.join(shots,'atria-desktop-90.png'),fullPage:false});

    const mobile=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:2});
    await mobile.goto(origin+'/',{waitUntil:'domcontentloaded'});
    await mobile.waitForFunction(()=>Boolean(document.querySelector('link[href*="atria-axora-exterior"]')?.sheet));
    const frame=await mobile.evaluate(()=>{
      const outer=document.querySelector('.shell'),drawer=document.querySelector('#sidebar');
      return {
        width:outer.getBoundingClientRect().width,
        x:outer.getBoundingClientRect().x,
        radius:getComputedStyle(outer).borderTopLeftRadius,
        drawerLeft:drawer.getBoundingClientRect().left,
        background:getComputedStyle(document.body).backgroundImage,
        docWidth:document.documentElement.scrollWidth,winWidth:innerWidth
      };
    });
    assert.ok(frame.x>=7 && frame.x<=16,JSON.stringify(frame));
    assert.ok(parseFloat(frame.radius)>=20);
    assert.ok(frame.drawerLeft<0,JSON.stringify(frame));
    assert.match(frame.background,/nexon-app-atmosphere\.svg/);
    assert.ok(frame.docWidth<=frame.winWidth+2,JSON.stringify(frame));
    await mobile.evaluate(()=>{
      const side=document.querySelector('#sidebar'),overlay=document.querySelector('#mobile-overlay');
      overlay.hidden=false;overlay.classList.add('show');
      side.classList.add('open');side.inert=false;
    });
    const drawer=await mobile.evaluate(()=>{
      const side=document.querySelector('#sidebar'),overlay=document.querySelector('#mobile-overlay');
      const rect=side.getBoundingClientRect(),overlayStyle=getComputedStyle(overlay);
      const x=rect.left+30,y=rect.top+120;
      return {
        x:rect.x,right:rect.right,width:rect.width,z:+getComputedStyle(side).zIndex,
        overlayZ:+overlayStyle.zIndex,hit:side.contains(document.elementFromPoint(x,y)),
        navScroll:getComputedStyle(side.querySelector('.menu')).overflowY
      };
    });
    assert.ok(Math.abs(drawer.x)<=2,JSON.stringify(drawer));
    assert.ok(drawer.right<=390 && drawer.width>230);
    assert.ok(drawer.z>drawer.overlayZ && drawer.hit,JSON.stringify(drawer));
    assert.ok(drawer.navScroll==='auto');
    await mobile.screenshot({path:path.join(shots,'atria-mobile-menu.png'),fullPage:false});
    console.log('ATRIA_AXORA_BROWSER_LAYOUT_OK desktop, zoom90, mobile drawer');
  }finally{
    await browser.close();
    server.close();
  }
})().catch(err=>{console.error(err);server.close();process.exitCode=1;});
