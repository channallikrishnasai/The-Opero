/* ===========================================================================
    OPERO — 3D holographic presence (avatar3d.js)
    ---------------------------------------------------------------------------
    The genuine-3D component for the visual-intelligence layer.

    It plugs into the existing deep-space scene through window.__operoWorld
    (exported by index.html) and shares the same renderer, composer, camera and
    audio feed.  Everything is transform-based — particles are built ONCE from
    the measured head geometry that core/avatar_mesh already produces, and all
    motion (look-at, breath, blink, jaw/brow, face -> object morphs) is group
    scaling/rotation/opacity/alpha and staged draw-ranges.  No per-frame vertex
    buffer writes, no generated code: the same physics as the galaxy, applied
    to a face.

    Public API (called from Python through widget.js bridge):
      window.setFaceMesh(payload)   measured head geometry (+ anchors)
      window.applyIntent(dir)       validated visual directive
      window.getVisualDiagnostics() {ready, face, last, errors}
      window.setAvatarState(state)  IDLE|LISTENING|THINKING|SPEAKING|
                                      VISUALIZING|ERROR|SUCCESS
      window.setVisualState(state)  FACE_ONLY|TRANSITIONING|VISUALIZING
      window.triggerTransitionIn(dir)  face → object morph
      window.triggerTransitionOut()    object → face morph
    =========================================================================== */

