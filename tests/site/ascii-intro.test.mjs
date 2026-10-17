import test from 'node:test';
import assert from 'node:assert/strict';
import * as model from '../../site/ascii-model.mjs';
import {hyperraumPose} from '../../site/ascii-hyperraum.mjs';
import {zoomiesPose} from '../../site/ascii-zoomies.mjs';

test('constrained actor heads stay coherent and within their safe areas from the first intro frame',()=>{
  assert.equal(typeof model.headIntroProgress,'function');
  const points=model.createCatPoints(38);
  for(const variant of ['hyperraum','zoomies'])for(const intro of [0,.25,.5,1])for(const [width,height] of variant==='hyperraum'?[[1160,610],[680,320],[354,290]]:[[550,500],[354,290]]){
    const frame={width,height,intro,time:0,energy:0,pointerX:0,pointerY:0,stacked:height<=320};
    const pose=variant==='hyperraum'?hyperraumPose(frame):zoomiesPose(frame);
    const progress=model.headIntroProgress(variant,intro);
    assert.equal(progress,1);
    for(const point of points){
      const p=model.projectCatPoint(point,{...frame,intro:progress,scatter:pose.scatter});
      const x=pose.x+(p.x-width*.5)*pose.scale,y=pose.y+(p.y-height*.5)*pose.scale;
      assert(x>=0&&x<=width&&y>=0&&y<=height,`${variant}: head outside canvas at intro ${intro}`);
      if(variant==='hyperraum'&&!frame.stacked)assert(x>=width*.52,'early head fragments must not enter the copy column');
    }
  }
});

test('Orbit retains its full-field particle assembly rather than losing its distinct choreography',()=>{
  assert.equal(typeof model.headIntroProgress,'function');
  for(const progress of [0,.25,.5,1])assert.equal(model.headIntroProgress('orbit',progress),progress);
});
