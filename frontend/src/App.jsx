import React, { useEffect, useState } from "react";
import { api } from "./api";
import Header from "./components/Header";
import LayerPanel from "./components/LayerPanel";
import MapView from "./components/MapView";
import DetailPanel from "./components/DetailPanel";
import RankingModal from "./components/RankingModal";
import UploadDialog from "./components/UploadDialog";

export default function App() {
  const [meta, setMeta] = useState(null);
  const [watershedGeojson, setWatershedGeojson] = useState(null);
  const [streamsGeojson, setStreamsGeojson] = useState(null);
  const [interventionsGeojson, setInterventionsGeojson] = useState(null);
  const [initError, setInitError] = useState(null);

  const [activeLayer, setActiveLayer] = useState("ndvi");
  const [activeYear, setActiveYear] = useState(null);
  const [layerInfo, setLayerInfo] = useState(null);

  const [showWatershed, setShowWatershed] = useState(true);
  const [showStreams, setShowStreams] = useState(true);
  const [showInterventions, setShowInterventions] = useState(true);

  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);

  const [pixel, setPixel] = useState(null);
  const [pixelLoading, setPixelLoading] = useState(false);
  const [pixelError, setPixelError] = useState(null);

  const [flyTarget, setFlyTarget] = useState(null);
  const [rankingOpen, setRankingOpen] = useState(false);
  const [rankingRows, setRankingRows] = useState([]);
  const [uploadOpen, setUploadOpen] = useState(false);

  // initial load
  useEffect(() => {
    Promise.all([api.meta(), api.watershed(), api.streams(), api.interventions()])
      .then(([m, w, s, iv]) => {
        setMeta(m);
        setWatershedGeojson(w);
        setStreamsGeojson(s);
        setInterventionsGeojson(iv);
        setActiveYear(m.years[m.years.length - 1]);
      })
      .catch((e) => setInitError(e.message));
  }, []);

  // layer image whenever layer/year changes
  useEffect(() => {
    if (!meta || activeYear === null) return;
    api.layer(activeLayer, activeYear).then(setLayerInfo).catch(() => setLayerInfo(null));
  }, [meta, activeLayer, activeYear]);

  const selectIntervention = (id) => {
    setSelectedId(id);
    setPixel(null);
    setPixelError(null);
    setDetailLoading(true);
    setDetailError(null);
    api.intervention(id)
      .then((d) => {
        setDetail(d);
        setFlyTarget({ lat: d.lat, lon: d.lon });
      })
      .catch((e) => setDetailError(e.message))
      .finally(() => setDetailLoading(false));
  };

  const handleMapClick = (lat, lon) => {
    setSelectedId(null);
    setDetail(null);
    setDetailError(null);
    setPixelLoading(true);
    setPixelError(null);
    api.pixel(lat, lon)
      .then(setPixel)
      .catch((e) => setPixelError(e.message))
      .finally(() => setPixelLoading(false));
  };

  const handleUploaded = (result) => {
    setSelectedId(result.intervention ? result.intervention.id : null);
    setPixel(null);
    setDetail({
      name: result.intervention ? result.intervention.name : "Uploaded photo",
      type: result.intervention ? result.intervention.type : "other",
      completed_on: result.intervention ? result.intervention.completed_on : null,
      lat: result.lat,
      lon: result.lon,
      photo: { id: result.id, ai: result.ai, verdict: result.verdict, verdict_reason: result.verdict_reason },
      impact: result.impact,
    });
    setFlyTarget({ lat: result.lat, lon: result.lon });
  };

  const openRanking = () => {
    api.ranking().then((rows) => {
      setRankingRows(rows);
      setRankingOpen(true);
    });
  };

  const generateReport = () => {
    const url = selectedId ? api.reportInterventionUrl(selectedId) : api.reportWatershedUrl();
    window.open(url, "_blank");
  };

  if (initError) {
    return (
      <div className="error-text" style={{ padding: 40 }} role="alert">
        Failed to load JalSakshya: {initError}. Is the backend running (uvicorn app.main:app)
        and has prepare_data.py / seed_db.py been run?
      </div>
    );
  }

  return (
    <div className="app-shell">
      <Header
        meta={meta}
        onGenerateReport={generateReport}
        onOpenRanking={openRanking}
        onOpenUpload={() => setUploadOpen(true)}
      />
      <div className="app-body">
        <LayerPanel
          years={meta?.years || []}
          activeLayer={activeLayer} setActiveLayer={setActiveLayer}
          activeYear={activeYear} setActiveYear={setActiveYear}
          showWatershed={showWatershed} setShowWatershed={setShowWatershed}
          showStreams={showStreams} setShowStreams={setShowStreams}
          showInterventions={showInterventions} setShowInterventions={setShowInterventions}
          interventionsGeojson={interventionsGeojson}
        />
        <MapView
          meta={meta}
          layerInfo={layerInfo}
          watershedGeojson={watershedGeojson}
          streamsGeojson={streamsGeojson}
          interventionsGeojson={interventionsGeojson}
          showWatershed={showWatershed}
          showStreams={showStreams}
          showInterventions={showInterventions}
          selectedId={selectedId}
          onSelectIntervention={selectIntervention}
          onMapClick={handleMapClick}
          flyTarget={flyTarget}
        />
        <DetailPanel
          detail={detail} loading={detailLoading} error={detailError}
          pixel={pixel} pixelLoading={pixelLoading} pixelError={pixelError}
        />
      </div>

      {rankingOpen && (
        <RankingModal
          rows={rankingRows}
          onClose={() => setRankingOpen(false)}
          onSelect={selectIntervention}
        />
      )}
      {uploadOpen && (
        <UploadDialog onClose={() => setUploadOpen(false)} onUploaded={handleUploaded} />
      )}
    </div>
  );
}