(function () {
  "use strict";

  var world = window.__operoWorld;
  if (!world) return;               // no WebGL page -> stay inert (galaxy only)
  var THREE = window.THREE;

  var TAU = Math.PI * 2;
  var ERRORS = [];
  var DIAG = { ready: false, face: false, last: null, errors: ERRORS };

  /* ── Avatar states ─────────────────────────────────────────────── */
  // ── Causal chain templates (shared with Python) ────
var CAUSAL_CHAINS = {
  engine_combustion: [
    { step: 1, label: "Fuel + Air", entity: "fuel", camera: "wide" },
    { step: 2, label: "Compression", entity: "piston", camera: "focus" },
    { step: 3, label: "Combustion", entity: "engine", camera: "closeup" },
    { step: 4, label: "Pressure", entity: "engine", camera: "focus" },
    { step: 5, label: "Piston Motion", entity: "piston", camera: "side" },
    { step: 6, label: "Crankshaft", entity: "crankshaft", camera: "focus" },
    { step: 7, label: "Rotation", entity: "gear", camera: "wide" },
  ],
  circulation: [
    { step: 1, label: "Heart Pumps", entity: "heart", camera: "focus" },
    { step: 2, label: "Blood to Lungs", entity: "blood_vessels", camera: "follow" },
    { step: 3, label: "Oxygenation", entity: "lungs", camera: "focus" },
    { step: 4, label: "Blood to Body", entity: "blood_vessels", camera: "wide" },
  ],
};

// ── Inspection modes ────────────────────────────────
var INSPECTION_MODES = ["normal", "cutaway", "exploded", "transparent", "isolated", "cross_section", "wireframe", "xray"];

// ── Temporal states ─────────────────────────────────
var TEMPORAL_STATES = ["playing", "paused", "slow", "fast", "stepped", "rewinding", "reset"];

// ── Camera directives ───────────────────────────────
var CAMERA_DIRECTIVES = ["WIDE", "FOCUS", "CLOSEUP", "ORBIT", "FOLLOW", "TOP_DOWN", "CINEMATIC", "INSPECTION", "ZOOM_IN", "ZOOM_OUT"];

// ── Entity relationships ────────────────────────────
var RELATIONSHIPS = {
  engine: [{ target: "piston", relation: "contains" }, { target: "crankshaft", relation: "contains" }, { target: "gear", relation: "contains" }, { target: "fuel", relation: "uses" }],
  piston: [{ target: "crankshaft", relation: "drives" }, { target: "engine", relation: "part_of" }],
  crankshaft: [{ target: "piston", relation: "driven_by" }, { target: "engine", relation: "part_of" }],
  heart: [{ target: "blood_vessels", relation: "drives" }, { target: "lungs", relation: "connects" }],
};

var AVATAR_STATES = {
    IDLE:       { glow: 0.15, particles: 0.3,  blinkRate: 3.0 },
    LISTENING:  { glow: 0.35, particles: 0.5,  blinkRate: 2.5 },
    THINKING:   { glow: 0.60, particles: 0.7,  blinkRate: 5.0 },
    PROCESSING: { glow: 0.50, particles: 0.6,  blinkRate: 4.0 },
    SPEAKING:   { glow: 0.90, particles: 1.0,  blinkRate: 1.5 },
    VISUALIZING:{ glow: 0.85, particles: 0.9,  blinkRate: 2.0 },
    ERROR:      { glow: 0.70, particles: 0.4,  blinkRate: 0.5 },
    SUCCESS:    { glow: 0.95, particles: 1.0,  blinkRate: 0.3 },
  };

  var currentAvatarState = "IDLE";
  var avatarStateParams = AVATAR_STATES.IDLE;

  /* ── Face↔Object transition state ──────────────────────────────── */
  var visualState = "FACE_ONLY";   // FACE_ONLY, TRANSITIONING, VISUALIZING
  var activeSubject = null;
  var transitionPhase = null;     // morph_in, hold, morph_out
  var transitionTimer = 0;

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function ease(t) { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function rnd() { return Math.random() - 0.5; }

  // ── Camera mode handler ───────────────────────
  function applyCameraMode(mode, target) {
    if (!camera) return;
    var dist = 10;
    switch (mode) {
      case 'WIDE':
        dist = 20; camera.position.set(0, 5, dist);
        break;
      case 'FOCUS':
        dist = 8; camera.position.set(0, 2, dist);
        break;
      case 'CLOSEUP':
        dist = 4; camera.position.set(0, 1.5, dist);
        break;
      case 'TOP_DOWN':
        dist = 15; camera.position.set(0, dist, 0);
        camera.lookAt(0, 0, 0);
        break;
      case 'ORBIT':
        var t = elapsed * 0.5;
        camera.position.set(Math.cos(t) * 8, 3, Math.sin(t) * 8);
        camera.lookAt(0, 0, 0);
        break;
      case 'FOLLOW':
        if (target && target.position) {
          camera.position.set(target.position.x, target.position.y + 2,
                                target.position.z + 6);
          camera.lookAt(target.position);
        }
        break;
      case 'CINEMATIC':
        dist = 12; camera.position.set(0, 8, dist);
        break;
      case 'INSPECTION':
        dist = 5; camera.position.set(2, 2, 5);
        break;
      case 'ZOOM_IN':
        dist = 3; camera.position.set(0, 1, dist);
        break;
      case 'ZOOM_OUT':
        dist = 25; camera.position.set(0, 10, dist);
        break;
      default:
        dist = 10; camera.position.set(0, 5, dist);
    }
    camera.fov = mode === 'CLOSEUP' ? 30 : mode === 'WIDE' ? 60 : 45;
    camera.updateProjectionMatrix();
  }

  // ── Causal chain renderer ─────────────────────
  function renderCausalChain(chain, step) {
    if (!chain || !chain.length) return;
    var s = Math.min(step, chain.length - 1);
    var chainGroup = new THREE.Group();
    chainGroup.userData.isCausalChain = true;
    for (var i = 0; i < chain.length; i++) {
      var node = chain[i];
      var sphereGeo = new THREE.SphereGeometry(0.15, 8, 6);
      var isActive = i === s;
      var mat = new THREE.MeshStandardMaterial({
        color: isActive ? 0x00ff88 : 0x333344,
        emissive: isActive ? 0x00ff88 : 0x000000,
        emissiveIntensity: isActive ? 2.0 : 0.1,
        transparent: true,
        opacity: isActive ? 1.0 : 0.3,
      });
      var sphere = new THREE.Mesh(sphereGeo, mat);
      var angle = (i / chain.length) * TAU;
      sphere.position.set(Math.cos(angle) * 2, Math.sin(angle) * 0.5, 0);
      chainGroup.add(sphere);
      // Add directional link to next node
      if (i < chain.length - 1) {
        var next = chain[i + 1];
        var lineGeo = new THREE.BufferGeometry().setFromPoints([
          sphere.position,
          new THREE.Vector3(
            Math.cos((i + 1) / chain.length * TAU) * 2,
            Math.sin((i + 1) / chain.length * TAU) * 0.5, 0
          )
        ]);
        var lineMat = new THREE.LineBasicMaterial({
          color: isActive ? 0x00ff88 : 0x222233,
          transparent: true, opacity: isActive ? 0.8 : 0.2,
        });
        var line = new THREE.Line(lineGeo, lineMat);
        chainGroup.add(line);
      }
      // Add label sprite
      var label = createLabel(node.label || ('Step ' + (i + 1)));
      label.position.copy(sphere.position);
      label.position.y += 0.4;
      chainGroup.add(label);
    }
    sceneAdd(chainGroup);
    avatar.causalChainGroup = chainGroup;
  }

  function createLabel(text) {
    var canvas = document.createElement('canvas');
    canvas.width = 256; canvas.height = 64;
    var ctx = canvas.getContext('2d');
    ctx.fillStyle = '#00ff88';
    ctx.font = 'bold 28px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(text, 128, 40);
    var texture = new THREE.CanvasTexture(canvas);
    var spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true });
    var sprite = new THREE.Sprite(spriteMat);
    sprite.scale.set(1.5, 0.4, 1);
    return sprite;
  }

  // ── Inspection mode handler ───────────────────
  function applyInspectionMode(mode, isolateList, transparency, exploded) {
    avatar.inspectionMode = mode;
    avatar.isolateList = isolateList || [];
    avatar.inspectionTransparency = transparency;
    avatar.exploded = exploded;
    // Apply to all scene objects
    if (world.scene) {
      world.scene.traverse(function (obj) {
        if (obj.isMesh || obj.isPoints || obj.isLine) {
          if (isolateList && isolateList.length > 0) {
            var isIsolated = isolateList.some(function (id) {
              return obj.userData && obj.userData.entityId === id;
            });
            obj.material.transparent = true;
            obj.material.opacity = isIsolated ? 1.0 : transparency;
            obj.visible = isIsolated || transparency < 1.0;
          } else if (mode === 'transparent') {
            obj.material.transparent = true;
            obj.material.opacity = Math.max(0.1, 1.0 - transparency);
          } else if (mode === 'cutaway') {
            obj.material.transparent = true;
            obj.material.opacity = 0.5;
          } else if (mode === 'exploded') {
            obj.material.transparent = true;
            obj.material.opacity = 1.0;
            if (exploded) {
              var dir = obj.position.clone().normalize();
              obj.position.add(dir.multiplyScalar(0.5));
            }
          } else if (mode === 'xray') {
            obj.material.transparent = true;
            obj.material.opacity = 0.2;
          } else if (mode === 'wireframe') {
            obj.material.wireframe = true;
          } else {
            obj.material.transparent = false;
            obj.material.opacity = 1.0;
            obj.material.wireframe = false;
          }
        }
      });
    }
  }

  // ── Temporal controls ─────────────────────────
  function applyTemporalState(state, speed, step) {
    avatar.temporalState = state;
    avatar.temporalSpeed = speed;
    avatar.temporalStep = step;
    // Update scene animation speed
    if (world.scene) {
      world.scene.traverse(function (obj) {
        if (obj.userData && obj.userData.animSpeed !== undefined) {
          obj.userData.animSpeed = speed;
        }
      });
    }
  }

  // ── Real 3D object builders ───────────────────
  // Each builder returns a THREE.Group with the actual shape

  /* --- Avatar states --- */
  var AVATAR_STATES = {
    IDLE:       { glow: 0.15, particles: 0.3,  blinkRate: 3.0 },
    LISTENING:  { glow: 0.35, particles: 0.5,  blinkRate: 2.5 },
    THINKING:   { glow: 0.60, particles: 0.7,  blinkRate: 5.0 },
    PROCESSING: { glow: 0.50, particles: 0.6,  blinkRate: 4.0 },
    SPEAKING:   { glow: 0.90, particles: 1.0,  blinkRate: 1.5 },
    VISUALIZING:{ glow: 0.85, particles: 0.9,  blinkRate: 2.0 },
    ERROR:      { glow: 0.70, particles: 0.4,  blinkRate: 0.5 },
    SUCCESS:    { glow: 0.95, particles: 1.0,  blinkRate: 0.3 },
  };
  var currentAvatarState = 'IDLE';
  var visualState = 'FACE_ONLY';
  var activeSubject = null;

  var HOME = { x: 0, y: 1.35, z: 0 };       // where the head lives
  var OPERO = 0x00d4ff;                     // identity blue/cyan
  var WHITE = 0xd8f8ff;

  /* ── materials ────────────────────────────────────────────────────────
     One factory, bounded params.  `kind` comes from the validated registry;
     numbers stay inside safe ranges set here, never from the intent. */
  var MATERIAL_KINDS = {
    holographic: { opacity: 0.55, additive: true,  rim: true  },
    glass:       { opacity: 0.30, additive: false, rim: true  },
    metal:       { opacity: 0.85, additive: true,  rim: true  },
    matte:       { opacity: 0.95, additive: false, rim: false },
    emissive:    { opacity: 0.80, additive: true,  rim: false },
    particle:    { opacity: 0.65, additive: true,  rim: false },
    transparent: { opacity: 0.16, additive: false, rim: true  },
  };

  function makeMeshMaterial(kind, color) {
    var m = MATERIAL_KINDS[kind] || MATERIAL_KINDS.holographic;
    return new THREE.MeshBasicMaterial({
      color: color || OPERO,
      transparent: true,
      opacity: m.opacity,
      blending: m.additive ? THREE.AdditiveBlending : THREE.SubtractiveBlending,
      depthWrite: !m.additive,
      side: THREE.DoubleSide,
    });
  }

  function makeLineMaterial(color, opacity) {
    return new THREE.LineBasicMaterial({
      color: color, transparent: true, opacity: opacity || 0.35,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
  }

  function makePointMaterial(color, opacity, size) {
    return new THREE.PointsMaterial({
      color: color || OPERO, size: size || 0.09,
      transparent: true, opacity: opacity || 0.9,
      blending: THREE.AdditiveBlending, depthWrite: false,
      sizeAttenuation: true, vertexColors: false,
    });
  }

  function disposeNode(node) {
    if (!node) return;
    try {
      var list = node.children ? node.children.slice() : [node];
      for (var i = 0; i < list.length; i++) {
        var child = list[i];
        try {
          if (child.geometry) child.geometry.dispose();
          if (child.material) {
            if (child.material.map) child.material.map.dispose();
            child.material.dispose();
          }
        } catch (e) { /* best effort */ }
        if (child.children && child.children.length) disposeNode(child);
      }
      if (node.geometry) node.geometry.dispose();
      if (node.material) node.material.dispose();
    } catch (e) { /* best effort */ }
  }

  function makePointsAt(points, size, opacity) {
    var n = points.length;
    var pos = new Float32Array(n * 3);
    for (var i = 0; i < n; i++) {
      pos[i * 3] = points[i].x; pos[i * 3 + 1] = points[i].y; pos[i * 3 + 2] = points[i].z;
    }
    var geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    var mat = makePointMaterial(null, opacity || 0.9, size);
    var pts = new THREE.Points(geo, mat);
    pts.frustumCulled = false;
    return pts;
  }

  function makeLines(pairs, color, opacity) {
    var n = pairs.length;
    var pos = new Float32Array(n * 2 * 3);
    for (var i = 0; i < n; i++) {
      pos[i * 6] = pairs[i].a.x; pos[i * 6 + 1] = pairs[i].a.y; pos[i * 6 + 2] = pairs[i].a.z;
      pos[i * 6 + 3] = pairs[i].b.x; pos[i * 6 + 4] = pairs[i].b.y; pos[i * 6 + 5] = pairs[i].b.z;
    }
    var geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    return new THREE.LineSegments(geo, makeLineMaterial(color, opacity));
  }

  /* ── avatar (the 3D presence) ───────────────────────────────────────────── */
  var MESH = null;
  var avatar = {
    root: null, jaw: null, brow: null, eyeL: null, eyeR: null,
    cloud: null, wire: null, solid: null, aura: null, rim: null,
    particles: null, eyes: null,
    presence: 1.0, blinkT: 2.0 + Math.random() * 2, blink: 0,
    look: { yaw: 0, pitch: 0 }, open: 0, browLn: 0, audSm: 0,
    state: 'IDLE', stateGlow: 0.15, stateParticles: 0.3,
    transitionPhase: null, transitionProgress: 0,
    hologramOpacity: 0.55, particleIntensity: 0.3,
    eyeGlow: 0.9, scanLine: -2.0, lod: 'full',
    // ── Inspection ──────────────────────────────
    inspectionMode: 'normal', isolateList: [],
    inspectionTransparency: 0.0, exploded: false,
    // ── Causal chain ────────────────────────────
    causalChain: '', causalStep: 0,
    // ── Temporal ────────────────────────────────
    temporalState: 'paused', temporalSpeed: 1.0,
    temporalStep: 0,
    // ── Camera ──────────────────────────────────
    cameraDirective: '', cameraTarget: '',
    // ── Story ───────────────────────────────────
    storyEnvironment: 'minimal', storyScenes: [],
    storyCharacter: '', storySceneIdx: 0,
    // ── Entity tracking ─────────────────────────
    entityId: '', entityIds: {},
  };
  var HS = 2.6;
  var TMPV = new THREE.Vector3();

  function v3(x, y, z) { return new THREE.Vector3(x || 0, y || 0, z || 0); }

  function P(i, payload) {
    return v3(payload.verts[i * 3] * HS, payload.verts[i * 3 + 1] * HS,
              payload.verts[i * 3 + 2] * HS);
  }

  function sceneAdd(node) { if (world.scene) world.scene.add(node); }

  function buildAvatar(payload) {
    MESH = payload;
    if (avatar.root) { disposeNode(avatar.root); avatar.root = null; }

    var n = payload.verts.length / 3;
    var root = new THREE.Group();
    root.position.set(HOME.x, HOME.y, HOME.z);
    sceneAdd(root);
    avatar.root = root;

    // Particle cloud: every vertex plus densified landmark rings (eyes, brows,
    // lips read denser than cheeks — the same trick the 2D renderer uses).
    var cloudPts = [];
    for (var i = 0; i < n; i++) cloudPts.push(P(i, payload));
    var lm = payload.anchors || {};
    if (lm.left_eye) for (var k = 0; k < 12; k++)
      cloudPts.push(v3(lm.left_eye[0] * HS + rnd() * 0.16, lm.left_eye[1] * HS + rnd() * 0.12, lm.left_eye[2] * HS + rnd() * 0.10));
    if (lm.right_eye) for (var k2 = 0; k2 < 12; k2++)
      cloudPts.push(v3(lm.right_eye[0] * HS + rnd() * 0.16, lm.right_eye[1] * HS + rnd() * 0.12, lm.right_eye[2] * HS + rnd() * 0.10));
    if (lm.face) for (var lk = 0; lk < 14; lk++)
      cloudPts.push(v3(lm.face[0] * HS + rnd() * 0.26, (lm.face[1] - 0.16) * HS + rnd() * 0.12, lm.face[2] * HS + rnd() * 0.06));
    avatar.cloud = makePointsAt(cloudPts, 0.085, 0.95);
    avatar.cloud.renderOrder = 3;
    root.add(avatar.cloud);

    // Wireframe: the thinned edge set the 2D avatar already computes.
    var edges = payload.edges, epairs = [];
    for (var ei = 0; ei < edges.length; ei += 2)
      epairs.push({ a: P(edges[ei], payload), b: P(edges[ei + 1], payload) });
    avatar.wire = makeLines(epairs, new THREE.Color(OPERO).mix(new THREE.Color(WHITE), 0.25), 0.30);
    avatar.wire.renderOrder = 1;
    root.add(avatar.wire);

    // Solid holographic face (facetted, additive, plus a fresnel rim shell).
    var faces = payload.faces;
    var fpos = new Float32Array(n * 3);
    for (var fi = 0; fi < n; fi++) {
      fpos[fi * 3] = payload.verts[fi * 3] * HS;
      fpos[fi * 3 + 1] = payload.verts[fi * 3 + 1] * HS;
      fpos[fi * 3 + 2] = payload.verts[fi * 3 + 2] * HS;
    }
    var fgeo = new THREE.BufferGeometry();
    fgeo.setAttribute("position", new THREE.Float32BufferAttribute(fpos, 3));
    fgeo.setAttribute("aVertexIndex", new THREE.Uint32BufferAttribute(new Uint32Array(faces), 1));
    var solidMat = makeMeshMaterial("holographic", OPERO);
    avatar.solid = new THREE.Mesh(fgeo, solidMat);
    avatar.solid.renderOrder = 2;
    root.add(avatar.solid);

    // Fresnel rim — a slightly larger back-only shell gives the hologram its
    // "lit edge" without bloom abuse.
    var rimMat = new THREE.MeshBasicMaterial({ color: OPERO, transparent: true, opacity: 0.10, blending: THREE.AdditiveBlending, side: THREE.BackSide, depthWrite: false });
    avatar.rim = new THREE.Mesh(fgeo, rimMat);
    avatar.rim.scale.setScalar(1.03);
    avatar.rim.renderOrder = 0;
    root.add(avatar.rim);

    // Sub-rigs: jaw + brows (weights come from the same mesh as the 2D avatar).
    var jawIdx = [], browIdx = [];
    var jawW = payload.jaw || [], browW = payload.brow || [];
    for (var vi = 0; vi < n; vi++) {
      if (jawW.length && jawW[vi] > 0.35) jawIdx.push(vi);
      if (browW.length && browW[vi] > 0.30) browIdx.push(vi);
    }
    if (jawIdx.length) {
      avatar.jaw = new THREE.Group();
      var jawPts = jawIdx.map(function (ix) { return P(ix, payload); });
      avatar.jaw.add(makePointsAt(jawPts, 0.10, 0.95));
      root.add(avatar.jaw);
    }
    if (browIdx.length) {
      avatar.brow = new THREE.Group();
      var browPts = browIdx.map(function (ix) { return P(ix, payload); });
      avatar.brow.add(makePointsAt(browPts, 0.075, 0.85));
      root.add(avatar.brow);
    }

    // Eyes: two small emissive orbs at the measured eye centres.
    if (lm.left_eye && lm.right_eye) {
      var eyeMatA = new THREE.MeshBasicMaterial({ color: 0xd8f8ff, transparent: true, opacity: 0.90, blending: THREE.AdditiveBlending, depthWrite: false });
      var eyeMatB = new THREE.MeshBasicMaterial({ color: 0xd8f8ff, transparent: true, opacity: 0.75, blending: THREE.AdditiveBlending, depthWrite: false });
      avatar.eyeL = new THREE.Mesh(new THREE.SphereGeometry(0.075, 14, 10), eyeMatB);
      avatar.eyeL.position.set(lm.left_eye[0] * HS, lm.left_eye[1] * HS, lm.left_eye[2] * HS);
      avatar.eyeR = new THREE.Mesh(new THREE.SphereGeometry(0.075, 14, 10), eyeMatA);
      avatar.eyeR.position.set(lm.right_eye[0] * HS, lm.right_eye[1] * HS, lm.right_eye[2] * HS);
      root.add(avatar.eyeL); root.add(avatar.eyeR);
    }

    // Volumetric aura — a faint additive shell around the head so the presence
    // reads as a volume, not a flat lit face.
    var auraMat = new THREE.MeshBasicMaterial({ color: 0x0a3a66, transparent: true, opacity: 0.12, blending: THREE.AdditiveBlending, side: THREE.BackSide, depthWrite: false });
    var aura = new THREE.Mesh(new THREE.SphereGeometry(2.0, 24, 16), auraMat);
    aura.scale.set(1.25, 1.35, 1.1);
    aura.renderOrder = -1;
    root.add(aura);
    avatar.aura = aura;

    DIAG.face = true;
  }

  function avatarStep(dt, elapsed) {
    if (!avatar.root) return;

    // Audio smoothing for the mouth (attack fast, release natural).
    avatar.audSm += ((world.audioAmp || 0) - avatar.audSm) * 0.25;
    if (avatar.audSm < 0.0004) avatar.audSm *= 0.88;

    // ── State-based parameters ────────────────────────────
    var stateParams = AVATAR_STATES[currentAvatarState] || AVATAR_STATES.IDLE;
    avatar.stateGlow = stateParams.glow;
    avatar.stateParticles = stateParams.particles;

    var speaking = world.stateName === "SPEAKING" || world.stateName === "EXECUTING";
    var target = avatar.audSm * (speaking ? 1.0 : 0.16) + (world.audioAmp || 0) * 0.10;
    avatar.open += (clamp(target, 0, 1) - avatar.open) * (dt / 0.045);
    avatar.browLn += (((world.stateName === "THINKING" || world.stateName === "PROCESSING") ? 1.0 : 0.15) - avatar.browLn) * dt;

    // Blink rate from state
    var blinkRate = stateParams.blinkRate;
    avatar.blinkT -= dt;
    if (avatar.blinkT <= 0) { avatar.blink = 1.0; avatar.blinkT = blinkRate + Math.random() * 2; }
    if (avatar.blink > 0) avatar.blink = Math.max(0, avatar.blink - dt * 9);
    var blinkS = 1 - (avatar.blink > 0 ? avatar.blink * 0.9 : 0);
    if (avatar.eyeL) avatar.eyeL.scale.set(1.15, Math.max(0.05, blinkS), 1.15);
    if (avatar.eyeR) avatar.eyeR.scale.set(1.15, Math.max(0.05, blinkS), 1.15);

    // ── Holographic glow ──────────────────────────────────
    avatar.hologramOpacity = lerp(avatar.hologramOpacity, avatar.stateGlow, dt * 3);
    if (aura) aura.material.opacity = 0.05 + avatar.stateGlow * 0.3;
    if (rim) rim.material.opacity = 0.04 + avatar.stateGlow * 0.15;

    // ── Eye glow ──────────────────────────────────────────
    avatar.eyeGlow = lerp(avatar.eyeGlow, speaking ? 1.0 : stateParams.glow, dt * 2);
    if (eyeL) eyeL.material.emissiveIntensity = avatar.eyeGlow;
    if (eyeR) eyeR.material.emissiveIntensity = avatar.eyeGlow;

    // ── Particle intensity ────────────────────────────────
    avatar.particleIntensity = lerp(avatar.particleIntensity, stateParams.particles, dt * 2);

    // ── Scan line animation ───────────────────────────────
    avatar.scanLine += dt * 0.8;
    if (avatar.scanLine > 2.0) avatar.scanLine = -2.0;

    // ── Transition handling ───────────────────────────────
    if (avatar.transitionPhase) {
      avatar.transitionProgress += dt / avatar.transitionDuration;
      if (avatar.transitionProgress >= 1.0) {
        avatar.transitionProgress = 1.0;
        avatar.transitionPhase = null;
        visualState = 'VISUALIZING';
      }
    }

    // ── LOD management ────────────────────────────────────
    avatar.lodFrame += dt;
    if (avatar.lodFrame > 0.5) {
      avatar.lodFrame = 0;
      var dist = camera ? camera.position.distanceTo(avatar.root.position) : 10;
      avatar.lod = dist > 15 ? "low" : dist > 8 ? "medium" : "full";
    }

    // Look-at: a slow wander toward the camera with a subtle idle sway.
    var wanderYaw = Math.sin(elapsed * 0.31) * 0.05 + Math.sin(elapsed * 0.23 + 1.7) * 0.03;
    skull(avatar.root).rotation.y = wanderYaw;
    skull(avatar.root).rotation.x = Math.sin(elapsed * 0.17) * 0.03 - avatar.open * 0.045;

    // Breathing + audio surge.
    var breath = Math.sin(elapsed * 0.9) * 0.012 + avatar.audSm * 0.045 + avatar.presence * 0.0;
    skull(avatar.root).scale.setScalar(1 + breath);

    // Jaw opening (rotations are euler in this fork).
    if (avatar.jaw) {
      avatar.jaw.rotation.x = -avatar.open * 0.10 + Math.sin(elapsed * 0.6) * 0.004;
    }
    if (avatar.brow) {
      avatar.brow.rotation.x = avatar.browLn * 0.06;
      avatar.brow.position.y = avatar.browLn * 0.10;
      avatar.brow.position.z = -avatar.browLn * 0.05;
    }

    // Presence (dim while a scene object owns the stage).
    var presence = visualState === 'FACE_ONLY' ? 1.0 : 0.4;
    if (avatar.cloud) avatar.cloud.material.opacity = 0.35 + 0.6 * presence;
    if (avatar.solid) avatar.solid.material.opacity = 0.16 + 0.42 * presence;
    if (avatar.rim) avatar.rim.material.opacity = 0.04 + 0.09 * presence;
    if (avatar.aura) avatar.aura.material.opacity = 0.05 + avatar.stateGlow * 0.09 * presence;

  function skull(g) { return g; }   // transform holder — keeps reads explicit

  /* ── object factory (procedural, offline, bounded) ─────────────────────── */
  // Every builder returns { group, interior:{group,at}|null }.  `dir` carries
  // the already-validated material + colour from the intent.
  function hexColor(h) { return parseInt(String(h).replace("#", ""), 16) || OPERO; }
  function colorInt(dir) { return hexColor(dir.color || OPERO); }

  function buildObject(kind, dir) {
    var g = new THREE.Group();
    var mat = makeMeshMaterial(dir.material, colorInt(dir));
    var interior = null;

    switch (kind) {
      case "apple": {
        // Squashed sphere + stem + leaf — stylised but unmistakably an apple.
        var body = new THREE.Mesh(new THREE.SphereGeometry(0.85, 28, 20), mat);
        body.scale.set(1.0, 0.84, 1.0);
        body.position.y = -0.05;
        g.add(body);
        var stem = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.14, 8),
                                  makeMeshMaterial("matte", 0x6b4a2a));
        stem.position.y = 0.72;
        g.add(stem);
        var leaf = new THREE.Mesh(new THREE.PlaneGeometry(0.3, 0.16, 1, 1),
                                  makeMeshMaterial("emissive", 0x2ec46a));
        leaf.position.set(0.3, 0.78, 0);
        leaf.rotation.set(0.4, 0, 0.9);
        g.add(leaf);
        // Interior: flesh-core + two seeds, shown for "show the inside".
        var coreG = new THREE.Group();
        coreG.add(new THREE.Mesh(new THREE.SphereGeometry(0.34, 16, 12),
                                 makeMeshMaterial("emissive", 0xffd9a0)));
        for (var si = -1; si <= 1; si += 2) {
          var seed = new THREE.Mesh(new THREE.SphereGeometry(0.09, 10, 8),
                                    makeMeshMaterial("matte", 0x5a3418));
          seed.position.set(si * 0.16, 0.12, 0.05);
          coreG.add(seed);
        }
        g.add(coreG);
        interior = { group: coreG, at: 0.32 };
        break;
      }
      case "sphere":
        g.add(new THREE.Mesh(new THREE.SphereGeometry(0.8, 28, 20), mat)); break;
      case "cube":
        g.add(new THREE.Mesh(new THREE.BoxGeometry(1.4, 1.4, 1.4), mat)); break;
      case "torus":
        g.add(new THREE.Mesh(new THREE.TorusGeometry(0.62, 0.24, 10, 26), mat)); break;
      case "cone":
        g.add(new THREE.Mesh(new THREE.ConeGeometry(0.7, 1.3, 22), mat)); break;
      case "cylinder":
        g.add(new THREE.Mesh(new THREE.CylinderGeometry(0.55, 1.2, 22), mat)); break;
      case "capsule": {
        // Cylinder body + two hemisphere caps — built from primitives so it
        // works on any bundled THREE (no CapsuleGeometry dependency).
        var capG = new THREE.Group();
        capG.add(new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.45, 0.9, 20), mat));
        var capTop = new THREE.Mesh(new THREE.SphereGeometry(0.45, 20, 12, 0, TAU, 0, Math.PI / 2), mat);
        capTop.position.y = 0.45;
        var capBot = new THREE.Mesh(new THREE.SphereGeometry(0.45, 20, 12, 0, TAU, Math.PI / 2, Math.PI / 2), mat);
        capBot.position.y = -0.45;
        capG.add(capTop); capG.add(capBot);
        g.add(capG); break;
      }
      case "icosa":
        g.add(new THREE.Mesh(new THREE.IcosahedronGeometry(0.9, 1), mat)); break;
      case "planet": {
        var pl = new THREE.Mesh(new THREE.SphereGeometry(0.85, 30, 22), mat);
        g.add(pl);
        var ring = new THREE.Mesh(new THREE.TorusGeometry(1.5, 0.09, 6, 40),
                                  makeMeshMaterial("holographic", 0x9eb2c8));
        ring.rotation.x = Math.PI / 2.6;
        g.add(ring);
        var coreG2 = new THREE.Group();
        coreG2.add(new THREE.Mesh(new THREE.SphereGeometry(0.4, 14, 10),
                                  makeMeshMaterial("emissive", 0xff8a2a)));
        g.add(coreG2);
        interior = { group: coreG2, at: 0.3 };
        break;
      }
      case "sun":
        g.add(new THREE.Mesh(new THREE.SphereGeometry(1.0, 30, 22),
                             makeMeshMaterial("emissive", 0xffb84d))); break;
      case "moon":
        g.add(new THREE.Mesh(new THREE.SphereGeometry(0.55, 20, 16), mat)); break;
      case "sunglasses": {
        var fmat = makeMeshMaterial(dir.material, colorInt(dir));
        for (var lx = -1; lx <= 1; lx += 2) {
          var lens = new THREE.Mesh(new THREE.TorusGeometry(0.17, 0.028, 10, 22), fmat);
          lens.position.x = lx * 0.185; lens.position.z = -0.02;
          g.add(lens);
        }
        var bridge = new THREE.Mesh(new THREE.TorusGeometry(0.06, 0.02, 8, 14), fmat);
        bridge.position.set(0, 0.01, -0.03);
        g.add(bridge);
        for (var ax = -1; ax <= 1; ax += 2) {
          var arm = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.16, 6), fmat);
          arm.position.set(ax * 0.3, 0.05, -0.2); arm.rotation.z = ax * 0.6;
          g.add(arm);
        }
        g.scale.setScalar(0.52);
        break;
      }
      case "watch": {
        var band = new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.1, 10, 26), mat);
        band.rotation.x = Math.PI / 2;
        g.add(band);
        var face = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.07, 20),
                                  makeMeshMaterial("glass", 0xbfe9ff));
        face.rotation.x = Math.PI / 2; face.position.z = 0.02;
        g.add(face);
        var hand = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.26),
                                  makeMeshMaterial("emissive", 0xffc94d));
        hand.position.z = 0.2;
        g.add(hand);
        break;
      }
      case "ring":
        g.add(new THREE.Mesh(new THREE.TorusGeometry(0.22, 0.045, 10, 22), mat)); break;
      case "necklace": {
        var ngroup = new THREE.Group();
        for (var bi = 0; bi < 16; bi++) {
          var bead = new THREE.Mesh(new THREE.SphereGeometry(0.035, 8, 6), mat);
          var ba = (bi / 16) * Math.PI;
          bead.position.set(Math.sin(ba) * 0.62, -Math.cos(ba) * 0.62, 0);
          ngroup.add(bead);
        }
        ngroup.position.set(0, -0.1, 0.25);
        g.add(ngroup);
        break;
      }
      case "hat": {
        var brim = new THREE.Mesh(new THREE.CircleGeometry(0.62, 24), mat);
        brim.rotation.x = -Math.PI / 2;
        g.add(brim);
        var dome = new THREE.Mesh(new THREE.SphereGeometry(0.45, 20, 14), mat);
        dome.scale.set(1, 0.8, 1); dome.position.y = 0.35;
        g.add(dome);
        break;
      }
      case "tree": {
        var trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.9, 8),
                                   makeMeshMaterial("matte", 0x6b4a2a));
        trunk.position.y = 0.45;
        g.add(trunk);
        var fol = new THREE.Mesh(new THREE.IcosahedronGeometry(0.85, 1),
                                 makeMeshMaterial(dir.material, 0x2ec46a));
        fol.position.y = 2.0; fol.scale.set(1.0, 0.9, 1.0);
        g.add(fol);
        break;
      }
      case "ground": {
        var ground = new THREE.Mesh(new THREE.PlaneGeometry(26, 26, 4, 4), mat);
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = -1.6;
        g.add(ground);
        break;
      }
      default:
        return null;
    }
    return { group: g, interior: interior, anchors: {} };
  }

  // ── camera rig ──────────────────────────────────────────────────────────
  // Smooth, mode-driven camera.  The index.html loop calls rig.step(dt) while
  // it is active; rig writes position + lookAt and moves controls.target so
  // OrbitControls never fights us.
  var CAMERA_POSES = {
    default:   { p: [0, 4.2, 10.5], l: [0, 1.0, 0] },
    portrait:  { p: [0, 2.3, 5.8],  l: [0, 1.0, 0] },
    focus:     { p: [0, 2.0, 5.0],  l: [0, 0.9, 0] },
    orbit:     { p: [0, 2.2, 6.5],  l: [0, 0.9, 0] },
    zoom:      { p: [0, 1.7, 3.6],  l: [0, 0.9, 0] },
    closeup:   { p: [0, 1.6, 3.1],  l: [0, 0.9, 0] },
    wide:      { p: [0, 6.0, 13.0], l: [0, 0.7, 0] },
    top_down:  { p: [0, 13.0, 0.1], l: [0, 0.0, 0] },
    side:      { p: [8.2, 2.2, 0],  l: [0, 1.0, 0] },
    inspection:{ p: [2.7, 1.9, 4.6],l: [0, 1.0, 0] },
    cinematic: { p: [3.6, 2.8, 9.4],l: [0, 1.0, 0] },
    follow:    { p: [0, 2.2, 5.2],  l: [0, 1.0, 0] },
  };

  var rig = {
    active: false, mode: "default", orbitA: 0, orbitSpeed: 0.30,
    orbitR: 6.5, look: v3(0, 1, 0),
    setMode: function (mode, opts) {
      var pose = CAMERA_POSES[mode] || CAMERA_POSES.default;
      this.mode = mode;
      this.orbitA = Math.random() * TAU;
      this.look.set(pose.l[0], pose.l[1], pose.l[2]);
      this.active = true;
    },
    step: function (dt) {
      if (!this.active) return;
      var cam = world.camera, ctl = world.controls;
      if (!cam || !ctl) return;
      var pose = CAMERA_POSES[this.mode] || CAMERA_POSES.default;
      var px = pose.p[0], py = pose.p[1], pz = pose.p[2];
      if (this.mode === "orbit") {
        this.orbitA += dt * this.orbitSpeed;
        px = Math.cos(this.orbitA) * this.orbitR;
        pz = Math.sin(this.orbitA) * this.orbitR;
        py = 1.9 + Math.sin(this.orbitA * 0.7) * 0.5;
      }
      if (this.mode === "cinematic") {
        this.orbitA += dt * 0.10;
        px += Math.sin(this.orbitA) * 0.6;
        py = 2.6 + Math.sin(this.orbitA * 0.5) * 0.3;
      }
      var k = 1 - Math.exp(-dt / 0.85);            // smooth approach
      cam.position.x += (px - cam.position.x) * k;
      cam.position.y += (py - cam.position.y) * k;
      cam.position.z += (pz - cam.position.z) * k;
      cam.lookAt(this.look.x, this.look.y, this.look.z);
      ctl.target.set(this.look.x, this.look.y, this.look.z);
    },
    release: function () {
      this.active = false;
      try { if (world.controls) world.controls.target.set(0, 0, 0); } catch (e) { /* fine */ }
    },
  };

  // ── environments (story scenes) ──────────────────────────────────────────
  var envGroup = null;
  function buildEnv(name, dir) {
    if (envGroup) { disposeNode(envGroup); envGroup = null; }
    var g = new THREE.Group();
    envGroup = g;
    sceneAdd(g);
    var m = makeMeshMaterial;
    if (name === "minimal" || !name) return;

    var gcolor = name === "ocean" ? 0x0a3a66 : (name === "desert" ? 0xc2a06a : 0x16283a);
    var ground = new THREE.Mesh(new THREE.PlaneGeometry(30, 30, 4, 4),
                                m(name === "ocean" ? "glass" : "matte", gcolor));
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -1.7;
    g.add(ground);

    function place(kind, x, z, s) {
      var o = buildObject(kind, dir);
      if (!o) return;
      o.group.position.set(x, 0, z);
      o.group.scale.setScalar(s || 1);
      g.add(o.group);
    }

    if (name === "space") {
      place("sun", 0, 3, 1.6);
      place("planet", 4, -3, 0.9);
      place("moon", -5, 1.5, 0.7);
      place("planet", -3, 4, 0.6);
    } else if (name === "forest") {
      for (var ti = 0; ti < 6; ti++) {
        var ta = (ti / 6) * TAU;
        place("tree", Math.cos(ta) * (5.5 + rnd() * 1.4), Math.sin(ta) * (5.5 + rnd() * 1.4), 1.5 + rnd() * 0.7);
      }
    } else if (name === "desert") {
      for (var ci = 0; ci < 4; ci++) {
        var ca = (ci / 4) * TAU + 0.5;
        place("tree", Math.cos(ca) * (5 + rnd() * 2), Math.sin(ca) * (5 + rnd() * 2), 1.2);
      }
    } else if (name === "city") {
      for (var bi2 = 0; bi2 < 7; bi2++) {
        var ba = (bi2 / 7) * TAU;
        var bx = Math.cos(ba) * (5.5 + rnd() * 1.5), bz = Math.sin(ba) * (5.5 + rnd() * 1.5);
        var bld = new THREE.Mesh(new THREE.BoxGeometry(0.9 + rnd() * 0.6, 1.6 + rnd() * 2.6, 0.9 + rnd() * 0.6),
                                 m("matte", 0x1a2c44));
        bld.position.set(bx, 0, bz);
        g.add(bld);
      }
    } else if (name === "ocean") {
      for (var wi = 0; wi < 5; wi++) {
        var wave = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 0.5, 8, 1), m("glass", 0x1e90ff));
        wave.rotation.x = -Math.PI / 2;
        wave.position.set(rnd() * 10, 0.1 + rnd() * 0.4, rnd() * 10);
        g.add(wave);
      }
    }
  }

  // A lightweight figure for story scenes ("a boy walks through a forest").
  var figure = null;
  function buildFigure() {
    var g = new THREE.Group();
    var skin = makeMeshMaterial("holographic", 0x9fd9e8);
    var torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.28, 0.8, 8, 10), skin);
    torso.position.y = 1.35;
    g.add(torso);
    var head = new THREE.Mesh(new THREE.SphereGeometry(0.34, 18, 14), skin);
    head.position.y = 2.35;
    g.add(head);
    var limbMat = makeMeshMaterial("holographic", 0x8fc0e8);
    for (var side = -1; side <= 1; side += 2) {
      var leg = new THREE.Mesh(new THREE.CapsuleGeometry(0.09, 0.75, 6, 8), limbMat);
      leg.position.set(side * 0.16, 0.38, 0);
      var arm = new THREE.Mesh(new THREE.CapsuleGeometry(0.07, 0.6, 6, 8), limbMat);
      arm.position.set(side * 0.33, 1.72, 0);
      leg.userData = { swing: side };
      arm.userData = { swing: side };
      g.add(leg); g.add(arm);
    }
    figure = { group: g, t: 0, walk: 0 };
    sceneAdd(g);
  }
  function stepFigure(dt) {
    if (!figure) return;
    figure.t += dt;
    figure.walk = Math.max(0, figure.walk - dt * 0.4);
    var sw = Math.sin(figure.t * 3.9) * (0.25 + figure.walk);
    figure.group.children.forEach(function (c) {
      if (c.userData && c.userData.swing) c.rotation.z = c.userData.swing * sw;
    });
    figure.group.position.y = Math.abs(Math.sin(figure.t * 5.4)) * 0.05 * figure.walk;
  }
  function setFigureWalk(v) { if (figure) figure.walk = clamp(v, 0, 1); }

  // ── stage: one scene at a time (morph -> hold -> return) ─────────────────
  var stage = {
    phase: "idle", dir: null,
    obj: null, objG: null, cloudIn: null, cloudInG: null, cloudOut: null, cloudOutG: null,
    t: 0, morphT: 2.2, tailT: 1.8, hold: 0, dur: 8, autoReturn: true,
    rotY: 0, pulse: 0, scanY: -2.2, scanning: false, interiorShown: false,
    story: null, sIdx: 0, sT: 0, storyOver: false,
    placed: [], figureUsed: false,
  };

  function sampleHead(count) {
    if (!MESH) return [];
    var n = MESH.verts.length / 3;
    var pts = [];
    for (var i = 0; i < count; i++) {
      var idx = Math.floor(Math.random() * n);
      pts.push(v3(MESH.verts[idx * 3] * HS + rnd() * 0.12,
                  MESH.verts[idx * 3 + 1] * HS + rnd() * 0.12,
                  MESH.verts[idx * 3 + 2] * HS + rnd() * 0.08));
    }
    return pts;
  }

  function clearScene() {
    if (stage.objG) { disposeNode(stage.objG); stage.objG = null; stage.obj = null; }
    if (stage.cloudInG) { disposeNode(stage.cloudInG); stage.cloudInG = null; stage.cloudIn = null; }
    if (stage.cloudOutG) { disposeNode(stage.cloudOutG); stage.cloudOutG = null; stage.cloudOut = null; }
    if (stage.placed.length) {
      stage.placed.forEach(function (p) { try { if (envGroup && p.parent === envGroup) envGroup.remove(p); } catch (e) {} });
      stage.placed = [];
    }
    if (figure) { try { world.scene.remove(figure.group); } catch (e) {} figure = null; }
    stage.scanning = false; stage.interiorShown = false; stage.story = null;
  }

  function showObject(dir) {
    clearScene();
    stage.dir = dir; stage.phase = "morph_in"; stage.t = 0; stage.hold = 0;
    stage.rotY = 0; stage.pulse = 0; stage.scanY = -2.2;
    if (dir.transition_duration) avatar.transitionDuration = dir.transition_duration;
    if (dir.lod) avatar.lod = dir.lod;
    if (dir.max_particles) avatar.maxParticles = dir.max_particles;
    // ── Apply inspection mode ──────────────────
    if (dir.inspection_mode && dir.inspection_mode !== 'normal') {
      applyInspectionMode(dir.inspection_mode, dir.isolate,
                            dir.transparency || 0.0, dir.exploded);
    }
    // ── Apply camera directive ─────────────────
    if (dir.camera_directive) {
      applyCameraMode(dir.camera_directive, dir.camera_target);
    } else if (dir.camera) {
      applyCameraMode(dir.camera, dir.subject);
    }
    // ── Apply temporal state ───────────────────
    if (dir.temporal_state) {
      applyTemporalState(dir.temporal_state, dir.temporal_speed, dir.temporal_step);
    }
    // ── Apply causal chain ─────────────────────
    if (dir.causal_chain) {
      renderCausalChain(CAUSAL_CHAINS[dir.causal_chain] || [], dir.chain_step || 0);
    }
    stage.scanning = dir.animation === "scan" || dir.animation === "process";
    stage.interiorShown = !!dir.interior;
    stage.dur = clamp(dir.duration || 8, 1, 120);
    stage.autoReturn = dir.autoReturn !== false;

    var built = buildObject(dir.subject || "sphere", dir);
    if (!built) { stage.phase = "idle"; return; }
    stage.obj = built;
    stage.objG = built.group;
    stage.objG.position.set(0, 1.02, 0);
    stage.objG.scale.setScalar(1.15 * (dir.particle_scale || 1));
    stage.objG.visible = false;
    sceneAdd(stage.objG);
    if (built.interior) built.interior.group.visible = false;

    var facePts = sampleHead(300);
    var objPts = sampleObject(dir.subject || "sphere", 300);
    stage.cloudOutG = new THREE.Group(); stage.cloudOutG.position.set(HOME.x, HOME.y, HOME.z);
    stage.cloudOut = makePointsAt(facePts, 0.09, 0.9);
    stage.cloudOutG.add(stage.cloudOut); sceneAdd(stage.cloudOutG);
    stage.cloudInG = new THREE.Group(); stage.cloudInG.position.set(0, 1.02, 0);
    stage.cloudIn = makePointsAt(objPts, 0.085, 0.85);
    stage.cloudInG.add(stage.cloudIn); sceneAdd(stage.cloudInG);
    stage.cloudInG.scale.setScalar(0.1);
    stage.cloudIn.material.opacity = 0;

    avatar.presence = 0.5;
    rig.setMode(dir.camera || "focus");
    world.fireState("VISUALIZING");
  }

  function showAccessory(dir) {
    clearScene();
    stage.dir = dir; stage.phase = "hold"; stage.t = 0; stage.hold = 0;
    stage.dur = clamp(dir.duration || 10, 1, 120); stage.autoReturn = true;
    var built = buildObject(dir.subject, dir);
    if (!built) { stage.phase = "idle"; return; }
    stage.obj = built; stage.objG = built.group;
    // Anchor: the validated anchor maps to measured head coordinates.
    var a = (MESH && MESH.anchors) || {};
    var an = (dir.attach || "face").replace("left_", "").replace("right_", "").replace("_wrist", "").replace("_index", "").replace("_ear", "");
    var ac = a[dir.attach] || a.face || [0, 0.05, 0.45];
    var off = dir.subject === "watch" ? [0.55, -0.35, 0.25]
            : dir.subject === "ring" ? [0.6, -0.55, 0.12]
            : dir.subject === "hat" ? [0, 1.0, 0]
            : dir.subject === "necklace" ? [0, -0.28, 0.2]
            : [0, 0.0, 0.1];
    stage.objG.position.set(ac[0] * HS + off[0], ac[1] * HS + off[1], ac[2] * HS + off[2]);
    stage.objG.scale.setScalar(0.001);
    sceneAdd(stage.objG);
    avatar.presence = 1.0;                 // the avatar stays: it "wears" it
    rig.setMode("focus");
    world.fireState("VISUALIZING");
  }

  function startStory(dir) {
    clearScene();
    stage.dir = dir; stage.phase = "story"; stage.t = 0;
    stage.story = dir.story || []; stage.sIdx = 0; stage.storyOver = false;
    stage.dur = Math.max(4, stage.story.length * 4);
    avatar.presence = 0.35;
    rig.setMode("cinematic");
    world.fireState("STORY");
    if (stage.story.length) enterStoryScene(dir, stage.story[0]);
  }

  function enterStoryScene(dir, scene) {
    var env = (scene && scene.scene) || "minimal";
    buildEnv(env, dir);
    if (!figure) buildFigure();
    stage.figureUsed = true;
    setFigureWalk(0.6);
    (scene.appear || []).forEach(function (kind) {
      var o = buildObject(kind, dir);
      if (!o) return;
      var ang = (stage.placed.length * 1.7) % TAU;
      o.group.position.set(Math.cos(ang) * 4.2, 0, Math.sin(ang) * 4.2);
      o.group.rotation.y = ang;
      envGroup.add(o.group);
      stage.placed.push(o.group);
    });
    (scene.remove || []).forEach(function (kind) { /* placeholders to keep schema honest */ });
    stage.sT = 0;
  }

  function stageStep(dt) {
    stepFigure(dt);

    if (stage.phase === "morph_in") {
      stage.t += dt;
      var p = ease(stage.t / stage.morphT);
      if (stage.cloudOut) stage.cloudOut.material.opacity = 0.9 * (1 - p);
      if (stage.cloudIn) {
        var grow = ease(Math.max(0, p * 1.35 - 0.35));
        stage.cloudInG.scale.setScalar(0.08 + 0.92 * grow);
        stage.cloudIn.material.opacity = 0.82 * grow;
        try { stage.cloudIn.geometry.setDrawRange(0, Math.floor(stage.cloudIn.geometry.getAttributeCount() * p)); } catch (e) { /* optional */ }
      }
      if (stage.objG && p > 0.45) {
        stage.objG.visible = true;
        stage.objG.children.forEach(function (c) { try { c.visible = true; } catch (e) {} });
        setObjectOpacity(stage.objG, clamp((p - 0.45) / 0.55, 0, 1) * 0.9);
      }
      if (stage.t >= stage.morphT) { stage.phase = "hold"; stage.t = 0; }
    } else if (stage.phase === "hold") {
      stage.t += dt; stage.hold = stage.t;
      animateObject(dt);
      if (stage.hold >= stage.dur) doReturnLocal();
    } else if (stage.phase === "morph_out") {
      stage.t += dt;
      var q = ease(clamp(stage.t / stage.tailT, 0, 1));
      if (stage.objG) {
        stage.objG.visible = (1 - q) > 0.02;
        setObjectOpacity(stage.objG, 0.9 * (1 - q));
        stage.objG.scale.setScalar((1.15 - 0.4 * q) * (stage.dir && stage.dir.particle_scale ? stage.dir.particle_scale : 1));
      }
      if (stage.cloudOutG) { stage.cloudOut.material.opacity = 0.3 + 0.66 * q; stage.cloudOutG.scale.setScalar(0.7 + 0.3 * q); }
      if (stage.cloudInG) { stage.cloudIn.material.opacity = 0.85 * (1 - q); stage.cloudInG.scale.setScalar((1 - 0.5 * q) ); }
      avatar.presence = 0.5 + 0.5 * q;
      if (stage.t >= stage.tailT) sendIdle();
    } else if (stage.phase === "story") {
      stage.t += dt; stage.sT += dt;
      if (stage.story && stage.sT >= (stage.story[stage.sIdx].duration || 4)) {
        stage.sIdx++;
        if (stage.sIdx < stage.story.length) {
          stage.sT = 0;
          enterStoryScene(stage.dir, stage.story[stage.sIdx]);
        } else {
          stage.storyOver = true;
          doReturnLocal();
        }
      }
    }
  }

  function setObjectOpacity(group, op) {
    if (!group) return;
    group.children.forEach(function (c) {
      try { if (c.material) c.material.opacity = op; } catch (e) {}
      if (c.children) setObjectOpacity(c, op);
    });
  }

  function animateObject(dt) {
    if (!stage.objG) return;
    var anim = stage.dir ? (stage.dir.animation || "rotate") : "rotate";
    stage.rotY += dt * (anim === "idle" ? 0.08 : 0.5);
    stage.objG.rotation.y = stage.rotY;
    var bob = 0;
    if (anim === "pulse") bob = Math.sin(stage.t * 3.0) * 0.05;
    if (anim === "bounce") bob = Math.abs(Math.sin(stage.t * 3.2)) * 0.22;
    if (anim === "float") bob = Math.sin(stage.t * 1.4) * 0.12;
    stage.objG.position.y = 1.02 - bob + (anim === "idle" ? Math.sin(stage.t * 0.8) * 0.03 : 0);
    stage.pulse = anim === "highlight" ? 0.55 + 0.4 * Math.sin(stage.t * 4.2) : 0;
    if (stage.pulse > 0) setObjectOpacity(stage.objG, 0.45 + 0.5 * stage.pulse);
    if (stage.scanning) {
      stage.scanY = -2.2 + ((stage.t * 30) % 4.4);
      drawScan(stage.scanY);
    }
    // Interior reveal (apple / planet inside).
    if (stage.obj && stage.obj.interior && stage.interiorShown) {
      stage.obj.interior.group.visible = true;
      setObjectOpacity(stage.obj.interior.group, 0.5 + 0.5 * Math.sin(stage.t * 2.2 + 1.0));
    }
  }

  var scanMesh = null;
  function drawScan(y) {
    if (!scanMesh) {
      var sm = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 0.18, 4, 1),
                              makeMeshMaterial("emissive", 0x00e5ff));
      scanMesh = sm; sceneAdd(sm);
    }
    scanMesh.position.set(0, y, 0);
    if (y >= 2.2) { sceneRemoveSafe(scanMesh); scanMesh = null; }
  }
  function sceneRemoveSafe(node) {
    try { if (node && node.parent) node.parent.remove(node); disposeNode(node); } catch (e) {}
  }

  function doReturnLocal() {
    if (stage.phase === "idle" || stage.phase === "morph_out") return;
    stage.phase = "morph_out"; stage.t = 0;
    visualState = 'FACE_ONLY';
    avatar.state = 'LISTENING';
    currentAvatarState = 'LISTENING';
    avatar.transitionPhase = null;
    activeSubject = null;
  }

  function sendIdle() {
    if (stage.objG) { disposeNode(stage.objG); stage.objG = null; stage.obj = null; }
    if (stage.cloudInG) { disposeNode(stage.cloudInG); stage.cloudInG = null; stage.cloudIn = null; }
    if (stage.cloudOutG) { disposeNode(stage.cloudOutG); stage.cloudOutG = null; stage.cloudOut = null; }
    if (envGroup) { disposeNode(envGroup); envGroup = null; }
    if (figure) { try { world.scene.remove(figure.group); } catch (e) {} figure = null; }
    if (scanMesh) { sceneRemoveSafe(scanMesh); scanMesh = null; }
    stage.phase = "idle"; stage.dir = null; stage.story = null;
    avatar.presence = 1.0;
    rig.release();
    world.fireState("RETURN");
  }

  function handleIntent(dir) {
    if (!dir || typeof dir !== "object") return;
    if (dir.op === "return") { doReturnLocal(); return; }
    if (dir.op === "face_only") { doFaceOnly(); return; }
    if (dir.op === "transition_in") { doTransitionIn(dir); return; }
    if (dir.op === "transition_out") { doTransitionOut(); return; }
    if (dir.mode === "story") { startStory(dir); return; }
    if (dir.mode === "accessory") { showAccessory(dir); return; }
    // Apply LOD, max_particles, resolution settings if present
    if (dir.lod) avatar.lod = dir.lod;
    if (dir.transition) { doTransitionIn(dir); return; }
    if (dir.return_to_face) { doFaceOnly(); return; }
    showObject(dir);
  }

  function doFaceOnly() {
    visualState = 'FACE_ONLY';
    avatar.state = 'LISTENING';
    currentAvatarState = 'LISTENING';
    transitionPhase = null;
    if (MESH && MESH.group) {
      // Dissolve object back into face
      if (MESH.group.userData.particles) {
        MESH.group.userData.particles.material.opacity = 0;
      }
      MESH.group.visible = false;
    }
  }

  function doTransitionIn(dir) {
    visualState = 'TRANSITIONING';
    activeSubject = dir.subject;
    avatar.transitionPhase = 'morph_in';
    avatar.transitionProgress = 0;
    if (dir.transition_duration) {
      avatar.transitionDuration = dir.transition_duration;
    } else {
      avatar.transitionDuration = 1.5;
    }
    // Set avatar state to VISUALIZING
    avatar.state = 'VISUALIZING';
    currentAvatarState = 'VISUALIZING';
    // Build and show the object
    showObject(dir);
  }

  function doTransitionOut() {
    avatar.transitionPhase = 'morph_out';
    avatar.transitionProgress = 0;
    // Hide the object and return to face
    if (MESH && MESH.group && MESH.group.userData.particles) {
      MESH.group.userData.particles.material.opacity = 0;
    }
    setTimeout(function() {
      if (MESH && MESH.group) MESH.group.visible = false;
      visualState = 'FACE_ONLY';
      avatar.state = 'LISTENING';
      currentAvatarState = 'LISTENING';
      avatar.transitionPhase = null;
    }, 1000);
  }

  // ── public API + boot ─────────────────────────────────────────────────────
  window.setFaceMesh = function (payload) {
    try { DIAG.ready = true; buildAvatar(payload); }
    catch (e) { ERRORS.push("setFaceMesh: " + e.message); }
  };
  window.applyIntent = function (dir) {
    try { DIAG.last = dir; handleIntent(dir); }
    catch (e) { ERRORS.push("applyIntent: " + e.message); }
  };
  window.getVisualDiagnostics = function () {
    return { ready: DIAG.ready, face: DIAG.face, last: DIAG.last,
             stage: stage.phase, camera: rig.mode, errors: ERRORS.slice(-20),
             avatarState: currentAvatarState, visualState: visualState,
             activeSubject: activeSubject };
  };

  window.setAvatarState = function (state) {
    if (AVATAR_STATES[state]) {
      currentAvatarState = state;
    }
  };

  window.setVisualState = function (state) {
    visualState = state;
  };

  window.triggerTransitionIn = function (dir) {
    try { handleIntent(dir); } catch (e) { ERRORS.push('transition_in: ' + e.message); }
  };

  window.triggerTransitionOut = function () {
    doReturnLocal();
  };

  window.applyInspection = function (mode, isolate, transparency, exploded) {
    applyInspectionMode(mode || 'normal', isolate || [], transparency || 0.0, exploded || false);
  };

  window.applyCameraDirective = function (mode, target) {
    applyCameraMode(mode, target);
  };

  window.applyTemporal = function (state, speed, step) {
    applyTemporalState(state, speed, step);
  };

  window.showCausalChain = function (chainId, step) {
    renderCausalChain(CAUSAL_CHAINS[chainId] || [], step || 0);
  };

  window.setEntityId = function (id, type, data) {
    avatar.entityId = id;
    avatar.entityIds[id] = { type: type, data: data || {} };
  };

  window.getEntityId = function (id) {
    return avatar.entityIds[id] || null;
  };

  window.setStoryScene = function (env, scenes, character) {
    avatar.storyEnvironment = env;
    avatar.storyScenes = scenes;
    avatar.storyCharacter = character;
    avatar.storySceneIdx = 0;
  };

  function mainStep(dt, elapsed) {
    avatarStep(dt, elapsed);
    stageStep(dt);
    if (!DIAG.ready && avatar.root) DIAG.ready = true;
  }

  // Register avatar API on __operoWorld so Python can call avatar state methods
  if (window.__operoWorld) {
    window.__operoWorld.setAvatarState = function (state) {
      window.setAvatarState(state);
    };
    window.__operoWorld.setVisualState = function (state) {
      window.setVisualState(state);
    };
    window.__operoWorld.triggerTransitionIn = function (dir) {
      window.triggerTransitionIn(dir);
    };
    window.__operoWorld.triggerTransitionOut = function () {
      window.triggerTransitionOut();
    };
    window.__operoWorld.getAvatarDiagnostics = function () {
      return window.getVisualDiagnostics();
    };
  }

  world.onFrame(mainStep);
  world.setCameraHost(rig);

  // Sample the OUTER SURFACE of an object kind -> array of Vector3 (world-ish
  // units).  Used by the particle morph so particles converge onto the object.
  function sampleObject(kind, count) {
    var pts = [];
    for (var i = 0; i < count; i++) {
      var theta = Math.random() * TAU, phi = Math.acos(1 - 2 * Math.random());
      var x, y, z;
      switch (kind) {
        case "apple": {
          var ra = 0.85;
          x = Math.sin(phi) * Math.cos(theta) * ra;
          y = Math.sin(phi) * Math.sin(theta) * ra * 0.84;
          z = Math.cos(phi) * ra;
          if (Math.random() < 0.06) y += 0.75;      // stem hints
          break;
        }
        case "sphere": case "planet": case "sun": case "moon":
          x = Math.sin(phi) * Math.cos(theta) * 0.85;
          y = Math.sin(phi) * Math.sin(theta) * 0.85;
          z = Math.cos(phi) * 0.85;
          break;
        case "torus": {
          var Rr = 0.62, tr = 0.24, u = Math.random() * TAU, v = Math.random() * TAU;
          x = (Rr + tr * Math.cos(v)) * Math.cos(u);
          y = (Rr + tr * Math.cos(v)) * Math.sin(u);
          z = tr * Math.sin(v);
          break;
        }
        case "cube": {
          var c = 0.66, faceAxis = Math.floor(Math.random() * 3), s = (Math.random() < 0.5 ? -1 : 1);
          x = faceAxis === 0 ? c * s : (Math.random() * 2 - 1) * c;
          y = faceAxis === 1 ? c * s : (Math.random() * 2 - 1) * c;
          z = faceAxis === 2 ? c * s : (Math.random() * 2 - 1) * c;
          break;
        }
        case "cylinder": {
          var a2 = Math.random() * TAU;
          x = Math.cos(a2) * 0.55; z = Math.sin(a2) * 0.55; y = (Math.random() * 2 - 1) * 0.6;
          break;
        }
        case "capsule": {
          x = Math.cos(theta) * 0.45; z = Math.sin(theta) * 0.45;
          y = (Math.random() * 2 - 1) * 0.9;
          break;
        }
        case "cone": {
          var a3 = Math.random() * TAU, yy = Math.random() * 1.3, rad = 0.7 * (1 - yy / 1.3);
          x = Math.cos(a3) * rad; z = Math.sin(a3) * rad; y = yy - 0.65;
          break;
        }
        case "icosa":
          x = Math.sin(phi) * Math.cos(theta) * 0.9;
          y = Math.sin(phi) * Math.sin(theta) * 0.9;
          z = Math.cos(phi) * 0.9;
          break;
        case "sunglasses":
          x = (Math.random() < 0.5 ? -0.2 : 0.2) + rnd() * 0.05;
          y = rnd() * 0.1; z = -0.04 + rnd() * 0.06;
          break;
        case "watch":
          x = Math.cos(theta) * 0.3; y = Math.sin(theta) * 0.3; z = rnd() * 0.08 + 0.03;
          break;
        case "ring": {
          var ra2 = Math.random() * TAU;
          x = Math.cos(ra2) * 0.22; y = Math.sin(ra2) * 0.22; z = rnd() * 0.03;
          break;
        }
        case "necklace": {
          var nb = Math.random() * Math.PI;
          x = Math.sin(nb) * 0.62; y = -Math.cos(nb) * 0.62 - 0.1; z = 0.25 + rnd() * 0.06;
          break;
        }
        case "hat": {
          var hb = Math.random() * TAU, hr = 0.4 + Math.random() * 0.24;
          x = Math.cos(hb) * hr; z = Math.sin(hb) * hr; y = rnd() * 0.35 + 0.25;
          break;
        }
        case "tree":
          x = Math.cos(theta) * 0.5; y = Math.random() * 1.9; z = Math.sin(theta) * 0.5;
          break;
        case "engine":
          x = Math.cos(theta) * 0.4; y = (Math.random() - 0.5) * 1.2; z = Math.sin(theta) * 0.4;
          break;
        case "piston":
          x = rnd() * 0.15; y = (Math.random() - 0.5) * 1.0; z = rnd() * 0.15;
          break;
        case "crankshaft":
          x = Math.cos(theta) * 0.35; y = (Math.random() - 0.5) * 0.1; z = Math.sin(theta) * 0.35;
          break;
        case "gear":
          x = Math.cos(theta) * 0.3; y = rnd() * 0.05; z = Math.sin(theta) * 0.3;
          break;
        case "battery":
          x = rnd() * 0.2; y = (Math.random() - 0.5) * 0.6; z = rnd() * 0.2;
          break;
        case "heart":
          x = Math.sin(phi) * Math.cos(theta) * 0.4; y = Math.sin(phi) * Math.sin(theta) * 0.35; z = Math.cos(phi) * 0.3;
          break;
        case "cell":
          x = Math.sin(phi) * Math.cos(theta) * 0.45; y = Math.sin(phi) * Math.sin(theta) * 0.45; z = Math.cos(phi) * 0.45;
          break;
        case "dna":
          x = Math.sin(theta) * 0.3; y = (Math.random() - 0.5) * 1.2; z = Math.cos(theta) * 0.3;
          break;
        case "wave":
          x = Math.cos(theta) * 0.5; y = Math.sin(phi) * 0.3; z = Math.sin(theta) * 0.5;
          break;
        case "circuit":
          x = rnd() * 0.4; y = rnd() * 0.4; z = rnd() * 0.4;
          break;
        case "laser":
          x = rnd() * 0.05; y = (Math.random() - 0.5) * 1.0; z = rnd() * 0.05;
          break;
        case "mirror":
          x = (Math.random() < 0.5 ? -0.4 : 0.4); y = (Math.random() - 0.5) * 0.3; z = rnd() * 0.05;
          break;
        case "prism":
          x = Math.cos(theta) * 0.3; y = Math.sin(theta) * 0.3; z = rnd() * 0.3;
          break;
        default:
          x = (Math.random() - 0.5); y = (Math.random() - 0.5); z = (Math.random() - 0.5);
          break;
      }
      pts.push(v3(x * 1.7, y * 1.7, z * 1.7));
    }
    return pts;
  }

  // The presence plugs into the shared galaxy page — module complete.
})();