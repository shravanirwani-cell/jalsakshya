import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import {
  MapContainer, TileLayer, ImageOverlay, GeoJSON, CircleMarker, Circle, Marker, Tooltip,
  ScaleControl, useMap, useMapEvents,
} from "react-leaflet";
import LiveWeather from "./LiveWeather";

const VERDICT_COLOR = {
  corroborated: "#1f9d55",
  mismatch: "#d93025",
  inconclusive: "#6b7280",
};

// Google Maps tile endpoints (lyrs: y = satellite+labels, m = roadmap, p = terrain)
const BASEMAPS = [
  { key: "hybrid", label: "Satellite", lyrs: "y" },
  { key: "roadmap", label: "Map", lyrs: "m" },
  { key: "terrain", label: "Terrain", lyrs: "p" },
];

const userIcon = L.divIcon({
  className: "user-location-icon",
  html: '<span class="user-pulse"></span><span class="user-dot"></span>',
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

function FlyTo({ target }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo([target.lat, target.lon], Math.max(map.getZoom(), 15), { duration: 0.8 });
  }, [target, map]);
  return null;
}

function FitBounds({ bounds, resetSignal }) {
  const map = useMap();
  const didFit = useRef(false);
  useEffect(() => {
    if (bounds && (!didFit.current || resetSignal)) {
      map.fitBounds(bounds);
      didFit.current = true;
    }
  }, [bounds, map, resetSignal]);
  return null;
}

function ClickHandler({ onMapClick, onCursor }) {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng.lat, e.latlng.lng);
    },
    mousemove(e) {
      onCursor(e.latlng);
    },
  });
  return null;
}

// Real-time device location via the browser Geolocation API (watchPosition under the hood).
function LiveLocation({ active, onStatus }) {
  const map = useMap();
  const [pos, setPos] = useState(null);
  const centered = useRef(false);

  useEffect(() => {
    if (!active) {
      setPos(null);
      centered.current = false;
      return undefined;
    }
    if (!navigator.geolocation) {
      onStatus("Geolocation is not supported by this browser.");
      return undefined;
    }
    onStatus("Locating…");
    const id = navigator.geolocation.watchPosition(
      (p) => {
        const next = { lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy };
        setPos(next);
        onStatus(`Live · ±${Math.round(next.acc)} m`);
        if (!centered.current) {
          centered.current = true;
          map.flyTo([next.lat, next.lon], Math.max(map.getZoom(), 15), { duration: 1 });
        }
      },
      (err) => onStatus(err.code === 1 ? "Location permission denied." : "Location unavailable."),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 },
    );
    return () => navigator.geolocation.clearWatch(id);
  }, [active, map, onStatus]);

  if (!pos) return null;
  return (
    <>
      <Circle center={[pos.lat, pos.lon]} radius={pos.acc}
              pathOptions={{ color: "#1a73e8", weight: 1, fillColor: "#1a73e8", fillOpacity: 0.12 }} />
      <Marker position={[pos.lat, pos.lon]} icon={userIcon} interactive={false} />
    </>
  );
}

