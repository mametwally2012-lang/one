import * as THREE from 'https://unpkg.com/three@0.153.0/build/three.module.js';
import { OrbitControls } from 'https://unpkg.com/three@0.153.0/examples/jsm/controls/OrbitControls.js';

const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({canvas, antialias:true});
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x111111);

const camera = new THREE.PerspectiveCamera(45, window.innerWidth/window.innerHeight, 0.1, 1000);
camera.position.set(0, 1.5, 3);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.screenSpacePanning = false;

// ضوء
const dir = new THREE.DirectionalLight(0xffffff, 1.0);
dir.position.set(5,10,7);
scene.add(dir);
scene.add(new THREE.AmbientLight(0x404040, 0.7));

// مجسم بسيط - كرة قابلة للتعديل
const geo = new THREE.SphereGeometry(1, 128, 128);
const mat = new THREE.MeshStandardMaterial({color:0xffcc88, metalness:0.1, roughness:0.6});
const mesh = new THREE.Mesh(geo, mat);
scene.add(mesh);

// شبك أرضية
const grid = new THREE.GridHelper(10,20,0x444444,0x222222);
grid.position.y = -1.2;
scene.add(grid);

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

// simple brush configuration
const brushes = {
  clay: {display: 'clay'},
  inflate: {display: 'inflate'},
  drag: {display: 'drag'},
  move: {display: 'move'},
  paint: {display: 'paint'},
  transform: {display: 'transform'},
  crease: {display: 'crease'},
  CC0: {display: 'CC0'},
  wire: {display: 'wire'},
  measure: {display: 'measure'},
  remove: {display: 'remove'},
  'rigging prev': {display: 'rigging prev'},
  add: {display: 'add'},
  eye: {display: 'eye'}
};
let currentBrush = 'clay';
let negativeMode = false;
let showUIEnabled = true;
let hotkeysEnabled = false;
let cameraSpeedMult = 1;
let uiScale = 1;

// Undo/Redo system
const undoStack = [];
const redoStack = [];
const MAX_UNDO_STATES = 10;

function saveState(){
  const posAttr = mesh.geometry.attributes.position;
  const posData = new Float32Array(posAttr.array);
  undoStack.push({positions: posData});
  redoStack.length = 0;
  if(undoStack.length > 100) checkMemoryPressure();
}

function undo(){
  if(undoStack.length <= 1) return;
  const curr = undoStack.pop();
  redoStack.push(curr);
  const prev = undoStack[undoStack.length-1];
  const posAttr = mesh.geometry.attributes.position;
  posAttr.array.set(prev.positions);
  posAttr.needsUpdate = true;
  mesh.geometry.computeVertexNormals();
}

function redo(){
  if(redoStack.length === 0) return;
  const state = redoStack.pop();
  undoStack.push(state);
  const posAttr = mesh.geometry.attributes.position;
  posAttr.array.set(state.positions);
  posAttr.needsUpdate = true;
  mesh.geometry.computeVertexNormals();
}

function checkMemoryPressure(){
  if(undoStack.length > MAX_UNDO_STATES){
    while(undoStack.length > MAX_UNDO_STATES){
      undoStack.shift();
    }
  }
}

function getMemoryUsage(){
  const info = renderer.info.memory;
  const vramMB = (info.geometries + info.textures) * 0.01;
  return {vram: vramMB};
}

function updateMemoryDisplay(){
  const mem = getMemoryUsage();
  let label = document.getElementById('memory-display');
  if(!label){
    label = document.createElement('div');
    label.id = 'memory-display';
    label.style.cssText = 'position:absolute;top:35px;left:8px;color:#fff;font-size:0.8em;background:rgba(0,0,0,0.3);padding:4px';
    document.getElementById('ui').appendChild(label);
  }
  label.textContent = `Memory: ${undoStack.length} states, VRAM: ${mem.vram.toFixed(1)}MB`;
}

function addCube(){
  const geom = new THREE.BoxGeometry(1,1,1,8,8,8);
  const mat = new THREE.MeshStandardMaterial({color:0x88ccff});
  const newMesh = new THREE.Mesh(geom, mat);
  newMesh.position.set(0, 0, 0);
  scene.add(newMesh);
}

function addSphere(){
  const geom = new THREE.SphereGeometry(0.8, 32, 32);
  const mat = new THREE.MeshStandardMaterial({color:0xff88cc});
  const newMesh = new THREE.Mesh(geom, mat);
  newMesh.position.set(0, 0, 0);
  scene.add(newMesh);
}

