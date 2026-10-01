import React from "react";

export default function Header({ meta, onGenerateReport, onOpenRanking, onOpenUpload }) {
  const isDemo = meta?.source === "synthetic";
  return (
    <header className="app-header">
      <div className="brand">
        <svg className="logo" viewBox="0 0 32 32" aria-hidden="true">
          <defs>
            <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#5cc8ff" /><stop offset="1" stopColor="#2dd4a0" />
            </linearGradient>
          </defs>
          <path d="M16 2C16 2 6 13 6 20a10 10 0 0 0 20 0C26 13 16 2 16 2z" fill="url(#lg)" />
          <path d="M11 21c2-2 4 2 6 0s3-2 4-1" stroke="#fff" strokeWidth="1.8" fill="none" strokeLinecap="round" />
        </svg>
        <div>
          <h1>JalSakshya</h1>
          <span className="subtitle">Geospatial Watershed Evidence &amp; Impact Workbench</span>
        </div>
        {isDemo && <span className="badge badge-demo">Demo Data</span>}
      </div>
      <div className="actions">
        <button className="btn" onClick={onOpenUpload}>📷 Upload Photo</button>
        <button className="btn" onClick={onOpenRanking}>⚑ Needs Field Verification</button>
        <button className="btn btn-primary" onClick={onGenerateReport}>⬇ Generate Report</button>
      </div>
    </header>
  );
}
