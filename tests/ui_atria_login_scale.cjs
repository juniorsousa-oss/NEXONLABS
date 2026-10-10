/* ATRIA login layout: real Chromium geometry at 100% desktop and mobile.
   Static app only, no login, production data or user credentials involved. */
'use strict';
const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const shots=path.join(root,'test-artifacts');
fs.mkdirSync(shots,{recursive:true});
const server=http.createServer((req,res)=>{
  const pathname=decodeURIComponent(new URL(req.url,'http://local').pathname);
  const filename=pathname==='/'?path.join(root,'static/login.html'):path.resolve(root,'.'+pathname);
  if(!filename.startsWith(root+path.sep)||!fs.existsSync(filename)||fs.statSync(filename).isDirectory()){
    res.writeHead(404);res.end();return;
  }
  const type=filename.endsWith('.css')?'text/css':filename.endsWith('.svg')?'image/svg+xml':
             filename.endsWith('.js')?'application/javascript': 'text/html';
  res.writeHead(200,{'Content-Type':type});
  res.end(fs.readFileSync(filename));
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin='http://127.0.0.1:'+server.address().port;
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  try{
    async function geometry(page){
      return page.evaluate(()=>{
        const rect=selector=>{
          const e=document.querySelector(selector);
          const r=e.getBoundingClientRect();
          return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height};
        };
        return {
          win:innerWidth,viewportHeight:innerHeight,scrollWidth:document.documentElement.scrollWidth,
          scrollHeight:document.documentElement.scrollHeight,
          shell:rect('.login-shell'),brand:rect('.login-brand-panel'),
          brandLogo:rect('.login-brand'),brandCopy:rect('.login-brand-copy'),
          formPanel:rect('.login-form-panel'),card:rect('.login-card'),
          title:rect('.login-card h1'),form:rect('#login-form'),
          submit:rect('#login-form button[type=submit]'),
          note:rect('.login-note'),password:rect('#password'),
          columns:getComputedStyle(document.querySelector('.login-shell')).gridTemplateColumns,
          fontSize:getComputedStyle(document.querySelector('#password')).fontSize,
          cssLoaded:Boolean([...document.styleSheets].some(x=>x.href?.includes('atria-login-axora-scale.css')))
        };
      });
    }
    const desktop=await browser.newPage({viewport:{width:1706,height:900},deviceScaleFactor:1});
    await desktop.goto(origin+'/',{waitUntil:'networkidle'});
    const d=await geometry(desktop);
    assert.ok(d.cssLoaded,JSON.stringify(d));
    assert.ok(d.shell.width>=940&&d.shell.width<=961,JSON.stringify(d));
    assert.ok(d.shell.height>=530&&d.shell.height<=551,JSON.stringify(d));
    assert.ok(d.shell.top>100 && 900-d.shell.bottom>100,JSON.stringify(d));
    assert.ok(Math.abs((d.shell.left)-(1706-d.shell.right))<3,JSON.stringify(d));
    assert.ok(Math.abs(d.brand.width-d.formPanel.width)<3,JSON.stringify(d));
    assert.ok(d.brandLogo.bottom+30<d.brandCopy.top,JSON.stringify(d));
    assert.ok(d.brandCopy.bottom<=d.brand.bottom-15,JSON.stringify(d));
    assert.ok(d.form.top>d.formPanel.top+30,JSON.stringify(d));
    assert.ok(d.note.bottom<=d.formPanel.bottom-12,JSON.stringify(d));
    assert.ok(d.scrollHeight<=900+2 && d.scrollWidth<=1706+2,JSON.stringify(d));
    await desktop.screenshot({path:path.join(shots,'atria-login-desktop-100.png')});

    const medium=await browser.newPage({viewport:{width:1440,height:800}});
    await medium.goto(origin+'/',{waitUntil:'networkidle'});
    const m=await geometry(medium);
    assert.ok(m.shell.width>=930 && m.shell.width<=961,JSON.stringify(m));
    assert.ok(m.shell.height<=551 && m.scrollWidth<=m.win+2,JSON.stringify(m));
    assert.ok(m.note.bottom<m.formPanel.bottom-10,JSON.stringify(m));
    await medium.screenshot({path:path.join(shots,'atria-login-desktop-1440.png')});

    const tablet=await browser.newPage({viewport:{width:820,height:1000}});
    await tablet.goto(origin+'/',{waitUntil:'networkidle'});
    const t=await geometry(tablet);
    assert.ok(t.shell.width<=620 && t.shell.width>500,JSON.stringify(t));
    assert.ok(Math.abs(t.brand.width-t.formPanel.width)<2,JSON.stringify(t));
    assert.ok(t.brand.bottom<=t.formPanel.top+2,JSON.stringify(t));
    assert.ok(t.scrollWidth<=t.win+2,JSON.stringify(t));

    const mobile=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:2,isMobile:true,hasTouch:true});
    await mobile.goto(origin+'/',{waitUntil:'networkidle'});
    const v=await geometry(mobile);
    assert.ok(v.cssLoaded,JSON.stringify(v));
    assert.ok(v.scrollWidth<=v.win+2,JSON.stringify(v));
    assert.ok(v.shell.width>=330&&v.shell.width<=390,JSON.stringify(v));
    assert.ok(Math.abs(v.brand.width-v.formPanel.width)<2,JSON.stringify(v));
    assert.ok(v.note.bottom<=v.shell.bottom+1,JSON.stringify(v));
    assert.ok(parseFloat(v.fontSize)>=16,JSON.stringify(v));
    await mobile.locator('#reveal-password').check();
    assert.equal(await mobile.locator('#password').getAttribute('type'),'text');
    await mobile.locator('#reveal-password').uncheck();
    assert.equal(await mobile.locator('#password').getAttribute('type'),'password');
    await mobile.screenshot({path:path.join(shots,'atria-login-mobile.png'),fullPage:true});
    console.log('ATRIA_LOGIN_SCALE_OK desktop100, 1440, tablet, mobile');
  }finally{
    await browser.close();
    server.close();
  }
})().catch(err=>{console.error(err);server.close();process.exitCode=1});
