import { useNavigate } from 'react-router-dom'
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import AppShell from '../components/AppShell'
import {
  createShoppingRecommendation,
  deleteShoppingRecommendation,
  fetchShoppingRecommendations,
  type ScoredShoppingRow,
  type ShoppingRecommendationsResponse,
} from '../api/shopping'
import {
  API_BASE_URL,
  scoreUtilityEnhanced,
  scoreUtilityEnhancedFromImage,
  type CandidateItem,
  type EnhancedUtilityResponse,
} from '../api/utility'

/** Bumped when Shopping UI changes — if your screen does not match, you are on a stale bundle. */
const SHOPPING_UI_REV = '2026-03-29f'

/** Backend sends 0–1 for these; show as % so "1" is not read as "one season". */
function pct01(n: number | undefined | null): string {
  if (n == null || Number.isNaN(n)) return '—'
  const x = Math.max(0, Math.min(1, n))
  return `${Math.round(x * 100)}%`
}

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

function titleCase(s: string): string {
  const t = s.trim()
  if (!t) return s
  return t.charAt(0).toUpperCase() + t.slice(1).toLowerCase()
}

type TableRow =
  | {
      key: string
      demo: true
      name: string
      type: string
      priceLabel: string
      score: number
      cpwLabel: string
      link?: string | null
    }
  | {
      key: string
      demo: false
      id: string
      name: string
      type: string
      priceLabel: string
      score: number
      cpwLabel: string
      link?: string | null
    }

