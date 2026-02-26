const canvas = document.getElementById('glcanvas');
const renderer = new THREE.WebGLRenderer({canvas});
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, window.innerWidth/window.innerHeight, 0.1, 100);
camera.position.set(0,0,5);

renderer.setSize(window.innerWidth, window.innerHeight);

const light = new THREE.DirectionalLight(0xffffff,1);
light.position.set(0,1,1);
scene.add(light);

// شبكة بسيطة
gridHelper = new THREE.GridHelper(10,10,0x888888,0x444444);
scene.add(gridHelper);

function animate(){
    requestAnimationFrame(animate);
    renderer.render(scene,camera);
}
animate();
