import React, { useEffect, useState } from "react";
import L from "leaflet";
import { MapContainer, ImageOverlay, GeoJSON, CircleMarker, useMap, useMapEvents } from "react-leaflet";

const VERDICT_COLOR = {
  corroborated: "#1f9d55",
  mismatch: "#d93025",
  inconclusive: "#6b7280",
};

function FlyTo({ target }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo([target.lat, target.lon], Math.max(map.getZoom(), 15), { duration: 0.8 });
  }, [target, map]);
  return null;
}

function FitBounds({ bounds }) {
  const map = useMap();
  const didFit = React.useRef(false);
  useEffect(() => {
    if (bounds && !didFit.current) {
      map.fitBounds(bounds);
      didFit.current = true;
    }
  }, [bounds, map]);
  return null;
}

function ClickHandler({ onMapClick }) {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

export default function MapView({
  meta, layerInfo, watershedGeojson, streamsGeojson, interventionsGeojson,
  showWatershed, showStreams, showInterventions,
  selectedId, onSelectIntervention, onMapClick, flyTarget,
}) {
  const [showLimits, setShowLimits] = useState(false);
  if (!meta) return <div className="loading-text">Loading map...</div>;

  const bbox = meta.bbox;
  const initialBounds = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]];
  const center = [(bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2];

  return (
    <div className="map-area">
      <MapContainer center={center} zoom={13} zoomControl={true} attributionControl={false}
                     style={{ background: "#dfe8e4" }}>
        <FitBounds bounds={initialBounds} />
        <ClickHandler onMapClick={onMapClick} />
        <FlyTo target={flyTarget} />

        {layerInfo && (
          <ImageOverlay key={layerInfo.url} url={layerInfo.url} bounds={layerInfo.bounds} opacity={0.85} />
        )}

        {showWatershed && watershedGeojson && (
          <GeoJSON
            data={watershedGeojson}
            style={{ color: "#0b4a3f", weight: 2, fillOpacity: 0 }}
          />
        )}

        {showStreams && streamsGeojson && (
          <GeoJSON
            data={streamsGeojson}
            style={{ color: "#2f6fa8", weight: 1.5, opacity: 0.8 }}
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
              radius={isSelected ? 10 : 7}
              pathOptions={{
                color: isSelected ? "#111" : "#fff",
                weight: isSelected ? 2 : 1.5,
                fillColor: color,
                fillOpacity: 0.95,
              }}
              eventHandlers={{
                click: (e) => {
                  L.DomEvent.stopPropagation(e);
                  onSelectIntervention(f.properties.id);
                },
              }}
            />
          );
        })}
      </MapContainer>

      <div className="limits-footer">
        {showLimits && (
          <div className="limits-popover">
            <strong>30 m limitation:</strong> Landsat pixels are 30&nbsp;m &times; 30&nbsp;m (0.09&nbsp;ha).
            Small structures such as a single check dam or pond bund cannot be reliably resolved.
            This workbench analyses the surrounding zone (a 3&times;3-pixel local zone and a
            ~500&nbsp;m context zone), not the structure itself, and marks weak evidence as
            <em> Inconclusive</em> rather than forcing a verdict.
          </div>
        )}
        <button className="limits-btn" onClick={() => setShowLimits((s) => !s)}>
          ⓘ 30m resolution limits
        </button>
      </div>
    </div>
  );
}
