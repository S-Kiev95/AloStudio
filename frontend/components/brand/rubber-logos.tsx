"use client";

import {
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  computeStretchedTargets,
  createSquashKick,
  RUBBER_DEFAULTS,
  type SquashState,
  stepSpring1D,
  stepSquashSpring,
  stepVertexSprings,
  type Vec2,
  type Vec3,
} from "@/lib/rubber-physics";
import { cn } from "@/lib/utils";

export type RubberLogoName =
  | "facebook"
  | "instagram"
  | "whatsapp"
  | "tiktok"
  | "telegram";

export interface RubberLogosProps {
  /** Rubber GLB names loaded from `/brand/3d/rubber/<name>.glb`. */
  logos: readonly RubberLogoName[];
  /** Margin side; tilts logos subtly toward the center content. */
  side?: "left" | "right";
  className?: string;
}

export interface RubberLogoMarginsProps {
  leftLogos: readonly RubberLogoName[];
  rightLogos: readonly RubberLogoName[];
  /** Minimum free width (in CSS px) required on each side before mounting. */
  minStripWidth?: number;
  /** Classes applied to the centered content container (unchanged layout). */
  contentClassName?: string;
  children: ReactNode;
}

/** Normalized local span of every rubber logo geometry ([-1, +1] -> size 2). */
const LOGO_LOCAL_SIZE = 2.0;

/** Minimum side strip width in CSS px from PLAN.logos-goma.md. */
export const MIN_RUBBER_STRIP_WIDTH = 180;

const STRIP_GUTTER_PX = 8;

type LogoState = "idle" | "dragging" | "springing";

interface DeformablePart {
  mesh: import("three").Mesh;
  restPositions: Float32Array;
  restNormals: Float32Array;
  displacements: Float32Array;
  velocities: Float32Array;
  targets: Float32Array;
  weights: Float32Array;
}

interface RubberLogoItem {
  name: RubberLogoName;
  slotGroup: import("three").Group;
  squashGroup: import("three").Group;
  unsquashGroup: import("three").Group;
  poseGroup: import("three").Group;
  parts: DeformablePart[];
  /** Center in canvas CSS coordinates (origin top-left). */
  cx: number;
  cy: number;
  radiusPx: number;
  /** Resting 3/4 tilt in radians. */
  baseRotX: number;
  baseRotY: number;
  /** Dynamic tilt added during stretch & spring release. */
  tiltX: number;
  tiltY: number;
  tiltVx: number;
  tiltVy: number;
  state: LogoState;
  grabPoint: Vec3;
  rawPull: Vec2;
  lastClampedPull: Vec2;
  squash: SquashState;
}

function resetLogoToRest(item: RubberLogoItem) {
  for (const part of item.parts) {
    part.displacements.fill(0);
    part.velocities.fill(0);
    part.targets.fill(0);
    part.weights.fill(0);
    const pos = part.mesh.geometry.getAttribute(
      "position",
    ) as import("three").BufferAttribute;
    const norm = part.mesh.geometry.getAttribute(
      "normal",
    ) as import("three").BufferAttribute | undefined;
    (pos.array as Float32Array).set(part.restPositions);
    pos.needsUpdate = true;
    if (norm && part.restNormals.length === norm.array.length) {
      (norm.array as Float32Array).set(part.restNormals);
      norm.needsUpdate = true;
    }
    part.mesh.geometry.computeBoundingSphere();
  }
  item.squash.s = 0;
  item.squash.sv = 0;
  item.tiltX = 0;
  item.tiltY = 0;
  item.tiltVx = 0;
  item.tiltVy = 0;
  item.rawPull = { x: 0, y: 0 };
  item.lastClampedPull = { x: 0, y: 0 };
  item.state = "idle";
  item.squashGroup.rotation.z = 0;
  item.squashGroup.scale.set(1, 1, 1);
  item.unsquashGroup.rotation.z = 0;
  item.poseGroup.rotation.set(item.baseRotX, item.baseRotY, 0);
}

function applyDeformedGeometry(item: RubberLogoItem) {
  for (const part of item.parts) {
    const pos = part.mesh.geometry.getAttribute(
      "position",
    ) as import("three").BufferAttribute;
    const arr = pos.array as Float32Array;
    const rest = part.restPositions;
    const disp = part.displacements;
    for (let i = 0; i < arr.length; i++) {
      arr[i] = rest[i]! + disp[i]!;
    }
    pos.needsUpdate = true;
    part.mesh.geometry.computeVertexNormals();
  }
}

