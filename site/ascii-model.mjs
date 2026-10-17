// SPDX-License-Identifier: GPL-3.0-or-later
// Canonical cat geometry from assets/astro.svg; never horizontally mirror it.
const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const TAU = Math.PI * 2;

function outline(commands) {
  const points = [];
  for (const command of commands) {
    if (command.length === 2) points.push(command);
    else {
      const [x, y] = points.at(-1);
      const [cx, cy, ex, ey] = command;
      for (let i = 1; i <= 12; i++) {
        const t = i / 12, a = 1 - t;
        points.push([a*a*x + 2*a*t*cx + t*t*ex, a*a*y + 2*a*t*cy + t*t*ey]);
      }
    }
  }
  return points;
}
const body = outline([[112,228],[104,84],[192,144],[256,124,320,144],[408,84],[400,228],
  [430,296,386,352],[350,348],[323,398],[288,390],[256,426],[224,390],[189,398],[162,348],
  [126,352],[82,296,112,228]]);
const ruff = outline([[180,282],[210,263,256,285],[302,263,332,282],[335,322],
  [317,347,300,354],[306,372],[280,366],[256,398],[232,366],[206,372],[212,354],[195,347,177,322]]);
const eye = outline([[287,231],[315,210,343,231],[315,261,287,231]]);
const nose = [[244,280],[256,276],[268,280],[256,293]];
const tabby = [[216,185],[224,160],[256,183],[288,160],[296,185]];

function inside(x, y, polygon) {
  let hit = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [ax, ay] = polygon[i], [bx, by] = polygon[j];
    if ((ay > y) !== (by > y) && x < (bx-ax)*(y-ay)/(by-ay)+ax) hit = !hit;
  }
  return hit;
}
function segmentDistance(x, y, a, b) {
  const dx = b[0]-a[0], dy = b[1]-a[1];
  const t = clamp(((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy));
  return Math.hypot(x-a[0]-t*dx,y-a[1]-t*dy);
}
export function randomAt(index) {
  let value = Math.imul(index ^ 0x45d9f3b, 0x45d9f3b);
  value = Math.imul(value ^ value >>> 16, 0x45d9f3b);
  return ((value ^ value >>> 16) >>> 0) / 4294967296;
}
export function sampleCat(x, y) {
  const u = 256+x*170, v = 260+y*170;
  if (!inside(u,v,body)) return null;
  const z = Math.sqrt(Math.max(.025,1-.68*x*x-.58*y*y))*.42;
  let part = 'fur', density = clamp(.48+z*.7-x*.11);
  if (inside(u,v,ruff)) { part = 'ruff'; density = clamp(.79+z*.36); }
  if (tabby.slice(1).some((end,i)=>segmentDistance(u,v,tabby[i],end)<5.5)) { part = 'stripe'; density = .16; }
  if (segmentDistance(u,v,[169,239],[203,234])<5) { part = 'closed-eye'; density = .035; }
  if (inside(u,v,eye)) {
    part = 'eye'; density = .88;
    if (segmentDistance(u,v,[315,222],[315,243])<4.5) { part = 'pupil'; density = .025; }
  }
  if (inside(u,v,nose)) { part = 'nose'; density = .74; }
  return {x,y,z,part,density};
}
export function createCatPoints(columns = 56) {
  columns = Math.round(clamp(columns,24,72));
  const step = 2.2/columns, points = [];
  for (let row = 0; row < columns; row++) for (let col = 0; col < columns; col++) {
    const point = sampleCat(-1.1+(col+.5)*step,-1.1+(row+.5)*step);
    if (point) points.push({...point,seed:randomAt(row*columns+col)});
  }
  return points;
}
export function glyphFor(density, seed = 0) {
  const glyphs = ' .:-=+*#%@';
  return glyphs[Math.round(clamp(density+(seed-.5)*.09)*(glyphs.length-1))];
}
export function scatterEnvelope(age) {
  return age > 0 && age < 2.6 ? Math.sin(age/2.6*Math.PI)**2 : 0;
}
export function animationState({reduced,paused,visible,inView}) {
  if (reduced) return 'reduced';
  if (paused) return 'paused';
  if (!visible) return 'hidden';
  return inView ? 'running' : 'offscreen';
}
// Only Orbit has room for a full-field particle assembly. Constrained actors
// keep the head coherent while their corridor, body, legs and trails animate.
export function headIntroProgress(variant,progress) {
  return variant==='orbit' ? clamp(progress) : 1;
}
export function projectCatPoint(point, {width,height,time=0,pointerX=0,pointerY=0,scatter=0,intro=1}) {
  pointerX = clamp(pointerX,-1,1); pointerY = clamp(pointerY,-1,1);
  const yaw = Math.sin(time*.24)*.14+pointerX*.095;
  const pitch = Math.cos(time*.19)*.035+pointerY*.045;
  const roll = Math.sin(time*.32)*.018;
  const x = point.x*Math.cos(yaw)+point.z*Math.sin(yaw);
  const depth = point.z*Math.cos(yaw)-point.x*Math.sin(yaw);
  const y = point.y*Math.cos(pitch)-depth*Math.sin(pitch);
  const perspective = 1/(1-depth*.12);
  const scale = Math.min(width*.35,height*.41);
  const spread = (1-clamp(intro))*1.65+clamp(scatter)*.34;
  const facial = ['eye','pupil','closed-eye','nose'].includes(point.part);
  const displacement = facial ? spread*.12 : spread;
  const angle = point.seed*TAU+point.y*1.8;
  return {
    x: width*.5+pointerX*Math.min(10,width*.016)+(x*Math.cos(roll)-y*Math.sin(roll))*scale*perspective+Math.cos(angle)*displacement*scale,
    y: height*.5+Math.sin(time*.7)*height*.012+(x*Math.sin(roll)+y*Math.cos(roll))*scale*perspective+Math.sin(angle)*displacement*scale,
    depth, scale,
  };
}