function addCylinder(){
  const geom = new THREE.CylinderGeometry(0.6, 0.6, 1.5, 24, 8);
  const mat = new THREE.MeshStandardMaterial({color:0x88ff88});
  const newMesh = new THREE.Mesh(geom, mat);
  newMesh.position.set(0, 0, 0);
  scene.add(newMesh);
}

function addTorus(){
  const geom = new THREE.TorusGeometry(0.8, 0.3, 16, 100);
  const mat = new THREE.MeshStandardMaterial({color:0xffcc88});
  const newMesh = new THREE.Mesh(geom, mat);
  newMesh.position.set(0, 0, 0);
  scene.add(newMesh);
}

function addCone(){
  const geom = new THREE.ConeGeometry(0.7, 1.5, 24, 8);
  const mat = new THREE.MeshStandardMaterial({color:0xff8888});
  const newMesh = new THREE.Mesh(geom, mat);
  newMesh.position.set(0, 0, 0);
  scene.add(newMesh);
}

function addPyramid(){
  const geom = new THREE.ConeGeometry(0.8, 1, 4, 4);
  const mat = new THREE.MeshStandardMaterial({color:0xcc88ff});
  const newMesh = new THREE.Mesh(geom, mat);
  newMesh.position.set(0, 0, 0);
  scene.add(newMesh);
}

const brushParams = {
  strength: 0.02,
  radius: 0.12,
  color: '#ff0000',
  roughness: 0.5,
  metallic: 0.1,
  lightAction: false,
  lightColor: '#ffffff',
  negativeDyntopo: false,
  forceDyntopo: false,
  intensity: 0.1
};

function updateBrushSettingsUI(){
  const container = document.getElementById('brush-settings');
  container.innerHTML='';
  function addSetting(labelText, input){
    const div=document.createElement('div');
    div.className='setting';
    const label=document.createElement('label');
    label.textContent=labelText+': ';
    label.appendChild(input);
    div.appendChild(label);
    container.appendChild(div);
  }
  switch(currentBrush){
    case 'clay':
      {
        const s=document.createElement('input'); s.type='range'; s.min=0.001; s.max=0.1; s.step=0.001; s.value=brushParams.strength;
        s.oninput=e=>brushParams.strength=parseFloat(e.target.value);
        addSetting('strength',s);
        const r=document.createElement('input'); r.type='range'; r.min=0.01; r.max=0.5; r.step=0.01; r.value=brushParams.radius;
        r.oninput=e=>brushParams.radius=parseFloat(e.target.value);
        addSetting('radius',r);
      }
      break;
    case 'inflate':
      // same as clay plus negative + dyntopo
      {
        const s=document.createElement('input'); s.type='range'; s.min=0.001; s.max=0.1; s.step=0.001; s.value=brushParams.strength;
        s.oninput=e=>brushParams.strength=parseFloat(e.target.value);
        addSetting('strength',s);
        const r=document.createElement('input'); r.type='range'; r.min=0.01; r.max=0.5; r.step=0.01; r.value=brushParams.radius;
        r.oninput=e=>brushParams.radius=parseFloat(e.target.value);
        addSetting('radius',r);
        const neg=document.createElement('input'); neg.type='checkbox'; neg.checked=brushParams.negativeDyntopo;
        neg.onchange=e=>brushParams.negativeDyntopo=e.target.checked;
        addSetting('negative/dyntopo',neg);
      }
      break;
    case 'drag':
    case 'move':
    case 'wire':
      // similar controls
      {
        const s=document.createElement('input'); s.type='range'; s.min=0.001; s.max=0.2; s.step=0.001; s.value=brushParams.strength;
        s.oninput=e=>brushParams.strength=parseFloat(e.target.value);
        addSetting('strength',s);
        const r=document.createElement('input'); r.type='range'; r.min=0.01; r.max=0.5; r.step=0.01; r.value=brushParams.radius;
        r.oninput=e=>brushParams.radius=parseFloat(e.target.value);
        addSetting('radius',r);
      }
      break;
    case 'paint':
      {
        const c=document.createElement('input'); c.type='color'; c.value=brushParams.color;
        c.oninput=e=>brushParams.color=e.target.value;
        addSetting('color',c);
        const rough=document.createElement('input'); rough.type='range'; rough.min=0; rough.max=1; rough.step=0.01; rough.value=brushParams.roughness;
        rough.oninput=e=>brushParams.roughness=parseFloat(e.target.value);
        addSetting('roughness',rough);
        const met=document.createElement('input'); met.type='range'; met.min=0; met.max=1; met.step=0.01; met.value=brushParams.metallic;
        met.oninput=e=>brushParams.metallic=parseFloat(e.target.value);
        addSetting('metallic',met);
        const la=document.createElement('input'); la.type='checkbox'; la.checked=brushParams.lightAction;
        la.onchange=e=>brushParams.lightAction=e.target.checked;
        addSetting('light action',la);
        const lc=document.createElement('input'); lc.type='color'; lc.value=brushParams.lightColor;
        lc.oninput=e=>brushParams.lightColor=e.target.value;
        addSetting('light color',lc);
      }
      break;
    case 'crease':
      {
        const s=document.createElement('input'); s.type='range'; s.min=0.01; s.max=0.5; s.step=0.01; s.value=brushParams.strength;
        s.oninput=e=>brushParams.strength=parseFloat(e.target.value);
        addSetting('strength',s);
        const r=document.createElement('input'); r.type='range'; r.min=0.01; r.max=0.5; r.step=0.01; r.value=brushParams.radius;
        r.oninput=e=>brushParams.radius=parseFloat(e.target.value);
        addSetting('radius',r);
        const f=document.createElement('input'); f.type='checkbox'; f.checked=brushParams.forceDyntopo;
        f.onchange=e=>brushParams.forceDyntopo=e.target.checked;
        addSetting('force dyntopo',f);
      }
      break;
    case 'CC0':
      {
        const i=document.createElement('input'); i.type='range'; i.min=0; i.max=1; i.step=0.01; i.value=brushParams.intensity;
        i.oninput=e=>brushParams.intensity=parseFloat(e.target.value);
        addSetting('intensity',i);
      }
      break;
    case 'measure':
    case 'transform':
      // no special settings
      break;
  }
}

