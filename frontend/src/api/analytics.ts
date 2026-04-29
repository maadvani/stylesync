const BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000"

export type AnalyticsOverview = {
  total_items: number
  wardrobe_utilization_pct: number
  most_worn_category: string | null
  color_palette_adherence_pct: number
  seasonal_coverage_pct: {
    spring: number
    summer: number
    fall: number
    winter: number
  }
  closet_gaps: string[]
  data_notes?: {
    utilization_source?: string
    most_worn_source?: string
    fallback_used?: boolean
  }
}

export async function getAnalyticsOverview(): Promise<AnalyticsOverview> {
  const r = await fetch(`${BASE}/api/analytics/overview`)
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.detail ?? "Failed to load analytics")
  return data as AnalyticsOverview
}

