import type { AggregatedScores, Clarity, Contrast, Depth, DominantProfile, QuizQuestion, Undertone } from './types'

const DEFAULT_SCORES: AggregatedScores = {
  undertone: { warm: 0, cool: 0, neutral: 0 },
  depth: { light: 0, medium: 0, deep: 0 },
  contrast: { low: 0, medium: 0, high: 0 },
  clarity: { muted: 0, bright: 0 },
}

function pickHighestKey<T extends string>(scores: Record<T, number>): T {
  const entries = Object.entries(scores) as Array<[T, number]>
  return entries.reduce((best, current) => (current[1] > best[1] ? current : best))[0]
}

export function calculateScores(
  questions: QuizQuestion[],
  answersByQuestionId: Record<string, string>,
): AggregatedScores {
  const totals: AggregatedScores = structuredClone(DEFAULT_SCORES)

  for (const question of questions) {
    const selectedId = answersByQuestionId[question.id]
    if (!selectedId) continue

    const option = question.options.find((candidate) => candidate.id === selectedId)
    if (!option) continue

    for (const [key, value] of Object.entries(option.scores.undertone ?? {})) {
      totals.undertone[key as Undertone] += value ?? 0
    }
    for (const [key, value] of Object.entries(option.scores.depth ?? {})) {
      totals.depth[key as Depth] += value ?? 0
    }
    for (const [key, value] of Object.entries(option.scores.contrast ?? {})) {
      totals.contrast[key as Contrast] += value ?? 0
    }
    for (const [key, value] of Object.entries(option.scores.clarity ?? {})) {
      totals.clarity[key as Clarity] += value ?? 0
    }
  }

  return totals
}

export function getDominantProfile(scores: AggregatedScores): DominantProfile {
  return {
    undertone: pickHighestKey(scores.undertone),
    depth: pickHighestKey(scores.depth),
    contrast: pickHighestKey(scores.contrast),
    clarity: pickHighestKey(scores.clarity),
  }
}
