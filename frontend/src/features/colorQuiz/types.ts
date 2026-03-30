export type Undertone = 'warm' | 'cool' | 'neutral'
export type Depth = 'light' | 'medium' | 'deep'
export type Contrast = 'low' | 'medium' | 'high'
export type Clarity = 'muted' | 'bright'

export type DimensionScores = {
  undertone?: Partial<Record<Undertone, number>>
  depth?: Partial<Record<Depth, number>>
  contrast?: Partial<Record<Contrast, number>>
  clarity?: Partial<Record<Clarity, number>>
}

export type QuizOption = {
  id: string
  label: string
  scores: DimensionScores
}

export type QuizQuestion = {
  id: string
  question: string
  helperText?: string
  options: QuizOption[]
}

export type AggregatedScores = {
  undertone: Record<Undertone, number>
  depth: Record<Depth, number>
  contrast: Record<Contrast, number>
  clarity: Record<Clarity, number>
}

export type DominantProfile = {
  undertone: Undertone
  depth: Depth
  contrast: Contrast
  clarity: Clarity
}

export type Season = 'Spring' | 'Summer' | 'Autumn' | 'Winter'
export type Subtype = 'Light' | 'Deep' | 'Soft' | 'Bright'

export type QuizResult = {
  season: Season
  subtype: Subtype
  seasonKey: string
  title: string
  description: string
  explanation: string[]
  tips: string[]
  profile: DominantProfile
}
