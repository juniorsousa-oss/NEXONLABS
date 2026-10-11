/* Smoke test visual do login ATRIA com geometria validada a 100%.
   Não executa login nem acessa dados de usuários. */
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const artifacts=path.join(root,'test-artifacts');
fs.mkdirSync(artifacts,{recursive:true});
const server=http.createServer((request,response)=>{
  const parsed=new URL(request.url,'http://127.0.0.1');
  if(parsed.pathname==='/api/product-brand'){
    response.writeHead(200,{'Content-Type':'application/json'});
    response.end(JSON.stringify({asset_urls:{logo_dark:'/static/logo.svg'}}));return;
  }
  const filename=parsed.pathname==='/'?path.join(root,'static/login.html'):
    path.resolve(root,'.'+decodeURIComponent(parsed.pathname));
  if(!filename.startsWith(root+path.sep) || !fs.existsSync(filename) || fs.statSync(filename).isDirectory()){
    response.writeHead(404);response.end('Not Found');return;
  }
  const ext=path.extname(filename);
  const mime={'.css':'text/css','.html':'text/html','.js':'text/javascript','.svg':'image/svg+xml'}[ext]||'application/octet-stream';
  response.writeHead(200,{'Content-Type':mime,'Cache-Control':'no-store'});
  response.end(fs.readFileSync(filename));
});
async function inspect(page){
 return await page.evaluate(()=>{
   const rect=sel=>{const r=document.querySelector(sel).getBoundingClientRect();
    return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,right:r.right}};
   return {
     viewport:{width:innerWidth,height:innerHeight},
     shell:rect('.login-shell'),blue:rect('.login-brand-panel'),
     white:rect('.login-form-panel'),logo:rect('.login-brand-official'),
     slogan:rect('.login-brand-copy'),leftFoot:rect('.login-brand-foot'),
     rightCard:rect('.login-card'),eyebrow:rect('.login-overline'),
     heading:rect('.login-card h1'),password:rect('#password'),
     action:rect('#login-form button[type=submit]'),
     note:rect('.atria-nexon-note'),
     brandFootDisplay:getComputedStyle(document.querySelector('.login-brand-foot')).display,
     docWidth:document.documentElement.scrollWidth,
     bodyHeight:document.body.scrollHeight,
   };
 });
}
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const base='http://127.0.0.1:'+server.address().port;
 try{
   // Mesma área útil 1440x900 dos testes existentes, navegador a 100%.
   const desktop=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
   await desktop.goto(base,{waitUntil:'networkidle'});
   await desktop.waitForFunction(()=>document.querySelector('link[href*="login-scale-r5-mobile-flex-center"]')?.sheet);
   const a=await inspect(desktop);
   assert.ok(a.shell.width>=950 && a.shell.width<=965,JSON.stringify(a));
   assert.ok(a.shell.height>=670 && a.shell.height<=690,JSON.stringify(a));
   assert.ok(a.shell.y>25 && a.shell.bottom<900-25,JSON.stringify(a));
   assert.ok(Math.abs(a.blue.width-a.white.width)<=3,JSON.stringify(a));
   assert.ok(a.logo.bottom+35<a.slogan.y,JSON.stringify(a));
   assert.ok(a.slogan.bottom+15<a.leftFoot.y,JSON.stringify(a));
   assert.ok(a.leftFoot.bottom<a.shell.bottom-20,JSON.stringify(a));
   assert.ok(a.eyebrow.y<a.heading.y && a.heading.bottom<a.password.y,JSON.stringify(a));
   assert.ok(a.password.bottom<a.action.y,JSON.stringify(a));
   assert.ok(a.action.bottom+15<a.note.y,JSON.stringify(a));
   assert.ok(a.note.bottom<a.shell.bottom-18,JSON.stringify(a));
   assert.ok(a.docWidth<=a.viewport.width+1,JSON.stringify(a));
   await desktop.screenshot({path:path.join(artifacts,'atria-login-desktop-100.png'),fullPage:false});

   await desktop.evaluate(()=>{document.body.style.zoom='90%'});
   const zoom=await inspect(desktop);
   assert.ok(zoom.docWidth<=zoom.viewport.width+1,JSON.stringify(zoom));
   assert.ok(zoom.shell.width>700 && zoom.shell.bottom<=zoom.viewport.height,JSON.stringify(zoom));
   await desktop.screenshot({path:path.join(artifacts,'atria-login-desktop-90.png'),fullPage:false});

   // Notebook baixo: nenhum controle cortado; rolagem permitida.
   const short=await browser.newPage({viewport:{width:1280,height:650}});
   await short.goto(base,{waitUntil:'networkidle'});
   const b=await inspect(short);
   assert.ok(b.docWidth<=b.viewport.width+1,JSON.stringify(b));
   assert.ok(b.note.bottom<=b.bodyHeight+1,JSON.stringify(b));
   assert.ok(b.shell.height>=550 && b.shell.height<=600,JSON.stringify(b));

   // Reprodução da proporção do usuário: 600 CSS px de altura útil
   // (monitor 1708x896 com escala de exibição do Windows / navegador).
   // AXORA nessa faixa usa card de 510px; ATRIA não deve cair para 480px.
   const compact=await browser.newPage({viewport:{width:1280,height:600},deviceScaleFactor:1});
   await compact.goto(base,{waitUntil:'networkidle'});
   const c=await inspect(compact);
   assert.ok(Math.abs(c.shell.height-510)<=2,JSON.stringify(c));
   assert.ok(Math.abs(c.shell.y-(600-510)/2)<=3,JSON.stringify(c));
   assert.ok(c.shell.bottom<=600-30,JSON.stringify(c));
   assert.ok(c.blue.bottom<=c.shell.bottom+1 && c.white.bottom<=c.shell.bottom+1,JSON.stringify(c));
   assert.ok(c.action.bottom<c.note.y && c.note.bottom<c.shell.bottom-12,JSON.stringify(c));
   assert.ok(c.slogan.bottom+10<c.leftFoot.y,JSON.stringify(c));
   assert.ok(c.docWidth<=1281,JSON.stringify(c));
   await compact.screenshot({path:path.join(artifacts,'atria-login-desktop-short-600.png'),fullPage:false});

   // Em alturas extremamente pequenas, o formulário continua acessível
   // por rolagem, sem aplicar overflow:hidden no corpo.
   const tiny=await browser.newPage({viewport:{width:1280,height:465},deviceScaleFactor:1});
   await tiny.goto(base,{waitUntil:'networkidle'});
   const small=await inspect(tiny);
   assert.ok(small.shell.height>=400,JSON.stringify(small));
   assert.ok(small.action.bottom<=small.bodyHeight,JSON.stringify(small));

   const tablet=await browser.newPage({viewport:{width:820,height:950}});
   await tablet.goto(base,{waitUntil:'networkidle'});
   const t=await inspect(tablet);
   assert.ok(t.blue.bottom<=t.white.y+2,JSON.stringify(t));
   assert.equal(t.brandFootDisplay,'none');
   assert.ok(t.docWidth<=t.viewport.width+1,JSON.stringify(t));

   const mobile=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:2});
   await mobile.goto(base,{waitUntil:'networkidle'});
   const m=await inspect(mobile);
   assert.ok(m.blue.bottom<=m.white.y+2,JSON.stringify(m));
   assert.equal(m.brandFootDisplay,'none');
   assert.ok(m.docWidth<=m.viewport.width+1,JSON.stringify(m));
   assert.ok(m.password.width>200 && m.action.width>200,JSON.stringify(m));
   assert.ok(m.note.bottom<=m.bodyHeight+1,JSON.stringify(m));
   // Telas altas: distancias superior e inferior equivalentes, sem card no topo.
   assert.ok(Math.abs(m.shell.y-(m.viewport.height-m.shell.bottom))<=12,JSON.stringify(m));
   await mobile.screenshot({path:path.join(artifacts,'atria-login-mobile-390.png'),fullPage:true});

   // Telefone de pouca altura: rolagem natural, sem cortar logo nem formulario.
   const mobileShort=await browser.newPage({viewport:{width:390,height:530},isMobile:true,hasTouch:true,deviceScaleFactor:2});
   await mobileShort.goto(base,{waitUntil:'networkidle'});
   const ms=await inspect(mobileShort);
   assert.ok(ms.shell.y>=8,JSON.stringify(ms));
   assert.ok(ms.bodyHeight>=ms.viewport.height,JSON.stringify(ms));
   assert.ok(ms.note.bottom<=ms.bodyHeight+1,JSON.stringify(ms));
   assert.ok(ms.docWidth<=ms.viewport.width+1,JSON.stringify(ms));

   console.log('ATRIA_LOGIN_AXORA_SCALE_OK desktop100 desktop90 laptop650 desktop600 card510 tablet820 mobile390');
 }finally{
   await browser.close();
   server.close();
 }
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
