// GeoLite v1 — globe component frontend.
// Modes: seismic | volcanoes | currents | climate.
// All user-visible strings come from spec.labels (sent by Python).

import { Streamlit } from "./vendor/streamlit.js";
import * as THREE from "three";
import { OrbitControls } from "./vendor/OrbitControls.js";

/* ------------------------------------------------------------------ */
/* Constants                                                           */
/* ------------------------------------------------------------------ */

const R = 1.0; // globe radius (scene units)
const DEG = THREE.MathUtils.degToRad;
const RAD = THREE.MathUtils.radToDeg;
const FALLBACK_GLOBE_COLOR = 0x2f3c58; // dark slate-blue when no texture
const SEED = 1337;

/* ------------------------------------------------------------------ */
/* Pure helpers (no DOM access)                                        */
/* ------------------------------------------------------------------ */

// Matches SphereGeometry UV mapping: u = (lon + 180) / 360 (left edge = 180W),
// v = 1 at the north pole.
function latLonToVec3(lat, lon, r) {
  const phi = DEG(lon + 180);
  const theta = Math.PI / 2 - DEG(lat);
  return new THREE.Vector3(
    -r * Math.cos(phi) * Math.sin(theta),
    r * Math.cos(theta),
    r * Math.sin(phi) * Math.sin(theta)
  );
}

function vec3ToLatLon(v) {
  const r = v.length();
  let lon = RAD * Math.atan2(v.z, -v.x) - 180;
  lon = ((lon + 540) % 360) - 180;
  const lat = 90 - RAD * Math.acos(THREE.MathUtils.clamp(v.y / r, -1, 1));
  return { lat, lon };
}

function clamp01(x) { return Math.min(1, Math.max(0, x)); }

const _cA = new THREE.Color();
const _cB = new THREE.Color();
function lerpHexInto(out, hexA, hexB, t) {
  _cA.setHex(hexA); _cB.setHex(hexB);
  out.copy(_cA).lerp(_cB, clamp01(t));
  return out;
}

// Earthquake depth color ramp:
//   0-60 km   : red -> orange        (0xff3814 -> 0xffa02a)
//   60-300 km : yellow -> green      (0xffe234 -> 0x35d05a)
//   300-700 km: blue -> purple       (0x3f7cff -> 0x9b4dff)
function depthColor(depthKm, out) {
  const d = Math.max(0, depthKm || 0);
  if (d < 60) return lerpHexInto(out, 0xff3814, 0xffa02a, d / 60);
  if (d < 300) return lerpHexInto(out, 0xffe234, 0x35d05a, (d - 60) / 240);
  if (d < 700) return lerpHexInto(out, 0x3f7cff, 0x9b4dff, (d - 300) / 400);
  return out.setHex(0x9b4dff);
}

/* Seeded value-noise fBm (inline, no deps) */

