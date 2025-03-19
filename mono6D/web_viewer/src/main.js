// main.js - RGBD Video Viewer for Quest
import * as THREE from 'three';
import { VRButton } from 'three/examples/jsm/webxr/VRButton.js';
import { XRControllerModelFactory } from 'three/examples/jsm/webxr/XRControllerModelFactory.js';

// Load shader files
import bgSimpleVertexShader from './shaders/VertexShader-bg_simple.js';
import bgSimpleFragmentShader from './shaders/FragmentShader-bg_simple.js';
import fgSimpleVertexShader from './shaders/VertexShader-fg_simple.js';
import fgSimpleFragmentShader from './shaders/FragmentShader-fg_simple.js';
import movSimpleVertexShader from './shaders/VertexShader-mov_simple.js';
import movSimpleFragmentShader from './shaders/FragmentShader-mov_simple.js';

// Scene setup
let scene, camera, renderer;
let controllerGrip1, controllerGrip2;
let rgbdPlayer;

// load assets
const filenames = 'bishop01_1';

const videoPath = `./video/${filename}.mp4`;
const depthVideoPath = `./video/${filename}_depth.mp4`;
const alphaVideoPath = `./video/${filename}_alphaproc.mp4`;

const extrapolatedImagePath = `./video/${filename}_BG.png`;
const extrapolatedDepthPath = `./video/${filename}_BGD.png`;
const extrapolatedAlphaPath = `./video/${filename}_BGA.png`;

const inpaintImagePath = `./video/${filename}_BG_inp.png`;
const inpaintDepthPath = `./video/${filename}_BGD_inp.png`;

// Initialize the app
function init() {
  // Create scene
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);
  
  // Create camera
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 2000);
  camera.position.set(0, 0, 0);
  // camera added automatically
  
  // Set up renderer with proper transparency handling
  setupRenderer();
  
  // Handle window resize
  window.addEventListener('resize', onWindowResize, false);
  
  // Set up controllers
  setupControllers();
  
  // Load media assets
  loadAssets().then(() => {
    // Create RGBD player when assets are loaded
    rgbdPlayer = new RGBDVideoPlayer();
    rgbdPlayer.addToScene(scene);
    rgbdPlayer.setLayerCount(3); // Enable all layers by default
    
    console.log('RGBD player ready');
  });
  
  // Start animation loop
  renderer.setAnimationLoop(animate);
}

// maybe optional, pending delete
function onWindowResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

// Handle XR controllers
function setupControllers() {
  const controllerModelFactory = new XRControllerModelFactory();
  
  // Controller 1
  const controller1 = renderer.xr.getController(0);
  controller1.addEventListener('selectstart', onSelectStart);
  controller1.addEventListener('selectend', onSelectEnd);
  scene.add(controller1);

  // Controller 2
  const controller2 = renderer.xr.getController(1);
  controller2.addEventListener('selectstart', onSelectStart);
  controller2.addEventListener('selectend', onSelectEnd);
  scene.add(controller2);

  // Controller grips for visualizing controllers
  controllerGrip1 = renderer.xr.getControllerGrip(0);
  controllerGrip1.add(controllerModelFactory.createControllerModel(controllerGrip1));
  scene.add(controllerGrip1);

  controllerGrip2 = renderer.xr.getControllerGrip(1);
  controllerGrip2.add(controllerModelFactory.createControllerModel(controllerGrip2));
  scene.add(controllerGrip2);
}

// Controller event handlers
function onSelectStart(event) {
  if (rgbdPlayer) {
    rgbdPlayer.togglePlayback();
  }
}

function onSelectEnd(event) {
  // TODO: pause or quit the player, back to menu
}

// Asset loading management
let assets = {
  videoElement: null,
  depthVideoElement: null,
  alphaVideoElement: null,
  extrapolatedTexture: null,
  extrapolatedDepth: null,
  extrapolatedAlpha: null,
  inpaintTexture: null,
  inpaintDepth: null
};

