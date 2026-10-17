"""Lightweight browser-side Three.js volcano cutaway model."""
from __future__ import annotations

import json


def volcano_scene_html(
    labels: dict[str, str],
    volcano_type: str,
    pressure: int,
    gas_content: int,
    viscosity: int,
) -> str:
    config = {
        "type": volcano_type,
        "pressure": pressure,
        "gas": gas_content,
        "viscosity": viscosity,
        "labels": labels,
    }
    config_json = json.dumps(config, ensure_ascii=False).replace("</", "<\\/")
    template = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* { box-sizing: border-box; }
html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; background: #c9eef3; font-family: 'Nunito', 'Avenir Next', sans-serif; }
#frame { position: relative; width: 100%; height: 100%; min-height: 490px; overflow: hidden; border: 2px solid #25302d; border-radius: 12px; background: linear-gradient(180deg, #bce8f1, #eff8d9 84%); }
#scene { position: absolute; inset: 0; width: 100%; height: 100%; touch-action: none; cursor: grab; }
#scene:active { cursor: grabbing; }
#badge, #help { position: absolute; top: 14px; padding: 7px 11px; border: 2px solid #25302d; border-radius: 8px; color: #202a2a; font-size: 12px; font-weight: 900; pointer-events: none; }
#badge { left: 14px; background: #ffdc68; }
#help { right: 14px; background: rgba(255,255,255,.92); }
#failure { position: absolute; inset: 0; display: none; place-items: center; padding: 24px; text-align: center; color: #202a2a; font-weight: 800; }
@media(max-width: 650px) { #frame { min-height: 400px; } #help { top: auto; bottom: 12px; left: 12px; right: auto; } }
</style>
</head>
<body>
<div id="frame"><div id="scene"></div><div id="badge"></div><div id="help"></div><div id="failure"></div></div>
<script type="module">
const cfg = __CONFIG__;
const badge = document.getElementById('badge');
const help = document.getElementById('help');
const failure = document.getElementById('failure');
badge.textContent = `🌋 ${cfg.labels.model_name}`;
help.textContent = cfg.labels.controls;
failure.textContent = cfg.labels.load_error;
try {
  const THREE = await import('https://cdn.jsdelivr.net/npm/three@0.161.0/build/three.module.js');
  const host = document.getElementById('scene');
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#c9eef3');
  scene.fog = new THREE.Fog('#dff3e5', 14, 25);
  const camera = new THREE.PerspectiveCamera(38, host.clientWidth / host.clientHeight, 0.1, 100);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setSize(host.clientWidth, host.clientHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  host.appendChild(renderer.domElement);
  scene.add(new THREE.HemisphereLight('#f8ffff', '#687755', 2.0));
  const sun = new THREE.DirectionalLight('#fff3d4', 2.7);
  sun.position.set(-5, 9, 7);
  scene.add(sun);

  const ground = new THREE.Mesh(new THREE.RingGeometry(3.0, 5.5, 80), new THREE.MeshStandardMaterial({ color: '#8ecb80', roughness: 1, side: THREE.DoubleSide }));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.13;
  scene.add(ground);

  const stratovolcano = cfg.type === 'stratovolcano';
  const caldera = cfg.type === 'caldera';
  const mountainHeight = stratovolcano ? 3.35 : caldera ? 2.3 : 2.0;
  const baseRadius = stratovolcano ? 2.1 : caldera ? 2.8 : 3.0;
  const summitRadius = stratovolcano ? 0.18 : caldera ? 1.05 : 0.9;
  const bands = [
    { y0: 0, y1: mountainHeight * .24, r0: baseRadius, r1: baseRadius * .76, color: '#9f5842' },
    { y0: mountainHeight * .24, y1: mountainHeight * .48, r0: baseRadius * .76, r1: baseRadius * .52, color: '#d18158' },
    { y0: mountainHeight * .48, y1: mountainHeight * .72, r0: baseRadius * .52, r1: baseRadius * .29, color: '#b6654a' },
    { y0: mountainHeight * .72, y1: mountainHeight, r0: baseRadius * .29, r1: summitRadius, color: '#e3a36a' },
  ];
  const frontArc = Math.PI * 1.22;
  const arcStart = -Math.PI * .61;
  for (const band of bands) {
    const material = new THREE.MeshStandardMaterial({ color: band.color, roughness: .94, side: THREE.DoubleSide });
    const geometry = new THREE.CylinderGeometry(band.r1, band.r0, band.y1 - band.y0, 72, 1, true, arcStart, frontArc);
    const layer = new THREE.Mesh(geometry, material);
    layer.position.y = (band.y0 + band.y1) / 2 - .02;
    scene.add(layer);
  }

  const chamber = new THREE.Mesh(new THREE.SphereGeometry(.82, 32, 24), new THREE.MeshStandardMaterial({ color: '#ff633c', emissive: '#ca2a12', emissiveIntensity: .8, roughness: .32 }));
  chamber.scale.set(1.12, .68, .82);
  chamber.position.set(-.05, -.33, .08);
  scene.add(chamber);
  const conduit = new THREE.Mesh(new THREE.CylinderGeometry(.19, .3, mountainHeight * .67, 32), new THREE.MeshStandardMaterial({ color: '#ff693f', emissive: '#ba2a14', emissiveIntensity: .55, roughness: .35 }));
  conduit.position.set(0, mountainHeight * .31, .12);
  scene.add(conduit);
  const craterY = mountainHeight - .08;
  const crater = new THREE.Mesh(new THREE.TorusGeometry(caldera ? .93 : .31, .12, 12, 48), new THREE.MeshStandardMaterial({ color: '#613a33', roughness: .9 }));
  crater.rotation.x = Math.PI / 2;
  crater.position.set(0, craterY, .02);
  scene.add(crater);
  const magmaSurface = new THREE.Mesh(new THREE.CircleGeometry(caldera ? .76 : .23, 32), new THREE.MeshBasicMaterial({ color: '#ff793e', side: THREE.DoubleSide }));
  magmaSurface.rotation.x = -Math.PI / 2;
  magmaSurface.position.set(0, craterY - .06, .02);
  scene.add(magmaSurface);

  const flowCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(.02, craterY - .01, .16), new THREE.Vector3(.36, mountainHeight * .76, .36),
    new THREE.Vector3(.57, mountainHeight * .53, .61), new THREE.Vector3(.89, mountainHeight * .29, .9),
    new THREE.Vector3(1.31, .13, 1.16),
  ]);
  const lavaFlow = new THREE.Mesh(new THREE.TubeGeometry(flowCurve, 44, .105, 10, false), new THREE.MeshStandardMaterial({ color: '#ff542f', emissive: '#e53917', emissiveIntensity: .72, roughness: .45 }));
  scene.add(lavaFlow);

  function labelSprite(number, text, color) {
    const canvas = document.createElement('canvas');
    canvas.width = 512; canvas.height = 112;
    const context = canvas.getContext('2d');
    context.fillStyle = 'rgba(255,255,255,.96)'; context.strokeStyle = '#25302d'; context.lineWidth = 7;
    context.beginPath(); context.roundRect(4, 4, 504, 104, 22); context.fill(); context.stroke();
    context.fillStyle = color; context.beginPath(); context.arc(58, 56, 33, 0, Math.PI * 2); context.fill();
    context.fillStyle = '#202a2a'; context.font = '900 31px sans-serif'; context.textBaseline = 'middle';
    context.fillText(String(number).padStart(2, '0'), 34, 57);
    context.font = '800 31px sans-serif'; context.fillText(text, 110, 57, 380);
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false }));
    sprite.scale.set(2.15, .47, 1); sprite.renderOrder = 10;
    return sprite;
  }
  const labelData = [
    { n: 1, key: 'crater', pos: [0, craterY + .32, .55], color: '#ffdc68' },
    { n: 2, key: 'layers', pos: [-1.1, mountainHeight * .55, .8], color: '#d18158' },
    { n: 3, key: 'conduit', pos: [0, mountainHeight * .36, .72], color: '#ff793e' },
    { n: 4, key: 'chamber', pos: [-.2, -.45, .84], color: '#ff633c' },
    { n: 5, key: 'flank', pos: [1.25, mountainHeight * .23, .78], color: '#8ecb80' },
  ];
  const labelSprites = [];
  for (const item of labelData) {
    const anchor = new THREE.Vector3(...item.pos);
    const sprite = labelSprite(item.n, cfg.labels[item.key], item.color);
    sprite.position.copy(anchor).add(new THREE.Vector3(item.n % 2 ? .82 : -.86, .1, .1));
    scene.add(sprite); labelSprites.push(sprite);
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([anchor, sprite.position]), new THREE.LineBasicMaterial({ color: '#25302d', depthTest: false }));
    line.renderOrder = 9; scene.add(line);
    const dot = new THREE.Mesh(new THREE.SphereGeometry(.075, 12, 12), new THREE.MeshBasicMaterial({ color: item.color }));
    dot.position.copy(anchor); scene.add(dot);
  }

  const plume = [];
  const plumeCount = 36;
  const particleGeometry = new THREE.SphereGeometry(1, 8, 8);
  const gasFactor = cfg.gas / 100;
  const pressureFactor = cfg.pressure / 100;
  for (let index = 0; index < plumeCount; index++) {
    const particle = new THREE.Mesh(particleGeometry, new THREE.MeshBasicMaterial({ color: index % 4 === 0 ? '#f4a98d' : '#edf3e9', transparent: true, opacity: .35, depthWrite: false }));
    particle.userData = { phase: index / plumeCount, spread: .16 + gasFactor * .5 };
    scene.add(particle); plume.push(particle);
  }

  let angle = -.08, elevation = .13, distance = 8.2, dragging = false, lastX = 0, lastY = 0;
  function updateCamera() {
    camera.position.set(Math.sin(angle) * distance, 1.45 + Math.sin(elevation) * distance, Math.cos(angle) * distance);
    camera.lookAt(0, .98, 0);
  }
  updateCamera();
  host.addEventListener('pointerdown', event => { dragging = true; lastX = event.clientX; lastY = event.clientY; host.setPointerCapture(event.pointerId); });
  host.addEventListener('pointerup', () => dragging = false);
  host.addEventListener('pointercancel', () => dragging = false);
  host.addEventListener('pointermove', event => {
    if (!dragging) return;
    angle -= (event.clientX - lastX) * .006;
    elevation = Math.max(-.28, Math.min(.62, elevation + (event.clientY - lastY) * .004));
    lastX = event.clientX; lastY = event.clientY; updateCamera();
  });
  host.addEventListener('wheel', event => { event.preventDefault(); distance = Math.max(5.2, Math.min(16, distance + event.deltaY * .008)); updateCamera(); }, { passive: false });
  const resize = new ResizeObserver(() => {
    const width = host.clientWidth, heightPx = host.clientHeight;
    if (!width || !heightPx) return;
    camera.aspect = width / heightPx; camera.updateProjectionMatrix(); renderer.setSize(width, heightPx);
  });
  resize.observe(host);
  let frame = 0;
  function animate() {
    requestAnimationFrame(animate); frame += .012 + pressureFactor * .013;
    plume.forEach((particle, index) => {
      const phase = (particle.userData.phase + frame * (.13 + pressureFactor * .12)) % 1;
      const spread = particle.userData.spread * phase;
      particle.position.set(Math.sin(index * 9.1 + frame) * spread, craterY + .25 + phase * (1.0 + gasFactor * 1.4), .02 + Math.cos(index * 7.3 + frame) * spread * .65);
      const scale = (.06 + phase * (.16 + gasFactor * .15)) * (1.15 - cfg.viscosity / 300);
      particle.scale.setScalar(Math.max(.045, scale));
      particle.material.opacity = Math.max(.04, (.48 - phase * .35) * (.45 + gasFactor * .6));
    });
    magmaSurface.material.color.setHSL(.035 + Math.sin(frame * 2) * .012, .88, .54 + pressureFactor * .12);
    labelSprites.forEach(sprite => sprite.quaternion.copy(camera.quaternion));
    renderer.render(scene, camera);
  }
  animate();
} catch (error) {
  failure.style.display = 'grid';
}
</script>
</body>
</html>"""
    return template.replace("__CONFIG__", config_json)