function mulberry32(seed) {
  let a = seed | 0;
  return function () {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hash2i(x, y, seed) {
  let h = (Math.imul(x | 0, 374761393) + Math.imul(y | 0, 668265263) + Math.imul(seed | 0, 987643211)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}

function smootherstep01(t) { return t * t * t * (t * (t * 6 - 15) + 10); }

function valueNoise2(x, z, seed) {
  const ix = Math.floor(x), iz = Math.floor(z);
  const fx = smootherstep01(x - ix), fz = smootherstep01(z - iz);
  const a = hash2i(ix, iz, seed), b = hash2i(ix + 1, iz, seed);
  const c = hash2i(ix, iz + 1, seed), d = hash2i(ix + 1, iz + 1, seed);
  return (a * (1 - fx) + b * fx) * (1 - fz) + (c * (1 - fx) + d * fx) * fz;
}

function fbm2(x, z, seed, octaves) {
  let sum = 0, amp = 0.5, freq = 1, norm = 0;
  for (let i = 0; i < (octaves || 5); i++) {
    sum += amp * valueNoise2(x * freq, z * freq, seed + i * 101);
    norm += amp;
    amp *= 0.5;
    freq *= 2;
  }
  return sum / norm; // 0..1
}

/* ------------------------------------------------------------------ */
/* State                                                               */
/* ------------------------------------------------------------------ */

const S = {
  booted: false,
  spec: null,
  signature: "",
  mode: null,
  buildId: 0,
  renderer: null,
  canvas: null,
  scene: null,
  camera: null,
  controls: null,
  globeMesh: null,
  eqLayer: null,       // { points, data, count }
  volLayer: null,      // { inst, data, positions, count, ring, ringPhase }
  particles: null,     // { points, n, lat, lon, life, maxLife, grid, vmax, posArr, colArr }
  texturePending: false,
  clock: new THREE.Clock(),
  rafId: null,
  mouse: null,         // { x, y } last pointer pos (client coords)
  tooltipQueued: false,
  dragDist: 0,
  menuCtx: null,
  loopStarted: false,
  lastSpecJson: "",
};

const _pv = new THREE.Vector3();
const _raycaster = new THREE.Raycaster();
const _ndc = new THREE.Vector2();
const _tmpColor = new THREE.Color();

let el = {}; // DOM refs, filled by boot()

/* ------------------------------------------------------------------ */
/* Frame height                                                        */
/* ------------------------------------------------------------------ */

function currentFrameHeight() {
  const fallback = (S.spec && S.spec.height) || 640;
  try {
    const pd = window.parent.document;
    const frames = pd.querySelectorAll("iframe");
    for (let i = 0; i < frames.length; i++) {
      if (frames[i].contentWindow === window) {
        let h = null;
        if (S.spec && S.spec.autoHeight) {
          // Page-scroll mode: fill the space below the iframe's top edge.
          // The Streamlit page scrolls inside a nested container
          // (section.stMain), so the iframe's document position must be
          // measured relative to that container's content: window.scrollY
          // stays 0 there and would make the frame grow while scrolling,
          // pushing the content below it out of reach.
          const fr = frames[i].getBoundingClientRect();
          let scroller = frames[i].parentElement;
          while (scroller && scroller !== pd.body) {
            const oy = window.parent.getComputedStyle(scroller).overflowY;
            if ((oy === "auto" || oy === "scroll") && scroller.scrollHeight > scroller.clientHeight + 1) break;
            scroller = scroller.parentElement;
          }
          let top, availH;
          if (scroller && scroller !== pd.body) {
            const sr = scroller.getBoundingClientRect();
            top = fr.top - sr.top + scroller.scrollTop;
            availH = scroller.clientHeight;
          } else {
            top = fr.top + (window.parent.scrollY || 0);
            availH = window.parent.innerHeight || 0;
          }
          const avail = availH - top;
          if (avail > 0) h = avail - 14;
        } else {
          h = frames[i].getBoundingClientRect().height || frames[i].clientHeight;
          if (!h || h < 40) {
            const p = frames[i].parentElement;
            if (p) h = p.getBoundingClientRect().height || p.clientHeight;
          }
        }
        if (h && h >= 40 && h <= 20000) return Math.round(h);
        break;
      }
    }
  } catch (err) { /* cross-origin: use fallback */ }
  return fallback;
}

function syncHeight() {
  Streamlit.setFrameHeight(currentFrameHeight());
}

/* ------------------------------------------------------------------ */
/* Rebuild / update dispatch                                           */
/* ------------------------------------------------------------------ */

function buildSignature(spec) {
  const g = spec.globe || {};
  return JSON.stringify([
    spec.mode,
    g.textureUrl || null,
    !!g.showGraticule,
    spec.mode === "currents" ? ((spec.climate && spec.climate.textureUrl) || null) : null,
  ]);
}

function render(spec) {
  spec = spec || {};
  S.spec = spec;
  syncHeight();
  const sig = buildSignature(spec);
  if (sig !== S.signature || !S.renderer) {
    S.signature = sig;
    rebuild(spec);
  } else {
    updateInPlace(spec);
  }
  updateChips(spec);
}

function rebuild(spec) {
  S.buildId++;
  disposeBuild();
  S.mode = spec.mode;
  const w = Math.max(el.app.clientWidth, 320);
  const h = Math.max(el.app.clientHeight, 240);
  S.renderer = new THREE.WebGLRenderer({ antialias: true });
  S.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  S.renderer.setSize(w, h);
  S.canvas = S.renderer.domElement;
  el.app.appendChild(S.canvas);
  buildGlobeScene(spec, w, h);
}

function updateInPlace(spec) {
  const g = spec.globe || {};
  if (S.controls) {
    S.controls.autoRotate = !!g.autoRotate;
    S.controls.update();
  }
  if (spec.mode === "seismic") refreshEarthquakes(spec.earthquakes);
  if (spec.mode === "volcanoes") refreshVolcanoes(spec.volcanoes);
  if (spec.mode === "currents") refreshClimate(spec.climate);
}

function disposeObject(root) {
  root.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    const mats = o.material ? (Array.isArray(o.material) ? o.material : [o.material]) : [];
    for (const m of mats) {
      for (const k in m) {
        const v = m[k];
        if (v && v.isTexture) v.dispose();
      }
      m.dispose();
    }
  });
}

function disposeBuild() {
  hideTooltip();
  closeMenu();
  if (S.controls) { S.controls.dispose(); S.controls = null; }
  if (S.scene) { disposeObject(S.scene); S.scene = null; }
  if (S.renderer) {
    S.renderer.dispose();
    if (S.canvas && S.canvas.parentNode) S.canvas.parentNode.removeChild(S.canvas);
    S.renderer = null;
    S.canvas = null;
  }
  S.globeMesh = null;
  S.eqLayer = null;
  S.volLayer = null;
  S.particles = null;
  S.texturePending = false;
}

/* ------------------------------------------------------------------ */
/* Globe scene (seismic / volcanoes / climate)                         */
/* ------------------------------------------------------------------ */

function makeStars() {
  const N = 1500;
  const pos = new Float32Array(N * 3);
  const col = new Float32Array(N * 3);
  const rng = mulberry32(SEED + 5);
  const v = new THREE.Vector3();
  for (let i = 0; i < N; i++) {
    v.set(rng() * 2 - 1, rng() * 2 - 1, rng() * 2 - 1);
    if (v.lengthSq() < 1e-6) v.set(1, 0, 0);
    v.normalize().multiplyScalar(28 + rng() * 24);
    pos[i * 3] = v.x; pos[i * 3 + 1] = v.y; pos[i * 3 + 2] = v.z;
    const b = 0.35 + rng() * 0.6;
    const warm = rng() * 0.25;
    col[i * 3] = b; col[i * 3 + 1] = b * (1 - warm * 0.4); col[i * 3 + 2] = b * (1 - warm);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  const mat = new THREE.PointsMaterial({
    size: 0.05, vertexColors: true, transparent: true, opacity: 0.9,
    sizeAttenuation: true, depthWrite: false,
  });
  return new THREE.Points(geo, mat);
}

function makeAtmosphere() {
  const geo = new THREE.SphereGeometry(R * 1.16, 64, 64);
  const mat = new THREE.ShaderMaterial({
    uniforms: { c: { value: new THREE.Color(0x3d6bb3) } },
    vertexShader: [
      "varying vec3 vNormal;",
      "void main() {",
      "  vNormal = normalize(normalMatrix * normal);",
      "  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);",
      "}",
    ].join("\n"),
    fragmentShader: [
      "uniform vec3 c;",
      "varying vec3 vNormal;",
      "void main() {",
      "  float intensity = pow(0.66 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 3.5);",
      "  gl_FragColor = vec4(c * intensity, intensity);",
      "}",
    ].join("\n"),
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false,
  });
  return new THREE.Mesh(geo, mat);
}

function makeGraticule(stepDeg, radius) {
  const pts = [];
  const r = radius || R * 1.002;
  for (let lon = -180; lon < 180; lon += stepDeg) {
    for (let lat = -90; lat < 90; lat += 3) {
      pts.push(latLonToVec3(lat, lon, r), latLonToVec3(lat + 3, lon, r));
    }
  }
  for (let lat = -75; lat <= 75; lat += stepDeg) {
    for (let lon = -180; lon < 180; lon += 3) {
      pts.push(latLonToVec3(lat, lon, r), latLonToVec3(lat, lon + 3, r));
    }
  }
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineBasicMaterial({
    color: 0x44546e, transparent: true, opacity: 0.5, depthWrite: false,
  });
  return new THREE.LineSegments(geo, mat);
}

function buildGlobeMesh(spec, showGraticule) {
  const mode = spec.mode;
  const texUrl = mode === "currents"
    ? ((spec.climate && spec.climate.textureUrl) || (spec.globe && spec.globe.textureUrl))
    : (spec.globe && spec.globe.textureUrl);
  const geo = new THREE.SphereGeometry(R, 96, 96);
  const mat = new THREE.MeshStandardMaterial({
    color: 0xffffff, roughness: 1, metalness: 0,
  });
  const mesh = new THREE.Mesh(geo, mat);
  S.scene.add(mesh);
  S.globeMesh = mesh;

  let grat = null;
  const wantGrat = !!showGraticule || !texUrl;
  if (wantGrat) {
    grat = makeGraticule(15);
    S.scene.add(grat);
    mesh.userData.graticule = grat;
  }

  if (texUrl) {
    S.texturePending = true;
    const id = S.buildId;
    new THREE.TextureLoader().load(
      texUrl,
      (tex) => {
        if (id !== S.buildId) { tex.dispose(); return; }
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.anisotropy = Math.min(4, S.renderer.capabilities.getMaxAnisotropy());
        mat.map = tex;
        mat.color.setHex(0xffffff);
        mat.needsUpdate = true;
        S.texturePending = false;
        updateChips(S.spec);
      },
      undefined,
      () => {
        if (id !== S.buildId) return;
        console.warn("Globe texture failed to load:", texUrl);
        mat.color.setHex(FALLBACK_GLOBE_COLOR);
        if (!grat) {
          grat = makeGraticule(15);
          S.scene.add(grat);
          mesh.userData.graticule = grat;
        }
        S.texturePending = false;
        updateChips(S.spec);
      }
    );
  } else {
    mat.color.setHex(FALLBACK_GLOBE_COLOR);
  }
}

function setupCameraAndControls(spec, w, h, camPos, target, minD, maxD) {
  S.camera = new THREE.PerspectiveCamera(42, w / h, 0.05, 400);
  S.camera.position.copy(camPos);
  S.controls = new OrbitControls(S.camera, S.canvas);
  S.controls.enableDamping = true;
  S.controls.dampingFactor = 0.08;
  S.controls.enablePan = false;
  S.controls.minDistance = minD;
  S.controls.maxDistance = maxD;
  S.controls.target.copy(target);
  S.controls.autoRotate = !!(spec.globe && spec.globe.autoRotate);
  S.controls.autoRotateSpeed = 0.5;
  S.controls.update();
}

function buildGlobeScene(spec, w, h) {
  S.scene = new THREE.Scene();
  S.scene.background = new THREE.Color(0x05070d);
  S.scene.add(makeStars());
  S.scene.add(makeAtmosphere());
  buildGlobeMesh(spec, spec.globe && spec.globe.showGraticule);

  const sun = new THREE.DirectionalLight(0xfff4e0, 2.6);
  sun.position.set(5, 3, 5);
  S.scene.add(sun);
  S.scene.add(new THREE.AmbientLight(0x8899bb, 0.5));

  const focus = spec.focus;
  let camPos = new THREE.Vector3(0.45, 0.55, 2.45);
  if (focus && isFinite(focus.lat) && isFinite(focus.lon)) {
    camPos = latLonToVec3(focus.lat, focus.lon, 2.35);
    camPos.y += 0.4;
  }
  setupCameraAndControls(spec, w, h, camPos, new THREE.Vector3(0, 0, 0), 1.35, 6);

  if (spec.mode === "seismic") refreshEarthquakes(spec.earthquakes);
  if (spec.mode === "volcanoes") refreshVolcanoes(spec.volcanoes);
  if (spec.mode === "currents") refreshClimate(spec.climate);
}

/* ------------------------------------------------------------------ */
/* Earthquakes layer                                                   */
/* ------------------------------------------------------------------ */

function refreshEarthquakes(events) {
  if (S.eqLayer) {
    S.scene.remove(S.eqLayer.points);
    disposeObject(S.eqLayer.points);
    if (S.eqLayer.selRing) {
      S.scene.remove(S.eqLayer.selRing);
      disposeObject(S.eqLayer.selRing);
    }
    S.eqLayer = null;
  }
  const list = Array.isArray(events) ? events : [];
  if (!list.length) return;

  const n = list.length;
  const pos = new Float32Array(n * 3);
  const col = new Float32Array(n * 3);
  const size = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const e = list[i];
    const v = latLonToVec3(e.lat, e.lon, R * 1.006);
    pos[i * 3] = v.x; pos[i * 3 + 1] = v.y; pos[i * 3 + 2] = v.z;
    depthColor(e.depth_km, _tmpColor);
    col[i * 3] = _tmpColor.r; col[i * 3 + 1] = _tmpColor.g; col[i * 3 + 2] = _tmpColor.b;
    // point size ~ 1.5^magnitude, clamped (px scale applied in shader)
    size[i] = THREE.MathUtils.clamp(Math.pow(1.5, e.magnitude || 0), 1.5, 26);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setAttribute("aColor", new THREE.BufferAttribute(col, 3));
  geo.setAttribute("aSize", new THREE.BufferAttribute(size, 1));
  const mat = new THREE.ShaderMaterial({
    vertexShader: [
      "attribute float aSize;",
      "attribute vec3 aColor;",
      "varying vec3 vColor;",
      "void main() {",
      "  vColor = aColor;",
      "  vec4 mv = modelViewMatrix * vec4(position, 1.0);",
      "  gl_PointSize = aSize * (8.0 / -mv.z);",
      "  gl_Position = projectionMatrix * mv;",
      "}",
    ].join("\n"),
    fragmentShader: [
      "varying vec3 vColor;",
      "void main() {",
      "  vec2 c = gl_PointCoord - 0.5;",
      "  float d = length(c);",
      "  if (d > 0.5) discard;",
      "  float a = smoothstep(0.5, 0.18, d);",
      "  gl_FragColor = vec4(vColor, a);",
      "}",
    ].join("\n"),
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const points = new THREE.Points(geo, mat);
  S.scene.add(points);

  // Anello di evidenziazione per il terremoto selezionato (spec.selectedId).
  let selRing = null;
  const selId = S.spec && S.spec.selectedId;
  const sel = selId ? list.filter((e) => e.id === selId)[0] : null;
  if (sel) {
    const p = latLonToVec3(sel.lat, sel.lon, R * 1.004);
    const ringGeo = new THREE.RingGeometry(0.016, 0.023, 40);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0xffffff, transparent: true, opacity: 0.95,
      blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide,
    });
    selRing = new THREE.Mesh(ringGeo, ringMat);
    selRing.position.copy(p);
    selRing.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), p.clone().normalize());
    const base = THREE.MathUtils.clamp((sel.magnitude || 3) / 4.5, 0.8, 1.9);
    selRing.userData.baseScale = base;
    selRing.scale.set(base, base, base);
    S.scene.add(selRing);
  }
  S.eqLayer = { points, data: list, count: n, selRing, selPhase: 0 };
}

