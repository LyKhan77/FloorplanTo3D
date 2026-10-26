import { useRef } from 'react';
import { Header, HeaderName, Theme } from '@carbon/react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { Mesh } from 'three';

function SpinningCube() {
  const ref = useRef<Mesh>(null);
  useFrame((_, dt) => {
    if (ref.current) ref.current.rotation.y += dt * 0.6;
  });
  return (
    <mesh ref={ref}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="#0f62fe" />
    </mesh>
  );
}

export default function App() {
  return (
    <Theme theme="g100" style={{ height: '100%' }}>
      <Header aria-label="Floorplan3D">
        <HeaderName prefix="">Floorplan3D</HeaderName>
      </Header>
      <main style={{ position: 'fixed', inset: '48px 0 0 0' }}>
        <Canvas camera={{ position: [2.5, 2, 2.5] }}>
          <ambientLight intensity={0.4} />
          <directionalLight position={[3, 5, 2]} />
          <SpinningCube />
          <OrbitControls />
        </Canvas>
      </main>
    </Theme>
  );
}
