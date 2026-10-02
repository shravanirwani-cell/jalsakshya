import React, { useEffect, useState } from "react";

const REFRESH_MS = 10 * 60 * 1000;

// WMO weather codes -> [icon, label]
function describe(code) {
  if (code === 0) return ["☀️", "Clear"];
  if (code <= 3) return ["⛅", "Partly cloudy"];
  if (code <= 48) return ["🌫️", "Fog"];
  if (code <= 57) return ["🌦️", "Drizzle"];
  if (code <= 67) return ["🌧️", "Rain"];
  if (code <= 77) return ["❄️", "Snow"];
  if (code <= 82) return ["🌧️", "Showers"];
  return ["⛈️", "Thunderstorm"];
}

// Live conditions at the watershed centre from Open-Meteo (free, no API key).
export default function LiveWeather({ lat, lon }) {
  const [wx, setWx] = useState(null);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const tick = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetch(
        `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
        "&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code",
      )
        .then((r) => r.json())
        .then((d) => { if (!cancelled && d.current) setWx(d.current); })
        .catch(() => {});
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [lat, lon]);

  const [icon, label] = wx ? describe(wx.weather_code) : ["…", "Loading"];
  return (
    <div className="weather-card glass">
      <div className="wx-head"><span className="live-dot" /> LIVE · {now.toLocaleTimeString()}</div>
      <div className="wx-main">
        <span className="wx-icon">{icon}</span>
        <span className="wx-temp">{wx ? `${Math.round(wx.temperature_2m)}°C` : "--"}</span>
        <span className="wx-label">{label}</span>
      </div>
      {wx && (
        <div className="wx-grid">
          <span>💧 {wx.relative_humidity_2m}%</span>
          <span>🌧 {wx.precipitation} mm</span>
          <span>💨 {Math.round(wx.wind_speed_10m)} km/h</span>
        </div>
      )}
    </div>
  );
}