/* ------------------------------------------------------------------ */
/* Volcanoes layer                                                     */
/* ------------------------------------------------------------------ */

function refreshVolcanoes(events) {
  if (S.volLayer) {
    S.scene.remove(S.volLayer.group);
    disposeObject(S.volLayer.group);
    S.volLayer = null;
  }
  const list = Array.isArray(events) ? events : [];
  if (!list.length) return;

  const group = new THREE.Group();
  const n = list.length;
  const coneGeo = new THREE.ConeGeometry(0.014, 0.04, 8);
  const coneMat = new THREE.MeshStandardMaterial({ color: 0xd8402a, roughness: 0.7 });
  const inst = new THREE.InstancedMesh(coneGeo, coneMat, n);
  const m4 = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  const positions = new Float32Array(n * 3);
  let newestIdx = 0, newestTime = -Infinity;
  for (let i = 0; i < n; i++) {
    const v = list[i];
    const p = latLonToVec3(v.lat, v.lon, R * 1.001);
    const normal = p.clone().normalize();
    q.setFromUnitVectors(up, normal);
    m4.compose(p, q, new THREE.Vector3(1, 1, 1));
    inst.setMatrixAt(i, m4);
    positions[i * 3] = p.x; positions[i * 3 + 1] = p.y; positions[i * 3 + 2] = p.z;
    const t = Date.parse(v.date);
    if (isFinite(t) && t > newestTime) { newestTime = t; newestIdx = i; }
  }
  inst.instanceMatrix.needsUpdate = true;
  group.add(inst);

  // pulsing ring at the most recent event
  const np = new THREE.Vector3(positions[newestIdx * 3], positions[newestIdx * 3 + 1], positions[newestIdx * 3 + 2]);
  const ringGeo = new THREE.RingGeometry(0.018, 0.026, 40);
  const ringMat = new THREE.MeshBasicMaterial({
    color: 0xff6a3d, transparent: true, opacity: 0.9,
    blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide,
  });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.position.copy(np.clone().multiplyScalar(1.004));
  ring.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), np.clone().normalize());
  group.add(ring);

  S.scene.add(group);
  S.volLayer = { group, inst, data: list, positions, count: n, ring, newestIdx, ringPhase: 0 };
}

