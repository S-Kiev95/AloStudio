"use client";

import { useEffect, useRef } from "react";

/**
 * 3D channel logos drifting in the empty space of their parent, bouncing off
 * its edges, off each other and off every `[data-bounce]` element inside it,
 * with a rubber squash-and-stretch on each impact.
 *
 * Mount it as a child of a positioned element (`relative`): it fills that
 * element, behind its content, and never takes pointer events.
 *
 * The physics is 2D and runs in CSS pixels; three.js only draws. The camera is
 * orthographic at one unit per pixel, so a body's position is its screen
 * position and DOM rects can be used as obstacles as they are.
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
}

interface Rect {
  left: number;
  top: number;
  right: number;
  bottom: number;
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
  // Centre inside the rect (it grew, or the window shrank): leave by the
  // nearest edge.
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
    // Ease the speed back to cruise: impacts die down, nothing ever stalls.
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
    // Never past a three-quarter view: edge-on, a logo is just a slab.
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
        return; // No WebGL: the page simply has no decoration.
      }
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1;

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
        renderer.setSize(w, h, false);
        camera.left = -w / 2;
        camera.right = w / 2;
        camera.top = h / 2;
        camera.bottom = -h / 2;
        camera.updateProjectionMatrix();
      };
      resize();

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
      // Sized by the screen, then held back so a crowded page still has room
      // for them to travel.
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
        // Normalise: centred, bounding sphere of radius `size`.
        const box = new THREE.Box3().setFromObject(model);
        const sphere = box.getBoundingSphere(new THREE.Sphere());
        const scale = size / sphere.radius;
        // The body that collides is the logo's outline as seen from the
        // front, not that sphere, which also wraps its depth and would keep
        // the logos visibly apart. Halfway between the circle inside the
        // outline and the one around it: a disc touches exactly, a tile gives
        // a little at the corners.
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
        const inside = Math.max(box.max.x - box.min.x, box.max.y - box.min.y) / 2;
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
        bodies.push({
          ...spawn(r, w, h, obstacles, bodies),
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

      const draw = (t: number) => {
        bodies.forEach((b, i) => {
          const n = nodes[i]!;
          // Screen y grows downwards, world y upwards.
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

      const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      let raf = 0;
      let last = performance.now();
      let sinceRects = 0;
      const frame = (now: number) => {
        raf = requestAnimationFrame(frame);
        const dt = Math.min(0.033, (now - last) / 1000);
        last = now;
        sinceRects += dt;
        if (sinceRects > 0.3) {
          sinceRects = 0;
          // Scrolling moves the canvas on screen, so its origin is re-read too.
          origin = canvas.getBoundingClientRect();
          obstacles = readObstacles(host, origin);
        }
        // Two substeps keep fast rebounds from tunnelling through thin edges.
        step(bodies, obstacles, w, h, pointer, dt / 2);
        step(bodies, obstacles, w, h, pointer, dt / 2);
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