function Shopping() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'manual' | 'photo'>('manual')
  const [typeValue, setTypeValue] = useState('dress')
  const [primaryColor, setPrimaryColor] = useState('ivory')
  const [pattern, setPattern] = useState('solid')
  const [formality, setFormality] = useState(3)
  const [seasons, setSeasons] = useState('spring, summer')
  const [price, setPrice] = useState('120')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<EnhancedUtilityResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(null)
  const [geminiReady, setGeminiReady] = useState<boolean | null>(null)

  const [recPack, setRecPack] = useState<ShoppingRecommendationsResponse | null>(null)
  const [recLoading, setRecLoading] = useState(true)
  const [recErr, setRecErr] = useState<string | null>(null)
  const [listBusy, setListBusy] = useState(false)
  const [addName, setAddName] = useState('')
  const [addType, setAddType] = useState('dress')
  const [addPrice, setAddPrice] = useState('')
  const [addLink, setAddLink] = useState('')
  const [addColor, setAddColor] = useState('')
  const [addPattern, setAddPattern] = useState('solid')
  const [saveNameOverride, setSaveNameOverride] = useState('')
  const [saveLinkOverride, setSaveLinkOverride] = useState('')

  const reloadRecs = useCallback(() => {
    setRecLoading(true)
    setRecErr(null)
    fetchShoppingRecommendations()
      .then(setRecPack)
      .catch((e) => {
        setRecErr(e instanceof Error ? e.message : 'Failed to load shopping list')
        setRecPack({ configured: false, user_id: '', items: [] })
      })
      .finally(() => setRecLoading(false))
  }, [])

  useEffect(() => {
    reloadRecs()
  }, [reloadRecs])

  const tableRows: TableRow[] = useMemo(() => {
    if (!recPack) return []
    if (!recPack.configured) {
      return MOCK_ITEMS.map((m) => ({
        key: `demo-${m.name}`,
        demo: true as const,
        name: m.name,
        type: m.type,
        priceLabel: m.price,
        score: m.score,
        cpwLabel: m.costPerWear,
        link: null,
      }))
    }
    return recPack.items.map((row: ScoredShoppingRow) => ({
      key: row.id,
      demo: false as const,
      id: row.id,
      name: row.name,
      type: titleCase(row.type),
      priceLabel: row.price == null ? '—' : `$${row.price}`,
      score: Math.round(row.adjusted_score),
      cpwLabel: row.cost_per_wear == null ? '—' : `$${Number(row.cost_per_wear).toFixed(2)}`,
      link: row.link ?? null,
    }))
  }, [recPack])

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/utility/ai-config`)
      .then((res) => res.json())
      .then((d: { gemini_configured?: boolean }) => setGeminiReady(!!d.gemini_configured))
      .catch(() => setGeminiReady(null))
  }, [])

  useEffect(() => {
    if (!photoFile) {
      setPhotoPreviewUrl(null)
      return
    }
    const url = URL.createObjectURL(photoFile)
    setPhotoPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [photoFile])

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

  const saveScoredItemToList = async () => {
    if (!result || !recPack?.configured) return
    const manualCandidate: CandidateItem = {
      ...candidate,
      secondary_color: null,
      material: null,
      style_tags: null,
    }
    const src = result.scored_item ?? manualCandidate
    setListBusy(true)
    setRecErr(null)
    try {
      const priceFromForm = Number(price)
      const p =
        src.price != null && Number.isFinite(Number(src.price))
          ? Number(src.price)
          : Number.isFinite(priceFromForm)
            ? priceFromForm
            : null
      const autoName = `${src.type || 'item'} · ${src.primary_color || 'unspecified'}`
      await createShoppingRecommendation({
        name: (saveNameOverride.trim() || autoName).slice(0, 200),
        type: (src.type || 'other').trim(),
        primary_color: src.primary_color ?? null,
        secondary_color: src.secondary_color ?? null,
        pattern: src.pattern ?? 'solid',
        formality: src.formality ?? 3,
        seasons: src.seasons ?? null,
        material: src.material ?? null,
        style_tags: src.style_tags ?? null,
        price: p,
        link: saveLinkOverride.trim() || null,
      })
      setSaveNameOverride('')
      setSaveLinkOverride('')
      await reloadRecs()
    } catch (e) {
      setRecErr(e instanceof Error ? e.message : 'Could not save')
    } finally {
      setListBusy(false)
    }
  }

  const handleAddManualRow = async (e: FormEvent) => {
    e.preventDefault()
    if (!recPack?.configured) return
    const priceNum = parseFloat(addPrice)
    setListBusy(true)
    setRecErr(null)
    try {
      await createShoppingRecommendation({
        name: (addName.trim() || `${addType} (untitled)`).slice(0, 200),
        type: addType.trim() || 'other',
        primary_color: addColor.trim() || null,
        pattern: addPattern || 'solid',
        formality: 3,
        price: Number.isFinite(priceNum) ? priceNum : null,
        link: addLink.trim() || null,
      })
      setAddName('')
      setAddPrice('')
      setAddLink('')
      await reloadRecs()
    } catch (err) {
      setRecErr(err instanceof Error ? err.message : 'Could not add item')
    } finally {
      setListBusy(false)
    }
  }

  const handleDeleteRow = async (id: string) => {
    if (!recPack?.configured) return
    setListBusy(true)
    setRecErr(null)
    try {
      await deleteShoppingRecommendation(id)
      await reloadRecs()
    } catch (err) {
      setRecErr(err instanceof Error ? err.message : 'Delete failed')
    } finally {
      setListBusy(false)
    }
  }

  return (
    <AppShell
      title="Shopping intelligence"
      subtitle="Enhanced scoring adds an AI summary and a preference-adjusted score on top of the wardrobe-based model. If the right panel still says Overall score (not Your score), stop every Vite dev server and run npm run dev again from the frontend folder."
    >
      <div className="space-y-6 max-w-5xl">
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="rounded-2xl border border-gray-100 bg-white p-5">
            <p className="text-xs font-medium text-gray-700 mb-3">
              Test a purchase <span className="text-pink-600 font-semibold">(enhanced API)</span>
            </p>

            <div className="flex gap-2 mb-4">
              <button
                type="button"
                onClick={() => {
                  setMode('manual')
                  setError(null)
                }}
                className={`flex-1 px-3 py-2 rounded-2xl text-sm font-semibold transition border ${
                  mode === 'manual'
                    ? 'bg-pink-50 border-pink-200 text-pink-700'
                    : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
                }`}
              >
                Manual details
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode('photo')
                  setError(null)
                }}
                className={`flex-1 px-3 py-2 rounded-2xl text-sm font-semibold transition border ${
                  mode === 'photo'
                    ? 'bg-pink-50 border-pink-200 text-pink-700'
                    : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
                }`}
              >
                Upload photo
              </button>
            </div>

            {mode === 'manual' ? (
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
            ) : (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Clothing photo</label>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => {
                      const f = e.target.files?.[0] ?? null
                      setPhotoFile(f)
                    }}
                    className="w-full text-sm"
                  />
                  <p className="text-[11px] text-gray-500 mt-1">
                    We’ll analyze the image and calculate your utility score.
                  </p>
                </div>

                {photoPreviewUrl && (
                  <div className="rounded-2xl border border-gray-200 bg-white p-2">
                    <img
                      src={photoPreviewUrl}
                      alt="Uploaded clothing preview"
                      className="w-full max-h-56 object-contain rounded-xl"
                    />
                  </div>
                )}

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Price (USD, optional)</label>
                  <input
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                    placeholder="120"
                  />
                </div>
              </div>
            )}

            <div className="mt-4 flex items-center gap-3">
              <button
                type="button"
                disabled={loading}
                onClick={async () => {
                  setLoading(true)
                  setError(null)
                  try {
                    const priceNum = Number(price)
                    if (mode === 'photo' && !photoFile) {
                      throw new Error('Please upload a photo first.')
                    }
                    const r =
                      mode === 'manual'
                        ? await scoreUtilityEnhanced(candidate)
                        : await scoreUtilityEnhancedFromImage(
                            photoFile as File,
                            Number.isFinite(priceNum) ? priceNum : undefined,
                          )
                    setResult(r)
                  } catch (e) {
                    const msg = e instanceof Error ? e.message : 'Scoring failed'
                    const friendly =
                      msg === 'Failed to fetch' || e instanceof TypeError
                        ? 'Cannot reach the backend. Start it: cd backend && python -m uvicorn main:app --reload'
                        : msg
                    setError(friendly)
                    setResult(null)
                  } finally {
                    setLoading(false)
                  }
                }}
                className="px-5 py-2 rounded-full text-sm font-semibold text-white shadow-sm hover:opacity-90 transition disabled:opacity-70"
                style={{ background: 'linear-gradient(135deg, #f43f7f, #ec4899)' }}
              >
                {loading ? 'Scoring…' : mode === 'manual' ? 'Calculate utility score' : 'Analyze & score'}
              </button>
              {error && <p className="text-sm text-red-600">{error}</p>}
            </div>
          </div>

          <div className="rounded-2xl border border-gray-100 bg-pink-50/50 p-5">
            <div className="flex items-center justify-between gap-2 mb-3">
              <p className="text-xs font-medium text-gray-700">Utility score + AI summary</p>
              <span className="text-[10px] font-mono text-gray-400 shrink-0">UI {SHOPPING_UI_REV}</span>
            </div>
            {!result ? (
              <p className="text-sm text-gray-500">
                Enter an item and click “Calculate utility score”.
              </p>
            ) : (
              <div className="space-y-4">
                <section
                  id="shopping-ai-summary"
                  className="rounded-2xl border-2 border-pink-400 bg-white p-4 shadow-sm"
                  aria-label="AI summary"
                >
                  <p className="text-xs font-bold text-pink-600 uppercase tracking-wider mb-2">AI summary</p>
                  <p className="text-lg font-semibold text-gray-900 leading-snug mb-2">
                    {(result.ai_explanation ?? { summary: '—' }).summary}
                  </p>
                  <ul className="text-sm text-gray-700 space-y-1.5 list-disc pl-5">
                    {(result.ai_explanation?.reasoning?.length
                      ? result.ai_explanation.reasoning
                      : ['No reasoning lines returned — update the frontend bundle or check the API response.']
                    ).map((line, i) => (
                      <li key={`${i}-${line.slice(0, 32)}`}>{line}</li>
                    ))}
                  </ul>
                </section>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Your score</p>
                    <p className="text-3xl font-bold text-gray-900">{result.adjusted_score}</p>
                    {result.adjusted_score !== result.score && (
                      <p className="text-xs text-gray-500">Base score: {result.score}</p>
                    )}
                    <p className="text-xs text-gray-500">
                      Color season:{' '}
                      <span className="font-semibold">{result.breakdown?.color_season ?? '—'}</span>
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-600">Cost per wear</p>
                    <p className="text-2xl font-semibold text-gray-900">
                      {(() => {
                        const cpw = result.cost_per_wear ?? result.breakdown?.cost_per_wear
                        return cpw == null ? '—' : `$${cpw}`
                      })()}
                    </p>
                    <p className="text-xs text-gray-500">
                      From {result.breakdown?.outfit_potential ?? '—'} predicted outfits
                    </p>
                  </div>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-700">Outfit potential</span>
                    <span className="font-semibold">{result.breakdown?.outfit_potential ?? '—'}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-gray-700 shrink-0">
                      Seasonal versatility
                      <span className="block text-[11px] font-normal text-gray-500">
                        100% = year-round in the model
                      </span>
                    </span>
                    <span className="font-semibold tabular-nums">
                      {pct01(result.breakdown?.seasonal_versatility)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-700">Color match</span>
                    <span className="font-semibold tabular-nums">{pct01(result.breakdown?.color_match)}</span>
                  </div>
                </div>

                {recPack?.configured && (
                  <div className="rounded-xl border border-pink-100 bg-white p-3 space-y-2">
                    <p className="text-xs font-semibold text-gray-800">Add this score to your shopping list</p>
                    <input
                      value={saveNameOverride}
                      onChange={(e) => setSaveNameOverride(e.target.value)}
                      placeholder="Optional display name (default: type · color)"
                      className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                    />
                    <input
                      value={saveLinkOverride}
                      onChange={(e) => setSaveLinkOverride(e.target.value)}
                      placeholder="Optional product link (https://...)"
                      className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                    />
                    <button
                      type="button"
                      disabled={listBusy}
                      onClick={() => void saveScoredItemToList()}
                      className="w-full px-3 py-2 rounded-full text-sm font-semibold text-pink-700 bg-pink-50 border border-pink-200 hover:bg-pink-100 disabled:opacity-60"
                    >
                      {listBusy ? 'Saving…' : 'Save to shopping list'}
                    </button>
                  </div>
                )}

                <p className="text-[11px] text-gray-500">
                  Scores use your wardrobe and saved palette.
                  {geminiReady === false && (
                    <span className="block mt-1 text-amber-700">
                      Gemini is not configured on the API — add GEMINI_API_KEY to <span className="font-mono">backend/.env</span>{' '}
                      or <span className="font-mono">backend/env</span>, then restart the server for live AI summaries.
                    </span>
                  )}
                  {geminiReady === true && (
                    <span className="block mt-1 text-emerald-700">Gemini is configured — summaries use Google AI.</span>
                  )}
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-gray-900">Saved shopping list</p>
            {recLoading && <span className="text-xs text-gray-500">Loading…</span>}
            {recErr && (
              <span className="text-xs text-red-600">
                {recErr}{' '}
                <button type="button" className="underline" onClick={() => void reloadRecs()}>
                  Retry
                </button>
              </span>
            )}
          </div>

          {!recPack?.configured && recPack && (
            <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2">
              Supabase is not configured on the API (<span className="font-mono">SUPABASE_URL</span> /{' '}
              <span className="font-mono">SUPABASE_KEY</span>). The table below shows demo rows only. Run{' '}
              <span className="font-mono">backend/supabase_shopping_recommendations.sql</span> in the Supabase SQL
              editor, then set env vars and refresh.
            </p>
          )}

          {recPack?.configured && (
            <form
              onSubmit={(e) => void handleAddManualRow(e)}
              className="rounded-2xl border border-gray-100 bg-gray-50/80 p-4 grid sm:grid-cols-2 lg:grid-cols-7 gap-2 items-end"
            >
              <div className="lg:col-span-2">
                <label className="block text-[11px] font-medium text-gray-600 mb-1">Name</label>
                <input
                  value={addName}
                  onChange={(e) => setAddName(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm"
                  placeholder="Camel wool blazer"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-gray-600 mb-1">Type</label>
                <input
                  value={addType}
                  onChange={(e) => setAddType(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm"
                  placeholder="blazer"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-gray-600 mb-1">Price USD</label>
                <input
                  value={addPrice}
                  onChange={(e) => setAddPrice(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm"
                  placeholder="180"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-gray-600 mb-1">Product link</label>
                <input
                  value={addLink}
                  onChange={(e) => setAddLink(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm"
                  placeholder="https://..."
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-gray-600 mb-1">Color</label>
                <input
                  value={addColor}
                  onChange={(e) => setAddColor(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm"
                  placeholder="camel"
                />
              </div>
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="block text-[11px] font-medium text-gray-600 mb-1">Pattern</label>
                  <input
                    value={addPattern}
                    onChange={(e) => setAddPattern(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm"
                    placeholder="solid"
                  />
                </div>
                <button
                  type="submit"
                  disabled={listBusy}
                  className="self-end px-4 py-2 rounded-full text-sm font-semibold text-white shrink-0 disabled:opacity-60"
                  style={{ background: 'linear-gradient(135deg, #f43f7f, #ec4899)' }}
                >
                  {listBusy ? '…' : 'Add'}
                </button>
              </div>
            </form>
          )}

          <div className="rounded-2xl border border-gray-100 overflow-hidden">
            <div className="bg-pink-50/70 px-4 py-2 text-xs font-medium text-gray-600 grid grid-cols-7 gap-2 items-center">
              <span className="col-span-2">Item</span>
              <span className="text-center">Price</span>
              <span className="text-center">Adjusted score</span>
              <span className="text-center">Cost / wear</span>
              <span className="text-center">Link</span>
              <span className="text-center"> </span>
            </div>
            <div className="divide-y divide-gray-100">
              {recLoading && tableRows.length === 0 ? (
                <div className="px-4 py-6 text-sm text-gray-500 text-center">Loading recommendations…</div>
              ) : tableRows.length === 0 ? (
                <div className="px-4 py-6 text-sm text-gray-500 text-center">
                  No saved items yet. Add one with the form above, or score an item and use &quot;Save to shopping
                  list&quot;.
                </div>
              ) : (
                tableRows.map((row) => (
                  <div
                    key={row.key}
                    className="px-4 py-3 text-xs text-gray-700 grid grid-cols-7 gap-2 items-center"
                  >
                    <div className="col-span-2">
                      <p className="font-semibold">{row.name}</p>
                      <p className="text-gray-500 mt-0.5">{row.type}</p>
                    </div>
                    <p className="text-center">{row.priceLabel}</p>
                    <p className="text-center">
                      <span
                        className={`inline-flex items-center justify-center px-2 py-1 rounded-full text-[11px] font-semibold ${
                          row.score >= 80
                            ? 'bg-emerald-50 text-emerald-700'
                            : row.score >= 60
                              ? 'bg-amber-50 text-amber-700'
                              : 'bg-red-50 text-red-600'
                        }`}
                      >
                        {row.score}/100
                      </span>
                    </p>
                    <p className="text-center text-gray-700">{row.cpwLabel}</p>
                    <p className="text-center">
                      {row.link ? (
                        <a
                          href={row.link}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[11px] text-pink-700 hover:underline"
                        >
                          Open
                        </a>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </p>
                    <p className="text-center">
                      {!row.demo ? (
                        <button
                          type="button"
                          disabled={listBusy}
                          onClick={() => void handleDeleteRow(row.id)}
                          className="text-[11px] text-red-600 hover:underline disabled:opacity-50"
                        >
                          Remove
                        </button>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <p className="text-[11px] text-gray-400">
          Rows load from Supabase table <span className="font-mono">shopping_recommendations</span>. Scores refresh on
          each load using your wardrobe and the same utility rules as the tester above (no Gemini on the list).
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

