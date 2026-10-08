"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";

import { stage } from "@/lib/stage";

import { type Formation, formations, type SlotRect } from "./formations";

// The page's one 3D scene: a few hundred glossy fins on a fixed canvas behind the content. In
// the hero they are the recorded call, both voices in time; as the page scrolls they lift off
// and settle into whichever bay's stage is in view, as that bay's own data. With no stage in
// view they sink below the fold, out of the way of reading.

const FOV = 30;
const DISTANCE = 20;
const SLOTS = ["hero", "turn", "numbers", "memory"] as const;
const LEAN = 0.34; // radians the hero sculpture leans back

export type SlotName = (typeof SLOTS)[number];

export default function Scene({ data }: { data: Formation["data"] }) {
  return (
    <Canvas
      className="!fixed inset-0 !h-[100lvh] !w-full"
      style={{ pointerEvents: "none" }}
      dpr={[1, 1.75]}
      shadows="soft"
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      camera={{ fov: FOV, position: [0, 0, DISTANCE], near: 0.1, far: 100 }}
    >
      <Fins data={data} />
      <ambientLight intensity={0.38} />
      <directionalLight
        position={[-3, 5, 16]}
        intensity={1.7}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0006}
        shadow-radius={6}
        shadow-camera-left={-16}
        shadow-camera-right={16}
        shadow-camera-top={10}
        shadow-camera-bottom={-10}
        shadow-camera-near={1}
        shadow-camera-far={40}
      />
      <directionalLight position={[8, -4, 6]} intensity={0.3} />
      {/* The wall behind the fins: invisible but for the shadows they cast on it. */}
      <Wall />
      <Room />
    </Canvas>
  );
}

// The wall behind the fins: invisible but for the shadows they cast on it. On a phone's narrow
// stage the shadows smear the thin fins, so it stays bare.
function Wall() {
  const { size } = useThree();
  if (size.width < 700) return null;
  return (
    <mesh position={[0, 0, -1.6]} receiveShadow>
      <planeGeometry args={[80, 50]} />
      <shadowMaterial transparent opacity={0.07} />
    </mesh>
  );
}

// A soft studio room for the fins' gloss to reflect, built once from three's own room preset.
function Room() {
  const { gl, scene } = useThree();
  useEffect(() => {
    const generator = new THREE.PMREMGenerator(gl);
    const texture = generator.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = texture;
    scene.environmentIntensity = 0.42;
    return () => {
      scene.environment = null;
      texture.dispose();
      generator.dispose();
    };
  }, [gl, scene]);
  return null;
}