function buildBrushSelector(){
  const sel=document.getElementById('brush-select');
  Object.keys(brushes).forEach(key=>{
    const opt=document.createElement('option');
    opt.value=key; opt.textContent=brushes[key].display;
    sel.appendChild(opt);
  });
  sel.value=currentBrush;
  sel.onchange=e=>{currentBrush=e.target.value; updateBrushSettingsUI();};
  // negative mode toggle
  const neg = document.createElement('input');
  neg.type='checkbox'; neg.id='negative-toggle';
  neg.onchange = e=>{ negativeMode = e.target.checked; };
  const negLabel = document.createElement('label');
  negLabel.textContent = 'negative mode';
  negLabel.appendChild(neg);
  sel.parentNode.appendChild(negLabel);
  updateBrushSettingsUI();
}

// utility: pretend to apply dyntopo
function applyDyntopo(){
  console.log('dyntopo applied (stub)');
}

// measurement helpers
let measuring = false;
let measurePoints = [];
let measureLine = null;

function finalizeMeasurement(){
  if(measureLine){ scene.remove(measureLine); measureLine.geometry.dispose(); measureLine=null; }
  if(measurePoints.length>1){
    const geo=new THREE.BufferGeometry().setFromPoints(measurePoints);
    const mat=new THREE.LineBasicMaterial({color:0xffff00});
    measureLine=new THREE.Line(geo,mat);
    scene.add(measureLine);
    // place labels as sprites
    measurePoints.forEach((p,i)=>{
      const txt=new THREE.Sprite(new THREE.SpriteMaterial({
        map: createTextTexture((i+1)+'cm'), transparent:true
      }));
      txt.position.copy(p).add(new THREE.Vector3(0,0.02,0));
      txt.scale.set(0.2,0.1,1);
      scene.add(txt);
    });
  }
  measurePoints=[];
}

function createTextTexture(text){
  const canvas=document.createElement('canvas');
  canvas.width=256; canvas.height=128;
  const ctx=canvas.getContext('2d');
  ctx.fillStyle='white'; ctx.font='48px sans-serif'; ctx.fillText(text,10,60);
  const tex=new THREE.CanvasTexture(canvas);
  return tex;
}


// لمس متعدد
const pointers = new Map();
let lastPinchDistance = null;
let isSculpting = false;
let isDraggingMesh = false;

function getPinchDistance(){
  const pts = Array.from(pointers.values());
  if(pts.length<2) return null;
  const dx = pts[0].x-pts[1].x; const dy = pts[0].y-pts[1].y;
  return Math.hypot(dx,dy);
}

function toNDCCoords(x,y){
  return {x:(x/window.innerWidth)*2-1, y:-(y/window.innerHeight)*2+1};
}

