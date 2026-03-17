/**
 * Wardrobe API client. Set VITE_API_URL in .env (e.g. http://127.0.0.1:8000) or leave unset for default.
 */
export const API_BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";
const BASE = API_BASE;

export type WardrobeItem = {
  id: string;
  user_id: string;
  image_url: string;
  type: string;
  primary_color: string | null;
  secondary_color: string | null;
  pattern: string | null;
  formality: number;
  seasons: string[] | null;
  material: string | null;
  style_tags: string[] | null;
  created_at?: string;
};

export async function listWardrobe(): Promise<{ items: WardrobeItem[] }> {
  const r = await fetch(`${BASE}/api/wardrobe`);
  if (!r.ok) throw new Error("Failed to load wardrobe");
  return r.json();
}

export async function uploadWardrobeItem(file: File): Promise<WardrobeItem> {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch(`${BASE}/api/wardrobe/upload`, {
    method: "POST",
    body: form,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ?? "Upload failed");
  return data as WardrobeItem;
}

export type WardrobeUpdate = Partial<
  Pick<
    WardrobeItem,
    | "type"
    | "primary_color"
    | "secondary_color"
    | "pattern"
    | "formality"
    | "seasons"
    | "material"
    | "style_tags"
  >
>;

export async function updateWardrobeItem(id: string, update: WardrobeUpdate): Promise<WardrobeItem> {
  const r = await fetch(`${BASE}/api/wardrobe/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ?? "Update failed");
  return data as WardrobeItem;
}

export async function deleteWardrobeItem(id: string): Promise<void> {
  const r = await fetch(`${BASE}/api/wardrobe/${id}`, { method: "DELETE" });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ?? "Delete failed");
}

export async function retagWardrobeItem(
  id: string,
  engine?: "default" | "gemini",
  targets?: string[],
): Promise<WardrobeItem> {
  const params = new URLSearchParams();
  if (engine === "gemini") params.set("engine", "gemini");
  if (targets && targets.length > 0) params.set("targets", targets.join(","));
  const qs = params.toString() ? `?${params.toString()}` : "";
  const r = await fetch(`${BASE}/api/wardrobe/${id}/retag${qs}`, { method: "POST" });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ?? "Retag failed");
  // New backend response: { items: WardrobeItem[] }
  if (data && Array.isArray(data.items)) {
    // For convenience, return the first (updated) item.
    return data.items[0] as WardrobeItem;
  }
  return data as WardrobeItem;
}
