import { useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import AppShell from '../components/AppShell'
import { listWardrobe, uploadWardrobeItem, updateWardrobeItem, deleteWardrobeItem, retagWardrobeItem, type WardrobeItem } from '../api/wardrobe'

const ALLOWED = ['image/jpeg', 'image/png', 'image/webp']
const MAX_MB = 10

function Wardrobe() {
  const navigate = useNavigate()
  const [items, setItems] = useState<WardrobeItem[]>([])
  const [loading, setLoading] = useState(true)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<WardrobeItem | null>(null)
  const [savingEdit, setSavingEdit] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [retagging, setRetagging] = useState(false)
  const [targetItems, setTargetItems] = useState<string[]>(['top'])
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let cancelled = false
    listWardrobe()
      .then((res) => { if (!cancelled) setItems(res.items); setError(null); })
      .catch((e) => {
        if (!cancelled) {
          const msg = e?.message === 'Failed to fetch' || (e instanceof TypeError)
            ? 'Cannot reach the backend. Start it in a terminal: cd backend && uvicorn main:app --reload'
            : 'Could not load wardrobe'
          setError(msg)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); })
    return () => { cancelled = true }
  }, [])

  const handleFile = async (file: File | null) => {
    if (!file) return
    if (!ALLOWED.includes(file.type)) {
      setError('Use JPEG, PNG, or WebP')
      setUploadStatus('error')
      return
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`File must be under ${MAX_MB} MB`)
      setUploadStatus('error')
      return
    }
    setError(null)
    setUploadStatus('uploading')
    try {
      const newItem = await uploadWardrobeItem(file)
      setItems((prev) => [newItem, ...prev])
      setUploadStatus('done')
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Upload failed'
      const friendly = msg === 'Failed to fetch' || (e instanceof TypeError)
        ? 'Cannot reach the backend. Start it in a terminal: cd backend && uvicorn main:app --reload'
        : msg
      setError(friendly)
      setUploadStatus('error')
    }
  }

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) handleFile(f)
    e.target.value = ''
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const f = e.dataTransfer.files?.[0]
    if (f && ALLOWED.includes(f.type)) handleFile(f)
    else if (f) setError('Use JPEG, PNG, or WebP')
  }

  const onDragOver = (e: React.DragEvent) => e.preventDefault()

  const closeModal = () => {
    setSelected(null)
    setEditError(null)
    setSavingEdit(false)
    setRetagging(false)
  }

  const saveEdits = async () => {
    if (!selected) return
    setSavingEdit(true)
    setEditError(null)
    try {
      const updated = await updateWardrobeItem(selected.id, {
        type: selected.type,
        primary_color: selected.primary_color,
        secondary_color: selected.secondary_color,
        pattern: selected.pattern,
        formality: selected.formality,
        seasons: selected.seasons ?? [],
        material: selected.material,
        style_tags: selected.style_tags ?? [],
      })
      setItems((prev) => prev.map((it) => (it.id === updated.id ? updated : it)))
      setSelected(updated)
      setSavingEdit(false)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Update failed'
      setEditError(msg)
      setSavingEdit(false)
    }
  }

  const deleteSelected = async () => {
    if (!selected) return
    const ok = window.confirm('Delete this wardrobe item? This cannot be undone.')
    if (!ok) return
    setSavingEdit(true)
    setEditError(null)
    try {
      await deleteWardrobeItem(selected.id)
      setItems((prev) => prev.filter((it) => it.id !== selected.id))
      closeModal()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Delete failed'
      setEditError(msg)
      setSavingEdit(false)
    }
  }

  const retagSelected = async (engine: 'default' | 'gemini' = 'default') => {
    if (!selected) return
    setRetagging(true)
    setEditError(null)
    try {
      const updated = await retagWardrobeItem(
        selected.id,
        engine === 'gemini' ? 'gemini' : 'default',
        engine === 'gemini' ? targetItems : undefined,
      )
      // Backend may create additional items for multi-target; easiest UX is to refresh list.
      // But to keep it snappy, we upsert the updated item and then refetch in background.
      setItems((prev) => {
        const next = prev.map((it) => (it.id === updated.id ? updated : it))
        return next
      })
      setSelected(updated)
      // Refresh list to include any newly created co-ord items.
      listWardrobe().then((res) => setItems(res.items)).catch(() => null)
      setRetagging(false)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Retag failed'
      setEditError(msg)
      setRetagging(false)
    }
  }

  return (
    <AppShell
      title="Digitize your closet"
      subtitle="Drag and drop or choose photos of your wardrobe. StyleSync will tag type, color, and formality via the AI pipeline."
    >
      <div className="grid lg:grid-cols-[2fr,1.5fr] gap-6">
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept={ALLOWED.join(',')}
            className="hidden"
            onChange={onInputChange}
          />
          <div className="bg-pink-50/80 border border-pink-100 rounded-2xl p-6 mb-6">
            <div
              onDrop={onDrop}
              onDragOver={onDragOver}
              className="border-2 border-dashed border-pink-200 rounded-2xl px-6 py-10 flex flex-col items-center justify-center text-center cursor-pointer hover:border-pink-400 transition-colors"
              onClick={() => fileInputRef.current?.click()}
            >
              {uploadStatus === 'uploading' && (
                <p className="text-sm font-medium text-pink-600 mb-2">Uploading & tagging…</p>
              )}
              {uploadStatus === 'error' && error && (
                <p className="text-sm font-medium text-red-600 mb-2">{error}</p>
              )}
              {uploadStatus !== 'uploading' && (
                <>
                  <p className="text-sm font-medium text-gray-800 mb-1">
                    Drop photos here or click to browse
                  </p>
                  <p className="text-xs text-gray-500 mb-4">
                    PNG, JPG, WebP up to {MAX_MB}MB each.
                  </p>
                  <button
                    type="button"
                    className="px-4 py-2 rounded-full text-sm font-semibold text-pink-600 bg-white shadow-sm hover:bg-pink-50 transition"
                    onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
                  >
                    Browse files
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-[0.15em]">
              Wardrobe preview
            </p>
            <button
              onClick={() => navigate('/analytics')}
              className="text-[11px] text-pink-500 hover:underline"
            >
              View analytics ↗
            </button>
          </div>

          {loading ? (
            <p className="text-sm text-gray-500">Loading…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-gray-500">No items yet. Upload a photo to start.</p>
          ) : (
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-3 mb-3">
              {items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setSelected(item)}
                  className="aspect-[3/4] rounded-2xl bg-gray-100 overflow-hidden border border-gray-200 text-left hover:border-pink-300 hover:shadow-sm transition"
                >
                  <img
                    src={item.image_url}
                    alt={item.type}
                    className="w-full h-full object-cover"
                  />
                  <div className="p-1.5 bg-white/90 text-[10px] text-gray-700 truncate">
                    <span className="font-semibold">{item.type}</span>
                    {item.primary_color && ` · ${item.primary_color}`}
                    {item.formality != null && (
                      <span className="ml-1 text-gray-500">F{item.formality}</span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Detail modal */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
          <button
            type="button"
            className="absolute inset-0 bg-black/30"
            onClick={closeModal}
          />
          <div className="relative w-full max-w-3xl bg-white rounded-3xl shadow-2xl overflow-hidden border border-pink-100">
            <div className="flex items-center justify-between px-6 py-4 bg-pink-50/60 border-b border-pink-100">
              <div>
                <p className="text-xs text-pink-500 uppercase tracking-wider">Wardrobe item</p>
                <p className="text-lg font-semibold text-gray-900" style={{ fontFamily: 'Georgia, serif' }}>
                  Edit details
                </p>
              </div>
              <button
                type="button"
                onClick={closeModal}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>

            <div className="grid md:grid-cols-2 gap-6 p-6">
              <div className="rounded-2xl overflow-hidden bg-gray-100 border border-gray-200">
                <img src={selected.image_url} alt={selected.type} className="w-full h-full object-cover" />
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-2">
                    Target item(s) for AI tagging (multi-select)
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { key: 'top', label: 'Top' },
                      { key: 'bottom', label: 'Bottom' },
                      { key: 'dress', label: 'Dress' },
                      { key: 'shoes', label: 'Shoes' },
                      { key: 'bag', label: 'Bag' },
                      { key: 'accessory', label: 'Accessory' },
                    ].map((t) => {
                      const active = targetItems.includes(t.key)
                      return (
                        <button
                          key={t.key}
                          type="button"
                          onClick={() =>
                            setTargetItems((prev) =>
                              prev.includes(t.key)
                                ? prev.filter((x) => x !== t.key)
                                : [...prev, t.key],
                            )
                          }
                          className={[
                            'px-3 py-1.5 rounded-full text-xs font-semibold transition',
                            active
                              ? 'bg-pink-500 text-white'
                              : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
                          ].join(' ')}
                        >
                          {t.label}
                        </button>
                      )
                    })}
                  </div>
                  <p className="mt-1 text-[11px] text-gray-500">
                    Tip: for a co-ord set, select both <span className="font-semibold">Top</span> and{' '}
                    <span className="font-semibold">Bottom</span>.
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Type</label>
                    <input
                      value={selected.type ?? ''}
                      onChange={(e) => setSelected({ ...selected, type: e.target.value })}
                      className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                      placeholder="e.g. blazer, jeans"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Formality (1–5)</label>
                    <input
                      type="number"
                      min={1}
                      max={5}
                      value={selected.formality ?? 3}
                      onChange={(e) =>
                        setSelected({ ...selected, formality: Number(e.target.value) })
                      }
                      className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Primary color</label>
                    <input
                      value={selected.primary_color ?? ''}
                      onChange={(e) => setSelected({ ...selected, primary_color: e.target.value })}
                      className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                      placeholder="e.g. navy"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Secondary color</label>
                    <input
                      value={selected.secondary_color ?? ''}
                      onChange={(e) =>
                        setSelected({ ...selected, secondary_color: e.target.value || null })
                      }
                      className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                      placeholder="optional"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Pattern</label>
                  <input
                    value={selected.pattern ?? ''}
                    onChange={(e) => setSelected({ ...selected, pattern: e.target.value })}
                    className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                    placeholder="e.g. solid, stripes"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Seasons (comma-separated)</label>
                  <input
                    value={(selected.seasons ?? []).join(', ')}
                    onChange={(e) =>
                      setSelected({
                        ...selected,
                        seasons: e.target.value
                          .split(',')
                          .map((s) => s.trim())
                          .filter(Boolean),
                      })
                    }
                    className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                    placeholder="spring, summer, fall, winter"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Material</label>
                  <input
                    value={selected.material ?? ''}
                    onChange={(e) => setSelected({ ...selected, material: e.target.value })}
                    className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                    placeholder="e.g. cotton"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Style tags (comma-separated)</label>
                  <input
                    value={(selected.style_tags ?? []).join(', ')}
                    onChange={(e) =>
                      setSelected({
                        ...selected,
                        style_tags: e.target.value
                          .split(',')
                          .map((s) => s.trim())
                          .filter(Boolean),
                      })
                    }
                    className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-pink-400"
                    placeholder="classic, minimal, trendy"
                  />
                </div>

                {editError && <p className="text-sm text-red-600">{editError}</p>}

                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={deleteSelected}
                    disabled={savingEdit}
                    className="mr-auto px-4 py-2 rounded-full text-sm font-semibold text-red-600 bg-red-50 hover:bg-red-100 transition disabled:opacity-70"
                  >
                    Delete item
                  </button>
                  <button
                    type="button"
                    onClick={() => retagSelected('default')}
                    disabled={retagging || savingEdit}
                    className="px-4 py-2 rounded-full text-sm font-semibold text-pink-600 bg-pink-50 hover:bg-pink-100 transition disabled:opacity-70"
                  >
                    {retagging ? 'Re-tagging…' : 'Re-run AI tagging'}
                  </button>
                  <button
                    type="button"
                    onClick={() => retagSelected('gemini')}
                    disabled={retagging || savingEdit}
                    className="px-4 py-2 rounded-full text-sm font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 transition disabled:opacity-70"
                  >
                    {retagging ? 'Re-tagging…' : 'Re-tag with Gemini Flash'}
                  </button>
                  <button
                    type="button"
                    onClick={closeModal}
                    className="px-4 py-2 rounded-full text-sm font-semibold text-gray-600 bg-gray-100 hover:bg-gray-200 transition"
                  >
                    Close
                  </button>
                  <button
                    type="button"
                    onClick={saveEdits}
                    disabled={savingEdit}
                    className="px-5 py-2 rounded-full text-sm font-semibold text-white shadow-sm hover:opacity-90 transition disabled:opacity-70"
                    style={{ background: 'linear-gradient(135deg, #f43f7f, #ec4899)' }}
                  >
                    {savingEdit ? 'Saving…' : 'Save changes'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  )
}

export default Wardrobe
