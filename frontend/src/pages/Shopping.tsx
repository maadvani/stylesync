import { useNavigate } from 'react-router-dom'
import { useMemo, useState } from 'react'
import AppShell from '../components/AppShell'
import { scoreUtility, type UtilityScore } from '../api/utility'

const MOCK_ITEMS = [
  {
    name: 'Camel wool blazer',
    type: 'Blazer',
    price: '$180',
    score: 92,
    costPerWear: '$3.20',
  },
  {
    name: 'Satin hot-pink mini dress',
    type: 'Dress',
    price: '$140',
    score: 48,
    costPerWear: '$11.60',
  },
  {
    name: 'Cream wide-leg trousers',
    type: 'Pants',
    price: '$110',
    score: 85,
    costPerWear: '$3.90',
  },
]

function Shopping() {
  const navigate = useNavigate()
  const [typeValue, setTypeValue] = useState('dress')
  const [primaryColor, setPrimaryColor] = useState('ivory')
  const [pattern, setPattern] = useState('solid')
  const [formality, setFormality] = useState(3)
  const [seasons, setSeasons] = useState('spring, summer')
  const [price, setPrice] = useState('120')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<UtilityScore | null>(null)
  const [error, setError] = useState<string | null>(null)

  const candidate = useMemo(() => {
    const seasonList = seasons
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    const priceNum = Number(price)
    return {
      type: typeValue.trim() || 'other',
      primary_color: primaryColor.trim() || null,
      pattern: pattern.trim() || null,
      formality: Number.isFinite(formality) ? formality : 3,
      seasons: seasonList.length ? seasonList : null,
      price: Number.isFinite(priceNum) ? priceNum : null,
    }
  }, [typeValue, primaryColor, pattern, formality, seasons, price])

  return (
    <AppShell
      title="Shopping intelligence"
      subtitle="Plug new pieces into your utility scoring algorithm—see outfit potential, seasonal versatility, color match, and cost-per-wear before buying."
    >
      <div className="space-y-6 max-w-5xl">
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="rounded-2xl border border-gray-100 bg-white p-5">
            <p className="text-xs font-medium text-gray-700 mb-3">Test a purchase (MVP)</p>
            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Type</label>
                <input
                  value={typeValue}
                  onChange={(e) => setTypeValue(e.target.value)}
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                  placeholder="dress, blazer, pants…"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Formality (1–5)</label>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={formality}
                  onChange={(e) => setFormality(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Primary color</label>
                <input
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                  placeholder="ivory, navy…"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Pattern</label>
                <input
                  value={pattern}
                  onChange={(e) => setPattern(e.target.value)}
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                  placeholder="solid, floral…"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Seasons (comma-separated)</label>
                <input
                  value={seasons}
                  onChange={(e) => setSeasons(e.target.value)}
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                  placeholder="spring, summer, fall, winter"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Price (USD)</label>
                <input
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                  placeholder="120"
                />
              </div>
            </div>

            <div className="mt-4 flex items-center gap-3">
              <button
                type="button"
                disabled={loading}
                onClick={async () => {
                  setLoading(true)
                  setError(null)
                  try {
                    const r = await scoreUtility(candidate)
                    setResult(r)
                  } catch (e) {
                    setError(e instanceof Error ? e.message : 'Scoring failed')
                    setResult(null)
                  } finally {
                    setLoading(false)
                  }
                }}
                className="px-5 py-2 rounded-full text-sm font-semibold text-white shadow-sm hover:opacity-90 transition disabled:opacity-70"
                style={{ background: 'linear-gradient(135deg, #f43f7f, #ec4899)' }}
              >
                {loading ? 'Scoring…' : 'Calculate utility score'}
              </button>
              {error && <p className="text-sm text-red-600">{error}</p>}
            </div>
          </div>

          <div className="rounded-2xl border border-gray-100 bg-pink-50/50 p-5">
            <p className="text-xs font-medium text-gray-700 mb-3">Utility score breakdown</p>
            {!result ? (
              <p className="text-sm text-gray-500">
                Enter an item and click “Calculate utility score”.
              </p>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Overall score</p>
                    <p className="text-3xl font-bold text-gray-900">{result.score}</p>
                    <p className="text-xs text-gray-500">
                      Color season: <span className="font-semibold">{result.color_season ?? '—'}</span>
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-600">Cost per wear</p>
                    <p className="text-2xl font-semibold text-gray-900">
                      {result.cost_per_wear == null ? '—' : `$${result.cost_per_wear}`}
                    </p>
                    <p className="text-xs text-gray-500">
                      From {result.outfit_potential} predicted outfits
                    </p>
                  </div>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-700">Outfit potential</span>
                    <span className="font-semibold">{result.outfit_potential}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-700">Seasonal versatility</span>
                    <span className="font-semibold">{result.seasonal_versatility}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-700">Color match</span>
                    <span className="font-semibold">{result.color_match}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-700">Trend alignment</span>
                    <span className="font-semibold">{result.trend_alignment}</span>
                  </div>
                </div>

                <p className="text-[11px] text-gray-500">
                  MVP note: trend alignment and gap filling are placeholders for now; outfit potential and color match are real.
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-gray-100 overflow-hidden">
          <div className="bg-pink-50/70 px-4 py-2 text-xs font-medium text-gray-600 grid grid-cols-5 gap-2">
            <span className="col-span-2">Item</span>
            <span className="text-center">Price</span>
            <span className="text-center">Utility score</span>
            <span className="text-center">Cost per wear</span>
          </div>
          <div className="divide-y divide-gray-100">
            {MOCK_ITEMS.map((item) => (
              <div
                key={item.name}
                className="px-4 py-3 text-xs text-gray-700 grid grid-cols-5 gap-2 items-center"
              >
                <div className="col-span-2">
                  <p className="font-semibold">{item.name}</p>
                  <p className="text-gray-500 mt-0.5">{item.type}</p>
                </div>
                <p className="text-center">{item.price}</p>
                <p className="text-center">
                  <span
                    className={`inline-flex items-center justify-center px-2 py-1 rounded-full text-[11px] font-semibold ${
                      item.score >= 80
                        ? 'bg-emerald-50 text-emerald-700'
                        : item.score >= 60
                          ? 'bg-amber-50 text-amber-700'
                          : 'bg-red-50 text-red-600'
                    }`}
                  >
                    {item.score}/100
                  </span>
                </p>
                <p className="text-center text-gray-700">{item.costPerWear}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="text-[11px] text-gray-400">
          Later, these rows will be generated from the `shopping_recommendations` table
          and your `UtilityScorer` service, with detail views that mirror your mock
          utility breakdown screen.
        </p>

        <button
          onClick={() => navigate('/outfits')}
          className="inline-flex items-center justify-center px-4 py-2 rounded-full text-sm font-semibold text-pink-600 bg-pink-50 hover:bg-pink-100 transition"
        >
          See how these pieces style into outfits ↗
        </button>
      </div>
    </AppShell>
  )
}

export default Shopping

