import AppShell from '../components/AppShell'
import { useState } from 'react'
import { generateOutfits, type CandidateItem, type OutfitCard } from '../api/outfits'

function Outfits() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [outfits, setOutfits] = useState<OutfitCard[] | null>(null)
  const [debug, setDebug] = useState<{
    fallback_used?: boolean
    compatible_items_count?: number
    filtered_count?: number
    candidate_type?: string
    compatible_expected_types?: string[]
  } | null>(null)

  const [occasion, setOccasion] = useState('client meeting')
  const [weatherTemp, setWeatherTemp] = useState<number | ''>('')
  const [weatherConditions, setWeatherConditions] = useState('partly cloudy')
  const [vibe, setVibe] = useState('modern')
  const [engine, setEngine] = useState<'react' | 'rules'>('react')

  // Hypothetical purchase (candidate)
  const [candidateType, setCandidateType] = useState('top')
  const [candidatePrimaryColor, setCandidatePrimaryColor] = useState('navy')
  const [candidatePattern, setCandidatePattern] = useState('solid')
  const [candidateFormality, setCandidateFormality] = useState(3)
  const [candidateSeasons, setCandidateSeasons] = useState('spring, summer')
  const [candidatePrice, setCandidatePrice] = useState('')

  return (
    <AppShell
      title="Daily outfit generation"
      subtitle="MVP: test a hypothetical purchase against your wardrobe. We generate 4 outfit matches using compatibility + your saved color season."
    >
      <div className="grid xl:grid-cols-[420px,1fr] gap-6 mb-2">
        <div className="space-y-4">
          <div className="rounded-2xl border border-gray-100 bg-white p-5">
            <p className="text-xs font-medium text-gray-700 mb-3">Occasion + weather</p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Occasion</label>
                <input
                  type="text"
                  value={occasion}
                  onChange={(e) => setOccasion(e.target.value)}
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-pink-400"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Weather temp</label>
                  <input
                    type="number"
                    value={weatherTemp}
                    onChange={(e) => setWeatherTemp(e.target.value === '' ? '' : Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-pink-400"
                    placeholder="e.g. 68"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Vibe</label>
                  <input
                    type="text"
                    value={vibe}
                    onChange={(e) => setVibe(e.target.value)}
                    className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-pink-400"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Conditions</label>
                <input
                  type="text"
                  value={weatherConditions}
                  onChange={(e) => setWeatherConditions(e.target.value)}
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-pink-400"
                />
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-gray-100 bg-pink-50/50 p-5">
            <p className="text-xs font-medium text-gray-700 mb-3">Hypothetical purchase</p>

            <div className="grid sm:grid-cols-2 gap-3">
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">Type</label>
                <input
                  value={candidateType}
                  onChange={(e) => setCandidateType(e.target.value)}
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-pink-400"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Primary color</label>
                <input
                  value={candidatePrimaryColor}
                  onChange={(e) => setCandidatePrimaryColor(e.target.value)}
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-pink-400"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Pattern</label>
                <input
                  value={candidatePattern}
                  onChange={(e) => setCandidatePattern(e.target.value)}
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-pink-400"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Formality (1–5)</label>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={candidateFormality}
                  onChange={(e) => setCandidateFormality(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-pink-400"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Price (optional)</label>
                <input
                  value={candidatePrice}
                  onChange={(e) => setCandidatePrice(e.target.value)}
                  placeholder="e.g. 120"
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-pink-400"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">Seasons</label>
                <input
                  value={candidateSeasons}
                  onChange={(e) => setCandidateSeasons(e.target.value)}
                  placeholder="spring, summer, fall, winter"
                  className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-pink-400"
                />
              </div>
            </div>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}
          {debug?.fallback_used && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-2xl px-4 py-2">
              Note: no type-compatible wardrobe matches were found, so results were broadened to fill all cards.
              Candidate type: <span className="font-semibold">{debug.candidate_type ?? '—'}</span>.
            </p>
          )}
          {!!debug && (
            <p className="text-[11px] text-gray-500">
              Engine: <span className="font-semibold">{String((debug as Record<string, unknown>).engine ?? 'rules')}</span>
            </p>
          )}

          <button
            type="button"
            disabled={loading}
            onClick={async () => {
              setLoading(true)
              setError(null)
              setOutfits(null)
              setDebug(null)
              try {
                const seasonsList = candidateSeasons
                  .split(',')
                  .map((s) => s.trim())
                  .filter(Boolean)
                const candidate: CandidateItem = {
                  type: candidateType.trim() || 'other',
                  primary_color: candidatePrimaryColor.trim() || null,
                  pattern: candidatePattern.trim() || null,
                  formality: candidateFormality,
                  seasons: seasonsList.length ? seasonsList : null,
                  price: candidatePrice.trim() ? Number(candidatePrice) : null,
                }
                const body = {
                  occasion,
                  vibe,
                  weather_temp: typeof weatherTemp === 'number' ? weatherTemp : null,
                  weather_conditions: weatherConditions,
                  engine,
                  candidate,
                }
                const res = await generateOutfits(body)
                setOutfits(res.outfits)
                setDebug(res.debug ?? null)
              } catch (e) {
                setError(e instanceof Error ? e.message : 'Outfit generation failed')
              } finally {
                setLoading(false)
              }
            }}
            className="w-full px-4 py-2 rounded-full text-sm font-semibold text-white shadow-sm hover:opacity-90 transition disabled:opacity-70"
            style={{ background: 'linear-gradient(135deg, #f43f7f, #ec4899)' }}
          >
            {loading ? 'Generating…' : 'Generate 4 outfits'}
          </button>
          <div className="flex items-center gap-2 text-xs text-gray-600 mt-2">
            <span>Engine</span>
            <button
              type="button"
              onClick={() => setEngine('react')}
              className={`px-3 py-1 rounded-full border ${engine === 'react' ? 'bg-pink-50 border-pink-300 text-pink-700' : 'bg-white border-gray-200'}`}
            >
              ReAct
            </button>
            <button
              type="button"
              onClick={() => setEngine('rules')}
              className={`px-3 py-1 rounded-full border ${engine === 'rules' ? 'bg-pink-50 border-pink-300 text-pink-700' : 'bg-white border-gray-200'}`}
            >
              Rules
            </button>
          </div>
        </div>

        <div className="space-y-4">
          {!outfits && (
            <div className="rounded-2xl border border-gray-100 bg-pink-50/60 px-5 py-4">
              <p className="text-sm font-medium text-gray-900">No results yet</p>
              <p className="text-xs text-gray-500 mt-1">
                Add your hypothetical purchase + click “Generate 4 outfits”.
              </p>
            </div>
          )}

          {outfits?.map((o, idx) => (
            <div key={idx} className="rounded-2xl border border-gray-100 bg-white px-5 py-4">
              <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                  <p className="text-xs font-semibold text-gray-900">Outfit {idx + 1}</p>
                  <p className="text-[11px] text-gray-500 mt-1">
                    Purchase: <span className="font-semibold">{candidateType}</span> ·{' '}
                    <span className="font-semibold">{candidatePrimaryColor || '—'}</span>
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-gray-600">Overall score</p>
                  <p className="text-2xl font-bold text-gray-900">{o.overall_score}</p>
                </div>
              </div>

              <div className="grid md:grid-cols-[140px,1fr] gap-4 items-start">
                <div className="rounded-2xl overflow-hidden bg-gray-100 border border-gray-200">
                  {o.matched_item?.image_url ? (
                    <img src={o.matched_item.image_url} alt="Matched wardrobe item" className="w-full h-full object-cover aspect-[3/4]" />
                  ) : (
                    <div className="w-full h-full aspect-[3/4] flex items-center justify-center text-xs text-gray-400">No image</div>
                  )}
                </div>
                <div>
                  <p className="text-xs font-semibold text-gray-900">Outfit items</p>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {(o.item_details?.length ? o.item_details : [o.matched_item]).map((it, i2) => (
                      <span key={`${i2}-${it?.id ?? 'x'}`} className="px-2 py-1 rounded-full text-[11px] bg-gray-100 text-gray-700">
                        {it?.type || 'Item'}{it?.primary_color ? ` · ${it.primary_color}` : ''}
                      </span>
                    ))}
                  </div>
                  <p className="text-[11px] text-gray-600 mt-1">{o.reasoning}</p>
                  <div className="mt-3 grid sm:grid-cols-5 gap-3">
                    <div>
                      <p className="text-[11px] text-gray-500">Color match</p>
                      <p className="text-xs font-semibold text-gray-900">{o.scores.color_match}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-gray-500">Season</p>
                      <p className="text-xs font-semibold text-gray-900">{o.scores.seasonal_versatility}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-gray-500">Coherence</p>
                      <p className="text-xs font-semibold text-gray-900">{o.scores.style_coherence}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-gray-500">Weather fit</p>
                      <p className="text-xs font-semibold text-gray-900">{o.scores.weather_fit ?? '—'}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-gray-500">Trend relevance</p>
                      <p className="text-xs font-semibold text-gray-900">{o.scores.trend_relevance ?? '—'}</p>
                    </div>
                  </div>
                  {!!o.scores.judge && (
                    <div className="mt-3 rounded-xl border border-gray-200 bg-gray-50 p-2 text-[11px] text-gray-700">
                      <p className="font-semibold text-gray-900">LLM judge</p>
                      <p>Overall: {o.scores.judge.overall_score ?? '—'}/10</p>
                      <p>Occasion: {o.scores.judge.occasion_appropriateness?.score ?? '—'}/10</p>
                      <p>Practicality: {o.scores.judge.practicality?.score ?? '—'}/10</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  )
}

export default Outfits

