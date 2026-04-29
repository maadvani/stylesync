import { useNavigate } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'
import AppShell from '../components/AppShell'
import { getAnalyticsOverview, type AnalyticsOverview } from '../api/analytics'

function Analytics() {
  const navigate = useNavigate()
  const [data, setData] = useState<AnalyticsOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getAnalyticsOverview()
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load analytics')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const seasonal = useMemo(
    () =>
      data?.seasonal_coverage_pct ?? {
        spring: 0,
        summer: 0,
        fall: 0,
        winter: 0,
      },
    [data],
  )

  const stat = (v: number | string | null, suffix = '') =>
    v == null || v === '' ? '—' : `${v}${suffix}`

  return (
    <AppShell
      title="Wardrobe analytics"
      subtitle="Powered by your wear-tracking data and trend coverage metrics—surfacing most/least worn pieces, seasonal gaps, and color balance."
    >
      {loading && (
        <div className="mb-4 rounded-xl border border-gray-100 bg-white px-4 py-3 text-sm text-gray-500">
          Loading analytics...
        </div>
      )}
      {error && (
        <div className="mb-4 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
          Could not load analytics: {error}
        </div>
      )}

      <div className="grid md:grid-cols-3 gap-4 mb-5">
        <div className="rounded-2xl bg-pink-50/70 px-4 py-3">
          <p className="text-xs text-gray-500 mb-1">Wardrobe utilization</p>
          <p className="text-2xl font-semibold text-gray-900">
            {stat(data?.wardrobe_utilization_pct ?? null, '%')}
          </p>
          <p className="text-[11px] text-gray-500 mt-1">
            {data?.data_notes?.utilization_source === 'times_worn'
              ? 'Percentage of pieces worn at least once from tracked wear counts.'
              : 'Estimated from current inventory mix (times_worn not yet available on all items).'}
          </p>
        </div>
        <div className="rounded-2xl bg-pink-50/70 px-4 py-3">
          <p className="text-xs text-gray-500 mb-1">Most-worn category</p>
          <p className="text-2xl font-semibold text-gray-900">
            {data?.most_worn_category ? data.most_worn_category : '—'}
          </p>
          <p className="text-[11px] text-gray-500 mt-1">
            {data?.data_notes?.most_worn_source === 'times_worn'
              ? 'Computed from total wear counts by category.'
              : 'Fallback from most common category in your current wardrobe.'}
          </p>
        </div>
        <div className="rounded-2xl bg-pink-50/70 px-4 py-3">
          <p className="text-xs text-gray-500 mb-1">Color palette adherence</p>
          <p className="text-2xl font-semibold text-gray-900">
            {stat(data?.color_palette_adherence_pct ?? null, '%')}
          </p>
          <p className="text-[11px] text-gray-500 mt-1">
            Average harmony between your wardrobe colors and your saved color season.
          </p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="rounded-2xl border border-gray-100 px-4 py-4">
          <p className="text-xs font-medium text-gray-700 mb-2">
            Seasonal coverage
          </p>
          <div className="space-y-2 text-xs text-gray-700">
            <div className="flex items-center justify-between">
              <span>Spring</span>
              <div className="flex-1 mx-3 h-1.5 rounded-full bg-pink-100 overflow-hidden">
                <div className="h-full bg-pink-400" style={{ width: `${seasonal.spring}%` }} />
              </div>
              <span>{Math.round(seasonal.spring)}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Summer</span>
              <div className="flex-1 mx-3 h-1.5 rounded-full bg-pink-100 overflow-hidden">
                <div className="h-full bg-pink-400" style={{ width: `${seasonal.summer}%` }} />
              </div>
              <span>{Math.round(seasonal.summer)}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Fall</span>
              <div className="flex-1 mx-3 h-1.5 rounded-full bg-pink-100 overflow-hidden">
                <div className="h-full bg-pink-400" style={{ width: `${seasonal.fall}%` }} />
              </div>
              <span>{Math.round(seasonal.fall)}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Winter</span>
              <div className="flex-1 mx-3 h-1.5 rounded-full bg-pink-100 overflow-hidden">
                <div className="h-full bg-pink-400" style={{ width: `${seasonal.winter}%` }} />
              </div>
              <span>{Math.round(seasonal.winter)}%</span>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-gray-100 px-4 py-4">
          <p className="text-xs font-medium text-gray-700 mb-2">
            Closet gaps
          </p>
          <ul className="text-xs text-gray-700 space-y-1.5">
            {(data?.closet_gaps ?? []).map((gap) => (
              <li key={gap}>• {gap}</li>
            ))}
          </ul>
          <p className="text-[11px] text-gray-500 mt-3">
            Based on your current wardrobe inventory and available wear-tracking fields.
          </p>
        </div>
      </div>

      <button
        onClick={() => navigate('/shopping')}
        className="mt-5 inline-flex items-center justify-center px-4 py-2 rounded-full text-sm font-semibold text-pink-600 bg-pink-50 hover:bg-pink-100 transition"
      >
        See shopping recommendations based on these gaps ↗
      </button>
    </AppShell>
  )
}

export default Analytics