async function loadAssets() {
  // Create video elements
  assets.videoElement = document.createElement('video');
  assets.videoElement.src = videoPath;
  assets.videoElement.loop = true;
  assets.videoElement.muted = true;
  assets.videoElement.crossOrigin = 'anonymous';
  assets.videoElement.preload = 'auto';
  
  assets.depthVideoElement = document.createElement('video');
  assets.depthVideoElement.src = depthVideoPath;
  assets.depthVideoElement.loop = true;
  assets.depthVideoElement.muted = true;
  assets.depthVideoElement.crossOrigin = 'anonymous';
  assets.depthVideoElement.preload = 'auto';
  
  assets.alphaVideoElement = document.createElement('video');
  assets.alphaVideoElement.src = alphaVideoPath;
  assets.alphaVideoElement.loop = true;
  assets.alphaVideoElement.muted = true;
  assets.alphaVideoElement.crossOrigin = 'anonymous';
  assets.alphaVideoElement.preload = 'auto';
  
  // Load all image textures
  const textureLoader = new THREE.TextureLoader();
  const loadTexture = (path) => {
    return new Promise((resolve) => {
      textureLoader.load(path, (texture) => {
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        resolve(texture);
      });
    });
  };
  
  const [extrapolatedTexture, extrapolatedDepth, extrapolatedAlpha, inpaintTexture, inpaintDepth] = await Promise.all([
    loadTexture(extrapolatedImagePath),
    loadTexture(extrapolatedDepthPath),
    loadTexture(extrapolatedAlphaPath),
    loadTexture(inpaintImagePath),
    loadTexture(inpaintDepthPath)
  ]);
  
  assets.extrapolatedTexture = extrapolatedTexture;
  assets.extrapolatedDepth = extrapolatedDepth;
  assets.extrapolatedAlpha = extrapolatedAlpha;

  assets.inpaintTexture = inpaintTexture;
  assets.inpaintDepth = inpaintDepth;
  
  return assets;
}

// Main Layered Video Player class
class RGBDVideoPlayer {
  constructor() {
    // Create video textures
    this.videoTexture = new THREE.VideoTexture(assets.videoElement);
    this.videoTexture.minFilter = THREE.LinearFilter;
    this.videoTexture.magFilter = THREE.LinearFilter;
    
    this.depthTexture = new THREE.VideoTexture(assets.depthVideoElement);
    this.depthTexture.minFilter = THREE.LinearFilter;
    this.depthTexture.magFilter = THREE.LinearFilter;
    
    this.alphaTexture = new THREE.VideoTexture(assets.alphaVideoElement);
    this.alphaTexture.minFilter = THREE.LinearFilter;
    this.alphaTexture.magFilter = THREE.LinearFilter;
    
    // Create panoramic geometry for spherical viewing
    this.radius = 6;
    this.geometry = new THREE.SphereGeometry(this.radius, 256, 256);
    this.geometry.scale(-1, 1, 1); // Invert to view from inside
    
    // Setup the different rendering layers
    this.setupLayers();
    
    this.sphereCenter = new THREE.Vector3(0, 0, 0);
    this.worldMatrix = new THREE.Matrix4();
    this.layerCount = 3;
  }
  
  setupLayers() {
    // Layer 1: Inpainted Layer
    this.bgSimpleMaterial = new THREE.ShaderMaterial({
      uniforms: {
        bgtext: { value: assets.inpaintTexture },
        depthbg: { value: assets.inpaintDepth },
        depthfg: { value: assets.extrapolatedDepth },
        depthfront: { value: this.depthTexture },
        matWVP: { value: new THREE.Matrix4() },
        desat: { value: 0.0 },
        colored: { value: 0.0 }
      },
      vertexShader: bgSimpleVertexShader,
      fragmentShader: bgSimpleFragmentShader,
    });
    this.bgLayer = new THREE.Mesh(this.geometry, this.bgSimpleMaterial);
    
    // Layer 2: Extrapolated Layer
    this.fgSimpleMaterial = new THREE.ShaderMaterial({
      uniforms: {
        fgtext: { value: assets.extrapolatedTexture },
        fgdepth: { value: assets.extrapolatedDepth },
        alphamask: { value: assets.extrapolatedAlpha },
        frontdepth: { value: this.depthTexture },
        matWVP2: { value: new THREE.Matrix4() },
        desat: { value: 0.0 },
        colored: { value: 0.0 }
      },
      vertexShader: fgSimpleVertexShader,
      fragmentShader: fgSimpleFragmentShader,
      transparent: true,
    });
    this.fgLayer = new THREE.Mesh(this.geometry, this.fgSimpleMaterial);
    
    // Layer 3: Foreground layer
    this.foregroundMat = new THREE.ShaderMaterial({
      uniforms: {
        fgtext: { value: this.videoTexture },
        fgdepth: { value: this.depthTexture },
        alphamask: { value: this.alphaTexture },
        Fragfgdepth: { value: this.depthTexture },
        matWVP2: { value: new THREE.Matrix4() },
        matW2: { value: new THREE.Matrix4() },
        ViewDir2: { value: new THREE.Matrix4() },
        SphCenter2: { value: new THREE.Vector3(0, 0, 0) },
        eyepos: { value: new THREE.Vector3(0, 0, 0) },
        headposition: { value: new THREE.Vector3(0, 0, 0) },
        spherecenter: { value: new THREE.Vector3(0, 0, 0) },
        desat: { value: 0.0 },
        colored: { value: 0.0 }
      },
      vertexShader: movSimpleVertexShader,
      fragmentShader: movSimpleFragmentShader,
      transparent: true,
    });
    this.movLayer = new THREE.Mesh(this.geometry, this.foregroundMat);

    this.bgLayer.renderOrder = 0;
    this.fgLayer.renderOrder = 1;
    this.movLayer.renderOrder = 2;
    
    // Group all layers
    this.group = new THREE.Group();
    this.group.add(this.bgLayer);
    this.group.add(this.fgLayer);
    this.group.add(this.movLayer);

    this.group.position.set(0, 1.7, 0);
  }
  