export default function MapView({
  meta, layerInfo, watershedGeojson, streamsGeojson, interventionsGeojson,
  showWatershed, showStreams, showInterventions,
  selectedId, onSelectIntervention, onMapClick, flyTarget,
}) {
  const [showLimits, setShowLimits] = useState(false);
  const [basemap, setBasemap] = useState("hybrid");
  const [opacity, setOpacity] = useState(0.7);
  const [locating, setLocating] = useState(false);
  const [locStatus, setLocStatus] = useState("");
  const [cursor, setCursor] = useState(null);
  const [resetSignal, setResetSignal] = useState(0);
  const areaRef = useRef(null);

  if (!meta) {
    return (
      <div className="map-area">
        <div className="map-skeleton"><div className="spinner" /><span>Loading map…</span></div>
      </div>
    );
  }

  const bbox = meta.bbox;
  const initialBounds = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]];
  const center = [(bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2];
  const lyrs = BASEMAPS.find((b) => b.key === basemap).lyrs;
  const dark = basemap === "hybrid";

  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else areaRef.current?.requestFullscreen?.();
  };

  return (
    <div className={`map-area${dark ? " map-dark" : ""}`} ref={areaRef}>
      <MapContainer center={center} zoom={13} zoomControl={true} maxZoom={20} attributionControl={false}>
        <TileLayer
          key={lyrs}
          url={`https://mt{s}.google.com/vt/lyrs=${lyrs}&x={x}&y={y}&z={z}`}
          subdomains={["0", "1", "2", "3"]}
          maxZoom={20}
          attribution="Map data ©2026 Google"
        />
        <ScaleControl position="bottomright" imperial={false} />
        <FitBounds bounds={initialBounds} resetSignal={resetSignal} />
        <ClickHandler onMapClick={onMapClick} onCursor={setCursor} />
        <FlyTo target={flyTarget} />
        <LiveLocation active={locating} onStatus={setLocStatus} />

        {layerInfo && (
          <ImageOverlay key={layerInfo.url} url={layerInfo.url} bounds={layerInfo.bounds} opacity={opacity} />
        )}

        {showWatershed && watershedGeojson && (
          <GeoJSON
            data={watershedGeojson}
            style={{ color: dark ? "#7dffd4" : "#0b4a3f", weight: 2.5, fillOpacity: 0, dashArray: "6 4" }}
          />
        )}

        {showStreams && streamsGeojson && (
          <GeoJSON
            data={streamsGeojson}
            style={{ color: dark ? "#5cc8ff" : "#2f6fa8", weight: 2, opacity: 0.9 }}
          />
        )}

        {showInterventions && interventionsGeojson && interventionsGeojson.features.map((f) => {
          const [lon, lat] = f.geometry.coordinates;
          const isSelected = f.properties.id === selectedId;
          const color = VERDICT_COLOR[f.properties.verdict] || "#6b7280";
          return (
            <CircleMarker
              key={f.properties.id}
              center={[lat, lon]}
              radius={isSelected ? 11 : 8}
              pathOptions={{
                color: isSelected ? "#fff" : "#fff",
                weight: isSelected ? 3 : 2,
                fillColor: color,
                fillOpacity: 1,
              }}
              eventHandlers={{
                click: (e) => {
                  L.DomEvent.stopPropagation(e);
                  onSelectIntervention(f.properties.id);
                },
              }}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                <strong>{f.properties.name}</strong>
                {f.properties.verdict && <div className="tt-sub">{f.properties.verdict}</div>}
              </Tooltip>
            </CircleMarker>
          );
        })}
      </MapContainer>

      <div className="map-toolbar glass">
        <div className="seg">
          {BASEMAPS.map((b) => (
            <button key={b.key} className={basemap === b.key ? "active" : ""} onClick={() => setBasemap(b.key)}>
              {b.label}
            </button>
          ))}
        </div>
        <label className="opacity-ctl" title="Data layer opacity">
          <span>Layer</span>
          <input type="range" min="0" max="1" step="0.05" value={opacity}
                 onChange={(e) => setOpacity(Number(e.target.value))} />
        </label>
      </div>

      <div className="map-fabs">
        <button className={`fab glass${locating ? " on" : ""}`} onClick={() => { setLocating((l) => !l); setLocStatus(""); }}
                title="Show my live location" aria-label="Show my live location">◎</button>
        <button className="fab glass" onClick={() => setResetSignal((n) => n + 1)}
                title="Reset view to watershed" aria-label="Reset view">⌂</button>
        <button className="fab glass" onClick={toggleFullscreen} title="Fullscreen" aria-label="Fullscreen">⛶</button>
      </div>
      {locating && locStatus && <div className="loc-status glass">{locStatus}</div>}

      <LiveWeather lat={center[0]} lon={center[1]} />

      <div className="coord-readout glass">
        {cursor ? `${cursor.lat.toFixed(5)}°N, ${cursor.lng.toFixed(5)}°E` : "Hover the map for coordinates"}
        <span className="attrib"> · Map data ©2026 Google</span>
      </div>

      <div className="limits-footer">
        {showLimits && (
          <div className="limits-popover glass">
            <strong>30 m limitation:</strong> Landsat pixels are 30&nbsp;m &times; 30&nbsp;m (0.09&nbsp;ha).
            Small structures such as a single check dam or pond bund cannot be reliably resolved.
            This workbench analyses the surrounding zone (a 3&times;3-pixel local zone and a
            ~500&nbsp;m context zone), not the structure itself, and marks weak evidence as
            <em> Inconclusive</em> rather than forcing a verdict.
          </div>
        )}
        <button className="limits-btn glass" onClick={() => setShowLimits((s) => !s)}>
          ⓘ 30m resolution limits
        </button>
      </div>
    </div>
  );
}
