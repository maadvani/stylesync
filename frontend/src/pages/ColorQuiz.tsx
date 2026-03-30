import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import AppShell from '../components/AppShell'
import { setColorSeason } from '../api/user'
import rawQuestions from '../features/colorQuiz/questions.json'
import { calculateScores, getDominantProfile } from '../features/colorQuiz/scoring'
import { generateQuizResult } from '../features/colorQuiz/resultGenerator'
import type { QuizQuestion } from '../features/colorQuiz/types'

const QUESTIONS = rawQuestions as QuizQuestion[]

function ColorQuiz() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const isResultStep = step >= QUESTIONS.length
  const progress = isResultStep ? 100 : ((step + 1) / QUESTIONS.length) * 100

  const handleOption = (optionId: string) => {
    if (isResultStep) return
    const currentQuestion = QUESTIONS[step]
    if (!currentQuestion) return

    setAnswers((prev) => ({ ...prev, [currentQuestion.id]: optionId }))

    if (step + 1 < QUESTIONS.length) {
      setStep(step + 1)
    } else {
      setStep(QUESTIONS.length)
      setDone(true)
    }
  }

  const totals = calculateScores(QUESTIONS, answers)
  const dominantProfile = getDominantProfile(totals)
  const result = done ? generateQuizResult(totals, dominantProfile) : null

  const handleSave = async () => {
    if (!result) return
    setSaveError(null)
    setSaving(true)
    try {
      await setColorSeason(result.seasonKey)
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
            {(() => {
              const currentQuestion = QUESTIONS[step]
              if (!currentQuestion) return null
              return (
                <>
            <p className="text-xs text-gray-500 mb-1">Question {step + 1} of {QUESTIONS.length}</p>
            <p className="text-base font-medium text-gray-900 mb-4">
              {currentQuestion.question}
            </p>
            {currentQuestion.helperText && (
              <p className="text-xs text-gray-500 mb-4">{currentQuestion.helperText}</p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
              {currentQuestion.options.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => handleOption(opt.id)}
                  className="px-4 py-3 rounded-2xl border border-gray-200 text-sm text-left text-gray-800 hover:border-pink-400 hover:bg-pink-50 transition"
                >
                  {opt.label}
                </button>
              ))}
            </div>
                </>
              )
            })()}
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

        {isResultStep && result && (
          <div className="mb-6">
            <p className="text-xs text-pink-500 uppercase tracking-wider mb-2">Your result</p>
            <h2 className="text-2xl font-bold text-gray-900 mb-2" style={{ fontFamily: 'Georgia, serif' }}>
              {result.title}
            </h2>
            <p className="text-sm text-gray-600 mb-6">
              {result.description}
            </p>

            <div className="mb-6 rounded-2xl bg-pink-50 border border-pink-100 p-4">
              <p className="text-xs font-semibold text-pink-700 uppercase tracking-wide mb-2">Why this works for you</p>
              <div className="space-y-2">
                {result.explanation.map((line) => (
                  <p key={line} className="text-sm text-gray-700">{line}</p>
                ))}
              </div>
            </div>

            <div className="mb-6 rounded-2xl bg-gray-50 border border-gray-200 p-4">
              <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">Styling tips</p>
              <ul className="space-y-2 text-sm text-gray-700 list-disc pl-5">
                {result.tips.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>
            </div>

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
                onClick={() => { setStep(0); setAnswers({}); setDone(false); setSaveError(null); }}
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
