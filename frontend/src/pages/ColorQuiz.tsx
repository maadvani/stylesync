import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import AppShell from '../components/AppShell'
import { setColorSeason } from '../api/user'

type Option = { label: string; warm?: number; cool?: number; light?: number; deep?: number }

const QUESTIONS: { question: string; options: Option[] }[] = [
  {
    question: 'What is your natural hair color?',
    options: [
      { label: 'Blonde (golden, honey)', warm: 2 },
      { label: 'Blonde (ash, platinum)', cool: 2 },
      { label: 'Brown (golden, auburn)', warm: 1 },
      { label: 'Brown (ash, cool tone)', cool: 1 },
      { label: 'Black', deep: 2 },
      { label: 'Red / ginger', warm: 3 },
    ],
  },
  {
    question: 'What do your wrist veins look like in natural light?',
    options: [
      { label: 'Greenish – warm undertone', warm: 3 },
      { label: 'Bluish – cool undertone', cool: 3 },
      { label: 'Hard to tell / mixed', warm: 1, cool: 1 },
    ],
  },
  {
    question: 'How does pure white look against your skin?',
    options: [
      { label: 'Harsh or washed out – I prefer cream/ivory', warm: 2 },
      { label: 'Bright and flattering', cool: 2 },
      { label: 'Both work okay', warm: 1, cool: 1 },
    ],
  },
]

// Map total scores to a season key (simplified 4 for MVP; expand to 12 later).
function scoresToSeason(warm: number, cool: number, light: number, deep: number): string {
  const isWarm = warm >= cool
  const isLight = light > deep
  if (isWarm && isLight) return 'warm_spring'
  if (isWarm && !isLight) return 'soft_autumn'
  if (!isWarm && isLight) return 'soft_summer'
  return 'cool_winter'
}

const SEASON_LABELS: Record<string, string> = {
  warm_spring: 'Warm Spring',
  soft_autumn: 'Soft Autumn',
  soft_summer: 'Soft Summer',
  cool_winter: 'Cool Winter',
}

function ColorQuiz() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState<Option[]>([])
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)

  const isResultStep = step >= QUESTIONS.length
  const progress = isResultStep ? 100 : ((step + 1) / QUESTIONS.length) * 100

  const handleOption = (opt: Option) => {
    if (isResultStep) return
    const next = answers.slice(0, step)
    next[step] = opt
    setAnswers([...next])
    if (step + 1 < QUESTIONS.length) {
      setStep(step + 1)
    } else {
      setStep(QUESTIONS.length)
      setDone(true)
    }
  }

  const warm = answers.reduce((s, a) => s + (a.warm ?? 0), 0)
  const cool = answers.reduce((s, a) => s + (a.cool ?? 0), 0)
  const light = answers.reduce((s, a) => s + (a.light ?? 0), 0)
  const deep = answers.reduce((s, a) => s + (a.deep ?? 0), 0)
  const resultSeason = done ? scoresToSeason(warm, cool, light, deep) : null
  const resultLabel = resultSeason ? SEASON_LABELS[resultSeason] ?? resultSeason : ''

  const [saveError, setSaveError] = useState<string | null>(null)

  const handleSave = async () => {
    if (!resultSeason) return
    setSaveError(null)
    setSaving(true)
    try {
      await setColorSeason(resultSeason)
      navigate('/dashboard')
    } catch (e) {
      setSaving(false)
      const msg = e instanceof Error ? e.message : 'Save failed'
      const friendly = msg === 'Failed to fetch' || (e instanceof TypeError)
        ? 'Cannot reach the backend. Start it: cd backend && uvicorn main:app --reload'
        : msg
      setSaveError(friendly)
    }
  }

  return (
    <AppShell
      title="Discover your color season"
      subtitle="Answer a few questions to estimate your seasonal palette. We'll use this to filter recommendations."
    >
      <div className="max-w-xl">
        <div className="w-full h-2 bg-gray-100 rounded-full mb-6 overflow-hidden">
          <div
            className="h-full bg-pink-400 rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>

        {!isResultStep && (
          <>
            <p className="text-xs text-gray-500 mb-1">Question {step + 1} of {QUESTIONS.length}</p>
            <p className="text-base font-medium text-gray-900 mb-4">
              {QUESTIONS[step].question}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
              {QUESTIONS[step].options.map((opt) => (
                <button
                  key={opt.label}
                  type="button"
                  onClick={() => handleOption(opt)}
                  className="px-4 py-3 rounded-2xl border border-gray-200 text-sm text-left text-gray-800 hover:border-pink-400 hover:bg-pink-50 transition"
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              disabled={step === 0}
              onClick={() => setStep((s) => Math.max(0, s - 1))}
              className="text-xs text-gray-400 hover:text-gray-600 disabled:opacity-30"
            >
              ← Back
            </button>
          </>
        )}

        {isResultStep && resultSeason && (
          <div className="mb-6">
            <p className="text-xs text-pink-500 uppercase tracking-wider mb-2">Your result</p>
            <h2 className="text-2xl font-bold text-gray-900 mb-2" style={{ fontFamily: 'Georgia, serif' }}>
              {resultLabel}
            </h2>
            <p className="text-sm text-gray-600 mb-6">
              We'll use this palette to filter shopping and outfit recommendations. You can retake the quiz anytime.
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="px-5 py-2 rounded-full text-sm font-semibold text-white shadow-sm hover:opacity-90 transition disabled:opacity-70"
                style={{ background: 'linear-gradient(135deg, #f43f7f, #ec4899)' }}
              >
                {saving ? 'Saving…' : 'Save & go to dashboard'}
              </button>
              <button
                type="button"
                onClick={() => { setStep(0); setAnswers([]); setDone(false); setSaveError(null); }}
                className="px-4 py-2 rounded-full text-sm font-semibold text-gray-600 bg-gray-100 hover:bg-gray-200 transition"
              >
                Retake quiz
              </button>
            </div>
            {saveError && (
              <p className="mt-3 text-sm text-red-600 max-w-md">{saveError}</p>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}

export default ColorQuiz
