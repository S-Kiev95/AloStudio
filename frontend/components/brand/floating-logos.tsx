"use client";

import { useEffect, useRef } from "react";

import { useAuthSingularity } from "@/components/auth/black-hole-context";

/**
 * 3D channel logos drifting in the empty space of their parent, bouncing off
 * its edges, off each other and off every `[data-bounce]` element inside it,
 * with a rubber squash-and-stretch on each impact.
 *
 * Inside `AuthSingularityShell` (login screen), when authentication succeeds,
 * the same WebGL scene switches into singularity mode: a procedural GLSL
 * cobalt accretion disk and pitch-black event horizon ignite at the login
 * card's center, every 3D `.glb` logo spirals inward while stretching like
 * gum (`squash` group), and the camera plunges into the black hole.
 */

const MODELS = [
  "whatsapp",
  "instagram",
  "facebook",
  "telegram",
  "gmail",
  "x",
  "messenger",
  "tiktok",
  "threads",
  "linkedin",
  "youtube",
] as const;

const OBSTACLE_SELECTOR = "[data-bounce]";

/** Cruise speed in px/s: bodies are eased back to it so they never stall. */
const CRUISE = 70;
const MAX_SPEED = 900;
/** Squash spring: stiffness and damping of the rubber wobble. */
const SQUASH_K = 190;
const SQUASH_C = 9;
/** How much squash one px/s of impact speed injects. */
const SQUASH_KICK = 0.022;
const POINTER_RADIUS = 46;
const MAX_TILT = 0.55;
/** Share of the free space the logos may cover between them. */
const COVERAGE = 0.2;

const ACCRETION_VERT = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const ACCRETION_FRAG = /* glsl */ `
  precision highp float;
  varying vec2 vUv;
  uniform float uTime;
  uniform float uDisk;
  uniform float uHorizon;
  uniform float uDive;

  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
  }

  void main() {
    vec2 p = (vUv - 0.5) * 2.0;
    float r = length(p);
    float rH = 0.21;

    // 1. Deep cobalt gravitational ambient glow
    float ambient = exp(-pow(max(0.0, r - rH) * 2.4, 1.45)) * 0.72;

    // 2. Gravitationally-lensed upper/lower photon halo (Gargantua arc)
    float lensedHalo = exp(-pow(max(0.0, r - rH) / 0.14, 1.6)) * 0.92;
    float photonRing = exp(-pow((r - rH * 1.02) / 0.017, 2.0)) * 1.65;

    // 3. Tilted swirling equatorial accretion disk
    float c = cos(0.22);
    float s = sin(0.22);
    vec2 rp = mat2(c, -s, s, c) * p;
    vec2 ep = vec2(rp.x, rp.y * 3.55);
    float er = length(ep);
    float ang = atan(ep.y, ep.x);
    float swirl = ang - uTime * 3.8 + 4.2 / (er + 0.22);
    float n = noise(vec2(cos(swirl) * 2.0 + er * 4.5, sin(swirl) * 2.0 - uTime * 1.2));
    float bands = 0.55 + 0.45 * sin(er * 48.0 - uTime * 5.0 + n * 3.2);
    float streaks = 0.65 + 0.35 * sin(swirl * 3.0 + er * 14.0);
    float diskMask = smoothstep(rH * 0.92, rH * 1.15, er) * smoothstep(0.96, 0.26, er);
    float diskGlow = diskMask * bands * streaks * 1.35;

    vec3 deepCobalt = vec3(0.114, 0.306, 0.847);   // #1d4ed8
    vec3 neonCore   = vec3(0.239, 0.420, 1.000);   // #3d6bff
    vec3 litWhite   = vec3(0.859, 0.894, 1.000);   // #dbe4ff

    vec3 col = deepCobalt * ambient;
    col += mix(neonCore, litWhite, clamp(exp(-max(0.0, r - rH) * 9.0), 0.0, 1.0)) * lensedHalo;
    col += mix(neonCore, litWhite, clamp(bands * smoothstep(0.7, 0.22, er), 0.0, 1.0)) * diskGlow;
    col += litWhite * photonRing;

    float glowAlpha = clamp((ambient + lensedHalo + diskGlow + photonRing) * uDisk, 0.0, 1.0);

    // 4. Event horizon pitch-black sphere occluding the center
    float sphereEdge = 1.0 - smoothstep(rH - 0.008, rH + 0.008, r);
    float horizonAlpha = sphereEdge * uHorizon;

    vec3 finalRgb = mix(col * uDisk, vec3(0.0), horizonAlpha);
    float finalAlpha = max(glowAlpha, horizonAlpha);

    // Fade outer quad edge to zero so no bounding box ever shows
    finalAlpha *= smoothstep(1.0, 0.88, r);
    gl_FragColor = vec4(finalRgb, finalAlpha);
  }
`;