function sculptAt(x,y, strength=0.02, radius=0.12, direction=1){
  // direction positive applies outward push, negative pulls
  const ndc = toNDCCoords(x,y);
  raycaster.setFromCamera(ndc, camera);
  const intersects = raycaster.intersectObject(mesh);
  if(!intersects.length) return false;
  const p = intersects[0].point;
  const pos = mesh.geometry.attributes.position;
  for(let i=0;i<pos.count;i++){
    const vx = pos.getX(i), vy=pos.getY(i), vz=pos.getZ(i);
    const d = Math.hypot(vx-p.x, vy-p.y, vz-p.z);
    if(d<radius){
      const fall = (1 - d/radius) * strength * direction;
      const nx = (vx - p.x), ny=(vy-p.y), nz=(vz-p.z);
      const len = Math.hypot(nx,ny,nz)||1;
      pos.setXYZ(i, vx + (nx/len)*fall, vy + (ny/len)*fall, vz + (nz/len)*fall);
    }
  }
  pos.needsUpdate = true;
  mesh.geometry.computeVertexNormals();
  return true;
}

function applyBrush(x,y, isStart=false, dx=0, dy=0){
  const sign = negativeMode ? -1 : 1;
  if(isStart) saveState();
  switch(currentBrush){
    case 'clay':
      sculptAt(x,y,brushParams.strength,brushParams.radius,1*sign);
      break;
    case 'inflate':
      const dir = brushParams.negativeDyntopo?-1:1;
      sculptAt(x,y,brushParams.strength,brushParams.radius,dir*sign);
      if(brushParams.negativeDyntopo) applyDyntopo();
      break;
    case 'remove':
      sculptAt(x,y,brushParams.strength,brushParams.radius,-1*sign);
      break;
    case 'rigging prev':
      // move entire mesh toward pointer similar to drag but stronger
      const ndc=toNDCCoords(x,y);
      raycaster.setFromCamera(ndc,camera);
      const hits=raycaster.intersectObject(mesh);
      if(hits.length){
        mesh.position.add(new THREE.Vector3(dx*0.02, -dy*0.02,0));
      }
      break;
    case 'add':
      // simulate subdivision by reassigning geometry and forcing dyntopo
      applyDyntopo();
      break;
    case 'eye':
      sculptAt(x,y,brushParams.strength,brushParams.radius,-1);
      brushParams.radius = Math.max(0.01, brushParams.radius - 0.1);
      sculptAt(x,y,brushParams.strength,brushParams.radius,1);
      break;
    case 'drag':
      // move vertices toward pointer direction
      {
        const ndc=toNDCCoords(x,y);
        raycaster.setFromCamera(ndc,camera);
        const hits=raycaster.intersectObject(mesh);
        if(hits.length){
          const p=hits[0].point;
          const pos=mesh.geometry.attributes.position;
          for(let i=0;i<pos.count;i++){
            const vx=pos.getX(i), vy=pos.getY(i), vz=pos.getZ(i);
            const d=Math.hypot(vx-p.x,vy-p.y,vz-p.z);
            if(d<brushParams.radius){
              pos.setXYZ(i, vx + dx*0.01*sign, vy - dy*0.01*sign, vz);
            }
          }
          pos.needsUpdate=true; mesh.geometry.computeVertexNormals();
        }
      }
      break;
    case 'move':
      // similar a bit softer
      sculptAt(x,y,brushParams.strength,brushParams.radius,1*sign);
      break;
    case 'paint':
      if(isStart){
        mesh.material.color.set(brushParams.color);
        mesh.material.roughness = brushParams.roughness;
        mesh.material.metalness = brushParams.metallic;
        if(brushParams.lightAction){
          mesh.material.emissive.set(brushParams.lightColor);
        }
      }
      break;
    case 'crease':
      sculptAt(x,y,brushParams.strength*2,brushParams.radius,1*sign);
      if(brushParams.forceDyntopo) applyDyntopo();
      break;
    case 'CC0':
      // jitter
      {
        const ndc2=toNDCCoords(x,y);
        raycaster.setFromCamera(ndc2,camera);
        const hits2=raycaster.intersectObject(mesh);
        if(hits2.length){
          const p=hits2[0].point;
          const pos=mesh.geometry.attributes.position;
          for(let i=0;i<pos.count;i++){
            const vx=pos.getX(i), vy=pos.getY(i), vz=pos.getZ(i);
            const d=Math.hypot(vx-p.x,vy-p.y,vz-p.z);
            if(d<brushParams.radius){
              const jitter=(Math.random()-0.5)*brushParams.intensity;
              pos.setXYZ(i, vx + jitter, vy + jitter, vz + jitter);
            }
          }
          pos.needsUpdate=true; mesh.geometry.computeVertexNormals();
        }
      }
      break;
    case 'wire':
      sculptAt(x,y,brushParams.strength,brushParams.radius,1*sign);
      sculptAt(x,y,brushParams.strength/2,brushParams.radius/2,-1*sign);
      break;
    case 'measure':
      // tracking in pointermove
      break;
    case 'transform':
      // handled in move events
      break;
  }
}

