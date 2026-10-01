import React from "react";

const BASE_LAYERS = [
  { key: "lulc", label: "Land Use / Land Cover" },
  { key: "ndvi", label: "NDVI (Vegetation)" },
  { key: "water_freq", label: "Water Frequency" },
  { key: "ndmi", label: "Moisture Proxy (NDMI)" },
];

const LULC_LEGEND = [
  { color: "#3182bd", label: "Water" },
  { color: "#1a762c", label: "Dense vegetation" },
  { color: "#a1d96a", label: "Cropland / moderate" },
  { color: "#decb89", label: "Scrub / sparse" },
  { color: "#969696", label: "Barren / built" },
];

const GRADIENT_LEGENDS = {
  ndvi: { css: "linear-gradient(90deg, #a50026, #ffffbf, #1a9850)", low: "-0.2", high: "0.8" },
  water_freq: { css: "linear-gradient(90deg, #f7fbff, #08306b)", low: "0", high: "1" },
  ndmi: { css: "linear-gradient(90deg, #8c510a, #f5f5f5, #01665e)", low: "-0.5", high: "0.5" },
};

export default function LayerPanel({
  years, activeLayer, setActiveLayer, activeYear, setActiveYear,
  showWatershed, setShowWatershed, showStreams, setShowStreams,
  showInterventions, setShowInterventions, interventionsGeojson,
}) {
  const counts = { total: 0, corroborated: 0, mismatch: 0, inconclusive: 0 };
  (interventionsGeojson?.features || []).forEach((f) => {
    counts.total += 1;
    if (counts[f.properties.verdict] !== undefined) counts[f.properties.verdict] += 1;
  });
  return (
    <div className="panel layer-panel">
      {interventionsGeojson && (
        <div className="stat-grid">
          <div className="stat"><b>{counts.total}</b><span>Interventions</span></div>
          <div className="stat ok"><b>{counts.corroborated}</b><span>Corroborated</span></div>
          <div className="stat bad"><b>{counts.mismatch}</b><span>Mismatch</span></div>
          <div className="stat mute"><b>{counts.inconclusive}</b><span>Inconclusive</span></div>
        </div>
      )}
      <div className="panel-section">
        <h3>Base Layer</h3>
        {BASE_LAYERS.map((l) => (
          <label className="radio-row" key={l.key}>
            <input
              type="radio"
              name="baseLayer"
              checked={activeLayer === l.key}
              onChange={() => setActiveLayer(l.key)}
            />
            {l.label}
          </label>
        ))}
      </div>

      <div className="panel-section">
        <h3>Year</h3>
        <select
          className="select-input"
          value={activeYear ?? ""}
          disabled={activeLayer === "water_freq"}
          onChange={(e) => setActiveYear(Number(e.target.value))}
        >
          {years.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
        {activeLayer === "water_freq" && (
          <div className="metric-card metric-caption" style={{ marginTop: 6, border: "none", padding: 0 }}>
            Water frequency is aggregated across all years.
          </div>
        )}
      </div>

      <div className="panel-section">
        <h3>Legend</h3>
        {activeLayer === "lulc" ? (
          LULC_LEGEND.map((item) => (
            <div className="legend-row" key={item.label}>
              <span className="legend-swatch" style={{ background: item.color }} />
              {item.label}
            </div>
          ))
        ) : (
          <>
            <div className="legend-gradient" style={{ background: GRADIENT_LEGENDS[activeLayer].css }} />
            <div className="legend-labels">
              <span>{GRADIENT_LEGENDS[activeLayer].low}</span>
              <span>{GRADIENT_LEGENDS[activeLayer].high}</span>
            </div>
          </>
        )}
        {activeLayer === "ndmi" && (
          <div className="metric-caption" style={{ marginTop: 6 }}>
            Moisture proxy — not measured soil moisture.
          </div>
        )}
      </div>

      <div className="panel-section">
        <h3>Overlays</h3>
        <label className="checkbox-row">
          <input type="checkbox" checked={showWatershed} onChange={(e) => setShowWatershed(e.target.checked)} />
          Watershed boundary
        </label>
        <label className="checkbox-row">
          <input type="checkbox" checked={showStreams} onChange={(e) => setShowStreams(e.target.checked)} />
          Streams
        </label>
        <label className="checkbox-row">
          <input type="checkbox" checked={showInterventions} onChange={(e) => setShowInterventions(e.target.checked)} />
          Interventions
        </label>
      </div>

      {showInterventions && (
        <div className="panel-section">
          <h3>Intervention Legend</h3>
          <div className="legend-row"><span className="dot dot-corroborated" /> Corroborated</div>
          <div className="legend-row"><span className="dot dot-mismatch" /> Mismatch</div>
          <div className="legend-row"><span className="dot dot-inconclusive" /> Inconclusive</div>
        </div>
      )}
    </div>
  );
}
