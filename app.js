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

// لمس متعدد
const pointers = new Map();
let lastPinchDistance = null;
let isSculpting = false;

function getPinchDistance(){
  const pts = Array.from(pointers.values());
  if(pts.length<2) return null;
  const dx = pts[0].x-pts[1].x; const dy = pts[0].y-pts[1].y;
  return Math.hypot(dx,dy);
}

function toNDCCoords(x,y){
  return {x:(x/window.innerWidth)*2-1, y:-(y/window.innerHeight)*2+1};
}

function sculptAt(x,y, strength=0.02, radius=0.12){
  // raycast
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
      const fall = (1 - d/radius) * strength;
      const nx = (vx - p.x), ny=(vy-p.y), nz=(vz-p.z);
      const len = Math.hypot(nx,ny,nz)||1;
      pos.setXYZ(i, vx + (nx/len)*fall, vy + (ny/len)*fall, vz + (nz/len)*fall);
    }
  }
  pos.needsUpdate = true;
  mesh.geometry.computeVertexNormals();
  return true;
}

// Pointer events handle multi-touch and mouse
renderer.domElement.addEventListener('pointerdown', (e)=>{
  renderer.domElement.setPointerCapture(e.pointerId);
  pointers.set(e.pointerId, {x:e.clientX, y:e.clientY, type:e.pointerType});

  if(pointers.size===1){
    // test if touching mesh
    const ndc = toNDCCoords(e.clientX, e.clientY);
    raycaster.setFromCamera(ndc, camera);
    const hits = raycaster.intersectObject(mesh);
    isSculpting = hits.length>0;
    if(isSculpting){
      sculptAt(e.clientX, e.clientY, 0.03, 0.12);
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
      sculptAt(e.clientX, e.clientY, 0.015, 0.12);
    } else {
      // orbit: rotate using OrbitControls by simulating mouse
      controls.rotateLeft(dx * 0.005);
      controls.rotateUp(dy * 0.005);
    }
  } else if(pointers.size===2){
    const pts = Array.from(pointers.values());
    const newDist = getPinchDistance();
    if(lastPinchDistance!==null){
      const diff = newDist - lastPinchDistance;
      // small diff -> interpret as pan when both fingers move same direction
      const mvA = {x:pts[0].x - prev.x, y: pts[0].y - prev.y};
      // simple zoom
      camera.position.addScaledVector(camera.getWorldDirection(new THREE.Vector3()), -diff*0.005);
    }
    lastPinchDistance = newDist;
  }
});

renderer.domElement.addEventListener('pointerup', (e)=>{
  pointers.delete(e.pointerId);
  renderer.domElement.releasePointerCapture(e.pointerId);
  if(pointers.size<2) lastPinchDistance = null;
  if(pointers.size===0) isSculpting = false;
});

window.addEventListener('resize', ()=>{
  camera.aspect = window.innerWidth/window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

function animate(){
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();
