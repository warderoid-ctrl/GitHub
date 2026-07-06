import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';

// Scene setup
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0a0a);  // Dark background color

// Camera setup
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 5000);

// Store initial camera position and rotation
const initialCameraPosition = new THREE.Vector3(0, 1.6, 5);
const initialCameraRotation = new THREE.Euler(0, 0, 0, 'XYZ');

// Set camera to initial position and rotation
camera.position.copy(initialCameraPosition);
camera.rotation.copy(initialCameraRotation);

// Renderer setup
const renderer = new THREE.WebGLRenderer();
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// Lighting
const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
scene.add(ambientLight);

const directionalLight = new THREE.DirectionalLight(0xff00ff, 1);  // Magenta color
directionalLight.position.set(5, 5, 5);
scene.add(directionalLight);

// PointerLockControls for camera movement
const controls = new PointerLockControls(camera, document.body);
document.addEventListener('click', () => {
    controls.lock();
});

// Variables for camera movement
let moveForward = false;
let moveBackward = false;
let moveLeft = false;
let moveRight = false;
let moveUp = false;
let moveDown = false;
const moveSpeed = 0.8;

// WASD + Space (up) and Shift (down) movement controls
document.addEventListener('keydown', (event) => {
    switch (event.code) {
        case 'KeyW':
            moveForward = true;
            break;
        case 'KeyS':
            moveBackward = true;
            break;
        case 'KeyA':
            moveLeft = true;
            break;
        case 'KeyD':
            moveRight = true;
            break;
        case 'Space':  // Move up
            moveUp = true;
            break;
        case 'ShiftLeft':  // Move down
            moveDown = true;
            break;
        case 'KeyR':  // Reset camera when "R" is pressed
            resetCamera();
            break;
    }
});

document.addEventListener('keyup', (event) => {
    switch (event.code) {
        case 'KeyW':
            moveForward = false;
            break;
        case 'KeyS':
            moveBackward = false;
            break;
        case 'KeyA':
            moveLeft = false;
            break;
        case 'KeyD':
            moveRight = false;
            break;
        case 'Space':  // Stop moving up
            moveUp = false;
            break;
        case 'ShiftLeft':  // Stop moving down
            moveDown = false;
            break;
    }
});





// Create a video element
const video = document.createElement('video');
video.src = 'Video/AR1.mp4';  // Replace with the path to your video
video.load();  // Load the video
video.muted = true;  // Optionally mute the video
video.loop = true;   // Loop the video
video.play();        // Start playing the video

// Create a video texture
const videoTexture = new THREE.VideoTexture(video);
videoTexture.minFilter = THREE.LinearFilter;  // Set the min filter
videoTexture.magFilter = THREE.LinearFilter;  // Set the mag filter
videoTexture.format = THREE.RGBFormat;

// Create a plane material using the video texture
const videoMaterial = new THREE.MeshBasicMaterial({ map: videoTexture, side: THREE.DoubleSide });

// Create a plane geometry
const videoPlaneGeometry = new THREE.PlaneGeometry(200, 100);

// Create the plane mesh with video material
const videoPlane = new THREE.Mesh(videoPlaneGeometry, videoMaterial);

// Position the plane in the scene
videoPlane.position.set(0, 60, 1000);  // Adjust this based on where you want the video to appear

// Add the video plane to the scene
scene.add(videoPlane);

// Define variables for circular rotation
let radius = 1000;  // The distance of the plane from the camera
let angle = 0;      // The current angle of rotation
let rotationSpeed = 0.001;  // Speed of rotation

// Global references to the STL meshes with speeds and rotation axes
let stlMeshes = [];

