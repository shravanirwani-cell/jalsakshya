import React from "react";

export default function PixelInspector({ pixel, loading, error }) {
  if (loading) return <div className="loading-text">Sampling pixel...</div>;
  if (error) return <div className="error-text">{error}</div>;
  if (!pixel) {
    return (
      <div className="empty-state">
        Click an intervention marker to see its evidence, or click anywhere else
        on the map to inspect the satellite index values at that point.
      </div>
    );
  }
  return (
    <div>
      <h2>Pixel Inspector</h2>
      <div className="type-tag">{pixel.lat.toFixed(5)}, {pixel.lon.toFixed(5)}</div>
      <table className="pixel-table">
        <thead>
          <tr><th>Year</th><th>NDVI</th><th>MNDWI</th><th>NDMI*</th></tr>
        </thead>
        <tbody>
          {pixel.series.map((row) => (
            <tr key={row.year}>
              <td>{row.year}</td>
              <td>{row.ndvi === null ? "—" : row.ndvi.toFixed(3)}</td>
              <td>{row.mndwi === null ? "—" : row.mndwi.toFixed(3)}</td>
              <td>{row.ndmi === null ? "—" : row.ndmi.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="metric-caption" style={{ marginTop: 8 }}>
        * NDMI is a moisture proxy, not measured soil moisture. Values describe the
        30m pixel and may not resolve small structures.
      </div>
    </div>
  );
}
