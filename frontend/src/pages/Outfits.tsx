import AppShell from '../components/AppShell'
import { useState } from 'react'
import { generateOutfits, logWearFromOutfit, tagHypotheticalPhoto, type CandidateItem, type OutfitCard } from '../api/outfits'

type OutfitPiece = NonNullable<OutfitCard['item_details']>[number]

/** Mirrors backend `outfit_tools.SLOT_MAP` for display order and labels. */
function slotForItemType(type: string | undefined): 'top' | 'bottom' | 'shoes' | 'layer' | 'other' {
  const key = (type || '').toLowerCase().trim()
  const map: Record<string, 'top' | 'bottom' | 'shoes' | 'layer' | 'other'> = {
    top: 'top',
    't-shirt': 'top',
    shirt: 'top',
    blouse: 'top',
    sweater: 'top',
    hoodie: 'top',
    pullover: 'top',
    tank: 'top',
    pants: 'bottom',
    jeans: 'bottom',
    skirt: 'bottom',
    shorts: 'bottom',
    leggings: 'bottom',
    shoes: 'shoes',
    boots: 'shoes',
    sneakers: 'shoes',
    sandals: 'shoes',
    heels: 'shoes',
    loafers: 'shoes',
    flats: 'shoes',
    cardigan: 'layer',
    vest: 'layer',
    blazer: 'layer',
    jacket: 'layer',
    coat: 'layer',
    dress: 'other',
    bag: 'other',
    accessory: 'other',
    other: 'other',
  }
  return map[key] || 'other'
}

const SLOT_LABELS: Record<string, string> = {
  top: 'Top',
  bottom: 'Bottom',
  shoes: 'Shoes',
  layer: 'Outer layer',
  other: 'Other',
}

const SLOT_ORDER = ['top', 'bottom', 'shoes', 'layer', 'other'] as const

function orderedPiecesForOutfit(o: OutfitCard): { slot: (typeof SLOT_ORDER)[number]; item: OutfitPiece }[] {
  const raw = o.item_details?.length ? o.item_details : o.matched_item ? [o.matched_item as OutfitPiece] : []
  const rows = raw.map((item) => ({ slot: slotForItemType(item?.type), item }))
  rows.sort((a, b) => SLOT_ORDER.indexOf(a.slot) - SLOT_ORDER.indexOf(b.slot))
  return rows
}

function isHypotheticalPiece(item: OutfitPiece | undefined): boolean {
  const id = item?.id
  if (id == null) return false
  const s = String(id)
  return s === 'hypothetical' || s.startsWith('hypothetical::')
}

function OutfitSlotGrid({ outfit }: { outfit: OutfitCard }) {
  const rows = orderedPiecesForOutfit(outfit)
  const gridClass =
    rows.length >= 5
      ? 'grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3'
      : 'grid grid-cols-2 sm:grid-cols-4 gap-3'

  return (
    <div className={gridClass}>
      {rows.map(({ slot, item }, i) => (
        <OutfitSlotBox key={`${i}-${String(item?.id ?? '')}-${slot}`} slot={slot} item={item} />
      ))}
    </div>
  )
}

function OutfitSlotBox({ slot, item }: { slot: string; item: OutfitPiece }) {
  const label = SLOT_LABELS[slot] || 'Item'
  const hyp = isHypotheticalPiece(item)
  const imgUrl = item?.image_url
  const showPhoto = Boolean(imgUrl)

  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden bg-white flex flex-col shadow-sm min-w-0">
      <div className="aspect-[3/4] relative bg-gradient-to-b from-gray-50 to-gray-100">
        {showPhoto ? (
          <div className="absolute inset-0">
            <img src={imgUrl} alt="" className="absolute inset-0 w-full h-full object-cover" />
            {hyp ? (
              <span className="absolute bottom-1 left-1 right-1 text-center text-[9px] font-bold uppercase tracking-wide text-white drop-shadow-md bg-black/35 rounded px-1 py-0.5">
                Hypothetical buy
              </span>
            ) : null}
          </div>
        ) : hyp ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-3 text-center border-2 border-dashed border-pink-300 bg-pink-50/70">
            <span className="text-[10px] font-bold text-pink-600 uppercase tracking-wide">Hypothetical buy</span>
            <span className="text-xs font-semibold text-gray-900 mt-2 capitalize">{item?.type || 'Item'}</span>
            {item?.primary_color ? (
              <span className="text-[11px] text-gray-600 mt-0.5">{item.primary_color}</span>
            ) : null}
          </div>
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-3 text-center text-gray-500">
            <span className="text-[11px] font-medium text-gray-700">Digitized item</span>
            <span className="text-[10px] mt-1">No photo on file</span>
            <span className="text-[10px] text-pink-700/80 mt-2">Add an image in Wardrobe</span>
          </div>
        )}
      </div>
      <div className="px-2 py-2 border-t border-gray-100 bg-white shrink-0">
        <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">{label}</p>
        <p className="text-[11px] text-gray-900 capitalize leading-snug">
          {item?.type || '—'}
          {item?.primary_color ? ` · ${item.primary_color}` : ''}
        </p>
      </div>
    </div>
  )
}

