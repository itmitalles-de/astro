import test from 'node:test';
import assert from 'node:assert/strict';
import { sampleCat, createCatPoints, projectCatPoint, scatterEnvelope, animationState, glyphFor } from '../../site/ascii-model.mjs';

const point = (x,y) => sampleCat((x-256)/170,(y-260)/170);

test('the canonical cat keeps only the viewer-right green eye and the closed left stroke', () => {
  assert.equal(point(305,231).part,'eye');
  assert.equal(point(315,231).part,'pupil');
  assert.equal(point(186,237).part,'closed-eye');
  assert.equal(point(256,283).part,'nose');
  assert.equal(sampleCat(-2,0),null);
  const eyes=createCatPoints().filter(p=>p.part==='eye');
  assert(eyes.length>4);
  assert(eyes.every(p=>p.x>0.15),'green glyphs must never form an eye on the left');
});

test('the sampled canonical shape is deterministic, bounded and composed of printable ASCII', () => {
  const a=createCatPoints();
  assert.deepEqual(a,createCatPoints());
  assert(a.length>1000&&a.length<4000);
  for(const p of a){
    assert(Number.isFinite(p.x)&&Number.isFinite(p.y)&&Number.isFinite(p.z));
    assert(p.density>=0&&p.density<=1);
    const glyph=glyphFor(p.density,p.seed);
    assert.equal(glyph.length,1);
    assert(glyph.charCodeAt(0)>=32&&glyph.charCodeAt(0)<=126);
  }
});

test('perspective and pointer drift never crop or mirror the coherent cat on mobile or desktop', () => {
  const points=createCatPoints(38);
  for(const [width,height] of [[320,280],[1160,420]])for(const time of [0,4,13,29])for(const pointerX of [-1,1]){
    const view={width,height,time,pointerX,pointerY:-1,scatter:0,intro:1};
    const projected=points.map(p=>({part:p.part,...projectCatPoint(p,view)}));
    assert(projected.every(p=>p.x>=0&&p.x<=width&&p.y>=0&&p.y<=height));
    const mean=part=>{const a=projected.filter(p=>p.part===part);return a.reduce((s,p)=>s+p.x,0)/a.length};
    assert(mean('eye')>mean('nose'));
    assert(mean('closed-eye')<mean('nose'));
  }
});

test('scatter is a bounded one-shot that completely settles, not an endless flashing effect', () => {
  assert.equal(scatterEnvelope(-1),0);
  assert.equal(scatterEnvelope(0),0);
  assert(scatterEnvelope(1)>0.8);
  assert.equal(scatterEnvelope(2.6),0);
  assert.equal(scatterEnvelope(10),0);
  for(let age=0;age<4;age+=.05)assert(scatterEnvelope(age)>=0&&scatterEnvelope(age)<=1);
});

test('motion is never scheduled for reduced motion, explicit pause, hidden pages or offscreen art', () => {
  const active={reduced:false,paused:false,visible:true,inView:true};
  assert.equal(animationState(active),'running');
  assert.equal(animationState({...active,reduced:true}),'reduced');
  assert.equal(animationState({...active,paused:true}),'paused');
  assert.equal(animationState({...active,visible:false}),'hidden');
  assert.equal(animationState({...active,inView:false}),'offscreen');
  assert.equal(animationState({...active,reduced:true,paused:true}),'reduced');
});