/* ------------------------------------------------------------------ */
/* Climate currents                                                    */
/* ------------------------------------------------------------------ */

function gkey(lat, lon) {
  return Math.round(lat * 1000) * 1000000 + Math.round((lon + 180) * 1000);
}

function buildCurrentsGrid(cells) {
  const map = new Map();
  const lats = [];
  for (const c of cells) {
    map.set(gkey(c[0], c[1]), c);
    if (lats.indexOf(c[0]) === -1) lats.push(c[0]);
  }
  lats.sort((a, b) => a - b);
  let step = 1;
  for (let i = 1; i < lats.length; i++) {
    const d = lats[i] - lats[i - 1];
    if (d > 1e-9) { step = d; break; }
  }
  const speeds = cells.map((c) => Math.hypot(c[2], c[3])).sort((a, b) => a - b);
  const vmax = Math.max(0.05, speeds[Math.floor(speeds.length * 0.95)] || 1);
  return { map, step, vmax, cells };
}

function sampleGrid(grid, lat, lon) {
  const s = grid.step;
  const lat0 = Math.floor(lat / s) * s;
  const lon0 = Math.floor(lon / s) * s;
  const c00 = grid.map.get(gkey(lat0, lon0));
  const c01 = grid.map.get(gkey(lat0, lon0 + s));
  const c10 = grid.map.get(gkey(lat0 + s, lon0));
  const c11 = grid.map.get(gkey(lat0 + s, lon0 + s));
  if (c00 && c01 && c10 && c11) {
    const fx = clamp01((lat - lat0) / s);
    const fy = clamp01((lon - lon0) / s);
    const u = (c00[2] * (1 - fx) + c10[2] * fx) * (1 - fy) + (c01[2] * (1 - fx) + c11[2] * fx) * fy;
    const v = (c00[3] * (1 - fx) + c10[3] * fx) * (1 - fy) + (c01[3] * (1 - fx) + c11[3] * fx) * fy;
    return { u, v };
  }
  const nn = grid.map.get(gkey(Math.round(lat / s) * s, Math.round(lon / s) * s));
  if (nn) return { u: nn[2], v: nn[3] };
  return null;
}