// Pointer events handle multi-touch and mouse
renderer.domElement.addEventListener('pointerdown', (e)=>{
  renderer.domElement.setPointerCapture(e.pointerId);
  pointers.set(e.pointerId, {x:e.clientX, y:e.clientY, type:e.pointerType});

  if(pointers.size===1){
    const ndc = toNDCCoords(e.clientX, e.clientY);
    raycaster.setFromCamera(ndc, camera);
    const hits = raycaster.intersectObject(mesh);
    isSculpting = hits.length>0;
    if(isSculpting){
      applyBrush(e.clientX, e.clientY, true);
    }
    if(currentBrush==='transform' && hits.length){
      // begin transform
      isDraggingMesh = true;
    }
    if(currentBrush==='measure' && hits.length){
      measuring = true; measurePoints=[hits[0].point.clone()];
    }
  }
  if(pointers.size===2){
    lastPinchDistance = getPinchDistance();
  }
});

renderer.domElement.addEventListener('pointermove', (e)=>{
  if(!pointers.has(e.pointerId)) return;
  const prev = pointers.get(e.pointerId);
  const dx = e.clientX - prev.x;
  const dy = e.clientY - prev.y;
  pointers.set(e.pointerId, {x:e.clientX, y:e.clientY, type:e.pointerType});

  if(pointers.size===1){
    if(isSculpting){
      applyBrush(e.clientX, e.clientY, false, dx, dy);
    } else if(currentBrush==='transform' && isDraggingMesh){
      // translate mesh according to pointer movement in screen space
      const dir=new THREE.Vector3(dx/100, -dy/100,0);
      mesh.position.add(dir);
    } else if(measuring){
      const ndc = toNDCCoords(e.clientX, e.clientY);
      raycaster.setFromCamera(ndc, camera);
      const hits = raycaster.intersectObject(mesh);
      if(hits.length){
        measurePoints.push(hits[0].point.clone());
      }
    } else {
      // orbit
      controls.rotateLeft(dx * 0.005);
      controls.rotateUp(dy * 0.005);
    }
  } else if(pointers.size===2){
    const pts = Array.from(pointers.values());
    const newDist = getPinchDistance();
    if(lastPinchDistance!==null){
      const diff = newDist - lastPinchDistance;
      camera.position.addScaledVector(camera.getWorldDirection(new THREE.Vector3()), -diff*0.005);
    }
    lastPinchDistance = newDist;
  }
});

renderer.domElement.addEventListener('pointerup', (e)=>{
  pointers.delete(e.pointerId);
  renderer.domElement.releasePointerCapture(e.pointerId);
  if(pointers.size<2) lastPinchDistance = null;
  if(pointers.size===0){
    isSculpting = false;
    isDraggingMesh = false;
    if(measuring){ finalizeMeasurement(); measuring=false; }
  }
});

window.addEventListener('resize', ()=>{
  camera.aspect = window.innerWidth/window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// initialize UI
buildBrushSelector();
setupMenus();

function setupMenus(){
  document.querySelectorAll('#menu-bar .menu').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const name = btn.dataset.menu + '-menu';
      document.querySelectorAll('.submenu').forEach(s=>{ if(s.id===name) s.style.display = (s.style.display==='block'? 'none':'block'); else s.style.display='none'; });
    });
  });
  // file submenu actions
  document.getElementById('file-menu').addEventListener('click', e=>{
    const act = e.target.dataset.action;
    if(!act) return;
    handleFileAction(act);
  });
  // edit submenu actions
  document.getElementById('edit-menu').addEventListener('click', e=>{
    const act = e.target.dataset.action;
    if(!act) return;
    handleEditAction(act);
  });
  // window submenu actions
  document.getElementById('window-menu').addEventListener('change', e=>{
    const act = e.target.dataset.action;
    if(!act) return;
    handleWindowAction(act, e.target);
  });
  document.getElementById('window-menu').addEventListener('input', e=>{
    const act = e.target.dataset.action;
    if(!act) return;
    handleWindowAction(act, e.target);
  });
}

