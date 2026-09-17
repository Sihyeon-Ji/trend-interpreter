"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import {
  geoCircle,
  geoContains,
  geoEquirectangular,
  geoInterpolate,
  geoOrthographic,
  geoPath,
} from "d3-geo";
import type { FeatureCollection, Geometry } from "geojson";
import { LocateFixed, Minus, Plus, RotateCw } from "lucide-react";
import rawGeography from "@/data/countries.geo.json";
import type { Country, Report } from "@/lib/types";
import { scenarioRadius, type ScenarioSettings } from "@/lib/scenario";

type CountryProperties = Country;
const geography = rawGeography as FeatureCollection<
  Geometry,
  CountryProperties
>;
export const GLOBE_COUNTRIES = geography.features
  .map((feature) => feature.properties)
  .filter((country) => country.code.length === 2 && country.code !== "AQ")
  .sort((a, b) => a.name.localeCompare(b.name));
const TEXTURE_WIDTH = 2048;
const TEXTURE_HEIGHT = 1024;
const INITIAL_DISTANCE = 3.25;

function scenarioEnvelope(origin: [number, number], radius: number) {
  const shape = geoCircle().center(origin).radius(radius).precision(2)();
  const ring = shape.coordinates[0];
  shape.coordinates[0] = ring.map((point, index) => {
    const angle = (index / (ring.length - 1)) * Math.PI * 2;
    const variation =
      0.95 + 0.09 * Math.sin(angle * 3) + 0.055 * Math.cos(angle * 7);
    return geoInterpolate(origin, point as [number, number])(variation);
  });
  shape.coordinates[0][shape.coordinates[0].length - 1] =
    shape.coordinates[0][0];
  return shape;
}

interface Props {
  reports: Report[];
  selected: string;
  onSelect: (country: Country) => void;
  scenario?: ScenarioSettings;
}

function cameraPosition(
  longitude: number,
  latitude: number,
  distance = INITIAL_DISTANCE,
) {
  const lon = THREE.MathUtils.degToRad(longitude);
  const lat = THREE.MathUtils.degToRad(latitude);
  return new THREE.Vector3(
    Math.cos(lat) * Math.cos(lon),
    Math.sin(lat),
    -Math.cos(lat) * Math.sin(lon),
  ).multiplyScalar(distance);
}

function paintOverlay(
  canvas: HTMLCanvasElement,
  reports: Report[],
  selected: string,
  scenario?: ScenarioSettings,
) {
  const context = canvas.getContext("2d");
  if (!context) return;
  context.clearRect(0, 0, TEXTURE_WIDTH, TEXTURE_HEIGHT);
  const projection = geoEquirectangular()
    .scale(TEXTURE_WIDTH / (2 * Math.PI))
    .translate([TEXTURE_WIDTH / 2, TEXTURE_HEIGHT / 2]);
  const path = geoPath(projection, context);
  const counts = new Map<string, number>();
  for (const report of reports)
    for (const country of report.countries)
      counts.set(country.code, (counts.get(country.code) ?? 0) + 1);
  for (const feature of geography.features) {
    context.beginPath();
    path(feature);
    if (!scenario && counts.has(feature.properties.code)) {
      context.fillStyle = "rgba(220,40,54,0.52)";
      context.fill();
      context.save();
      context.clip();
      context.strokeStyle = "rgba(255,118,113,0.28)";
      context.lineWidth = 1;
      for (let x = -TEXTURE_HEIGHT; x < TEXTURE_WIDTH; x += 10) {
        context.beginPath();
        context.moveTo(x, 0);
        context.lineTo(x + TEXTURE_HEIGHT, TEXTURE_HEIGHT);
        context.stroke();
      }
      context.restore();
      context.beginPath();
      path(feature);
    }
    context.strokeStyle =
      feature.properties.code === selected
        ? "rgba(255,226,194,0.9)"
        : "rgba(166,188,193,0.24)";
    context.lineWidth = feature.properties.code === selected ? 1.8 : 0.65;
    context.stroke();
  }
  if (!scenario) return;
  context.save();
  context.beginPath();
  path(geography);
  context.clip();
  const radius = scenarioRadius(scenario.day, scenario.pace, scenario.response);
  for (let band = 32; band >= 1; band--) {
    const envelope = scenarioEnvelope(
      [scenario.origin.longitude, scenario.origin.latitude],
      (radius * band) / 32,
    );
    context.beginPath();
    path(envelope);
    context.fillStyle =
      band > 24 ? "rgba(246,130,70,0.025)" : "rgba(241,43,54,0.065)";
    context.fill();
  }
  context.restore();
  context.beginPath();
  path(
    scenarioEnvelope(
      [scenario.origin.longitude, scenario.origin.latitude],
      radius,
    ),
  );
  context.strokeStyle = "rgba(250,148,95,0.55)";
  context.lineWidth = 0.9;
  context.setLineDash([4, 5]);
  context.stroke();
  context.setLineDash([]);
}

