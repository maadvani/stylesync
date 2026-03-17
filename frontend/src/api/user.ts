const BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export async function getColorSeason(): Promise<{ color_season: string | null }> {
  const r = await fetch(`${BASE}/api/user/color-season`);
  if (!r.ok) throw new Error("Failed to load color season");
  return r.json();
}

export async function setColorSeason(colorSeason: string): Promise<{ ok: boolean }> {
  const r = await fetch(`${BASE}/api/user/color-season`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ color_season: colorSeason }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ?? "Failed to save");
  return data;
}
