import React from "react";

const TYPE_LABEL = {
  check_dam: "Check Dam", farm_pond: "Farm Pond", trench: "Trench", plantation: "Plantation",
};

export default function RankingModal({ rows, onClose, onSelect }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Needs Field Verification</h2>
          <button className="close-x" onClick={onClose}>&times;</button>
        </div>
        <p className="metric-caption" style={{ marginTop: -8, marginBottom: 12 }}>
          Sorted so mismatches come first, then inconclusive cases, then corroborated ones by lowest WII.
        </p>
        <table className="ranking-table">
          <thead>
            <tr>
              <th>Name</th><th>Type</th><th>Verdict</th><th>WII</th>
              <th>NDVI DiD</th><th>Water DiD</th><th>Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} onClick={() => { onSelect(r.id); onClose(); }}>
                <td>{r.name}</td>
                <td>{TYPE_LABEL[r.type] || r.type}</td>
                <td><span className={`dot dot-${r.verdict}`} />{r.verdict}</td>
                <td>{r.wii?.toFixed(0)}</td>
                <td>{r.ndvi_did?.toFixed(3) ?? "—"}</td>
                <td>{r.water_freq_did?.toFixed(3) ?? "—"}</td>
                <td>
                  {r.verdict === "mismatch" ? "Field visit recommended" :
                   r.verdict === "inconclusive" ? "Needs more evidence" : "No action needed"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