function FallbackGlobe({ reports, onSelect, selected, scenario }: Props) {
  const [rotation, setRotation] = useState<[number, number]>([-25, -15]);
  const drag = useRef<[number, number] | null>(null);
  useEffect(() => {
    const country = GLOBE_COUNTRIES.find((item) => item.code === selected);
    if (country) setRotation([-country.longitude, -country.latitude]);
  }, [selected]);
  const projection = geoOrthographic()
    .scale(235)
    .translate([300, 270])
    .rotate(rotation);
  const path = geoPath(projection);
  const covered = new Set(
    reports.flatMap((report) =>
      report.countries.map((country) => country.code),
    ),
  );
  return (
    <div className="fallback-globe">
      <svg
        viewBox="0 0 600 540"
        aria-label="Interactive globe in compatibility mode"
        onPointerDown={(event) => {
          drag.current = [event.clientX, event.clientY];
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (!drag.current) return;
          const [x, y] = drag.current;
          setRotation(([lon, lat]) => [
            lon + (event.clientX - x) * 0.4,
            Math.max(-70, Math.min(70, lat - (event.clientY - y) * 0.4)),
          ]);
          drag.current = [event.clientX, event.clientY];
        }}
        onPointerUp={() => {
          drag.current = null;
        }}
      >
        <defs>
          <radialGradient id="fallback-ocean">
            <stop stopColor="#360d22" />
            <stop offset="1" stopColor="#080309" />
          </radialGradient>
          <clipPath id="fallback-land">
            {geography.features.map((feature, index) => (
              <path key={index} d={path(feature) ?? ""} />
            ))}
          </clipPath>
        </defs>
        <circle
          cx="300"
          cy="270"
          r="237"
          fill="url(#fallback-ocean)"
          stroke="#6b839355"
        />
        {geography.features.map((feature, index) => (
          <path
            key={index}
            d={path(feature) ?? ""}
            fill={
              !scenario && covered.has(feature.properties.code)
                ? "#d33553"
                : "#452337"
            }
            stroke={
              selected === feature.properties.code ? "#eed3a9" : "#824656"
            }
            strokeWidth=".55"
            onClick={() => onSelect(feature.properties)}
          />
        ))}
        {scenario ? (
          <path
            clipPath="url(#fallback-land)"
            d={
              path(
                scenarioEnvelope(
                  [scenario.origin.longitude, scenario.origin.latitude],
                  scenarioRadius(
                    scenario.day,
                    scenario.pace,
                    scenario.response,
                  ),
                ),
              ) ?? ""
            }
            fill="#e63b4a99"
            stroke="#f1a47d"
          />
        ) : null}
      </svg>
      <span className="compatibility-note">
        Compatibility renderer · drag to rotate
      </span>
    </div>
  );
}