  addToScene(scene) {
    scene.add(this.group);
  }
  
  togglePlayback() {
    if (assets.videoElement.paused) {
      assets.videoElement.play();
      assets.depthVideoElement.play();
      assets.alphaVideoElement.play();
      // synchronize videos
      assets.depthVideoElement.currentTime = assets.videoElement.currentTime;
      assets.alphaVideoElement.currentTime = assets.videoElement.currentTime;
    } else {
      assets.videoElement.pause();
      assets.depthVideoElement.pause();
      assets.alphaVideoElement.pause();
    }
  }

  recenterCamera() {
    // recenter to the center of projection
    camera.position.set(0, 0, 0);
  }
  
  update(camera) {
    if (!camera) return;
    
    // Get the world matrix of the group
    this.worldMatrix.copy(this.group.matrixWorld);
    
    // Calculate sphere center in world space
    this.sphereCenter.set(0, 0, 0).applyMatrix4(this.worldMatrix);
    
    if (renderer.xr.isPresenting) {
      // XR mode - get the head position and update matrices for each eye
      const xrCamera = renderer.xr.getCamera();
      const headPosition = new THREE.Vector3().setFromMatrixPosition(xrCamera.matrixWorld);
      
      // Set up eye-specific updates through the onBeforeRender callback
      const onBeforeRender = (renderer, scene, camera, geometry, material, group) => {
        // Get view and projection matrices for the current eye
        const viewMatrix = camera.matrixWorldInverse;
        const projectionMatrix = camera.projectionMatrix;
        
        // Get eye position
        const eyePosition = new THREE.Vector3().setFromMatrixPosition(camera.matrixWorld);
        
        // Calculate combined matrices
        const mvpMatrix = new THREE.Matrix4()
          .multiplyMatrices(projectionMatrix, viewMatrix)
          .multiply(this.worldMatrix);
        
        // Calculate view direction matrix
        const viewDir = new THREE.Matrix4().lookAt(
          eyePosition,
          this.sphereCenter,
          new THREE.Vector3(0, 1, 0)
        );
        
        // Update based on which material/layer we're rendering
        if (material === this.bgSimpleMaterial) {
          // Background layer
          material.uniforms.matWVP.value.copy(mvpMatrix);
          material.uniforms.desat.value = 0.0;
          material.uniforms.colored.value = 0.0;
        } 
        else if (material === this.fgSimpleMaterial) {
          // Extrapolated layer
          material.uniforms.matWVP2.value.copy(mvpMatrix);
          material.uniforms.desat.value = 0.0;
          material.uniforms.colored.value = 0.0;
        } 
        else if (material === this.foregroundMat) {
          // Foreground video layer
          material.uniforms.matWVP2.value.copy(mvpMatrix);
          material.uniforms.matW2.value.copy(this.worldMatrix);
          material.uniforms.ViewDir2.value.copy(viewDir);
          material.uniforms.SphCenter2.value.copy(this.sphereCenter);
          material.uniforms.spherecenter.value.copy(this.sphereCenter);
          material.uniforms.eyepos.value.copy(eyePosition);
          material.uniforms.headposition.value.copy(headPosition);
          material.uniforms.desat.value = 0.0;
          material.uniforms.colored.value = 0.0;
        }
      };
      
      // Apply the callback to all layers
      this.bgLayer.onBeforeRender = onBeforeRender;
      this.fgLayer.onBeforeRender = onBeforeRender;
      this.movLayer.onBeforeRender = onBeforeRender;
    } 
    else {
      // Non-VR mode - simpler update
      const viewMatrix = camera.matrixWorldInverse;
      const projectionMatrix = camera.projectionMatrix;
      const eyePosition = camera.position.clone();
      
      // Calculate combined matrices
      const mvpMatrix = new THREE.Matrix4()
        .multiplyMatrices(projectionMatrix, viewMatrix)
        .multiply(this.worldMatrix);
        
      // Calculate view direction matrix
      const viewDir = new THREE.Matrix4().lookAt(
        eyePosition,
        this.sphereCenter,
        new THREE.Vector3(0, 1, 0)
      );
      
      // Update all materials directly
      // Background layer
      this.bgSimpleMaterial.uniforms.matWVP.value.copy(mvpMatrix);
      this.bgSimpleMaterial.uniforms.desat.value = 0.0;
      this.bgSimpleMaterial.uniforms.colored.value = 0.0;
      
      // Extrapolated layer
      this.fgSimpleMaterial.uniforms.matWVP2.value.copy(mvpMatrix);
      this.fgSimpleMaterial.uniforms.desat.value = 0.0;
      this.fgSimpleMaterial.uniforms.colored.value = 0.0;
      
      // Foreground video layer
      this.foregroundMat.uniforms.matWVP2.value.copy(mvpMatrix);
      this.foregroundMat.uniforms.matW2.value.copy(this.worldMatrix);
      this.foregroundMat.uniforms.ViewDir2.value.copy(viewDir);
      this.foregroundMat.uniforms.SphCenter2.value.copy(this.sphereCenter);
      this.foregroundMat.uniforms.spherecenter.value.copy(this.sphereCenter);
      this.foregroundMat.uniforms.eyepos.value.copy(eyePosition);
      this.foregroundMat.uniforms.headposition.value.copy(eyePosition);
      this.foregroundMat.uniforms.desat.value = 0.0;
      this.foregroundMat.uniforms.colored.value = 0.0;
    }
  }
  
