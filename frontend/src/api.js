const BASE = import.meta.env.VITE_API_URL || "/api";

async function getJSON(path) {
  const res = await fetch(BASE + path);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${path}`);
  }
  return res.json();
}

export const api = {
  meta: () => getJSON("/meta"),
  watershed: () => getJSON("/watershed"),
  streams: () => getJSON("/streams"),
 layer: async (name, year) => {
  const data = await getJSON(`/layers/${name}/${year}`);

  const backendOrigin = BASE.replace(/\/api\/?$/, "");

  return {
    ...data,
    url: data.url.startsWith("http")
      ? data.url
      : backendOrigin + data.url,
  };
},
  interventions: () => getJSON("/interventions"),
  intervention: (id) => getJSON(`/interventions/${id}`),
  ranking: () => getJSON("/ranking"),
  pixel: (lat, lon) => getJSON(`/pixel?lat=${lat}&lon=${lon}`),
  photoFileUrl: (id) => `${BASE}/photos/${id}/file`,
  reportWatershedUrl: () => `${BASE}/report/watershed.pdf`,
  reportInterventionUrl: (id) => `${BASE}/report/${id}.pdf`,

  async uploadPhoto(file, interventionId) {
    const form = new FormData();
    form.append("file", file);
    if (interventionId) form.append("intervention_id", interventionId);
    const res = await fetch(BASE + "/photos", { method: "POST", body: form });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || "Upload failed");
    return body;
  },
};
