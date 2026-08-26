import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'

// Premium Volkswagen / Nexus AI Brand Palette
const PALETTE = {
  teal: 0x008c82,
  tealGlow: 0x00e5c9,
  cyan: 0x8cbee6,
  cyanBright: 0x64d2ff,
  amber: 0xfaaa3c,
  amberGlow: 0xffcc00,
  green: 0x64a844,
  purple: 0xc882be,
  white: 0xffffff,
  deepBlue: 0x001f2d,
}

// Procedural soft-glow radial texture generator (avoids external asset loading dependencies)
function createGlowSpriteTexture(innerColor = '#00e5c9', midColor = 'rgba(0, 140, 130, 0.45)', size = 128) {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  const center = size / 2
  const grad = ctx.createRadialGradient(center, center, 0, center, center, center)
  grad.addColorStop(0, '#ffffff')
  grad.addColorStop(0.2, innerColor)
  grad.addColorStop(0.55, midColor)
  grad.addColorStop(1, 'rgba(0, 0, 0, 0)')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, size, size)
  const texture = new THREE.CanvasTexture(canvas)
  texture.needsUpdate = true
  return texture
}

/**
 * High-End Holographic Cyber-Physical Operational Twin (Wolfsburg DC)
 * Features:
 * - Holographic gyroscopic core with counter-rotating segmented telemetry rings
 * - 3D faceted crystal icosahedron with procedural inner plasma emission
 * - 6 Specialist Logistics nodes (ERP, WMS, TMS, PPAP, AGVs, Reconciler)
 * - 3D curved bezier laser feeds carrying high-velocity data packets
 * - Undulating perspective warehouse cyber-grid floor
 * - 1,200-particle floating telemetry data vortex with depth blending
 * - Interactive mouse parallax + click-activated operational radar shockwave
 */