function handleEditAction(action){
  switch(action){
    case 'undo':
      undo();
      break;
    case 'redo':
      redo();
      break;
    case 'add-cube':
      addCube();
      break;
    case 'add-sphere':
      addSphere();
      break;
    case 'add-cylinder':
      addCylinder();
      break;
    case 'add-torus':
      addTorus();
      break;
    case 'add-cone':
      addCone();
      break;
    case 'add-pyramid':
      addPyramid();
      break;
  }
}

function handleWindowAction(action, el){
  switch(action){
    case 'toggle-ui':
      showUIEnabled = el.checked;
      const ui = document.getElementById('ui');
      ui.classList.toggle('hide-ui', !showUIEnabled);
      break;
    case 'toggle-hotkeys':
      hotkeysEnabled = el.checked;
      if(hotkeysEnabled) setupHotkeys();
      break;
    case 'camera-speed':
      cameraSpeedMult = parseFloat(el.value) / 0.005;
      controls.dampingFactor = 0.07 * cameraSpeedMult;
      break;
    case 'ui-scale':
      uiScale = parseFloat(el.value);
      const ui2 = document.getElementById('ui');
      ui2.classList.remove('scale-reduced', 'scale-normal', 'scale-enlarged');
      if(uiScale < 0.8) ui2.classList.add('scale-reduced');
      else if(uiScale > 1.2) ui2.classList.add('scale-enlarged');
      else ui2.classList.add('scale-normal');
      break;
    case 'bg-color':
      scene.background = new THREE.Color(el.value);
      break;
    case 'ui-color':
      const hue = parseInt(el.value.substring(1), 16) % 360;
      document.getElementById('ui').style.filter = `hue-rotate(${hue}deg) brightness(0.8)`;
      break;
  }
}

function setupHotkeys(){
  if(window._hotkeysBound) return;
  window._hotkeysBound = true;
  window.addEventListener('keydown', e=>{
    if(!hotkeysEnabled) return;
    if(e.ctrlKey || e.metaKey) return;
    const key = e.key;
    document.querySelectorAll('button[data-action]').forEach(btn=>{
      if(btn.textContent.endsWith(key + ')')){
        e.preventDefault();
        btn.click();
      }
    });
  });
}

function handleFileAction(action){
  switch(action){
    case 'new':
      if(confirm('Are you sure you want to clear the object?')){
        // reset mesh
        mesh.geometry.dispose();
        mesh.geometry = new THREE.SphereGeometry(1,128,128);
      }
      break;
    case 'import':
      const inp = document.createElement('input');
      inp.type='file';
      // allow many extensions
      inp.accept = '.obj,.fbx,.glb,.gltf,.ply,.stl,.dae,.3ds,.blend,.x3d,.off,.3mf,.svg,.amf,.wrl,.x,.lwo,.lws,.ac,.ac3d,.ase,.cob,.x,.bvh,.vrml,.xsi,.dxf,.fbx,.gltf,.js,.json,.pbobjs,.ply,.prwm,.stl,.wrl';
      inp.onchange = e=>{
        const file = e.target.files[0];
        if(!file) return;
        alert('imported '+file.name+' (format:'+file.type+')');
        // stub: real parsing would go here
      };
      inp.click();
      break;
    case 'export':
      const fmt = prompt('Choose format (fbx,glb,ply,blend,obj):');
      if(!fmt) break;
      const bin = confirm('binary? OK=yes ASCII=no');
      // stub: create simple OBJ for now
      let data='';
      if(fmt==='obj'){
        const pos=mesh.geometry.attributes.position;
        for(let i=0;i<pos.count;i++){
          data += `v ${pos.getX(i)} ${pos.getY(i)} ${pos.getZ(i)}\n`;
        }
      } else {
        data = 'exported '+fmt+' (binary='+bin+')';
      }
      const blob = new Blob([data],{type:'application/octet-stream'});
      const url = URL.createObjectURL(blob);
      const a=document.createElement('a');
      a.href=url; a.download='model.'+fmt;
      a.click();
      URL.revokeObjectURL(url);
      break;
    case 'fix':
      alert('Topological fix (stub)');
      break;
  }
}

function animate(){
  requestAnimationFrame(animate);
  controls.update();
  updateMemoryDisplay();
  renderer.render(scene, camera);
}
animate();
