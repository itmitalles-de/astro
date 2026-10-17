// SPDX-License-Identifier: GPL-3.0-or-later
import { animationState, createCatPoints, glyphFor, headIntroProgress, projectCatPoint, randomAt, scatterEnvelope } from './ascii-model.mjs';

const TAU = Math.PI*2;
const colors = {
  background:'#191919', fur:'#bdae93', ruff:'#d8d4ce', gold:'#fabd2f',
  purple:'#bc8ed1', eye:'#bfc78c', nose:'#d3869b', ink:'#504945', far:'#4d4740',
};
const ease = value => 1-Math.pow(1-Math.min(1,Math.max(0,value)),3);

export async function createAsciiScene({element,translate,initiallyPaused=false,savePaused=()=>{}}) {
  const variant = document.documentElement.dataset.asciiVariant || 'orbit';
  const artist = variant==='zoomies' ? (await import('./ascii-zoomies.mjs')).drawZoomies
    : variant==='hyperraum' ? (await import('./ascii-hyperraum.mjs')).drawHyperraum : null;
  const field = element.querySelector('#ascii-scene');
  const canvas = element.querySelector('canvas');
  const context = canvas.getContext('2d',{alpha:false});
  if (!context) return null;
  const controls = element.querySelector('#ascii-controls');
  const pauseButton = element.querySelector('#ascii-pause');
  const scatterButton = element.querySelector('#ascii-scatter');
  const caption = element.querySelector('.ascii-caption > [data-i18n]');
  const preference = matchMedia('(prefers-reduced-motion: reduce)');
  const stackedLayout = matchMedia('(max-width:760px)');
  let reduced = preference.matches, paused = initiallyPaused, inView = false, suspended = false;
  let width = 0, height = 0, dpr = 1, points = [], columns = 0;
  let clock = reduced || paused ? 3 : 0, flow = 0, burstStart = -100, frame = 0;
  let raf = 0, lastDraw = 0, lastScheduled = 0;
  let pointerX = 0, pointerY = 0, targetX = 0, targetY = 0;
  const stars = Array.from({length:170},(_,i)=>({angle:randomAt(i+1000)*TAU,depth:randomAt(i+2000),radius:.25+randomAt(i+3000)*.8}));
  const state = () => animationState({reduced,paused,inView,visible:!document.hidden&&!suspended});

  function refreshLabels() {
    pauseButton.dataset.i18n = reduced ? 'asciiReduced' : paused ? 'asciiResume' : 'asciiPause';
    pauseButton.textContent = translate(pauseButton.dataset.i18n);
    pauseButton.setAttribute('aria-pressed',String(paused));
    pauseButton.disabled = reduced;
    const titleKey = variant==='zoomies' ? 'asciiZoomies' : variant==='hyperraum' ? 'asciiHyperraum' : 'asciiOrbit';
    const actionKey = variant==='zoomies' ? 'asciiZoomiesAction' : variant==='hyperraum' ? 'asciiHyperraumAction' : 'asciiScatter';
    caption.dataset.i18n = titleKey;caption.textContent = translate(titleKey);
    scatterButton.dataset.i18n = actionKey;scatterButton.textContent = translate(actionKey);
    scatterButton.disabled = reduced || paused;
  }
  function glyph(char,x,y,size,color,alpha=1) {
    // Continuously varying depth must not create thousands of font cache keys.
    context.font = `${Math.round(size*4)/4}px "IBM Plex Mono",monospace`;
    context.fillStyle = color;
    context.globalAlpha = alpha;
    context.fillText(char,x,y);
  }
  function drawStars(time,energy) {
    const count = width<600 ? 95 : stars.length;
    for (let i=0;i<count;i++) {
      const star = stars[i];
      const depth = ((star.depth-time*.045)%1+1)%1;
      const distance = star.radius/(depth+.13);
      const angle = star.angle+pointerX*.018;
      const x = width*.5+Math.cos(angle)*distance*width*.24-pointerX*depth*10;
      const y = height*.5+Math.sin(angle)*distance*height*.43-pointerY*depth*7;
      if (x<0||x>width||y<0||y>height) continue;
      const near = 1-depth;
      glyph(i%9===0?'+':i%3===0?':':'.',x,y,6+near*5,i%7===0?colors.gold:i%5===0?colors.purple:colors.ruff,.16+near*.4);
      if (energy>.15 && depth<.55) {
        for (let tail=1;tail<=3;tail++) glyph('.',x-Math.cos(angle)*tail*energy*9,y-Math.sin(angle)*tail*energy*5,8,colors.gold,(1-tail/4)*energy*.45);
      }
    }
  }
  function drawOrbits(time,energy,front) {
    const count = width<600 ? 115 : 220;
    for (let ring=0;ring<3;ring++) for (let i=0;i<count;i++) {
      const angle = i/count*TAU+time*(ring%2?-.13:.11)+ring*1.7;
      const radius = 1+ring*.19+Math.sin(i*1.7)*.025+energy*.14;
      const x = Math.cos(angle)*width*.31*radius;
      const y = Math.sin(angle)*height*.18*radius+x*.14;
      const sy = height*.55+y;
      const isFront = Math.sin(angle)>.3 && sy>height*.70;
      if (isFront!==front) continue;
      const sx = width*.5+x+pointerX*7;
      const alpha = (front?.72:.44)+(Math.sin(angle)+1)*.09;
      glyph(i%17===0?'+':i%7===0?'*':i%3===0?':':'-',sx,sy,ring===1?9:8,ring===1?colors.purple:colors.gold,alpha);
      if (i%5===0) glyph('.',sx*1.02-width*.01,sy+3,6,colors.ruff,alpha*.25);
    }
  }
  function drawCat(time,energy,intro) {
    const scene = {width,height,time,pointerX,pointerY,scatter:energy,intro};
    const scale = Math.min(width*.35,height*.41);
    const font = Math.max(6,scale*2.2/columns*1.3);
    context.font = `${font}px "IBM Plex Mono",monospace`;
    context.globalAlpha = 1;
    context.shadowBlur = 0;
    for (const point of points) {
      const p = projectCatPoint(point,scene);
      const wave = Math.sin(point.x*4+point.y*3-time*.6)*.045;
      const ink = ['closed-eye','pupil','stripe'].includes(point.part);
      let color = ink ? colors.ink : colors[point.part] || colors.fur;
      let char = glyphFor(point.density+wave,point.seed);
      if (point.part==='eye') { color = intro>.88?colors.eye:colors.gold; char = point.seed>.6?'@':'o'; }
      else if (point.part==='nose') char = point.seed>.4?'v':':';
      else if (point.part==='closed-eye') char = '-';
      else if (point.part==='pupil') char = '|';
      if (char===' ') char = '.';
      context.fillStyle = color;
      context.fillText(char,p.x,p.y);
    }
    // A restrained glow only on the one canonical green eye, never a second lens.
    if (intro>.88) {
      context.fillStyle = colors.eye; context.shadowColor = colors.eye; context.shadowBlur = 7;
      for (const point of points) if (point.part==='eye') {
        const p = projectCatPoint(point,scene);
        context.fillText(point.seed>.6?'@':'o',p.x,p.y);
      }
      context.shadowBlur = 0;
    }
  }
  function drawPulse(age,energy) {
    if (energy<.025) return;
    const radius = .1+age/2.6;
    const count = width<600?76:130;
    for (let i=0;i<count;i++) {
      const angle = i/count*TAU;
      glyph(i%3?'*':'+',width*.5+Math.cos(angle)*width*.54*radius,
        height*.5+Math.sin(angle)*height*.77*radius,7,i%4?colors.gold:colors.purple,energy*.53);
    }
  }
  function draw(still=false) {
    if (!width||!height) return;
    const began = performance.now();
    const time = still?4:clock, energy = still?0:scatterEnvelope(clock-burstStart);
    context.setTransform(dpr,0,0,dpr,0,0);
    context.globalAlpha = 1;
    context.fillStyle = colors.background;
    context.fillRect(0,0,width,height);
    context.textAlign = 'center';context.textBaseline = 'middle';
    const intro = still?1:ease(clock/1.8);
    if (artist) {
      artist(context,{width,height,time,energy,pointerX,pointerY,intro,still,flow:still?0:flow,stacked:stackedLayout.matches},{
        glyph,
        cat: ({x=width*.5,y=height*.5,scale=1,scatter=energy}={}) => {
          if (!(scale>0)) throw new RangeError('ASCII cat scale must be positive; never mirror Astro');
          context.save();
          context.translate(x-width*.5*scale,y-height*.5*scale);
          context.scale(scale,scale);
          drawCat(time,scatter,headIntroProgress(variant,intro));
          context.restore();
        },
      });
    } else {
      drawStars(time+flow,energy);
      drawOrbits(time+flow,energy,false);
      drawCat(time,energy,intro);
      drawOrbits(time+flow,energy,true);
      drawPulse(clock-burstStart,energy);
    }
    context.globalAlpha = 1;
    canvas.dataset.frame = String(++frame);
    canvas.dataset.frameMs = (performance.now()-began).toFixed(2);
    field.dataset.burst = energy>0?'active':'idle';
  }
  function tick(stamp) {
    raf = 0;
    if (state()!=='running') return;
    const interval = 1000/(width<600?18:24);
    if (stamp-lastScheduled>=interval) {
      const delta = Math.min(.08,Math.max(0,(stamp-lastDraw)/1000));
      lastDraw = stamp;lastScheduled = stamp-(stamp-lastScheduled)%interval;
      clock += delta;
      const energy = scatterEnvelope(clock-burstStart);
      flow += energy*delta*5;
      pointerX += (targetX-pointerX)*.11;pointerY += (targetY-pointerY)*.11;
      draw();
    }
    raf = requestAnimationFrame(tick);
  }
  function synchronize() {
    const next = state();
    field.dataset.motion = next;
    refreshLabels();
    if (next==='running') {
      if (!raf) { lastDraw = performance.now();lastScheduled = lastDraw-100;raf = requestAnimationFrame(tick); }
    } else if (raf) { cancelAnimationFrame(raf);raf = 0; }
  }
  function resize() {
    const rect = field.getBoundingClientRect();
    width = rect.width;height = rect.height;dpr = Math.min(devicePixelRatio||1,1.5);
    canvas.width = Math.round(width*dpr);canvas.height = Math.round(height*dpr);
    const nextColumns = width<600?44:56;
    if (columns!==nextColumns) { columns = nextColumns;points = createCatPoints(columns); }
    draw(reduced);
  }
  let resolution;
  function watchResolution() {
    resolution?.removeEventListener('change',densityChanged);
    resolution = matchMedia(`(resolution: ${devicePixelRatio||1}dppx)`);
    resolution.addEventListener('change',densityChanged,{once:true});
  }
  function densityChanged() { resize();watchResolution(); }
  const observer = new IntersectionObserver(entries=>{
    inView = entries[0].isIntersecting&&entries[0].intersectionRatio>=.1;
    synchronize();
  },{threshold:[0,.1]});
  const resizer = new ResizeObserver(resize);
  const visibility = () => synchronize();
  const motionPreference = event => {
    reduced = event.matches;
    if (reduced) { pointerX = 0;pointerY = 0;targetX = 0;targetY = 0;clock = Math.max(3,clock);draw(true); }
    synchronize();
  };
  const movePointer = event => {
    if (state()!=='running'||event.pointerType==='touch') return;
    const rect = field.getBoundingClientRect();
    targetX = Math.max(-1,Math.min(1,(event.clientX-rect.left)/rect.width*2-1));
    targetY = Math.max(-1,Math.min(1,(event.clientY-rect.top)/rect.height*2-1));
  };
  field.addEventListener('pointermove',movePointer,{passive:true});
  field.addEventListener('pointerleave',()=>{targetX = 0;targetY = 0;},{passive:true});
  pauseButton.addEventListener('click',()=>{ paused = !paused;savePaused(paused);synchronize(); });
  scatterButton.addEventListener('click',()=>{ if (state()==='running') {burstStart = clock;field.dataset.burst = 'active';} });
  document.addEventListener('visibilitychange',visibility);
  window.addEventListener('resize',resize,{passive:true});
  preference.addEventListener('change',motionPreference);
  window.addEventListener('pagehide',()=>{suspended = true;synchronize();});
  window.addEventListener('pageshow',()=>{suspended = false;synchronize();});
  watchResolution();resize();observer.observe(field);resizer.observe(field);
  field.dataset.ready = 'true';controls.hidden = false;synchronize();
  document.fonts.ready.then(()=>{ if (state()!=='running') draw(reduced); });
  return {refreshLabels};
}