function Fins({ data }: { data: Formation["data"] }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const { size, viewport } = useThree();
  const count = 240;
  const geometry = useMemo(() => new RoundedBoxGeometry(1, 1, 1, 3, 0.16), []);
  const material = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        // Anodised aluminium: metal under a tint, brushed along the fin.
        roughness: 0.5,
        metalness: 0.22,
        anisotropy: 0.9,
      }),
    [],
  );

  // Each fin's current state, eased every frame toward where its formation wants it.
  const state = useMemo(
    () => ({
      position: new Float32Array(count * 3),
      scale: new Float32Array(count * 3),
      color: new Float32Array(count * 3),
      target: {
        position: new Float32Array(count * 3),
        scale: new Float32Array(count * 3),
        color: new Float32Array(count * 3),
      },
      started: false,
    }),
    [count],
  );
  const slots = useRef(new Map<SlotName, HTMLElement>());
  const matrix = useMemo(() => new THREE.Matrix4(), []);
  const quaternion = useMemo(() => new THREE.Quaternion(), []);
  const euler = useMemo(() => new THREE.Euler(), []);
  const vector = useMemo(() => new THREE.Vector3(), []);
  const scaleVector = useMemo(() => new THREE.Vector3(), []);
  const colour = useMemo(() => new THREE.Color(), []);
  const lean = useRef(0);

  useEffect(() => {
    const find = () => {
      for (const name of SLOTS) {
        const element = document.querySelector<HTMLElement>(`[data-stage-slot="${name}"]`);
        if (element) slots.current.set(name, element);
      }
    };
    find();
    const observer = new MutationObserver(find);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const element = mesh.current;
    if (!element) return;
    element.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(count * 3), 3);
  }, [count]);

  useFrame((frame, delta) => {
    const element = mesh.current;
    if (!element || !element.instanceColor) return;
    const width = size.width;
    const height = size.height;
    const perPixel = viewport.height / height; // world units per CSS pixel at the fins' plane

    // The stage most in view decides the formation; none in view, the fins sink out of sight.
    let best: SlotName | null = null;
    let bestShare = 0.12;
    let rect: SlotRect | null = null;
    for (const name of SLOTS) {
      const slot = slots.current.get(name);
      if (!slot) continue;
      const box = slot.getBoundingClientRect();
      const visible = Math.max(0, Math.min(box.bottom, height) - Math.max(box.top, 0));
      const share = visible / Math.max(1, Math.min(box.height, height));
      if (share > bestShare) {
        bestShare = share;
        best = name;
        rect = {
          x: (box.left + box.width / 2 - width / 2) * perPixel,
          y: -(box.top + box.height / 2 - height / 2) * perPixel,
          width: box.width * perPixel,
          height: box.height * perPixel,
        };
      }
    }

    const time = frame.clock.elapsedTime;
    const target = state.target;
    if (best && rect) {
      const px = (stage.pointer.x * width) / 2;
      const py = (stage.pointer.y * height) / 2;
      const pointer = {
        x: px * perPixel,
        y: -py * perPixel,
        inside: Math.abs(px * perPixel - rect.x) < rect.width / 2 && Math.abs(-py * perPixel - rect.y) < rect.height / 2,
      };
      formations[best]({ data, rect, count, time, target, now: stage.now, playing: stage.playing, board: stage.board, call: stage.call, reduced: stage.reduced, pointer, pixels: rect.width / perPixel });
      // The call leans back from the viewer, so it stands as a sculpture rather than a chart.
      if (best === "hero") {
        for (let i = 0; i < count; i++) {
          const dy = target.position[i * 3 + 1] - rect.y;
          target.position[i * 3 + 1] = rect.y + dy * Math.cos(LEAN);
          target.position[i * 3 + 2] -= dy * Math.sin(LEAN);
        }
      }
    } else {
      // Rest: the fins drop below the fold and shrink, keeping their order.
      for (let i = 0; i < count; i++) {
        target.position[i * 3] = ((i / count) - 0.5) * viewport.width;
        target.position[i * 3 + 1] = -viewport.height * 0.75;
        target.position[i * 3 + 2] = 0;
        target.scale[i * 3] = target.scale[i * 3 + 1] = target.scale[i * 3 + 2] = 0.05;
      }
    }

    // Fins start below the fold and rise into their first formation.
    if (!state.started) {
      for (let i = 0; i < count; i++) {
        state.position[i * 3] = target.position[i * 3];
        state.position[i * 3 + 1] = -viewport.height * 0.7 - (i % 7) * 0.4;
        state.position[i * 3 + 2] = 0;
        state.color.set(target.color.subarray(i * 3, i * 3 + 3), i * 3);
      }
      state.started = true;
    }

    lean.current += ((best === "hero" ? LEAN : 0) - lean.current) * (stage.reduced ? 1 : 1 - Math.exp(-delta * 4));

    // Ease toward the targets: fast enough to follow a scroll, slow enough to read as flight.
    const ease = stage.reduced ? 1 : 1 - Math.exp(-delta * 5.5);
    const easeColour = stage.reduced ? 1 : 1 - Math.exp(-delta * 8);
    const tiltX = stage.reduced ? 0 : stage.pointer.y * 0.06;
    const tiltY = stage.reduced ? 0 : stage.pointer.x * 0.12;
    for (let i = 0; i < count; i++) {
      for (let k = 0; k < 3; k++) {
        const j = i * 3 + k;
        // A little lag down the line, so a formation change ripples rather than jumps.
        const stagger = stage.reduced ? 1 : Math.min(1, ease * (1 - (i / count) * 0.45));
        state.position[j] += (target.position[j] - state.position[j]) * stagger;
        state.scale[j] += (target.scale[j] - state.scale[j]) * stagger;
        state.color[j] += (target.color[j] - state.color[j]) * easeColour;
      }
      vector.set(state.position[i * 3], state.position[i * 3 + 1], state.position[i * 3 + 2]);
      scaleVector.set(Math.max(0.0001, state.scale[i * 3]), Math.max(0.0001, state.scale[i * 3 + 1]), Math.max(0.0001, state.scale[i * 3 + 2]));
      euler.set(tiltX - lean.current, tiltY + (best === "hero" ? (vector.x / Math.max(1, viewport.width)) * -0.5 : 0), 0);
      quaternion.setFromEuler(euler);
      matrix.compose(vector, quaternion, scaleVector);
      element.setMatrixAt(i, matrix);
      colour.setRGB(state.color[i * 3], state.color[i * 3 + 1], state.color[i * 3 + 2], THREE.SRGBColorSpace);
      element.setColorAt(i, colour);
    }
    element.instanceMatrix.needsUpdate = true;
    element.instanceColor.needsUpdate = true;
  });

  return <instancedMesh ref={mesh} args={[geometry, material, count]} frustumCulled={false} castShadow />;
}