export default function EarthGlobe(props: Props) {
  const { reports, selected, scenario } = props;
  const mount = useRef<HTMLDivElement>(null);
  const onSelect = useRef(props.onSelect);
  const runtime = useRef<{
    texture: THREE.CanvasTexture;
    canvas: HTMLCanvasElement;
    controls: OrbitControls;
    camera: THREE.PerspectiveCamera;
    focus: THREE.Vector3 | null;
  } | null>(null);
  const [fallback, setFallback] = useState(false);
  const [ready, setReady] = useState(false);
  const [rotating, setRotating] = useState(false);
  const [hovered, setHovered] = useState<Country | null>(null);
  const [textureFailed, setTextureFailed] = useState(false);
  const [terrainReady, setTerrainReady] = useState(false);
  const input = useRef({ reports, selected, scenario });
  onSelect.current = props.onSelect;
  input.current = { reports, selected, scenario };

  useEffect(() => {
    const element = mount.current;
    if (!element) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: "low-power",
      });
    } catch {
      setFallback(true);
      return;
    }
    let disposed = false;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 50);
    camera.position.copy(cameraPosition(27, 14));
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    element.appendChild(renderer.domElement);
    renderer.domElement.setAttribute(
      "aria-label",
      "Rotatable Earth globe. Drag to rotate; scroll or use controls to zoom. Select a country to inspect its reports.",
    );
    renderer.domElement.setAttribute("role", "img");
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.minDistance = 1.75;
    controls.maxDistance = 5;
    controls.rotateSpeed = 0.55;
    controls.zoomSpeed = 0.65;
    controls.autoRotateSpeed = 0.35;
    const geometry = new THREE.SphereGeometry(1, 96, 64);
    const earthMaterial = new THREE.MeshPhongMaterial({
      color: 0x9aaba9,
      shininess: 5,
      specular: 0x141e25,
    });
    earthMaterial.onBeforeCompile = (shader) => {
      shader.fragmentShader = shader.fragmentShader.replace(
        "#include <color_fragment>",
        "#include <color_fragment>\nfloat terrainLuma = dot(diffuseColor.rgb, vec3(0.299, 0.587, 0.114));\ndiffuseColor.rgb = mix(diffuseColor.rgb, vec3(terrainLuma * 1.48, terrainLuma * 0.25, terrainLuma * 0.38), 0.82);",
      );
    };
    const earth = new THREE.Mesh(geometry, earthMaterial);
    scene.add(earth);
    const ambient = new THREE.AmbientLight(0xbacbd2, 1.05);
    scene.add(ambient);
    const sunlight = new THREE.DirectionalLight(0xf6f0e1, 2);
    sunlight.position.set(3, 4, 4);
    scene.add(sunlight);
    const rim = new THREE.DirectionalLight(0x56768b, 1.25);
    rim.position.set(-3, 1, -4);
    scene.add(rim);
    const canvas = document.createElement("canvas");
    canvas.width = TEXTURE_WIDTH;
    canvas.height = TEXTURE_HEIGHT;
    paintOverlay(
      canvas,
      input.current.reports,
      input.current.selected,
      input.current.scenario,
    );
    const overlayTexture = new THREE.CanvasTexture(canvas);
    overlayTexture.colorSpace = THREE.SRGBColorSpace;
    const overlayMaterial = new THREE.MeshBasicMaterial({
      map: overlayTexture,
      transparent: true,
      depthWrite: false,
    });
    const overlay = new THREE.Mesh(geometry, overlayMaterial);
    overlay.scale.setScalar(1.004);
    scene.add(overlay);
    const atmosphereMaterial = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      side: THREE.BackSide,
      vertexShader:
        "varying vec3 n; varying vec3 p; void main(){vec4 pos=modelViewMatrix*vec4(position,1.0);p=pos.xyz;n=normalize(normalMatrix*normal);gl_Position=projectionMatrix*pos;}",
      fragmentShader:
        "varying vec3 n; varying vec3 p; void main(){float rim=pow(max(0.0,1.0-abs(dot(normalize(n),normalize(-p)))),3.0);gl_FragColor=vec4(0.66,0.1,0.2,rim*0.28);}",
    });
    const atmosphere = new THREE.Mesh(geometry, atmosphereMaterial);
    atmosphere.scale.setScalar(1.012);
    scene.add(atmosphere);
    runtime.current = {
      camera,
      controls,
      texture: overlayTexture,
      canvas,
      focus: null,
    };
    const loader = new THREE.TextureLoader();
    const earthTexture = loader.load(
      "/earth-day.jpg",
      (texture) => {
        if (disposed) {
          texture.dispose();
          return;
        }
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.anisotropy = Math.min(
          8,
          renderer.capabilities.getMaxAnisotropy(),
        );
        earthMaterial.map = texture;
        earthMaterial.needsUpdate = true;
        setTerrainReady(true);
      },
      undefined,
      () => {
        if (!disposed) setTextureFailed(true);
      },
    );
    const resize = () => {
      const { width, height } = element.getBoundingClientRect();
      if (!width || !height) return;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    resize();
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let down: [number, number] | null = null;
    const pick = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        (-(event.clientY - rect.top) / rect.height) * 2 + 1,
      );
      raycaster.setFromCamera(pointer, camera);
      const uv = raycaster.intersectObject(earth)[0]?.uv;
      if (!uv) return null;
      const coordinate: [number, number] = [uv.x * 360 - 180, uv.y * 180 - 90];
      return (
        geography.features.find((feature) => geoContains(feature, coordinate))
          ?.properties ?? null
      );
    };
    const pointerDown = (event: PointerEvent) => {
      down = [event.clientX, event.clientY];
      if (runtime.current) runtime.current.focus = null;
    };
    const pointerMove = (event: PointerEvent) => {
      if (!down) setHovered(pick(event));
    };
    const pointerUp = (event: PointerEvent) => {
      if (
        down &&
        Math.hypot(event.clientX - down[0], event.clientY - down[1]) < 5
      ) {
        const country = pick(event);
        if (country && country.code.length === 2 && country.code !== "AQ")
          onSelect.current(country);
      }
      down = null;
    };
    const pointerLeave = () => {
      setHovered(null);
      down = null;
    };
    renderer.domElement.addEventListener("pointerdown", pointerDown);
    renderer.domElement.addEventListener("pointermove", pointerMove);
    renderer.domElement.addEventListener("pointerup", pointerUp);
    renderer.domElement.addEventListener("pointerleave", pointerLeave);
    const contextLost = (event: Event) => {
      event.preventDefault();
      cancelAnimationFrame(frame);
      setFallback(true);
    };
    renderer.domElement.addEventListener("webglcontextlost", contextLost);
    let frame = 0;
    let lastFrame = 0;
    const animate = (time: number) => {
      frame = requestAnimationFrame(animate);
      if (document.hidden || time - lastFrame < 1000 / 45) return;
      lastFrame = time;
      if (runtime.current?.focus) {
        camera.position.lerp(runtime.current.focus, 0.075);
        if (camera.position.distanceTo(runtime.current.focus) < 0.01)
          runtime.current.focus = null;
      }
      controls.update();
      renderer.render(scene, camera);
    };
    frame = requestAnimationFrame(animate);
    setReady(true);
    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener("pointerdown", pointerDown);
      renderer.domElement.removeEventListener("pointermove", pointerMove);
      renderer.domElement.removeEventListener("pointerup", pointerUp);
      renderer.domElement.removeEventListener("pointerleave", pointerLeave);
      renderer.domElement.removeEventListener("webglcontextlost", contextLost);
      geometry.dispose();
      earthMaterial.dispose();
      overlayMaterial.dispose();
      atmosphereMaterial.dispose();
      earthTexture.dispose();
      overlayTexture.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      runtime.current = null;
    };
  }, []);

  useEffect(() => {
    const current = runtime.current;
    if (!current) return;
    paintOverlay(current.canvas, reports, selected, scenario);
    current.texture.needsUpdate = true;
  }, [reports, selected, scenario, ready]);
  const focusCode = scenario?.origin.code ?? selected;
  useEffect(() => {
    const country = GLOBE_COUNTRIES.find(
      (country) => country.code === focusCode,
    );
    if (country && runtime.current)
      runtime.current.focus = cameraPosition(
        country.longitude,
        country.latitude,
      );
  }, [focusCode, ready]);
  useEffect(() => {
    if (runtime.current) runtime.current.controls.autoRotate = rotating;
  }, [rotating]);
  const reportCount = useMemo(
    () =>
      hovered
        ? reports.filter((report) =>
            report.countries.some((country) => country.code === hovered.code),
          ).length
        : 0,
    [hovered, reports],
  );

  return (
    <div
      className="earth-view"
      data-renderer={fallback ? "compatibility" : ready ? "webgl" : "loading"}
      data-terrain={
        terrainReady ? "ready" : textureFailed ? "unavailable" : "loading"
      }
      data-scenario-radius={
        scenario
          ? scenarioRadius(
              scenario.day,
              scenario.pace,
              scenario.response,
            ).toFixed(2)
          : undefined
      }
    >
      <div className="orbital-guide orbit-one" />
      <div className="orbital-guide orbit-two" />
      <div
        className="earth-canvas"
        ref={mount}
        style={fallback ? { display: "none" } : undefined}
      />
      {fallback ? <FallbackGlobe {...props} /> : null}
      {!ready && !fallback ? (
        <div className="globe-loading">
          INITIALIZING EARTH VIEW
          <span />
        </div>
      ) : null}
      {textureFailed ? (
        <div className="compatibility-note">
          Terrain image unavailable · country boundaries remain available
        </div>
      ) : null}
      {hovered && !fallback ? (
        <div className="earth-hover">
          <span>{hovered.name}</span>
          <small>
            {scenario
              ? "Click to set scenario origin"
              : `${reportCount} reports · click to inspect`}
          </small>
          {!scenario ? (
            <ul>
              {reports
                .filter((report) =>
                  report.countries.some(
                    (country) => country.code === hovered.code,
                  ),
                )
                .slice(0, 2)
                .map((report) => (
                  <li key={report.id}>{report.title}</li>
                ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {!fallback ? (
        <div className="earth-tools">
          <button
            aria-label="Zoom in"
            onClick={() => {
              const r = runtime.current;
              if (r)
                r.camera.position.setLength(
                  Math.max(1.75, r.camera.position.length() - 0.35),
                );
            }}
          >
            <Plus size={17} />
          </button>
          <button
            aria-label="Zoom out"
            onClick={() => {
              const r = runtime.current;
              if (r)
                r.camera.position.setLength(
                  Math.min(5, r.camera.position.length() + 0.35),
                );
            }}
          >
            <Minus size={17} />
          </button>
          <button
            aria-label="Reset globe"
            onClick={() => {
              if (runtime.current)
                runtime.current.focus = cameraPosition(27, 14);
              setRotating(false);
            }}
          >
            <LocateFixed size={17} />
          </button>
          <button
            aria-label="Auto rotate globe"
            aria-pressed={rotating}
            className={rotating ? "on" : ""}
            onClick={() => setRotating(!rotating)}
          >
            <RotateCw size={17} />
          </button>
        </div>
      ) : null}
      <div className="earth-instructions">
        DRAG TO ROTATE <span>/</span> SCROLL TO ZOOM
      </div>
    </div>
  );
}