function Outfits() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [outfits, setOutfits] = useState<OutfitCard[] | null>(null)
  const [shoppingMessage, setShoppingMessage] = useState<string | null>(null)
  const [suggestedBuys, setSuggestedBuys] = useState<string[] | null>(null)
  const [debug, setDebug] = useState<{
    fallback_used?: boolean
    compatible_items_count?: number
    filtered_count?: number
    candidate_type?: string
    compatible_expected_types?: string[]
    generation_path?: string
    pipeline_stages?: Array<{ name?: string; outcome?: string; detail?: string | null; selected_id_count?: number }>
    react_fallback_reason?: string | null
  } | null>(null)

  const [occasion, setOccasion] = useState('client meeting')
  const [weatherTemp, setWeatherTemp] = useState<number | ''>('')
  const [weatherConditions, setWeatherConditions] = useState('partly cloudy')
  const [vibe, setVibe] = useState('modern')

  // Hypothetical purchase (candidate)
  const [candidateType, setCandidateType] = useState('top')
  const [candidatePrimaryColor, setCandidatePrimaryColor] = useState('navy')
  const [candidatePattern, setCandidatePattern] = useState('solid')
  const [candidateFormality, setCandidateFormality] = useState(3)
  const [candidateSeasons, setCandidateSeasons] = useState('spring, summer')
  const [candidatePrice, setCandidatePrice] = useState('')
  const [includeHypothetical, setIncludeHypothetical] = useState(false)
  const [taggingPhoto, setTaggingPhoto] = useState(false)
  const [candidateImageUrl, setCandidateImageUrl] = useState<string | null>(null)
  const [photoTagMessage, setPhotoTagMessage] = useState<string | null>(null)
  const [loggingWearFor, setLoggingWearFor] = useState<number | null>(null)
  const [wearSuccessFor, setWearSuccessFor] = useState<number | null>(null)

  return (
    <AppShell
      title="Daily outfit recommendation"
      subtitle="Each look is top + bottom + shoes from your digitized wardrobe (optional outer layer). Optionally add a hypothetical purchase from a photo (Gemini tagging) to reserve its slot; or use wardrobe only. Occasion, weather, and vibe inform scoring and the judge."
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

          <div className="rounded-2xl border border-gray-100 bg-pink-50/50 p-5 space-y-3">
            <div className="flex items-start gap-3">
              <input
                id="include-hyp"
                type="checkbox"
                checked={includeHypothetical}
                onChange={(e) => {
                  setIncludeHypothetical(e.target.checked)
                  if (!e.target.checked) {
                    setCandidateImageUrl(null)
                    setPhotoTagMessage(null)
                  }
                }}
                className="mt-0.5 rounded border-gray-300"
              />
              <label htmlFor="include-hyp" className="text-xs text-gray-800 leading-snug cursor-pointer">
                <span className="font-semibold text-gray-900">Include hypothetical purchase</span> in outfits (one
                slot: top, bottom, or shoes — from photo + tags below). Turn off to use{' '}
                <strong>only</strong> digitized wardrobe pieces.
              </label>
            </div>

            <div className={includeHypothetical ? '' : 'opacity-50 pointer-events-none'}>
              <p className="text-xs font-medium text-gray-700 mb-2">Photo of the item you are considering (recommended)</p>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                disabled={!includeHypothetical || taggingPhoto}
                onChange={async (e) => {
                  const f = e.target.files?.[0]
                  e.target.value = ''
                  if (!f || !includeHypothetical) return
                  setTaggingPhoto(true)
                  setError(null)
                  setPhotoTagMessage(null)
                  try {
                    const { candidate: c } = await tagHypotheticalPhoto(f)
                    setCandidateImageUrl(c.image_url || null)
                    setCandidateType(c.type || 'top')
                    setCandidatePrimaryColor(c.primary_color || '')
                    setCandidatePattern(c.pattern || 'solid')
                    setCandidateFormality(c.formality ?? 3)
                    setCandidateSeasons((c.seasons || []).join(', ') || 'spring, summer')
                    setCandidatePrice(c.price != null ? String(c.price) : '')
                    setPhotoTagMessage(
                      `Photo tagged successfully. Detected: ${c.type || 'top'}${c.primary_color ? ` · ${c.primary_color}` : ''}.`,
                    )
                  } catch (err) {
                    setError(err instanceof Error ? err.message : 'Photo tagging failed')
                  } finally {
                    setTaggingPhoto(false)
                  }
                }}
                className="block w-full text-[11px] text-gray-700 file:mr-2 file:rounded-full file:border-0 file:bg-pink-500 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white"
              />
              <p className="text-[10px] text-gray-500 mt-1">
                {taggingPhoto ? 'Tagging with Gemini (same pipeline as Wardrobe)…' : 'Upload runs Cloudinary + Gemini; tags fill the fields below.'}
              </p>
              {photoTagMessage ? <p className="text-[11px] text-green-700 mt-1">{photoTagMessage}</p> : null}
              {candidateImageUrl ? (
                <div className="mt-2 rounded-xl border border-pink-200 bg-white p-2">
                  <p className="text-[10px] font-semibold text-gray-700 mb-1">Hypothetical preview</p>
                  <img
                    src={candidateImageUrl}
                    alt="Hypothetical candidate"
                    className="w-24 h-24 rounded-lg object-cover border border-gray-200"
                  />
                </div>
              ) : null}
            </div>

            <p className="text-xs font-medium text-gray-700 pt-1">Tags (editable after photo upload)</p>
            <div className={`grid sm:grid-cols-2 gap-3 ${includeHypothetical ? '' : 'opacity-50 pointer-events-none'}`}>
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
            <div className="text-[11px] text-gray-600 space-y-1 rounded-2xl border border-gray-100 bg-gray-50/80 px-3 py-2">
              <p>
                <span className="text-gray-500">Generation path:</span>{' '}
                <span className="font-semibold text-gray-900">
                  {debug.generation_path ?? (debug as { llm_mode?: string }).llm_mode ?? '—'}
                </span>
              </p>
              <p>
                <span className="text-gray-500">Engine label:</span>{' '}
                <span className="font-semibold">{String((debug as Record<string, unknown>).engine ?? 'rules')}</span>
              </p>
              {debug.react_fallback_reason ? (
                <p className="text-amber-800">
                  <span className="text-gray-500">LLM fallback reason:</span> {debug.react_fallback_reason}
                </p>
              ) : null}
              {debug.pipeline_stages && debug.pipeline_stages.length > 0 ? (
                <ul className="list-disc pl-4 space-y-0.5 text-gray-600">
                  {debug.pipeline_stages.map((s, i) => (
                    <li key={i}>
                      <span className="font-medium text-gray-800">{s.name ?? 'stage'}</span>: {s.outcome ?? '—'}
                      {s.detail ? ` (${s.detail})` : ''}
                      {typeof s.selected_id_count === 'number' ? ` · ids=${s.selected_id_count}` : ''}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          )}

          <button
            type="button"
            disabled={loading}
            onClick={async () => {
              setLoading(true)
              setError(null)
              setOutfits(null)
              setDebug(null)
              setShoppingMessage(null)
              setSuggestedBuys(null)
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
                  image_url: candidateImageUrl || null,
                }
                const body: Parameters<typeof generateOutfits>[0] = {
                  occasion,
                  vibe,
                  weather_temp: typeof weatherTemp === 'number' ? weatherTemp : null,
                  weather_conditions: weatherConditions,
                  engine: 'react',
                  include_hypothetical: includeHypothetical,
                }
                if (includeHypothetical) {
                  body.candidate = candidate
                }
                const res = await generateOutfits(body)
                setOutfits(res.outfits)
                setDebug(res.debug ?? null)
                setShoppingMessage(res.shopping_message ?? null)
                setSuggestedBuys(res.suggested_buys ?? null)
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
          <p className="text-[11px] text-gray-500 mt-2">Mode: structured outfits + LLM judge</p>
        </div>

        <div className="space-y-4">
          {!outfits && !shoppingMessage && (
            <div className="rounded-2xl border border-gray-100 bg-pink-50/60 px-5 py-4">
              <p className="text-sm font-medium text-gray-900">No results yet</p>
              <p className="text-xs text-gray-500 mt-1">
                Add your hypothetical purchase + click “Generate 4 outfits”.
              </p>
            </div>
          )}

          {shoppingMessage && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50/90 px-5 py-4 space-y-2">
              <p className="text-sm text-gray-900">{shoppingMessage}</p>
              {suggestedBuys && suggestedBuys.length > 0 ? (
                <div>
                  <p className="text-xs font-semibold text-gray-800 mb-1">Ideas to buy or digitize next</p>
                  <ul className="list-disc pl-4 text-xs text-gray-700 space-y-1">
                    {suggestedBuys.map((line, i) => (
                      <li key={i}>{line}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          )}

          {outfits?.map((o, idx) => (
            <div key={idx} className="rounded-2xl border border-gray-100 bg-white px-5 py-4">
              {/*
                Only show purchase metadata when hypothetical mode is enabled
                and this specific outfit actually contains a hypothetical piece.
              */}
              {(() => {
                const hasHypothetical = Boolean(
                  o.item_details?.some((it) => {
                    const id = String(it?.id ?? '')
                    return id === 'hypothetical' || id.startsWith('hypothetical::')
                  }),
                )
                return (
              <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                  <p className="text-xs font-semibold text-gray-900">Outfit {idx + 1}</p>
                  {includeHypothetical && hasHypothetical ? (
                    <p className="text-[11px] text-gray-500 mt-1">
                      Purchase: <span className="font-semibold">{candidateType}</span> ·{' '}
                      <span className="font-semibold">{candidatePrimaryColor || '—'}</span>
                    </p>
                  ) : (
                    <p className="text-[11px] text-gray-500 mt-1">Using only digitized wardrobe pieces.</p>
                  )}
                </div>
                <div className="text-right">
                  <p className="text-xs text-gray-600">Overall score</p>
                  <p className="text-2xl font-bold text-gray-900">{o.overall_score}</p>
                </div>
              </div>
                )
              })()}

              <div className="space-y-3">
                <p className="text-xs font-semibold text-gray-900">Pieces in this look</p>
                <OutfitSlotGrid outfit={o} />
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={loggingWearFor === idx}
                    onClick={async () => {
                      try {
                        setLoggingWearFor(idx)
                        setError(null)
                        const ids = (o.items || [])
                          .map((x) => String(x))
                          .filter((x) => x && x !== 'hypothetical' && !x.startsWith('hypothetical::'))
                        await logWearFromOutfit(ids)
                        setWearSuccessFor(idx)
                      } catch (e) {
                        setError(e instanceof Error ? e.message : 'Could not log wear for this outfit')
                      } finally {
                        setLoggingWearFor(null)
                      }
                    }}
                    className="inline-flex items-center justify-center px-3 py-1.5 rounded-full text-xs font-semibold text-pink-700 bg-pink-50 hover:bg-pink-100 transition disabled:opacity-60"
                  >
                    {loggingWearFor === idx ? 'Logging...' : 'Wear this today'}
                  </button>
                  {wearSuccessFor === idx ? (
                    <span className="text-[11px] text-green-700">Logged for today</span>
                  ) : null}
                </div>
                <p className="text-[11px] text-gray-600">{o.reasoning}</p>
                <div className="mt-1 grid sm:grid-cols-5 gap-3">
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
          ))}
        </div>
      </div>
    </AppShell>
  )
}

export default Outfits

