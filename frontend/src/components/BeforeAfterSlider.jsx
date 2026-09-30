import React, { useRef, useState } from "react";

/**
 * Shows two full-extent layer PNGs (different years) zoomed and panned so the
 * selected intervention's point is centered, with a draggable divider. This
 * reuses the same rendered layer PNGs the map uses (no extra backend work),
 * cropped/zoomed purely in CSS.
 */
export default function BeforeAfterSlider({ beforeUrl, afterUrl, bounds, lat, lon, beforeLabel, afterLabel }) {
  const [pos, setPos] = useState(50);
  const containerRef = useRef(null);
  const zoom = 6;

  const [south, west] = bounds[0];
  const [north, east] = bounds[1];
  const xFrac = (lon - west) / (east - west);
  const yFrac = (north - lat) / (north - south);

  const imgStyle = {
    position: "absolute",
    width: `${zoom * 100}%`,
    height: `${zoom * 100}%`,
    left: `${50 - xFrac * zoom * 100}%`,
    top: `${50 - yFrac * zoom * 100}%`,
    maxWidth: "none",
  };

  const handleDrag = (clientX) => {
    const rect = containerRef.current.getBoundingClientRect();
    const frac = ((clientX - rect.left) / rect.width) * 100;
    setPos(Math.min(100, Math.max(0, frac)));
  };

  const onMouseDown = (e) => {
    handleDrag(e.clientX);
    const move = (ev) => handleDrag(ev.clientX);
    const up = () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };

  return (
    <div className="before-after" ref={containerRef} onMouseDown={onMouseDown}>
      <img src={beforeUrl} style={imgStyle} alt="before" />
      <div style={{ position: "absolute", inset: 0, clipPath: `inset(0 0 0 ${pos}%)` }}>
        <img src={afterUrl} style={imgStyle} alt="after" />
      </div>
      <div className="slider-handle" style={{ left: `${pos}%` }} />
      <div className="before-after-label" style={{ left: 8 }}>{beforeLabel}</div>
      <div className="before-after-label" style={{ right: 8 }}>{afterLabel}</div>
    </div>
  );
}
