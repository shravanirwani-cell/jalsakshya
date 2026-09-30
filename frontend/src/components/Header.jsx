import React from "react";

export default function Header({ meta, onGenerateReport, onOpenRanking, onOpenUpload }) {
  const isDemo = meta?.source === "synthetic";
  return (
    <header className="app-header">
      <div className="brand">
        <h1>JalSakshya</h1>
        <span className="subtitle">Geospatial Watershed Evidence &amp; Impact Workbench</span>
        {isDemo && <span className="badge badge-demo">Demo Data</span>}
      </div>
      <div className="actions">
        <button className="btn" onClick={onOpenUpload}>Upload Photo</button>
        <button className="btn" onClick={onOpenRanking}>Needs Field Verification</button>
        <button className="btn btn-primary" onClick={onGenerateReport}>Generate Report</button>
      </div>
    </header>
  );
}