  // Add method to set layer visibility
  setLayerCount(count) {
    this.layerCount = Math.max(1, Math.min(3, count));
    
    // Always show background
    this.bgLayer.visible = true;
    
    // Show/hide extrapolated layer
    this.fgLayer.visible = this.layerCount >= 2;
    
    // Show/hide foreground video layer
    this.movLayer.visible = this.layerCount >= 3;
  }
  
  // Add method to set desaturation and coloring effects
  setVisualEffects(desaturation, colored) {
    // Update all materials
    this.bgSimpleMaterial.uniforms.desat.value = desaturation;
    this.bgSimpleMaterial.uniforms.colored.value = colored ? 1.0 : 0.0;
    
    this.fgSimpleMaterial.uniforms.desat.value = desaturation;
    this.fgSimpleMaterial.uniforms.colored.value = colored ? 1.0 : 0.0;
    
    this.foregroundMat.uniforms.desat.value = desaturation;
    this.foregroundMat.uniforms.colored.value = colored ? 1.0 : 0.0;
  }
}

// Additional renderer setup for proper transparency handling
function setupRenderer() {
  renderer = new THREE.WebGLRenderer({ 
    antialias: true,
    alpha: true
  });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.xr.enabled = true;
  
  // Set up transparency and depth testing
  renderer.setClearColor(0x000000, 0);
  renderer.autoClear = false;
  
  // Modify render loop for proper transparency handling
  const originalSetAnimationLoop = renderer.setAnimationLoop;
  renderer.setAnimationLoop = function(callback) {
    originalSetAnimationLoop.call(this, function() {
      // Clear the buffers
      renderer.clear();
      
      // Render the scene
      if (callback) callback();
    });
  };
  
  document.body.appendChild(renderer.domElement);
  document.body.appendChild(VRButton.createButton(renderer));
}

// animate loop
function animate() {
  if (rgbdPlayer) {
    rgbdPlayer.update(camera);
  }
  
  renderer.render(scene, camera);
}

// Initialize the application
init();