interface Body {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  /** Squash amount along `axis` (screen angle) and its velocity. */
  s: number;
  sv: number;
  axis: number;
  /** Tumble: tilt angles, their velocities, and a per-body sway phase. */
  tx: number;
  ty: number;
  tvx: number;
  tvy: number;
  phase: number;
  /** Snapshot at singularity start for deterministic spaghettification spiral. */
  sx: number;
  sy: number;
  absorbDelay: number;
}

interface Rect {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

function clamp01(v: number) {
  return Math.max(0, Math.min(1, v));
}

function squashHit(b: Body, nx: number, ny: number, impact: number) {
  b.axis = Math.atan2(ny, nx);
  b.sv += Math.min(impact, MAX_SPEED) * SQUASH_KICK;
  // An off-centre knock: the logo rocks around the axis across the normal.
  b.tvy += nx * impact * 0.012;
  b.tvx += ny * impact * 0.012;
}

/** Bounce a body off a normal it is moving into. Returns the impact speed. */
function reflect(b: Body, nx: number, ny: number) {
  const vn = b.vx * nx + b.vy * ny;
  if (vn >= 0) return 0;
  b.vx -= 2 * vn * nx;
  b.vy -= 2 * vn * ny;
  squashHit(b, nx, ny, -vn);
  return -vn;
}

function collideRect(b: Body, o: Rect) {
  const cx = Math.max(o.left, Math.min(b.x, o.right));
  const cy = Math.max(o.top, Math.min(b.y, o.bottom));
  let dx = b.x - cx;
  let dy = b.y - cy;
  const d2 = dx * dx + dy * dy;
  if (d2 >= b.r * b.r) return;
  if (d2 > 1e-6) {
    const d = Math.sqrt(d2);
    dx /= d;
    dy /= d;
    b.x = cx + dx * b.r;
    b.y = cy + dy * b.r;
    reflect(b, dx, dy);
    return;
  }
  const exits = [
    { d: b.x - o.left, nx: -1, ny: 0 },
    { d: o.right - b.x, nx: 1, ny: 0 },
    { d: b.y - o.top, nx: 0, ny: -1 },
    { d: o.bottom - b.y, nx: 0, ny: 1 },
  ].sort((p, q) => p.d - q.d)[0]!;
  b.x += exits.nx * (exits.d + b.r);
  b.y += exits.ny * (exits.d + b.r);
  reflect(b, exits.nx, exits.ny);
}

function collidePair(a: Body, b: Body) {
  let dx = b.x - a.x;
  let dy = b.y - a.y;
  const min = a.r + b.r;
  const d2 = dx * dx + dy * dy;
  if (d2 >= min * min) return;
  const d = Math.sqrt(d2) || 1;
  dx /= d;
  dy /= d;
  const ma = a.r * a.r;
  const mb = b.r * b.r;
  const overlap = min - d;
  a.x -= dx * overlap * (mb / (ma + mb));
  a.y -= dy * overlap * (mb / (ma + mb));
  b.x += dx * overlap * (ma / (ma + mb));
  b.y += dy * overlap * (ma / (ma + mb));
  const rel = (b.vx - a.vx) * dx + (b.vy - a.vy) * dy;
  if (rel >= 0) return;
  const j = (-2 * rel) / (1 / ma + 1 / mb);
  a.vx -= (j / ma) * dx;
  a.vy -= (j / ma) * dy;
  b.vx += (j / mb) * dx;
  b.vy += (j / mb) * dy;
  squashHit(a, -dx, -dy, -rel);
  squashHit(b, dx, dy, -rel);
}

function step(
  bodies: Body[],
  obstacles: Rect[],
  w: number,
  h: number,
  pointer: { x: number; y: number; active: boolean },
  dt: number,
) {
  for (const b of bodies) {
    const speed = Math.hypot(b.vx, b.vy);
    if (speed < 1) {
      const a = Math.random() * Math.PI * 2;
      b.vx = Math.cos(a) * CRUISE;
      b.vy = Math.sin(a) * CRUISE;
    } else {
      const target = speed + (CRUISE - speed) * Math.min(1, dt * 0.8);
      const k = Math.min(target, MAX_SPEED) / speed;
      b.vx *= k;
      b.vy *= k;
    }
    b.x += b.vx * dt;
    b.y += b.vy * dt;

    if (b.x < b.r) {
      b.x = b.r;
      reflect(b, 1, 0);
    } else if (b.x > w - b.r) {
      b.x = w - b.r;
      reflect(b, -1, 0);
    }
    if (b.y < b.r) {
      b.y = b.r;
      reflect(b, 0, 1);
    } else if (b.y > h - b.r) {
      b.y = h - b.r;
      reflect(b, 0, -1);
    }
    for (const o of obstacles) collideRect(b, o);

    if (pointer.active) {
      const dx = b.x - pointer.x;
      const dy = b.y - pointer.y;
      const min = b.r + POINTER_RADIUS;
      const d2 = dx * dx + dy * dy;
      if (d2 < min * min && d2 > 1e-6) {
        const d = Math.sqrt(d2);
        const push = (min - d) * 14;
        b.vx += (dx / d) * push;
        b.vy += (dy / d) * push;
        if (Math.abs(b.s) < 0.05) squashHit(b, dx / d, dy / d, 160);
      }
    }

    b.sv += (-SQUASH_K * b.s - SQUASH_C * b.sv) * dt;
    b.s = Math.max(-0.3, Math.min(0.42, b.s + b.sv * dt));
    b.tvx += (-14 * b.tx - 2.2 * b.tvx) * dt;
    b.tvy += (-14 * b.ty - 2.2 * b.tvy) * dt;
    b.tx = Math.max(-MAX_TILT, Math.min(MAX_TILT, b.tx + b.tvx * dt));
    b.ty = Math.max(-MAX_TILT, Math.min(MAX_TILT, b.ty + b.tvy * dt));
    if (Math.abs(b.tx) === MAX_TILT) b.tvx = 0;
    if (Math.abs(b.ty) === MAX_TILT) b.tvy = 0;
  }
  for (let i = 0; i < bodies.length; i++) {
    for (let j = i + 1; j < bodies.length; j++) {
      collidePair(bodies[i]!, bodies[j]!);
    }
  }
}

/** The host's `[data-bounce]` elements, in the canvas's own coordinates. */
function readObstacles(host: Element, origin: DOMRect): Rect[] {
  return Array.from(host.querySelectorAll(OBSTACLE_SELECTOR)).map((el) => {
    const r = el.getBoundingClientRect();
    return {
      left: r.left - origin.left,
      top: r.top - origin.top,
      right: r.right - origin.left,
      bottom: r.bottom - origin.top,
    };
  });
}

/** A free spot: inside the area, off every obstacle and every body. */
function spawn(r: number, w: number, h: number, obstacles: Rect[], others: Body[]) {
  let x = r;
  let y = r;
  for (let attempt = 0; attempt < 80; attempt++) {
    x = r + Math.random() * Math.max(1, w - 2 * r);
    y = r + Math.random() * Math.max(1, h - 2 * r);
    const blocked =
      obstacles.some(
        (o) =>
          x > o.left - r && x < o.right + r && y > o.top - r && y < o.bottom + r,
      ) || others.some((b) => Math.hypot(b.x - x, b.y - y) < b.r + r + 8);
    if (!blocked) break;
  }
  return { x, y };
}

export function FloatingLogos() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const singularity = useAuthSingularity();
  const singularityRef = useRef(singularity);
  singularityRef.current = singularity;