// Function to load an STL file with custom rotation parameters
function loadSTLFile(filePath, position, color, rotationAxis, rotationSpeed) {
    const loader = new STLLoader();
    loader.load(filePath, function (geometry) {
        geometry.center();  // Center the geometry on its origin
        const material = new THREE.MeshPhongMaterial({
            color: color || 0x7777ff,  // Default color or provided color
            side: THREE.DoubleSide
        });

        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.copy(position);  // Set the position of the mesh

        // Add custom rotation properties
        mesh.userData = { rotationAxis, rotationSpeed };

        scene.add(mesh);
        stlMeshes.push(mesh);  // Store the mesh with rotation data in the array
    });
}


loadSTLFile('STLs/leafScan.stl', new THREE.Vector3(0, 0, 200), 0x7777ff, 'y', 0.01);  // First STL at position (0, 0, -3)
loadSTLFile('STLs/pineCone.stl', new THREE.Vector3(300, 100, -150), 0xff7777, 'z', .004);  // Second STL at position (3, 0, -3)
loadSTLFile('STLs/waterBird.stl', new THREE.Vector3(-300, -1000, 50), 0x77ff77, 'x', .05);  // Third STL at position (-3, 0, -3)

// Add a particle system for shimmering effect
const particleCount = 2000;
const particlesGeometry = new THREE.BufferGeometry();
const positions = new Float32Array(particleCount * 3);  // 3 coordinates (x, y, z) for each particle

for (let i = 0; i < particleCount * 3; i++) {
    positions[i] = (Math.random() - 0.5) * 5000;
}

particlesGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

const particlesMaterial = new THREE.PointsMaterial({
    color: 0xffffff,
    size: 0.3,
    transparent: true,
    opacity: 0.8
});

const particles = new THREE.Points(particlesGeometry, particlesMaterial);
scene.add(particles);

// Reset the camera to its initial position and rotation
function resetCamera() {
    camera.position.copy(initialCameraPosition);
    camera.rotation.copy(initialCameraRotation);
    controls.update();
}

// Fly movement
function flyMove() {
    const direction = new THREE.Vector3(); // Create a new direction vector

    if (moveForward) {
        camera.getWorldDirection(direction);  // Get the direction the camera is facing
        camera.position.addScaledVector(direction, moveSpeed);  // Move forward in that direction
    }
    if (moveBackward) {
        camera.getWorldDirection(direction);  // Get the direction the camera is facing
        camera.position.addScaledVector(direction, -moveSpeed);  // Move backward
    }
    if (moveLeft) {
        camera.getWorldDirection(direction);
        camera.position.x -= moveSpeed;  // Move left on the X-axis
    }
    if (moveRight) {
        camera.getWorldDirection(direction);
        camera.position.x += moveSpeed;  // Move right on the X-axis
    }
    if (moveUp) {
        camera.position.y += moveSpeed;   // Move up on the Y-axis
    }
    if (moveDown) {
        camera.position.y -= moveSpeed;  // Move down on the Y-axis
    }
}

// Animation loop
function animate() {
    requestAnimationFrame(animate);


    // Update the angle to rotate the plane
    angle += rotationSpeed/2;

    // Calculate the new position of the plane based on the angle
    const x = radius * Math.cos(angle);
    const z = radius * Math.sin(angle);

    // Set the new position of the video plane around the camera
    videoPlane.position.set(x, 60, z);

    // Ensure the plane is always facing the camera
    videoPlane.lookAt(camera.position);

    // Rotate each STL model based on its axis and speed
    stlMeshes.forEach(mesh => {
        switch (mesh.userData.rotationAxis) {
            case 'x':
                mesh.rotation.x += mesh.userData.rotationSpeed;
                break;
            case 'y':
                mesh.rotation.y += mesh.userData.rotationSpeed;
                break;
            case 'z':
                mesh.rotation.z += mesh.userData.rotationSpeed;
                break;
        }
    });

    // Move the camera based on WASD and Space/Shift input
    if (controls.isLocked) {
        flyMove();  // Call the flying movement logic
    }

    // Animate the particles (create shimmer effect)
    particles.rotation.y += 0.0001;  // Slowly rotate particles to create a dynamic effect

    renderer.render(scene, camera);
}

// Handle window resize
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

animate();  // Start the animation