function applyLogoTransform(item: RubberLogoItem) {
  const axis = item.squash.axis;
  const s = item.squash.s;
  item.squashGroup.rotation.z = axis;
  item.squashGroup.scale.set(1 - s, 1 + s * 0.75, 1);
  item.unsquashGroup.rotation.z = -axis;
  item.poseGroup.rotation.set(
    item.baseRotX + item.tiltX,
    item.baseRotY + item.tiltY,
    0,
  );
}

/**
 * Interactive WebGL strip of stretchable 3D rubber channel logos.
 *
 * Uses one WebGL canvas for all logos in the strip, dynamically loads Three.js
 * on mount, and only runs a `requestAnimationFrame` loop while a logo is being
 * dragged or wobbling back to rest. Still logos consume zero JS/WebGL CPU.
 */
export function RubberLogos({ logos, side = "left", className }: RubberLogosProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const logosKey = logos.join(",");

  useEffect(() => {
    const canvas = canvasRef.current;
    const host = canvas?.parentElement;
    if (!canvas || !host) return;
    const names = (logosKey ? logosKey.split(",") : []) as RubberLogoName[];
    if (names.length === 0) return;

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
        return; // No WebGL available: gracefully leave the strip empty.
      }
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1;

      const scene = new THREE.Scene();
      const pmrem = new THREE.PMREMGenerator(renderer);
      const envTarget = pmrem.fromScene(new RoomEnvironment(), 0.04);
      scene.environment = envTarget.texture;
      scene.environmentIntensity = 0.55;

      const keyLight = new THREE.DirectionalLight(0xffffff, 1.6);
      keyLight.position.set(-0.6, 1, 1.4);
      scene.add(keyLight);

      // Camera sits at +Z looking down -Z so orthographic raycasts always begin
      // strictly in front of every logo mesh.
      const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 1, 1400);
      camera.position.set(0, 0, 700);
      camera.lookAt(0, 0, 0);

      let width = 1;
      let height = 1;
      let rect = canvas.getBoundingClientRect();

      const items: RubberLogoItem[] = [];
      const meshToItem = new Map<import("three").Object3D, RubberLogoItem>();
      const pickMeshes: import("three").Mesh[] = [];

      const layoutItems = () => {
        const count = items.length;
        if (count === 0) return;
        const radiusPx = Math.max(
          30,
          Math.min(44, width * 0.23, (height / Math.max(count, 1)) * 0.26),
        );
        const horizontalNudge = Math.min(12, width * 0.06);

        items.forEach((item, index) => {
          const t =
            count === 1
              ? 0.5
              : count === 2
                ? index === 0
                  ? 0.34
                  : 0.66
                : (index + 0.5) / count;
          const nudgeDir = index % 2 === 0 ? -1 : 1;
          const cx =
            width * 0.5 + nudgeDir * horizontalNudge * (side === "left" ? 1 : -1);
          const cy = height * t;
          item.cx = cx;
          item.cy = cy;
          item.radiusPx = radiusPx;
          item.slotGroup.position.set(cx - width / 2, height / 2 - cy, 0);
          item.poseGroup.scale.setScalar(radiusPx);
        });
      };

      const renderOnce = () => {
        renderer.render(scene, camera);
      };

      const resize = () => {
        rect = canvas.getBoundingClientRect();
        width = Math.max(1, rect.width);
        height = Math.max(1, rect.height);
        renderer.setSize(width, height, false);
        camera.left = -width / 2;
        camera.right = width / 2;
        camera.top = height / 2;
        camera.bottom = -height / 2;
        camera.updateProjectionMatrix();
        layoutItems();
        renderOnce();
      };
      resize();

      const loader = new GLTFLoader();
      const loaded = await Promise.all(
        names.map((name) =>
          loader
            .loadAsync(`/brand/3d/rubber/${name}.glb`)
            .then((gltf) => ({ name, model: gltf.scene }))
            .catch(() => null),
        ),
      );
      if (disposed) {
        envTarget.dispose();
        pmrem.dispose();
        renderer.dispose();
        return;
      }

      const inwardSign = side === "left" ? 1 : -1;
      loaded.forEach((entry, index) => {
        if (!entry) return;
        const { name, model } = entry;
        model.updateMatrixWorld(true);

        const box = new THREE.Box3().setFromObject(model);
        const center = box.getCenter(new THREE.Vector3());
        const span = Math.max(
          box.max.x - box.min.x,
          box.max.y - box.min.y,
          1e-4,
        );
        const normScale = LOGO_LOCAL_SIZE / span;

        // Bake each child mesh's transform into normalized [-1, +1] logo-local
        // space so multi-material parts deform in lockstep without seams.
        const toLocal = new THREE.Matrix4()
          .makeScale(normScale, normScale, normScale)
          .multiply(
            new THREE.Matrix4().makeTranslation(-center.x, -center.y, -center.z),
          );

        const parts: DeformablePart[] = [];
        const poseGroup = new THREE.Group();

        model.traverse((node) => {
          const mesh = node as import("three").Mesh;
          if (!mesh.isMesh || !mesh.geometry) return;
          const posAttr = mesh.geometry.getAttribute("position");
          if (!posAttr) return;

          const geom = mesh.geometry.clone();
          const bake = toLocal.clone().multiply(mesh.matrixWorld);
          geom.applyMatrix4(bake);
          if (!geom.getAttribute("normal")) {
            geom.computeVertexNormals();
          }

          const bakedPos = geom.getAttribute(
            "position",
          ) as import("three").BufferAttribute;
          const bakedNorm = geom.getAttribute(
            "normal",
          ) as import("three").BufferAttribute;
          bakedPos.setUsage(THREE.DynamicDrawUsage);
          bakedNorm.setUsage(THREE.DynamicDrawUsage);

          const clonedMesh = new THREE.Mesh(geom, mesh.material);
          poseGroup.add(clonedMesh);

          const restPositions = new Float32Array(
            bakedPos.array as Float32Array,
          );
          const restNormals = new Float32Array(bakedNorm.array as Float32Array);
          const count = bakedPos.count;

          parts.push({
            mesh: clonedMesh,
            restPositions,
            restNormals,
            displacements: new Float32Array(count * 3),
            velocities: new Float32Array(count * 3),
            targets: new Float32Array(count * 3),
            weights: new Float32Array(count),
          });
          pickMeshes.push(clonedMesh);
        });

        // Dispose original unbaked geometries from GLTFLoader (materials are reused).
        model.traverse((node) => {
          const mesh = node as import("three").Mesh;
          if (mesh.isMesh) mesh.geometry?.dispose();
        });

        if (parts.length === 0) return;

        const unsquashGroup = new THREE.Group();
        unsquashGroup.add(poseGroup);
        const squashGroup = new THREE.Group();
        squashGroup.add(unsquashGroup);
        const slotGroup = new THREE.Group();
        slotGroup.add(squashGroup);
        scene.add(slotGroup);

        const baseRotX = -0.14 + (index % 2 === 0 ? -0.05 : 0.05);
        const baseRotY = inwardSign * (0.24 + (index % 3) * 0.04);
        poseGroup.rotation.set(baseRotX, baseRotY, 0);

        const item: RubberLogoItem = {
          name,
          slotGroup,
          squashGroup,
          unsquashGroup,
          poseGroup,
          parts,
          cx: 0,
          cy: 0,
          radiusPx: 38,
          baseRotX,
          baseRotY,
          tiltX: 0,
          tiltY: 0,
          tiltVx: 0,
          tiltVy: 0,
          state: "idle",
          grabPoint: { x: 0, y: 0, z: 0 },
          rawPull: { x: 0, y: 0 },
          lastClampedPull: { x: 0, y: 0 },
          squash: { s: 0, sv: 0, axis: 0 },
        };
        for (const p of parts) {
          meshToItem.set(p.mesh, item);
        }
        items.push(item);
      });

      layoutItems();
      renderOnce();
      canvas.dataset.rubberState = "ready";
      canvas.style.opacity = "1";

      const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      let reducedMotion = motionQuery.matches;
      const onMotionChange = (e: MediaQueryListEvent) => {
        reducedMotion = e.matches;
        if (reducedMotion) {
          for (const item of items) {
            if (item.state === "springing") {
              resetLogoToRest(item);
            }
          }
          renderOnce();
          stopLoop();
        }
      };

      const raycaster = new THREE.Raycaster();
      const ndc = new THREE.Vector2();
      const tmpVec = new THREE.Vector3();
      const invQuat = new THREE.Quaternion();

      let activeDrag: {
        item: RubberLogoItem;
        pointerId: number;
        startClientX: number;
        startClientY: number;
      } | null = null;

      let rafId = 0;
      let lastTime = 0;

      const hasRunningWork = () =>
        items.some((item) => item.state !== "idle");

      const stopLoop = () => {
        if (rafId !== 0) {
          cancelAnimationFrame(rafId);
          rafId = 0;
        }
        if (!activeDrag) {
          canvas.dataset.rubberState = "ready";
        }
      };

      const stepFrame = (now: number) => {
        rafId = 0;
        if (disposed || document.hidden) return;

        const dt = Math.min(0.05, Math.max(0.001, (now - lastTime) / 1000));
        lastTime = now;

        let anyActive = false;

        for (const item of items) {
          if (item.state === "dragging") {
            anyActive = true;
            let clamped = { x: 0, y: 0, magnitude: 0, ratio: 0 };

            const follow = 1 - Math.exp(-34 * dt);
            for (const part of item.parts) {
              const res = computeStretchedTargets(
                part.restPositions,
                item.grabPoint,
                item.rawPull,
                LOGO_LOCAL_SIZE,
                part.targets,
                part.weights,
              );
              clamped = res.clampedPull;

              const disp = part.displacements;
              const vel = part.velocities;
              const tgt = part.targets;
              for (let i = 0; i < disp.length; i++) {
                const prev = disp[i]!;
                const next = prev + (tgt[i]! - prev) * follow;
                disp[i] = next;
                // Track gentle drag velocity (clamped) for lively flick release.
                const instVel = (next - prev) / dt;
                vel[i] = Math.max(-18, Math.min(18, vel[i]! * 0.5 + instVel * 0.5));
              }
            }

            item.lastClampedPull = { x: clamped.x, y: clamped.y };
            // Subtle tactile tilt toward the stretch direction.
            const targetTiltY = Math.max(-0.18, Math.min(0.18, clamped.x * 0.08));
            const targetTiltX = Math.max(-0.18, Math.min(0.18, -clamped.y * 0.08));
            item.tiltX += (targetTiltX - item.tiltX) * follow;
            item.tiltY += (targetTiltY - item.tiltY) * follow;
            item.tiltVx = 0;
            item.tiltVy = 0;

            applyDeformedGeometry(item);
            applyLogoTransform(item);
          } else if (item.state === "springing") {
            let verticesActive = false;
            for (const part of item.parts) {
              const step = stepVertexSprings(
                part.displacements,
                part.velocities,
                part.weights,
                dt,
                RUBBER_DEFAULTS,
              );
              if (step.active) verticesActive = true;
            }

            const squashActive = stepSquashSpring(
              item.squash,
              dt,
              RUBBER_DEFAULTS,
            );

            const nextTx = stepSpring1D(item.tiltX, item.tiltVx, dt, 220, 11);
            const nextTy = stepSpring1D(item.tiltY, item.tiltVy, dt, 220, 11);
            item.tiltX = nextTx.x;
            item.tiltVx = nextTx.v;
            item.tiltY = nextTy.x;
            item.tiltVy = nextTy.v;
            const tiltActive =
              Math.abs(item.tiltX) > 0.002 ||
              Math.abs(item.tiltY) > 0.002 ||
              Math.abs(item.tiltVx) > 0.01 ||
              Math.abs(item.tiltVy) > 0.01;

            if (verticesActive || squashActive || tiltActive) {
              anyActive = true;
              applyDeformedGeometry(item);
              applyLogoTransform(item);
            } else {
              resetLogoToRest(item);
            }
          }
        }

        renderOnce();

        if (anyActive) {
          rafId = requestAnimationFrame(stepFrame);
        } else {
          canvas.dataset.rubberState = "ready";
        }
      };

      const startLoop = () => {
        if (rafId !== 0 || disposed || document.hidden) return;
        lastTime = performance.now();
        rafId = requestAnimationFrame(stepFrame);
      };

      const pickLogoAt = (clientX: number, clientY: number) => {
        rect = canvas.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return null;
        const localX = clientX - rect.left;
        const localY = clientY - rect.top;

        // Cheap screen-space proximity check so hover over empty space skips raycast.
        const nearAny = items.some((item) => {
          const hitRadius = item.radiusPx * 1.45;
          const dx = localX - item.cx;
          const dy = localY - item.cy;
          return dx * dx + dy * dy <= hitRadius * hitRadius;
        });
        if (!nearAny) return null;

        ndc.set(
          (localX / rect.width) * 2 - 1,
          -(localY / rect.height) * 2 + 1,
        );
        raycaster.setFromCamera(ndc, camera);
        const hits = raycaster.intersectObjects(pickMeshes, false);
        const first = hits[0];
        if (!first) return null;
        const item = meshToItem.get(first.object);
        if (!item) return null;
        return { item, worldPoint: first.point };
      };

      const updateDragFromClient = (clientX: number, clientY: number) => {
        if (!activeDrag) return;
        const { item, startClientX, startClientY } = activeDrag;
        const dxPx = clientX - startClientX;
        const dyPx = -(clientY - startClientY);
        const invScale = 1 / Math.max(item.radiusPx, 1);

        // Unrotate screen-space pull by the resting tilt so dragging right/up
        // pulls the rubber cleanly right/up in view space.
        invQuat
          .setFromEuler(new THREE.Euler(item.baseRotX, item.baseRotY, 0))
          .invert();
        tmpVec.set(dxPx * invScale, dyPx * invScale, 0).applyQuaternion(invQuat);
        item.rawPull = { x: tmpVec.x, y: tmpVec.y };
      };

      const onPointerDown = (e: PointerEvent) => {
        if (e.button !== 0 && e.pointerType === "mouse") return;
        const picked = pickLogoAt(e.clientX, e.clientY);
        if (!picked) return;

        e.preventDefault();
        const { item, worldPoint } = picked;
        item.poseGroup.updateMatrixWorld(true);
        const localHit = item.poseGroup.worldToLocal(worldPoint.clone());

        item.grabPoint = {
          x: Math.max(-1, Math.min(1, localHit.x)),
          y: Math.max(-1, Math.min(1, localHit.y)),
          z: Math.max(-0.5, Math.min(0.5, localHit.z)),
        };
        item.rawPull = { x: 0, y: 0 };
        item.squash.s = 0;
        item.squash.sv = 0;
        item.state = "dragging";

        activeDrag = {
          item,
          pointerId: e.pointerId,
          startClientX: e.clientX,
          startClientY: e.clientY,
        };

        try {
          canvas.setPointerCapture(e.pointerId);
        } catch {
          // Synthetic events in tests may not have an active pointerId.
        }
        canvas.style.cursor = "grabbing";
        canvas.dataset.rubberState = "dragging";
        startLoop();
      };

      const onPointerMove = (e: PointerEvent) => {
        if (activeDrag && activeDrag.pointerId === e.pointerId) {
          updateDragFromClient(e.clientX, e.clientY);
          startLoop();
          return;
        }
        if (e.pointerType === "mouse") {
          const hovered = pickLogoAt(e.clientX, e.clientY);
          canvas.style.cursor = hovered ? "grab" : "";
        }
      };

      const releaseDrag = (e: PointerEvent) => {
        if (!activeDrag || activeDrag.pointerId !== e.pointerId) return;
        const { item, pointerId } = activeDrag;
        activeDrag = null;

        try {
          if (canvas.hasPointerCapture(pointerId)) {
            canvas.releasePointerCapture(pointerId);
          }
        } catch {
          // Ignore if already released.
        }

        const hovered =
          e.pointerType === "mouse" ? pickLogoAt(e.clientX, e.clientY) : null;
        canvas.style.cursor = hovered ? "grab" : "";

        if (reducedMotion) {
          resetLogoToRest(item);
          renderOnce();
          if (!hasRunningWork()) stopLoop();
          return;
        }

        item.squash = createSquashKick(
          item.lastClampedPull.x,
          item.lastClampedPull.y,
          LOGO_LOCAL_SIZE,
        );
        item.state = "springing";
        canvas.dataset.rubberState = "springing";
        startLoop();
      };

      const onPointerLeave = () => {
        if (!activeDrag) {
          canvas.style.cursor = "";
        }
      };

      const onVisibilityChange = () => {
        if (document.hidden) {
          stopLoop();
        } else if (hasRunningWork()) {
          startLoop();
        }
      };

      const observer = new ResizeObserver(resize);
      observer.observe(host);
      canvas.addEventListener("pointerdown", onPointerDown);
      canvas.addEventListener("pointermove", onPointerMove);
      canvas.addEventListener("pointerup", releaseDrag);
      canvas.addEventListener("pointercancel", releaseDrag);
      canvas.addEventListener("pointerleave", onPointerLeave);
      document.addEventListener("visibilitychange", onVisibilityChange);
      motionQuery.addEventListener?.("change", onMotionChange);

      cleanup = () => {
        stopLoop();
        observer.disconnect();
        canvas.removeEventListener("pointerdown", onPointerDown);
        canvas.removeEventListener("pointermove", onPointerMove);
        canvas.removeEventListener("pointerup", releaseDrag);
        canvas.removeEventListener("pointercancel", releaseDrag);
        canvas.removeEventListener("pointerleave", onPointerLeave);
        document.removeEventListener("visibilitychange", onVisibilityChange);
        motionQuery.removeEventListener?.("change", onMotionChange);

        const disposedMaterials = new Set<import("three").Material>();
        const disposedTextures = new Set<import("three").Texture>();
        scene.traverse((node) => {
          const mesh = node as import("three").Mesh;
          if (!mesh.isMesh) return;
          mesh.geometry?.dispose();
          const mats = Array.isArray(mesh.material)
            ? mesh.material
            : mesh.material
              ? [mesh.material]
              : [];
          for (const mat of mats) {
            if (disposedMaterials.has(mat)) continue;
            disposedMaterials.add(mat);
            const std = mat as import("three").MeshStandardMaterial;
            if (std.map && !disposedTextures.has(std.map)) {
              disposedTextures.add(std.map);
              std.map.dispose();
            }
            mat.dispose();
          }
        });
        envTarget.dispose();
        pmrem.dispose();
        renderer.dispose();
      };
      if (disposed) cleanup();
    })();

    return () => {
      disposed = true;
      cleanup();
    };
  }, [logosKey, side]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      tabIndex={-1}
      data-rubber-strip={side}
      className={cn(
        "rubber-strip-idle pointer-events-auto block h-full w-full touch-none select-none opacity-0 transition-opacity duration-500",
        className,
      )}
    />
  );
}

