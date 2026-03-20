import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import { useEffect, useState } from 'react'
import { listTrends, type Trend } from '../api/trends'

function Trends() {
  const navigate = useNavigate()
  const [items, setItems] = useState<Trend[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listTrends(10)
      .then((res) => {
        if (!cancelled) setItems(res.items)
        if (!cancelled) setError(null)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load trends')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <AppShell
      title="Daily trend intelligence"
      subtitle="Once connected, StyleSync will scrape 50+ sources nightly, cluster trends with HDBSCAN, and filter everything through your personal color palette."
    >
      <div className="space-y-4 max-w-3xl">
        {loading && <p className="text-sm text-gray-500">Loading trends…</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}

        {!loading && !error && items.length === 0 && (
          <div className="rounded-2xl border border-gray-100 bg-pink-50/60 px-5 py-4">
            <p className="text-sm font-medium text-gray-900">No trends yet.</p>
            <p className="text-xs text-gray-500 mt-1">
              Run the local scraper: <span className="font-mono">cd backend && python run_trends_local.py</span>
            </p>
          </div>
        )}

        {items.map((trend) => (
          <div
            key={trend.id}
            className="rounded-2xl border border-gray-100 bg-pink-50/60 px-5 py-4 flex items-start justify-between gap-4"
          >
            <div>
              <h2
                className="text-base font-semibold text-gray-900 mb-1"
                style={{ fontFamily: 'Georgia, serif' }}
              >
                {trend.name || 'Trend'}
              </h2>
              <p className="text-xs text-gray-600 mb-2">{trend.description}</p>
              <p className="text-xs text-gray-500">
                Wardrobe coverage:{' '}
                <span className="font-semibold">
                  {trend.wardrobe_coverage == null ? '—' : `${Math.round(trend.wardrobe_coverage * 100)}%`}
                </span>
              </p>
            </div>
            <div className="flex flex-col items-end gap-2">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-pink-100 via-rose-100 to-fuchsia-100 flex items-center justify-center text-xs text-gray-500">
                Trend
              </div>
              <button
                onClick={() => navigate('/shopping')}
                className="text-[11px] text-pink-500 hover:underline"
              >
                Shop this trend
              </button>
            </div>
          </div>
        ))}

        <p className="mt-3 text-[11px] text-gray-400">
          MVP note: trends are clustered locally (HDBSCAN) and stored in Supabase. Match score + coverage are computed server-side.
        </p>
      </div>
    </AppShell>
  )
}

export default Trends