  useEffect(() => {
    const canvas = canvasRef.current;
    const host = canvas?.parentElement;
    if (!canvas || !host) return;
    let disposed = false;
    let cleanup = () => {};

    (async () => {
      const [THREE, { GLTFLoader }, { RoomEnvironment }] = await Promise.all([
        import("three"),
        import("three/addons/loaders/GLTFLoader.js"),
        import("three/addons/environments/RoomEnvironment.js"),
      ]);
      if (disposed) return;

      let renderer: import("three").WebGLRenderer;
      try {
        renderer = new THREE.WebGLRenderer({
          canvas,
          alpha: true,
          antialias: true,
        });
      } catch {
        singularityRef.current?.registerWebGL(false);
        return; // No WebGL: fallback CSS handles singularity if active.
      }
      singularityRef.current?.registerWebGL(true);

      const scene = new THREE.Scene();
      const pmrem = new THREE.PMREMGenerator(renderer);
      scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
      scene.environmentIntensity = 0.55;
      const key = new THREE.DirectionalLight(0xffffff, 1.6);
      key.position.set(-0.6, 1, 1.4);
      scene.add(key);

      const camera = new THREE.OrthographicCamera(0, 1, 0, 1, -2000, 2000);
      let w = 0;
      let h = 0;
      let origin = canvas.getBoundingClientRect();
      const resize = () => {
        origin = canvas.getBoundingClientRect();
        w = Math.max(1, origin.width);
        h = Math.max(1, origin.height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, w < 480 ? 1.5 : 2));
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1;
        renderer.setSize(w, h, false);
        camera.left = -w / 2;
        camera.right = w / 2;
        camera.top = h / 2;
        camera.bottom = -h / 2;
        camera.updateProjectionMatrix();
      };
      resize();

      // Procedural GLSL accretion disk + photon ring + black sphere horizon
      const diskUniforms = {
        uTime: { value: 0 },
        uDisk: { value: 0 },
        uHorizon: { value: 0 },
        uDive: { value: 0 },
      };
      const diskGeo = new THREE.PlaneGeometry(1, 1);
      const diskMat = new THREE.ShaderMaterial({
        vertexShader: ACCRETION_VERT,
        fragmentShader: ACCRETION_FRAG,
        uniforms: diskUniforms,
        transparent: true,
        depthWrite: false,
      });
      const diskMesh = new THREE.Mesh(diskGeo, diskMat);
      diskMesh.visible = false;
      diskMesh.position.set(0, 0, -140);
      scene.add(diskMesh);

      // Radial warp streaks for Phase 4 camera plunge
      const STAR_COUNT = w < 480 ? 40 : 72;
      const starSeeds = Array.from({ length: STAR_COUNT }, (_, i) => ({
        angle: (i * 2.399963) % (Math.PI * 2),
        dist: 70 + (((i * 73) % 100) / 100) * Math.hypot(w, h) * 0.52,
      }));
      const starPositions = new Float32Array(STAR_COUNT * 2 * 3);
      const starGeo = new THREE.BufferGeometry();
      starGeo.setAttribute(
        "position",
        new THREE.BufferAttribute(starPositions, 3),
      );
      const starMat = new THREE.LineBasicMaterial({
        color: 0x93c5fd,
        transparent: true,
        opacity: 0,
      });
      const starLines = new THREE.LineSegments(starGeo, starMat);
      starLines.visible = false;
      starLines.position.set(0, 0, 120);
      scene.add(starLines);

      // A narrow area has room for about half of them.
      const names = w < 480 ? MODELS.slice(0, 6) : MODELS;
      const loader = new GLTFLoader();
      const loaded = await Promise.all(
        names.map((name) =>
          loader
            .loadAsync(`/brand/3d/${name}.glb`)
            .then((gltf) => gltf.scene)
            .catch(() => null),
        ),
      );
      if (disposed) {
        diskGeo.dispose();
        diskMat.dispose();
        starGeo.dispose();
        starMat.dispose();
        pmrem.dispose();
        renderer.dispose();
        return;
      }

      let obstacles = readObstacles(host, origin);
      const bodies: Body[] = [];
      const nodes: {
        squash: import("three").Group;
        unsquash: import("three").Group;
        model: import("three").Object3D;
      }[] = [];
      const free =
        w * h -
        obstacles.reduce(
          (sum, o) => sum + (o.right - o.left) * (o.bottom - o.top),
          0,
        );
      const fit = Math.sqrt(
        (COVERAGE * Math.max(free, 0)) / (Math.PI * names.length),
      );
      const base = Math.max(
        26,
        Math.min(72, Math.min(w, h) * 0.072, fit),
      );
      loaded.forEach((model, i) => {
        if (!model) return;
        const size = base * (0.85 + ((i * 37) % 30) / 100);
        const box = new THREE.Box3().setFromObject(model);
        const sphere = box.getBoundingSphere(new THREE.Sphere());
        const scale = size / sphere.radius;
        let around = 0;
        const v = new THREE.Vector3();
        model.traverse((o) => {
          const mesh = o as import("three").Mesh;
          const pos = mesh.geometry?.getAttribute("position");
          if (!pos) return;
          for (let k = 0; k < pos.count; k++) {
            v.fromBufferAttribute(pos, k).applyMatrix4(mesh.matrixWorld);
            around = Math.max(
              around,
              Math.hypot(v.x - sphere.center.x, v.y - sphere.center.y),
            );
          }
        });
        const inside =
          Math.max(box.max.x - box.min.x, box.max.y - box.min.y) / 2;
        const r = ((inside + around) / 2) * scale;
        const holder = new THREE.Group();
        model.position.sub(sphere.center);
        holder.add(model);
        holder.scale.setScalar(scale);

        const squash = new THREE.Group();
        const unsquash = new THREE.Group();
        unsquash.add(holder);
        squash.add(unsquash);
        scene.add(squash);
        nodes.push({ squash, unsquash, model: holder });

        const a = Math.random() * Math.PI * 2;
        const spot = spawn(r, w, h, obstacles, bodies);
        bodies.push({
          ...spot,
          vx: Math.cos(a) * CRUISE,
          vy: Math.sin(a) * CRUISE,
          r,
          s: 0,
          sv: 0,
          axis: 0,
          tx: 0,
          ty: 0,
          tvx: 0,
          tvy: 0,
          phase: Math.random() * Math.PI * 2,
          sx: spot.x,
          sy: spot.y,
          absorbDelay: (i / Math.max(1, names.length)) * 0.28,
        });
      });

      const pointer = { x: 0, y: 0, active: false };
      const onMove = (e: PointerEvent) => {
        pointer.x = e.clientX - origin.left;
        pointer.y = e.clientY - origin.top;
        pointer.active = e.pointerType === "mouse";
      };
      const onLeave = () => {
        pointer.active = false;
      };

      let capturedSingularity = false;

      const draw = (t: number) => {
        const singState = singularityRef.current?.stateRef.current;

        if (singState?.active) {
          if (!capturedSingularity) {
            capturedSingularity = true;
            for (const b of bodies) {
              b.sx = b.x;
              b.sy = b.y;
            }
          }

          const bhX = singState.cx - origin.left;
          const bhY = singState.cy - origin.top;
          const worldBhX = bhX - w / 2;
          const worldBhY = h / 2 - bhY;

          // Bring canvas above the fading card once the accretion disk ignites
          if (singState.disk > 0.04) {
            canvas.style.zIndex = "15";
          }

          // Update procedural GLSL accretion disk + horizon mesh
          const diskSize = singState.radius * 9.4;
          diskMesh.visible = singState.disk > 0.001 || singState.horizon > 0.001;
          diskMesh.position.set(worldBhX, worldBhY, -140);
          diskMesh.scale.set(
            diskSize * (0.45 + 0.55 * singState.disk),
            diskSize * (0.45 + 0.55 * singState.disk),
            1,
          );
          diskUniforms.uTime.value = t % 1000;
          diskUniforms.uDisk.value = singState.disk;
          diskUniforms.uHorizon.value = singState.horizon;
          diskUniforms.uDive.value = singState.dive;

          // Spiral + gum-stretch ("como chicle") every 3D .glb logo into the black hole
          const pull = singState.pull;
          bodies.forEach((b, i) => {
            const n = nodes[i]!;
            const localT = clamp01(
              (pull - b.absorbDelay) / Math.max(0.2, 1 - b.absorbDelay),
            );
            const e = localT * localT * localT;
            const dx0 = b.sx - bhX;
            const dy0 = b.sy - bhY;
            const dist0 = Math.hypot(dx0, dy0);
            const ang0 = Math.atan2(dy0, dx0);
            const spiralAng = ang0 + e * 3.6;
            const dist = dist0 * (1 - e * 0.99);
            const x = bhX + Math.cos(spiralAng) * dist;
            const y = bhY + Math.sin(spiralAng) * dist;

            const toCenterAxis = -Math.atan2(bhY - y, bhX - x);
            const stretchX = 1 + Math.pow(localT, 1.25) * 4.6;
            const stretchY = Math.max(0.16, 1 - Math.pow(localT, 1.15) * 0.82);
            const stretchZ = Math.max(0.35, 1 - localT * 0.65);
            const vanish =
              localT > 0.78 ? 1 - clamp01((localT - 0.78) / 0.22) : 1;

            n.squash.visible = vanish > 0.01;
            n.squash.position.set(x - w / 2, h / 2 - y, 20);
            n.squash.rotation.z = toCenterAxis;
            n.squash.scale.set(
              stretchX * vanish,
              stretchY * vanish,
              stretchZ * vanish,
            );
            n.unsquash.rotation.z = -toCenterAxis;
            n.model.rotation.set(
              b.tx + localT * 1.4,
              b.ty + localT * 2.4,
              localT * 0.9,
            );
          });

          // Phase 4: Camera plunges straight into the black hole + radial warp streaks
          const dive = singState.dive;
          if (dive > 0.001) {
            camera.position.set(worldBhX * dive, worldBhY * dive, 0);
            camera.zoom = 1 + dive * 10.5;
            camera.updateProjectionMatrix();

            starLines.visible = true;
            starMat.opacity = Math.min(0.85, dive * 1.35);
            const posAttr = starGeo.getAttribute(
              "position",
            ) as import("three").BufferAttribute;
            const arr = posAttr.array as Float32Array;
            for (let i = 0; i < starSeeds.length; i++) {
              const s = starSeeds[i]!;
              const d1 = s.dist * (1 + dive * 1.8);
              const len = 12 + dive * 160;
              const cosA = Math.cos(s.angle);
              const sinA = Math.sin(s.angle);
              const idx = i * 6;
              arr[idx] = worldBhX + cosA * d1;
              arr[idx + 1] = worldBhY + sinA * d1;
              arr[idx + 2] = 0;
              arr[idx + 3] = worldBhX + cosA * (d1 + len);
              arr[idx + 4] = worldBhY + sinA * (d1 + len);
              arr[idx + 5] = 0;
            }
            posAttr.needsUpdate = true;
          } else {
            starLines.visible = false;
          }

          renderer.render(scene, camera);
          return;
        }

        // Normal idle bouncing mode
        bodies.forEach((b, i) => {
          const n = nodes[i]!;
          const axis = -b.axis;
          n.squash.position.set(b.x - w / 2, h / 2 - b.y, 0);
          n.squash.rotation.z = axis;
          n.squash.scale.set(1 - b.s, 1 + b.s * 0.6, 1);
          n.unsquash.rotation.z = -axis;
          n.model.rotation.set(
            b.tx + Math.sin(t * 0.5 + b.phase) * 0.22,
            b.ty + Math.sin(t * 0.37 + b.phase * 1.7) * 0.5,
            Math.sin(t * 0.3 + b.phase) * 0.1,
          );
        });
        renderer.render(scene, camera);
      };

      const still = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches;
      let raf = 0;
      let last = performance.now();
      let sinceRects = 0;
      const frame = (now: number) => {
        raf = requestAnimationFrame(frame);
        const dt = Math.min(0.033, (now - last) / 1000);
        last = now;
        const singActive = Boolean(singularityRef.current?.stateRef.current.active);
        if (!singActive) {
          sinceRects += dt;
          if (sinceRects > 0.3) {
            sinceRects = 0;
            origin = canvas.getBoundingClientRect();
            obstacles = readObstacles(host, origin);
          }
          step(bodies, obstacles, w, h, pointer, dt / 2);
          step(bodies, obstacles, w, h, pointer, dt / 2);
        }
        draw(now / 1000);
      };
      const onVisibility = () => {
        cancelAnimationFrame(raf);
        if (!document.hidden && !still) {
          last = performance.now();
          raf = requestAnimationFrame(frame);
        }
      };
      const onResize = () => {
        resize();
        obstacles = readObstacles(host, origin);
        if (still) draw(0);
      };

      const observer = new ResizeObserver(onResize);
      observer.observe(host);
      window.addEventListener("pointermove", onMove);
      document.addEventListener("pointerleave", onLeave);
      document.addEventListener("visibilitychange", onVisibility);
      if (still) draw(0);
      else raf = requestAnimationFrame(frame);
      canvas.style.opacity = "1";

      cleanup = () => {
        cancelAnimationFrame(raf);
        observer.disconnect();
        window.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerleave", onLeave);
        document.removeEventListener("visibilitychange", onVisibility);
        diskGeo.dispose();
        diskMat.dispose();
        starGeo.dispose();
        starMat.dispose();
        scene.traverse((o) => {
          const mesh = o as import("three").Mesh;
          mesh.geometry?.dispose();
          const mats = Array.isArray(mesh.material)
            ? mesh.material
            : mesh.material
              ? [mesh.material]
              : [];
          mats.forEach((m) => m.dispose());
        });
        pmrem.dispose();
        renderer.dispose();
      };
      if (disposed) cleanup();
    })();

    return () => {
      disposed = true;
      cleanup();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className="pointer-events-none absolute inset-0 z-0 h-full w-full opacity-0 transition-opacity duration-700"
    />
  );
}