/**
 * Places two interactive `RubberLogos` strips into the empty left/right margins
 * beside a centered content column, mounting them ONLY when each margin has at
 * least `minStripWidth` px (default 180 px). On narrower screens Three.js is
 * never loaded and the content layout is completely unaffected.
 */
export function RubberLogoMargins({
  leftLogos,
  rightLogos,
  minStripWidth = MIN_RUBBER_STRIP_WIDTH,
  contentClassName,
  children,
}: RubberLogoMarginsProps) {
  const outerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [stripWidth, setStripWidth] = useState(0);

  useEffect(() => {
    const outer = outerRef.current;
    const content = contentRef.current;
    if (!outer || !content || typeof ResizeObserver === "undefined") return;

    const measure = () => {
      const outerW = outer.getBoundingClientRect().width;
      const contentW = content.getBoundingClientRect().width;
      const available = Math.floor((outerW - contentW) / 2) - STRIP_GUTTER_PX;
      setStripWidth((prev) => {
        const next = available >= minStripWidth ? available : 0;
        return prev === next ? prev : next;
      });
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(outer);
    observer.observe(content);
    return () => observer.disconnect();
  }, [minStripWidth]);

  const showStrips = stripWidth >= minStripWidth;

  return (
    <div
      ref={outerRef}
      className="relative min-h-[min(calc(100dvh-11rem),560px)]"
    >
      {showStrips ? (
        <>
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 left-0 z-0 overflow-hidden"
            style={{ width: stripWidth }}
          >
            <div className="sticky top-24 h-[min(calc(100dvh-9rem),640px)]">
              <RubberLogos logos={leftLogos} side="left" />
            </div>
          </div>
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 right-0 z-0 overflow-hidden"
            style={{ width: stripWidth }}
          >
            <div className="sticky top-24 h-[min(calc(100dvh-9rem),640px)]">
              <RubberLogos logos={rightLogos} side="right" />
            </div>
          </div>
        </>
      ) : null}

      <div ref={contentRef} className={cn("relative z-10", contentClassName)}>
        {children}
      </div>
    </div>
  );
}
