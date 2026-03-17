import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'

const MOCK_TRENDS = [
  {
    name: 'Soft Tailored Neutrals',
    coverage: 72,
    description: 'Relaxed blazers, wide-leg trousers, and soft knits in camel, cream, and warm grey.',
  },
  {
    name: 'Cool Winter Pops',
    coverage: 38,
    description: 'Sharp black, white, and cobalt moments with high-contrast accents.',
  },
  {
    name: 'Everyday Quiet Luxury',
    coverage: 55,
    description: 'Elevated basics and minimal silhouettes styled with your existing neutrals.',
  },
]

function Trends() {
  const navigate = useNavigate()

  return (
    <AppShell
      title="Daily trend intelligence"
      subtitle="Once connected, StyleSync will scrape 50+ sources nightly, cluster trends with HDBSCAN, and filter everything through your personal color palette."
    >
      <div className="space-y-4 max-w-3xl">
        {MOCK_TRENDS.map((trend) => (
          <div
            key={trend.name}
            className="rounded-2xl border border-gray-100 bg-pink-50/60 px-5 py-4 flex items-start justify-between gap-4"
          >
            <div>
              <h2
                className="text-base font-semibold text-gray-900 mb-1"
                style={{ fontFamily: 'Georgia, serif' }}
              >
                {trend.name}
              </h2>
              <p className="text-xs text-gray-600 mb-2">{trend.description}</p>
              <p className="text-xs text-gray-500">
                Wardrobe coverage:{' '}
                <span className="font-semibold">{trend.coverage}%</span> (mock data)
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
          In the full build, these cards will be backed by your `trends` and
          `user_trend_matches` tables, plus embeddings stored in FAISS/MongoDB.
        </p>
      </div>
    </AppShell>
  )
}

export default Trends

