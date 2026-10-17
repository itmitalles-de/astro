// SPDX-License-Identifier: GPL-3.0-or-later
// Shared real-browser motion acceptance; no desktop input or clipboard access.
export async function checkAsciiScene({send,evaluate,until,check,navigate,click,target}) {
  const pause = ms => new Promise(resolve=>setTimeout(resolve,ms));
  const frames = () => evaluate('Number(document.querySelector("#ascii-canvas").dataset.frame)');
  const motion = () => evaluate('document.querySelector("#ascii-scene").dataset.motion');
  await send('Page.bringToFront');
  await evaluate('document.querySelector("#ascii-art").scrollIntoView({block:"center",behavior:"instant"})');
  await until('document.querySelector("#ascii-scene").dataset.motion==="running" && Number(document.querySelector("#ascii-canvas").dataset.frame)>40');
  const variant = await evaluate('document.documentElement.dataset.asciiVariant');
  const first = await frames();await pause(220);
  check('ASCII renders changing real frames while visible',await frames()>first);
  await evaluate('globalThis.__asciiPixels=document.querySelector("#ascii-canvas").toDataURL()');await pause(180);
  check('ASCII animation changes actual pixels, not only a counter',await evaluate('document.querySelector("#ascii-canvas").toDataURL()!==globalThis.__asciiPixels'));

  // Observe original Canvas calls for one frame; RGB hue thresholds misclassify
  // colored text-edge pixels. Never replace the renderer or its drawing result.
  const eye = await evaluate(`new Promise((resolve,reject)=>{
    const canvas=document.querySelector('#ascii-canvas'),prototype=CanvasRenderingContext2D.prototype;
    const original=prototype.fillText;let gx=0,gn=0,fx=0,fn=0,min=canvas.width,max=0;
    const restore=()=>{prototype.fillText=original;observer.disconnect();clearTimeout(timer)};
    prototype.fillText=function(text,x,y,...rest){
      const eye=this.fillStyle==='#bfc78c',fur=this.fillStyle==='#bdae93'||this.fillStyle==='#d8d4ce';
      if(eye||fur){const m=this.getTransform(),px=m.a*x+m.c*y+m.e;
        if(eye){gx+=px;gn++;min=Math.min(min,px);max=Math.max(max,px)}else{fx+=px;fn++}
      }
      return original.call(this,text,x,y,...rest);
    };
    const observer=new MutationObserver(()=>{restore();resolve({green_glyphs:gn,green_x:gx/gn,fur_x:fx/fn,green_min:min,green_max:max,width:canvas.width,method:'Observed native fillText calls; original rendering preserved'})});
    const timer=setTimeout(()=>{restore();reject(Error('Eye paint observation timed out'))},4000);
    observer.observe(canvas,{attributes:true,attributeFilter:['data-frame']});
  })`);
  check('The actual green eye is on the viewer-right side of the ASCII cat',eye.green_glyphs>4&&eye.green_x>eye.fur_x&&eye.green_max<eye.width-2,eye);

  await evaluate('document.querySelector("#ascii-pause").focus({preventScroll:true})');
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',text:'\r',unmodifiedText:'\r',windowsVirtualKeyCode:13});
  await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await until('document.querySelector("#ascii-scene").dataset.motion==="paused"');
  const paused = await frames();await pause(250);
  check('Keyboard Pause freezes rendering and exposes the correct pressed state',await frames()===paused&&await evaluate('document.querySelector("#ascii-pause").getAttribute("aria-pressed")==="true"&&document.querySelector("#ascii-pause").textContent==="Resume"'));
  await click('#language-toggle');
  check('A paused animation retains its state and correct German Resume label',await motion()==='paused'&&await evaluate('document.querySelector("#ascii-pause").textContent==="Fortsetzen"'));
  await click('#language-toggle');
  await navigate();await until('document.querySelector("#ascii-scene")?.dataset.ready==="true"');await pause(120);
  check('Explicit animation pause survives reload',await motion()==='paused');
  const reloaded = await frames();await pause(180);
  check('Reloaded pause does not leave a background render loop',await frames()===reloaded);
  await click('#ascii-pause');await until('document.querySelector("#ascii-scene").dataset.motion==="running"');
  check('Resume restores motion without overriding the saved pause semantics',await evaluate('localStorage.getItem("astro-site.motion")==="auto"&&document.querySelector("#ascii-pause").getAttribute("aria-pressed")==="false"'));
  await click('#ascii-scatter');await until('document.querySelector("#ascii-scene").dataset.burst==="active"');
  check('The user-triggered burst enters its actual animated sequence',await motion()==='running');
  await until('document.querySelector("#ascii-scene").dataset.burst==="idle"');
  check('The burst completes and settles back to idle',await motion()==='running');

  const timings = await evaluate(`new Promise((resolve,reject)=>{
    const canvas=document.querySelector('#ascii-canvas'),values=[];
    const timer=setTimeout(()=>{observer.disconnect();reject(Error('Frame timing sample timed out'))},6000);
    const observer=new MutationObserver(()=>{values.push(Number(canvas.dataset.frameMs));if(values.length>=40){observer.disconnect();clearTimeout(timer);resolve(values)}});
    observer.observe(canvas,{attributes:true,attributeFilter:['data-frame']});
  })`);
  const sorted = [...timings].sort((a,b)=>a-b);
  const performance = {samples:sorted.length,median_ms:sorted[Math.floor(sorted.length*.5)],p95_ms:sorted[Math.floor(sorted.length*.95)],max_ms:sorted.at(-1)};
  check('ASCII frame work stays within the stated 18ms p95 software-rendering budget',performance.p95_ms<=18,performance);

  await evaluate('scrollTo({top:document.body.scrollHeight,behavior:"instant"})');
  await until('document.querySelector("#ascii-scene").dataset.motion==="offscreen"');
  const offscreen = await frames();await pause(250);
  check('Offscreen artwork stops rendering',await frames()===offscreen);
  await evaluate('scrollTo({top:0,behavior:"instant"})');await until('document.querySelector("#ascii-scene").dataset.motion==="running"');
  const other = await send('Target.createTarget',{url:'about:blank',background:false});
  try{
    await send('Target.activateTarget',{targetId:other.targetId});
    await until('document.hidden&&document.querySelector("#ascii-scene").dataset.motion==="hidden"');
    const hidden = await frames();await pause(250);
    check('A genuinely hidden tab stops its renderer',await frames()===hidden);
  } finally {
    await send('Target.closeTarget',{targetId:other.targetId});
    await send('Target.activateTarget',{targetId:target.id});
  }
  await until('document.querySelector("#ascii-scene").dataset.motion==="running"');
  check('Returning to the tab resumes the existing renderer',await frames()>offscreen);

  await click('#ascii-pause');await until('document.querySelector("#ascii-scene").dataset.motion==="paused"');
  const cssBox = await evaluate('(()=>{const r=document.querySelector("#ascii-scene").getBoundingClientRect();return {width:r.width,height:r.height}})()');
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1.5,mobile:false});
  // CDP changes DPR/query values without dispatching resolution changes until
  // media reevaluation. Ask Chromium to do that; do not synthesize DOM events.
  await send('Emulation.setEmulatedMedia',{media:'screen',features:[{name:'prefers-color-scheme',value:'dark'},{name:'prefers-reduced-motion',value:'no-preference'}]});
  await until('devicePixelRatio===1.5&&document.querySelector("#ascii-canvas").width===Math.round(document.querySelector("#ascii-scene").getBoundingClientRect().width*1.5)');
  check('A DPR-only change refreshes backing pixels without changing the CSS box',await evaluate(`(()=>{const r=document.querySelector('#ascii-scene').getBoundingClientRect();return r.width===${cssBox.width}&&r.height===${cssBox.height}})()`));
  const densityFrame = await frames();await pause(180);
  check('Resolution changes preserve explicit pause without a recurring render loop',await motion()==='paused'&&await frames()===densityFrame);
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await send('Emulation.setEmulatedMedia',{media:'',features:[{name:'prefers-color-scheme',value:'dark'},{name:'prefers-reduced-motion',value:'no-preference'}]});
  await until('document.querySelector("#ascii-canvas").width===Math.round(document.querySelector("#ascii-scene").getBoundingClientRect().width)');
  await click('#ascii-pause');await until('document.querySelector("#ascii-scene").dataset.motion==="running"');

  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:'dark'},{name:'prefers-reduced-motion',value:'reduce'}]});
  await until('document.querySelector("#ascii-scene").dataset.motion==="reduced"');
  const reduced = await frames();await pause(220);
  await click('#ascii-scatter');
  check('Reduced motion composes a still, disables motion controls and does not render continuously',await frames()===reduced&&await evaluate('document.querySelector("#ascii-pause").disabled&&document.querySelector("#ascii-scatter").disabled'));
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:'dark'},{name:'prefers-reduced-motion',value:'no-preference'}]});
  await until('document.querySelector("#ascii-scene").dataset.motion==="running"');

  const injection=await send('Page.addScriptToEvaluateOnNewDocument',{source:'HTMLCanvasElement.prototype.getContext=function(){return null}'});
  try{
    await navigate();await pause(120);
    check('Canvas failure leaves the static ASCII fallback and functional page intact',await evaluate('!document.querySelector("#ascii-scene").dataset.ready&&getComputedStyle(document.querySelector(".ascii-fallback")).display!=="none"&&document.querySelector("#ascii-controls").hidden&&document.querySelectorAll("[data-pane]").length===3'));
    if(variant==='hyperraum')check('The immersive hero fallback stays out of the desktop text column',await evaluate('(()=>{const f=document.querySelector("#ascii-scene").getBoundingClientRect(),p=document.querySelector(".ascii-fallback").getBoundingClientRect();return p.left>=f.left+f.width*.52})()'));
    await click('#split-right');
    check('Optional artwork failure does not break the interactive pane diagram',await evaluate('document.querySelectorAll("[data-pane]").length===4'));
  } finally { await send('Page.removeScriptToEvaluateOnNewDocument',{identifier:injection.identifier}); }
  await navigate();await until('document.querySelector("#ascii-scene")?.dataset.ready==="true"');
  await evaluate('scrollTo({top:0,behavior:"instant"})');
  return {variant,eye,performance};
}