export function VwTwinScene({ theme = 'light' }) {
  const hostRef = useRef(null)
  const [interactiveHint, setInteractiveHint] = useState('Click to pulse twin')

  useEffect(() => {
    const host = hostRef.current
    if (!host) return undefined

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const scene = new THREE.Scene()
    
    // Smooth atmospheric fog for depth
    scene.fog = new THREE.FogExp2(0x001724, 0.075)

    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100)
    camera.position.set(0, 0.25, 6.2)

    let renderer
    try {
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
        powerPreference: 'high-performance',
      })
    } catch {
      host.classList.add('is-fallback')
      return () => host.classList.remove('is-fallback')
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.setClearColor(0x000000, 0)
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.domElement.className = 'landing-twin-canvas'
    renderer.domElement.setAttribute('aria-label', 'Interactive 3D Volkswagen Operational Twin')
    host.appendChild(renderer.domElement)

    // Reusable glow textures
    const glowTexTeal = createGlowSpriteTexture('#00e5c9', 'rgba(0, 140, 130, 0.4)')
    const glowTexCyan = createGlowSpriteTexture('#64d2ff', 'rgba(140, 190, 230, 0.4)')
    const glowTexAmber = createGlowSpriteTexture('#ffcc00', 'rgba(250, 170, 60, 0.4)')

    // -------------------------------------------------------------------------
    // 1. Lighting Architecture
    // -------------------------------------------------------------------------
    const ambientLight = new THREE.AmbientLight(0xd0e8f0, 0.8)
    scene.add(ambientLight)

    const coreLight = new THREE.PointLight(PALETTE.tealGlow, 3.2, 8, 1.2)
    coreLight.position.set(0, 0, 0)
    scene.add(coreLight)

    const keyLight = new THREE.DirectionalLight(PALETTE.cyanBright, 1.4)
    keyLight.position.set(4, 5, 4)
    scene.add(keyLight)

    const rimLight = new THREE.DirectionalLight(PALETTE.amber, 1.1)
    rimLight.position.set(-4, -3, -2)
    scene.add(rimLight)

    // -------------------------------------------------------------------------
    // 2. Master Twin Group Hierarchy
    // -------------------------------------------------------------------------
    const masterTwin = new THREE.Group()
    scene.add(masterTwin)

    // -------------------------------------------------------------------------
    // 3. Central Holographic Core & Gyroscope Telemetry Rings
    // -------------------------------------------------------------------------
    const coreGroup = new THREE.Group()
    masterTwin.add(coreGroup)

    // Inner wireframe icosahedron
    const icoGeo = new THREE.IcosahedronGeometry(0.55, 1)
    const icoMat = new THREE.MeshStandardMaterial({
      color: PALETTE.tealGlow,
      emissive: PALETTE.teal,
      emissiveIntensity: 0.85,
      wireframe: true,
      transparent: true,
      opacity: 0.88,
    })
    const innerCore = new THREE.Mesh(icoGeo, icoMat)
    coreGroup.add(innerCore)

    // Outer crystal shield octahedron
    const octGeo = new THREE.OctahedronGeometry(0.76, 0)
    const octMat = new THREE.MeshStandardMaterial({
      color: PALETTE.cyan,
      emissive: PALETTE.teal,
      emissiveIntensity: 0.35,
      roughness: 0.1,
      metalness: 0.9,
      transparent: true,
      opacity: 0.38,
      wireframe: true,
    })
    const crystalCore = new THREE.Mesh(octGeo, octMat)
    coreGroup.add(crystalCore)

    // Central pulsing glow billboard sprite
    if (glowTexTeal) {
      const coreSpriteMat = new THREE.SpriteMaterial({
        map: glowTexTeal,
        color: PALETTE.tealGlow,
        transparent: true,
        opacity: 0.75,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      })
      const coreSprite = new THREE.Sprite(coreSpriteMat)
      coreSprite.scale.set(2.4, 2.4, 1)
      coreGroup.add(coreSprite)
    }

    // Gyroscope Telemetry Gimbal Rings
    const ringMaterials = [
      new THREE.MeshBasicMaterial({ color: PALETTE.tealGlow, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending }),
      new THREE.MeshBasicMaterial({ color: PALETTE.cyanBright, transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending }),
      new THREE.MeshBasicMaterial({ color: PALETTE.amber, transparent: true, opacity: 0.65, blending: THREE.AdditiveBlending }),
    ]

    const gyroRing1 = new THREE.Mesh(new THREE.TorusGeometry(0.96, 0.012, 16, 100), ringMaterials[0])
    gyroRing1.rotation.x = Math.PI / 2.3
    coreGroup.add(gyroRing1)

    const gyroRing2 = new THREE.Mesh(new THREE.TorusGeometry(1.18, 0.009, 16, 100), ringMaterials[1])
    gyroRing2.rotation.y = Math.PI / 3.4
    gyroRing2.rotation.x = -Math.PI / 4.2
    coreGroup.add(gyroRing2)

    const gyroRing3 = new THREE.Mesh(new THREE.TorusGeometry(1.42, 0.007, 16, 120), ringMaterials[2])
    gyroRing3.rotation.x = Math.PI / 1.8
    gyroRing3.rotation.z = Math.PI / 5.5
    coreGroup.add(gyroRing3)

    // Dashed Outer Equatorial Horizon Radar Ring
    const horizonGeo = new THREE.BufferGeometry()
    const horizonPoints = []
    const HORIZON_SEGMENTS = 80
    for (let i = 0; i <= HORIZON_SEGMENTS; i++) {
      const theta = (i / HORIZON_SEGMENTS) * Math.PI * 2
      horizonPoints.push(new THREE.Vector3(Math.cos(theta) * 1.68, 0, Math.sin(theta) * 1.68))
    }
    horizonGeo.setFromPoints(horizonPoints)
    const horizonLine = new THREE.Line(
      horizonGeo,
      new THREE.LineDashedMaterial({
        color: PALETTE.cyan,
        dashSize: 0.12,
        gapSize: 0.06,
        transparent: true,
        opacity: 0.5,
        blending: THREE.AdditiveBlending,
      })
    )
    horizonLine.computeLineDistances()
    coreGroup.add(horizonLine)

    // -------------------------------------------------------------------------
    // 4. Logistics Nodes & Dynamic Curved Laser Feeds
    // -------------------------------------------------------------------------
    const NODES_CONFIG = [
      { name: 'ERP S/4HANA', color: PALETTE.tealGlow, radius: 2.15, angle: 0.15, y: 0.45, speed: 0.18, size: 0.09 },
      { name: 'WMS High-Bay', color: PALETTE.cyanBright, radius: 2.35, angle: 1.25, y: -0.35, speed: 0.14, size: 0.085 },
      { name: 'TMS Inbound', color: PALETTE.amber, radius: 2.5, angle: 2.35, y: 0.55, speed: 0.22, size: 0.09 },
      { name: 'PPAP Quality', color: PALETTE.green, radius: 2.1, angle: 3.45, y: -0.4, speed: 0.16, size: 0.08 },
      { name: 'AGV Fleet', color: PALETTE.purple, radius: 2.4, angle: 4.55, y: 0.2, speed: 0.2, size: 0.085 },
      { name: 'Reconciler', color: PALETTE.cyan, radius: 2.25, angle: 5.6, y: -0.5, speed: 0.15, size: 0.09 },
    ]

    const nodesGroup = new THREE.Group()
    masterTwin.add(nodesGroup)

    const nodeMeshes = []
    const laserLines = []
    const dataPackets = []

    NODES_CONFIG.forEach((cfg, idx) => {
      // Node 3D Mesh (dual faceted diamond octahedron)
      const nodeGeom = new THREE.OctahedronGeometry(cfg.size, 0)
      const nodeMat = new THREE.MeshStandardMaterial({
        color: cfg.color,
        emissive: cfg.color,
        emissiveIntensity: 0.9,
        roughness: 0.1,
        metalness: 0.9,
      })
      const nodeMesh = new THREE.Mesh(nodeGeom, nodeMat)
      nodeMesh.userData = { ...cfg, currentAngle: cfg.angle }

      // Orbiting halo sprite around node
      const haloTex = idx % 2 === 0 ? glowTexTeal : (idx % 3 === 0 ? glowTexAmber : glowTexCyan)
      if (haloTex) {
        const haloSprite = new THREE.Sprite(new THREE.SpriteMaterial({
          map: haloTex,
          color: cfg.color,
          transparent: true,
          opacity: 0.8,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        }))
        haloSprite.scale.set(0.65, 0.65, 1)
        nodeMesh.add(haloSprite)
      }

      nodesGroup.add(nodeMesh)
      nodeMeshes.push(nodeMesh)

      // Laser Feed Bezier Curve connecting Node to Core
      const curveGeo = new THREE.BufferGeometry()
      const curveMat = new THREE.LineBasicMaterial({
        color: cfg.color,
        transparent: true,
        opacity: 0.38,
        blending: THREE.AdditiveBlending,
      })
      const lineMesh = new THREE.Line(curveGeo, curveMat)
      nodesGroup.add(lineMesh)
      laserLines.push({ line: lineMesh, nodeMesh })

      // 2 High-velocity laser data packets traveling on each feed
      for (let p = 0; p < 2; p++) {
        const packetGeo = new THREE.SphereGeometry(0.038, 8, 8)
        const packetMat = new THREE.MeshBasicMaterial({
          color: PALETTE.white,
          transparent: true,
          opacity: 0.95,
          blending: THREE.AdditiveBlending,
        })
        const packet = new THREE.Mesh(packetGeo, packetMat)
        packet.userData = {
          nodeIndex: idx,
          offset: p * 0.5,
          speed: 0.38 + idx * 0.04,
        }
        nodesGroup.add(packet)
        dataPackets.push(packet)
      }
    })

    // -------------------------------------------------------------------------
    // 5. Undulating Cyber Warehouse Floor Grid (Radar Lattice)
    // -------------------------------------------------------------------------
    const GRID_SIZE = 7.5
    const GRID_DIVISIONS = 24
    const gridHelper = new THREE.GridHelper(GRID_SIZE, GRID_DIVISIONS, PALETTE.tealGlow, 0x003b47)
    gridHelper.position.y = -1.65
    gridHelper.material.transparent = true
    gridHelper.material.opacity = 0.35
    gridHelper.material.blending = THREE.AdditiveBlending
    masterTwin.add(gridHelper)

    // Corner pulse markers on the grid
    const cornerMarkers = new THREE.Group()
    masterTwin.add(cornerMarkers)
    ;[-2.4, 2.4].forEach((cx) => {
      ;[-2.4, 2.4].forEach((cz) => {
        const marker = new THREE.Mesh(
          new THREE.CylinderGeometry(0.015, 0.015, 0.45, 6),
          new THREE.MeshBasicMaterial({ color: PALETTE.tealGlow, transparent: true, opacity: 0.6, blending: THREE.AdditiveBlending })
        )
        marker.position.set(cx, -1.42, cz)
        cornerMarkers.add(marker)
      })
    })

    // -------------------------------------------------------------------------
    // 6. Floating Telemetry Data Particle Vortex (1,000 Particles)
    // -------------------------------------------------------------------------
    const PARTICLE_COUNT = 900
    const particleGeo = new THREE.BufferGeometry()
    const particlePositions = new Float32Array(PARTICLE_COUNT * 3)
    const particleColors = new Float32Array(PARTICLE_COUNT * 3)
    const particleData = []

    const colorChoices = [
      new THREE.Color(PALETTE.tealGlow),
      new THREE.Color(PALETTE.cyanBright),
      new THREE.Color(PALETTE.amber),
      new THREE.Color(PALETTE.green),
      new THREE.Color(0xffffff),
    ]

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const radius = 0.75 + Math.pow(Math.random(), 0.65) * 2.85
      const theta = Math.random() * Math.PI * 2
      const phi = (Math.random() - 0.5) * Math.PI * 0.75
      
      const x = radius * Math.cos(phi) * Math.cos(theta)
      const y = radius * Math.sin(phi) * 0.85
      const z = radius * Math.cos(phi) * Math.sin(theta)

      particlePositions[i * 3] = x
      particlePositions[i * 3 + 1] = y
      particlePositions[i * 3 + 2] = z

      const c = colorChoices[Math.floor(Math.random() * colorChoices.length)]
      particleColors[i * 3] = c.r
      particleColors[i * 3 + 1] = c.g
      particleColors[i * 3 + 2] = c.b

      particleData.push({
        radius,
        theta,
        phi,
        speed: (0.003 + Math.random() * 0.006) * (Math.random() > 0.5 ? 1 : -1),
        bobSpeed: 0.8 + Math.random() * 1.6,
        bobPhase: Math.random() * Math.PI * 2,
      })
    }

    particleGeo.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3))
    particleGeo.setAttribute('color', new THREE.BufferAttribute(particleColors, 3))

    const particleMat = new THREE.PointsMaterial({
      size: 0.052,
      vertexColors: true,
      transparent: true,
      opacity: 0.78,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    const particleSystem = new THREE.Points(particleGeo, particleMat)
    masterTwin.add(particleSystem)

    // -------------------------------------------------------------------------
    // 7. Interactive Radar Scanwave Shockwave Ring
    // -------------------------------------------------------------------------
    const shockwaveGeo = new THREE.RingGeometry(0.1, 0.16, 64)
    const shockwaveMat = new THREE.MeshBasicMaterial({
      color: PALETTE.tealGlow,
      transparent: true,
      opacity: 0,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    })
    const shockwaveMesh = new THREE.Mesh(shockwaveGeo, shockwaveMat)
    shockwaveMesh.rotation.x = Math.PI / 2
    masterTwin.add(shockwaveMesh)

    let shockwaveState = { active: false, progress: 0, speed: 1.4 }

    const triggerPulse = () => {
      shockwaveState = { active: true, progress: 0, speed: 1.4 }
      coreLight.intensity = 5.5
      setInteractiveHint('Scanning 72,900 twin signals…')
      setTimeout(() => setInteractiveHint('Click to pulse twin'), 2200)
    }

    // Trigger pulse on host click
    const onHostClick = () => {
      triggerPulse()
    }
    host.addEventListener('click', onHostClick)

    // -------------------------------------------------------------------------
    // 8. Mouse Physics & Interactive Raycaster
    // -------------------------------------------------------------------------
    const pointer = { x: 0, y: 0, targetX: 0, targetY: 0 }
    const onPointerMove = (event) => {
      const bounds = host.getBoundingClientRect()
      pointer.targetX = ((event.clientX - bounds.left) / bounds.width - 0.5) * 2
      pointer.targetY = ((event.clientY - bounds.top) / bounds.height - 0.5) * 2
    }
    host.addEventListener('pointermove', onPointerMove)

    // Resize Handler
    let width = 1
    let height = 1
    const resize = () => {
      width = Math.max(host.clientWidth, 1)
      height = Math.max(host.clientHeight, 1)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height, false)
    }
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null
    observer?.observe(host)
    resize()

    // -------------------------------------------------------------------------
    // 9. Main 60fps Animation Loop
    // -------------------------------------------------------------------------
    const clock = new THREE.Clock()
    let animationFrame

    const draw = () => {
      const elapsed = clock.getElapsedTime()
      const dt = clock.getDelta()
      const time = reducedMotion ? 0 : elapsed

      // 1. Smooth Pointer Lerp with Gentle Inertia
      pointer.x += (pointer.targetX - pointer.x) * 0.055
      pointer.y += (pointer.targetY - pointer.y) * 0.055

      // 2. Master Twin Group Parallax & Continuous Gentle Levitation
      masterTwin.rotation.y = time * 0.065 + pointer.x * 0.22
      masterTwin.rotation.x = -0.04 - pointer.y * 0.14
      masterTwin.position.y = Math.sin(time * 0.8) * 0.05

      // 3. Central Core Transformations
      innerCore.rotation.x = time * 0.45
      innerCore.rotation.y = time * 0.65
      const corePulse = 1 + Math.sin(time * 3.2) * 0.06
      innerCore.scale.setScalar(corePulse)

      crystalCore.rotation.x = -time * 0.3
      crystalCore.rotation.z = time * 0.4
      crystalCore.scale.setScalar(1 + Math.sin(time * 2.1) * 0.04)

      // Light breathing
      coreLight.intensity = THREE.MathUtils.lerp(coreLight.intensity, 3.2 + Math.sin(time * 3.0) * 0.6, 0.08)

      // 4. Gyroscopic Telemetry Rings Counter-Rotation
      gyroRing1.rotation.z = time * 0.35
      gyroRing1.rotation.y = Math.sin(time * 0.5) * 0.2
      gyroRing2.rotation.x = -time * 0.42
      gyroRing2.rotation.z = Math.cos(time * 0.4) * 0.25
      gyroRing3.rotation.z = time * 0.22
      horizonLine.rotation.y = -time * 0.18

      // 5. Update Logistics Nodes, Dynamic Bezier Laser Feeds & Packets
      const corePos = new THREE.Vector3(0, 0, 0)
      nodeMeshes.forEach((mesh, idx) => {
        const d = mesh.userData
        d.currentAngle += (reducedMotion ? 0 : d.speed * 0.016)
        
        const nodeX = Math.cos(d.currentAngle) * d.radius
        const nodeZ = Math.sin(d.currentAngle) * d.radius
        const nodeY = d.y + Math.sin(time * 1.8 + idx) * 0.12

        mesh.position.set(nodeX, nodeY, nodeZ)
        mesh.rotation.x = time * 1.2
        mesh.rotation.y = time * 1.5

        // Calculate Curved Quadratic Bezier between Core and Node
        const midPoint = new THREE.Vector3(
          nodeX * 0.5 + Math.sin(time * 2.0 + idx) * 0.15,
          (nodeY + corePos.y) * 0.5 + 0.35,
          nodeZ * 0.5 + Math.cos(time * 2.0 + idx) * 0.15
        )
        const curve = new THREE.QuadraticBezierCurve3(corePos, midPoint, mesh.position)
        const curvePoints = curve.getPoints(24)
        
        const lineItem = laserLines[idx]
        if (lineItem?.line) {
          lineItem.line.geometry.setFromPoints(curvePoints)
        }

        // Update data packets traveling along this specific curve
        dataPackets.filter((p) => p.userData.nodeIndex === idx).forEach((packet) => {
          const pData = packet.userData
          const progress = (time * pData.speed + pData.offset) % 1
          const pt = curve.getPoint(progress)
          if (pt) {
            packet.position.copy(pt)
            const scale = Math.sin(progress * Math.PI) * 1.25 + 0.3
            packet.scale.setScalar(scale)
          }
        })
      })

      // 6. Animate 1,000-Particle Swarm
      const positions = particleGeo.attributes.position.array
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        const p = particleData[i]
        p.theta += (reducedMotion ? 0 : p.speed)
        
        const r = p.radius + Math.sin(time * p.bobSpeed + p.bobPhase) * 0.08
        const py = r * Math.sin(p.phi) * 0.85 + Math.sin(time * 1.2 + p.bobPhase) * 0.06
        const px = r * Math.cos(p.phi) * Math.cos(p.theta)
        const pz = r * Math.cos(p.phi) * Math.sin(p.theta)

        positions[i * 3] = px
        positions[i * 3 + 1] = py
        positions[i * 3 + 2] = pz
      }
      particleGeo.attributes.position.needsUpdate = true

      // 7. Undulating Floor Grid Pulse
      gridHelper.position.y = -1.65 + Math.sin(time * 1.4) * 0.03
      gridHelper.material.opacity = 0.28 + Math.sin(time * 2.2) * 0.1

      // 8. Radar Shockwave Expansion Animation
      if (shockwaveState.active) {
        shockwaveState.progress += dt * shockwaveState.speed
        const scale = shockwaveState.progress * 32.0 + 1.0
        shockwaveMesh.scale.set(scale, scale, 1)
        shockwaveMat.opacity = Math.max(0, (1 - shockwaveState.progress) * 0.85)
        
        if (shockwaveState.progress >= 1) {
          shockwaveState.active = false
          shockwaveMat.opacity = 0
        }
      }

      renderer.render(scene, camera)
      animationFrame = window.requestAnimationFrame(draw)
    }

    draw()

    // -------------------------------------------------------------------------
    // Cleanup on Unmount
    // -------------------------------------------------------------------------
    return () => {
      window.cancelAnimationFrame(animationFrame)
      observer?.disconnect()
      host.removeEventListener('pointermove', onPointerMove)
      host.removeEventListener('click', onHostClick)

      scene.traverse((object) => {
        if (object.geometry) object.geometry.dispose()
        if (object.material) {
          const materials = Array.isArray(object.material) ? object.material : [object.material]
          materials.forEach((mat) => {
            if (mat.map) mat.map.dispose()
            mat.dispose()
          })
        }
      })
      glowTexTeal?.dispose()
      glowTexCyan?.dispose()
      glowTexAmber?.dispose()
      renderer.dispose()
      if (renderer.domElement.parentNode === host) {
        host.removeChild(renderer.domElement)
      }
    }
  }, [theme])

  return (
    <div ref={hostRef} className="landing-twin-scene" aria-hidden="true" />
  )
}