function respawnParticle(P, i) {
  const cells = P.grid.cells;
  const c = cells[(Math.random() * cells.length) | 0];
  const s = P.grid.step;
  P.lat[i] = c[0] + (Math.random() - 0.5) * s * 0.9;
  let lon = c[1] + (Math.random() - 0.5) * s * 0.9;
  P.lon[i] = ((lon + 540) % 360) - 180;
  P.life[i] = 0;
  P.maxLife[i] = 12 + Math.random() * 28;
}

function speedColor(t, out) {
  t = clamp01(t);
  if (t < 0.5) return lerpHexInto(out, 0x2961ff, 0x40ebff, t * 2);
  return lerpHexInto(out, 0x40ebff, 0xffffff, (t - 0.5) * 2);
}

function buildCurrentsParticles(grid) {
  const n = Math.min(2000, Math.max(200, grid.cells.length));
  const pos = new Float32Array(n * 3);
  const col = new Float32Array(n * 3);
  const P = {
    n,
    lat: new Float32Array(n),
    lon: new Float32Array(n),
    life: new Float32Array(n),
    maxLife: new Float32Array(n),
    grid,
    posArr: pos,
    colArr: col,
    points: null,
  };
  const v = new THREE.Vector3();
  for (let i = 0; i < n; i++) {
    respawnParticle(P, i);
    P.life[i] = Math.random() * P.maxLife[i]; // stagger initial ages
    v.copy(latLonToVec3(P.lat[i], P.lon[i], R * 1.01));
    pos[i * 3] = v.x; pos[i * 3 + 1] = v.y; pos[i * 3 + 2] = v.z;
    speedColor(Math.random() * 0.5, _tmpColor);
    col[i * 3] = _tmpColor.r; col[i * 3 + 1] = _tmpColor.g; col[i * 3 + 2] = _tmpColor.b;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  const mat = new THREE.PointsMaterial({
    size: 0.012, vertexColors: true, transparent: true, opacity: 0.85,
    sizeAttenuation: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  P.points = new THREE.Points(geo, mat);
  S.scene.add(P.points);
  return P;
}

function advectCurrents(dtReal) {
  const P = S.particles;
  if (!P) return;
  const dt = dtReal * 60000; // sim-seconds per real second (exaggerated for visibility)
  const v = _pv;
  for (let i = 0; i < P.n; i++) {
    let lat = P.lat[i], lon = P.lon[i];
    const s = sampleGrid(P.grid, lat, lon);
    P.life[i] += dtReal;
    if (!s || P.life[i] > P.maxLife[i] || lat > 85 || lat < -85) {
      respawnParticle(P, i);
      lat = P.lat[i]; lon = P.lon[i];
    } else {
      const dlat = (s.v * dt) / 111320;
      const dlon = (s.u * dt) / (111320 * Math.max(0.17, Math.cos(DEG(lat))));
      lat += dlat;
      lon = ((lon + dlon + 540) % 360) - 180;
      if (lat > 89) lat = 89; else if (lat < -89) lat = -89;
      P.lat[i] = lat; P.lon[i] = lon;
      speedColor(Math.hypot(s.u, s.v) / P.grid.vmax, _tmpColor);
      P.colArr[i * 3] = _tmpColor.r; P.colArr[i * 3 + 1] = _tmpColor.g; P.colArr[i * 3 + 2] = _tmpColor.b;
    }
    v.copy(latLonToVec3(P.lat[i], P.lon[i], R * 1.01));
    P.posArr[i * 3] = v.x; P.posArr[i * 3 + 1] = v.y; P.posArr[i * 3 + 2] = v.z;
  }
  const g = P.points.geometry;
  g.attributes.position.needsUpdate = true;
  g.attributes.color.needsUpdate = true;
}

function refreshClimate(climate) {
  if (S.particles) {
    S.scene.remove(S.particles.points);
    disposeObject(S.particles.points);
    S.particles = null;
  }
  if (climate && climate.showCurrents && Array.isArray(climate.currents) && climate.currents.length) {
    const grid = buildCurrentsGrid(climate.currents);
    S.particles = buildCurrentsParticles(grid);
  }
}

/* ------------------------------------------------------------------ */
/* Chips (legend / status overlays)                                    */
/* ------------------------------------------------------------------ */

function setChips(container, items) {
  container.textContent = "";
  for (const it of items) {
    const d = document.createElement("div");
    d.className = "chip";
    if (it.html) d.innerHTML = it.html;
    else d.textContent = it.text;
    container.appendChild(d);
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

function updateChips(spec) {
  if (!spec || !spec.mode) return;
  const labels = spec.labels || {};
  const left = [], right = [];
  const mode = spec.mode;

  if (mode === "currents") {
    const cl = spec.climate || {};
    if (cl.showCurrents && Array.isArray(cl.currents) && cl.currents.length) {
      const dateTxt = cl.currentsDate ? " &middot; " + escapeHtml(cl.currentsDate) : "";
      left.push({ html: "<b>" + escapeHtml(labels.currents_label || "") + "</b>" + dateTxt });
    }
    if (labels.sst_label) right.push({ text: labels.sst_label });
    if (S.texturePending && labels.loading) left.push({ text: labels.loading });
  } else if (mode === "climate") {
    if (labels.heat_label) right.push({ text: labels.heat_label });
    if (S.texturePending && labels.loading) left.push({ text: labels.loading });
  } else if (mode === "seismic" || mode === "volcanoes") {
    if (labels.base_label) right.push({ text: labels.base_label });
    const arr = mode === "seismic" ? spec.earthquakes : spec.volcanoes;
    if ((!Array.isArray(arr) || !arr.length) && labels.no_features) {
      left.push({ text: labels.no_features });
    }
    if (S.texturePending && labels.loading) left.push({ text: labels.loading });
  }

  setChips(el.chips, left);
  setChips(el.chipsTr, right);
}

/* ------------------------------------------------------------------ */
/* Picking                                                             */
/* ------------------------------------------------------------------ */

// Nearest-projected-point search in screen space (reliable for both
// ShaderMaterial Points and InstancedMesh).
function screenPickPositions(array, count, clientX, clientY, thrPx) {
  if (!S.camera || !S.canvas) return -1;
  const rect = S.canvas.getBoundingClientRect();
  const px = clientX - rect.left, py = clientY - rect.top;
  let best = -1, bd = thrPx;
  for (let i = 0; i < count; i++) {
    _pv.set(array[i * 3], array[i * 3 + 1], array[i * 3 + 2]).project(S.camera);
    if (_pv.z > 1 || _pv.z < -1) continue;
    const sx = (_pv.x * 0.5 + 0.5) * rect.width;
    const sy = (-_pv.y * 0.5 + 0.5) * rect.height;
    const d = Math.hypot(sx - px, sy - py);
    if (d < bd) { bd = d; best = i; }
  }
  return best;
}

function pickFeature(clientX, clientY) {
  if (S.mode === "seismic" && S.eqLayer) {
    const pos = S.eqLayer.points.geometry.attributes.position.array;
    const i = screenPickPositions(pos, S.eqLayer.count, clientX, clientY, 9);
    if (i >= 0) return { kind: "earthquake", data: S.eqLayer.data[i] };
  }
  if (S.mode === "volcanoes" && S.volLayer) {
    const i = screenPickPositions(S.volLayer.positions, S.volLayer.count, clientX, clientY, 11);
    if (i >= 0) return { kind: "volcano", data: S.volLayer.data[i] };
  }
  return null;
}

function featureContext(f) {
  if (f.kind === "earthquake") return Object.assign({ kind: "earthquake" }, f.data);
  return Object.assign({ kind: "volcano" }, f.data);
}

function globeLatLon(clientX, clientY) {
  if (!S.globeMesh || !S.camera || !S.canvas) return null;
  const rect = S.canvas.getBoundingClientRect();
  _ndc.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
  _raycaster.setFromCamera(_ndc, S.camera);
  const hits = _raycaster.intersectObject(S.globeMesh, false);
  if (!hits.length) return null;
  return vec3ToLatLon(hits[0].point);
}

/* ------------------------------------------------------------------ */
/* Tooltip                                                             */
/* ------------------------------------------------------------------ */

function hideTooltip() {
  el.tooltip.style.display = "none";
}

function renderTooltip() {
  S.tooltipQueued = false;
  if (!S.mouse || !S.canvas) { hideTooltip(); return; }
  const f = pickFeature(S.mouse.x, S.mouse.y);
  if (!f) {
    hideTooltip();
    if (S.canvas) S.canvas.style.cursor = "";
    return;
  }
  let title = "", sub = "";
  if (f.kind === "earthquake") {
    title = f.data.place || "";
    sub = "M " + f.data.magnitude + " \u00b7 " + Math.round(f.data.depth_km) + " km";
  } else {
    title = f.data.title || "";
    sub = f.data.date || "";
  }
  el.tooltip.innerHTML = "";
  const t = document.createElement("div");
  t.className = "tt-title";
  t.textContent = title;
  const s = document.createElement("div");
  s.className = "tt-sub";
  s.textContent = sub;
  el.tooltip.appendChild(t);
  el.tooltip.appendChild(s);
  el.tooltip.style.display = "block";
  const pad = 14;
  const tw = el.tooltip.offsetWidth, th = el.tooltip.offsetHeight;
  let x = S.mouse.x + pad, y = S.mouse.y + pad;
  if (x + tw > window.innerWidth - 4) x = S.mouse.x - tw - pad;
  if (y + th > window.innerHeight - 4) y = S.mouse.y - th - pad;
  el.tooltip.style.left = x + "px";
  el.tooltip.style.top = y + "px";
  S.canvas.style.cursor = "pointer";
}

function queueTooltip() {
  if (S.tooltipQueued) return;
  S.tooltipQueued = true;
  requestAnimationFrame(renderTooltip);
}

/* ------------------------------------------------------------------ */
/* Context menu                                                        */
/* ------------------------------------------------------------------ */

function closeMenu() {
  el.menu.style.display = "none";
  S.menuCtx = null;
}

function openMenu(x, y, ctx, header, isFeature) {
  const labels = (S.spec && S.spec.labels) || {};
  S.menuCtx = ctx;
  el.menu.textContent = "";
  if (header) {
    const hd = document.createElement("div");
    hd.className = "menu-header";
    hd.textContent = header;
    el.menu.appendChild(hd);
  }
  const mkItem = (label, icon, action) => {
    const it = document.createElement("div");
    it.className = "menu-item";
    const ic = document.createElement("span");
    ic.className = "mi-icon";
    ic.textContent = icon;
    const tx = document.createElement("span");
    tx.textContent = label;
    it.appendChild(ic);
    it.appendChild(tx);
    it.addEventListener("click", (ev) => {
      ev.stopPropagation();
      Streamlit.setComponentValue({ type: action, context: S.menuCtx });
      closeMenu();
    });
    el.menu.appendChild(it);
  };
  if (isFeature) mkItem(labels.details || "", "\u2139", "select");
  mkItem(labels.ask_ai || "", "\u2726", "ask_ai");

  el.menu.style.display = "block";
  el.menu.style.left = "0px";
  el.menu.style.top = "0px";
  const mw = el.menu.offsetWidth, mh = el.menu.offsetHeight;
  let px = Math.min(x, window.innerWidth - mw - 6);
  let py = Math.min(y, window.innerHeight - mh - 6);
  px = Math.max(4, px);
  py = Math.max(4, py);
  el.menu.style.left = px + "px";
  el.menu.style.top = py + "px";
}

function onContextMenu(e) {
  if (!S.canvas) return;
  e.preventDefault();
  const f = pickFeature(e.clientX, e.clientY);
  if (f) {
    const d = f.data;
    openMenu(e.clientX, e.clientY, featureContext(f), d.place || d.title || "", true);
    return;
  }
  const ll = globeLatLon(e.clientX, e.clientY);
  if (ll) {
    const kind = S.mode === "currents" ? "currents" : (S.mode === "climate" ? "climate" : "globe");
    const ctx = { kind, lat: ll.lat, lon: ll.lon };
    if (kind === "climate" && S.spec.heat && S.spec.heat.date) ctx.date = S.spec.heat.date;
    const header = ll.lat.toFixed(2) + "\u00b0, " + ll.lon.toFixed(2) + "\u00b0";
    openMenu(e.clientX, e.clientY, ctx, header, false);
  }
}

/* ------------------------------------------------------------------ */
/* Events                                                              */
/* ------------------------------------------------------------------ */

function onPointerMove(e) {
  S.mouse = { x: e.clientX, y: e.clientY };
  queueTooltip();
}

function onPointerDown(e) {
  S.dragDist = 0;
  if (S.canvas && e.target === S.canvas) {
    S.dragStart = { x: e.clientX, y: e.clientY };
  }
  if (S.menuCtx && !el.menu.contains(e.target)) closeMenu();
}

function onPointerUp(e) {
  if (S.dragStart) {
    S.dragDist = Math.hypot(e.clientX - S.dragStart.x, e.clientY - S.dragStart.y);
    S.dragStart = null;
  }
}

function onClick(e) {
  if (S.dragDist > 6) return;
  if (!S.canvas || e.target !== S.canvas) return;
  const f = pickFeature(e.clientX, e.clientY);
  if (f) Streamlit.setComponentValue({ type: "select", context: featureContext(f) });
}

function onResize() {
  if (S.renderer && S.canvas) {
    const w = Math.max(el.app.clientWidth, 320);
    const h = Math.max(el.app.clientHeight, 240);
    S.renderer.setSize(w, h);
    if (S.camera) {
      S.camera.aspect = w / h;
      S.camera.updateProjectionMatrix();
    }
  }
  syncHeight();
}

function onKeyDown(e) {
  if (e.key === "Escape") closeMenu();
}

/* ------------------------------------------------------------------ */
/* Main loop                                                           */
/* ------------------------------------------------------------------ */

function loop() {
  S.rafId = requestAnimationFrame(loop);
  if (document.hidden) return; // paused while tab is hidden
  const dt = Math.min(S.clock.getDelta(), 0.1);
  if (S.controls) S.controls.update();
  if (S.mode === "currents") advectCurrents(dt);
  if (S.volLayer && S.volLayer.ring) {
    S.volLayer.ringPhase += dt;
    const k = (S.volLayer.ringPhase % 1.6) / 1.6;
    const s = 1 + k * 0.9;
    S.volLayer.ring.scale.set(s, s, s);
    S.volLayer.ring.material.opacity = 0.9 * (1 - k);
  }
  if (S.eqLayer && S.eqLayer.selRing) {
    S.eqLayer.selPhase += dt;
    const k = (S.eqLayer.selPhase % 1.4) / 1.4;
    const base = S.eqLayer.selRing.userData.baseScale || 1;
    const s = base * (1 + k * 0.8);
    S.eqLayer.selRing.scale.set(s, s, s);
    S.eqLayer.selRing.material.opacity = 0.95 * (1 - k);
  }
  if (S.renderer && S.scene && S.camera) {
    S.renderer.render(S.scene, S.camera);
  }
}

function startLoop() {
  if (S.loopStarted) return;
  S.loopStarted = true;
  loop();
}

/* ------------------------------------------------------------------ */
/* Boot                                                                */
/* ------------------------------------------------------------------ */

function boot() {
  if (S.booted) return;
  S.booted = true;
  el.app = document.getElementById("app");
  el.tooltip = document.getElementById("tooltip");
  el.menu = document.getElementById("menu");
  el.chips = document.getElementById("chips");
  el.chipsTr = document.getElementById("chips-tr");

  const app = el.app;
  app.addEventListener("pointermove", onPointerMove);
  app.addEventListener("pointerdown", onPointerDown);
  app.addEventListener("pointerup", onPointerUp);
  app.addEventListener("click", onClick);
  document.addEventListener("contextmenu", onContextMenu);
  window.addEventListener("resize", onResize);
  window.addEventListener("keydown", onKeyDown);
  window.addEventListener("wheel", closeMenu, { capture: true, passive: true });
  window.addEventListener("blur", closeMenu);
  document.addEventListener("mousedown", (e) => {
    if (S.menuCtx && !el.menu.contains(e.target)) closeMenu();
  });
  try { window.parent.addEventListener("resize", onResize); } catch (err) { /* ignore */ }
  setInterval(syncHeight, 1500);

  startLoop();
  syncHeight();
}

/* ------------------------------------------------------------------ */
/* Module-level bootstrap (environment-guarded, keeps module           */
/* import-safe for syntax checkers)                                    */
/* ------------------------------------------------------------------ */

if (typeof window !== "undefined" && typeof document !== "undefined") {
  // The vendored lib exposes setComponentReady() (registers the message
  // listener and tells Streamlit the component is ready).
  Streamlit.setComponentReady();
  Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, (e) => {
    const args = (e.detail && e.detail.args) || {};
    render(args.spec || {});
  });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
}
