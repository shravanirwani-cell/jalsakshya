import React, { useState } from "react";
import { api } from "../api";

export default function UploadDialog({ onClose, onUploaded }) {
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const handleFile = async (file) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.uploadPhoto(file);
      onUploaded(result);
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box small" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Upload Geo-tagged Photo</h2>
          <button className="close-x" onClick={onClose}>&times;</button>
        </div>
        <div
          className={`dropzone${dragging ? " dragging" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            handleFile(e.dataTransfer.files?.[0]);
          }}
          onClick={() => document.getElementById("upload-file-input").click()}
        >
          {busy ? "Uploading and analysing..." : "Drag & drop a geo-tagged photo here, or click to choose a file"}
          <input
            id="upload-file-input" type="file" accept="image/*" hidden
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
        </div>
        {error && <div className="upload-error">{error}</div>}
        <p className="metric-caption" style={{ marginTop: 12 }}>
          The photo must have GPS coordinates in its EXIF data and be located inside the
          demo watershed boundary.
        </p>
      </div>
    </div>
  );
}
