import React, { useEffect, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from "recharts";
import { api } from "../api";
import PixelInspector from "./PixelInspector";
import BeforeAfterSlider from "./BeforeAfterSlider";

const TYPE_LABEL = {
  check_dam: "Check Dam", farm_pond: "Farm Pond", trench: "Trench", plantation: "Plantation",
};

function VerdictBadge({ verdict }) {
  if (!verdict) return null;
  return <span className={`verdict-badge verdict-${verdict}`}>{verdict.toUpperCase()}</span>;
}

function AISection({ ai }) {
  if (!ai) return <div className="empty-state">No AI interpretation available.</div>;
  return (
    <div>
      <div className="chip-row">
        <span className="chip">{ai.structure_type}</span>
        <span className="chip">{ai.water_present ? "Water present" : "No water"}</span>
        <span className="chip">Vegetation: {ai.vegetation_level}</span>
        <span className="chip">Land: {ai.land_condition}</span>
        <span className="chip">Structure: {ai.structure_condition}</span>
      </div>
      <div className="metric-caption">Confidence: {(ai.confidence * 100).toFixed(0)}%</div>
      <div className="confidence-bar-track">
        <div className="confidence-bar-fill" style={{ width: `${ai.confidence * 100}%` }} />
      </div>
      {ai.notes && <div className="reason-text" style={{ marginTop: 8 }}>{ai.notes}</div>}
    </div>
  );
}

function ImpactMetrics({ impact }) {
  if (!impact) return null;
  const fmt = (v) => (v === null || v === undefined || Number.isNaN(v) ? "—" : v.toFixed(3));
  return (
    <div className="metric-grid">
      <div className="metric-card">
        <div className="metric-value">{fmt(impact.ndvi_did)}</div>
        <div className="metric-label">NDVI DiD</div>
        <div className="metric-caption">Vegetation gain vs. control area</div>
      </div>
      <div className="metric-card">
        <div className="metric-value">{fmt(impact.water_freq_did)}</div>
        <div className="metric-label">Water Frequency DiD</div>
        <div className="metric-caption">Change in wet-pixel share vs. control</div>
      </div>
      <div className="metric-card">
        <div className="metric-value">{fmt(impact.ndmi_did)}</div>
        <div className="metric-label">Moisture Proxy DiD</div>
        <div className="metric-caption">NDMI change vs. control (not measured soil moisture)</div>
      </div>
      <div className="metric-card">
        <div className="metric-value">{impact.n_clear_scenes ?? "—"}</div>
        <div className="metric-label">Clear Years</div>
        <div className="metric-caption">Years of usable satellite data</div>
      </div>
    </div>
  );
}

function WiiGauge({ wii }) {
  if (wii === null || wii === undefined) return null;
  return (
    <div className="wii-gauge">
      <div>
        <div className="wii-number">{wii.toFixed(0)}</div>
        <div className="wii-sub">/ 100</div>
      </div>
      <div style={{ flex: 1 }}>
        <div className="wii-bar-track">
          <div className="wii-bar-fill" style={{ width: `${Math.min(100, Math.max(0, wii))}%` }} />
        </div>
        <div className="metric-caption" style={{ marginTop: 6 }}>
          Watershed Impact Index — weighted: NDVI 35%, Water 35%, Moisture 15%, Photo confidence 15%
        </div>
      </div>
    </div>
  );
}

function SeriesChart({ series, completedOn }) {
  if (!series || !series.years) return null;
  const data = series.years.map((y, i) => ({
    year: y,
    Treated: series.treated_ndvi[i],
    Control: series.control_ndvi[i],
  }));
  const completedYear = completedOn ? Number(completedOn.slice(0, 4)) : null;
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8e5" />
        <XAxis dataKey="year" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} domain={["auto", "auto"]} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {completedYear && (
          <ReferenceLine x={completedYear} stroke="#f5b301" strokeDasharray="4 2"
                         label={{ value: "Completed", fontSize: 10, position: "top" }} />
        )}
        <Line type="monotone" dataKey="Treated" stroke="#1f9d55" strokeWidth={2} dot={{ r: 3 }} />
        <Line type="monotone" dataKey="Control" stroke="#9ca3af" strokeWidth={2} strokeDasharray="5 3" dot={{ r: 3 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export default function DetailPanel({ detail, loading, error, pixel, pixelLoading, pixelError }) {
  const [beforeAfter, setBeforeAfter] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setBeforeAfter(null);
    if (!detail || !detail.completed_on) return;
    const completedYear = Number(detail.completed_on.slice(0, 4));
    const beforeYear = completedYear - 1;
    Promise.all([api.layer("ndvi", beforeYear), api.layer("ndvi", 2025)])
      .then(([before, after]) => {
        if (!cancelled) setBeforeAfter({ before, after, beforeYear, afterYear: 2025 });
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [detail]);

  if (loading) return <div className="panel detail-panel"><div className="loading-text">Loading...</div></div>;
  if (error) return <div className="panel detail-panel"><div className="error-text">{error}</div></div>;

  if (!detail) {
    return (
      <div className="panel detail-panel">
        <PixelInspector pixel={pixel} loading={pixelLoading} error={pixelError} />
      </div>
    );
  }

  const photo = detail.photo;
  const impact = detail.impact;

  return (
    <div className="panel detail-panel">
      <h2>{detail.name}</h2>
      <div className="type-tag">{TYPE_LABEL[detail.type] || detail.type} &middot; completed {detail.completed_on}</div>

      {photo && (
        <div className="photo-frame">
          <img src={api.photoFileUrl(photo.id)} alt={detail.name} />
        </div>
      )}

      <div className="section-label">AI Photo Interpretation</div>
      <AISection ai={photo?.ai} />

      <div className="section-label">Verification Verdict</div>
      <VerdictBadge verdict={photo?.verdict} />
      {photo?.verdict_reason && <div className="reason-text" style={{ marginTop: 8 }}>{photo.verdict_reason}</div>}

      <div className="section-label">Impact (Control-Area DiD)</div>
      <ImpactMetrics impact={impact} />
      <div className="metric-caption">
        Impact = (treated after − before) − (control after − before), using untreated pixels of the
        same land class and similar slope, &gt;500m from any intervention, as the control area.
      </div>

      <div className="section-label">Watershed Impact Index</div>
      <WiiGauge wii={impact?.wii} />

      <div className="section-label">NDVI Time Series (Treated vs Control)</div>
      <SeriesChart series={impact?.series} completedOn={detail.completed_on} />

      {beforeAfter && (
        <>
          <div className="section-label">Before / After (NDVI)</div>
          <BeforeAfterSlider
            beforeUrl={beforeAfter.before.url} afterUrl={beforeAfter.after.url}
            bounds={beforeAfter.before.bounds} lat={detail.lat} lon={detail.lon}
            beforeLabel={String(beforeAfter.beforeYear)} afterLabel={String(beforeAfter.afterYear)}
          />
        </>
      )}
    </div>
  );
}
