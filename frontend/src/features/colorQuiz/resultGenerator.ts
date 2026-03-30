import type { AggregatedScores, DominantProfile, QuizResult, Season, Subtype } from './types'

function resolveWarmVsCool(profile: DominantProfile, scores: AggregatedScores): 'warm' | 'cool' {
  if (profile.undertone === 'warm') return 'warm'
  if (profile.undertone === 'cool') return 'cool'
  return scores.undertone.warm >= scores.undertone.cool ? 'warm' : 'cool'
}

function inferSeason(profile: DominantProfile, scores: AggregatedScores): Season {
  const temperature = resolveWarmVsCool(profile, scores)
  const isLight = profile.depth === 'light'
  const isDeep = profile.depth === 'deep'
  const isBright = profile.clarity === 'bright'
  const isMuted = profile.clarity === 'muted'
  const isHighContrast = profile.contrast === 'high'

  if (temperature === 'warm' && isLight && isBright) return 'Spring'
  if (temperature === 'cool' && isLight && isMuted) return 'Summer'
  if (temperature === 'warm' && isDeep && isMuted) return 'Autumn'
  if (temperature === 'cool' && isDeep && isHighContrast) return 'Winter'

  // Fallback: pick by strongest weighted season alignment.
  const spring = scores.undertone.warm + scores.depth.light + scores.clarity.bright
  const summer = scores.undertone.cool + scores.depth.light + scores.clarity.muted
  const autumn = scores.undertone.warm + scores.depth.deep + scores.clarity.muted
  const winter = scores.undertone.cool + scores.depth.deep + scores.contrast.high
  const best = [
    ['Spring', spring],
    ['Summer', summer],
    ['Autumn', autumn],
    ['Winter', winter],
  ].reduce((acc, cur) => (cur[1] > acc[1] ? cur : acc)) as [Season, number]
  return best[0]
}

function inferSubtype(scores: AggregatedScores): Subtype {
  const subtypeScores: Record<Subtype, number> = {
    Light: scores.depth.light,
    Deep: scores.depth.deep,
    Soft: scores.clarity.muted + (scores.contrast.low * 0.5),
    Bright: scores.clarity.bright + (scores.contrast.high * 0.5),
  }

  return Object.entries(subtypeScores).reduce(
    (best, current) => (current[1] > best[1] ? current : best),
  )[0] as Subtype
}

function getWhyLines(season: Season, profile: DominantProfile): string[] {
  return [
    `Your answers point to a ${profile.undertone} color temperature with a ${profile.depth} overall value.`,
    `Your look reads as ${profile.contrast} contrast with ${profile.clarity} color intensity.`,
    `${season} colors balance these traits so your complexion, eyes, and hair look clearer and more harmonious.`,
  ]
}

function getTips(season: Season): string[] {
  const bySeason: Record<Season, string[]> = {
    Spring: [
      'Opt for warm, lively shades like coral, peach, warm turquoise, and fresh greens.',
      'Use creamy neutrals over stark black for a softer, brighter finish.',
      'Avoid overly dusty or cool gray-heavy palettes that can flatten your glow.',
    ],
    Summer: [
      'Choose cool, soft tones like dusty rose, lavender, slate blue, and soft navy.',
      'Build outfits with gentle contrast rather than sharp black-and-white pairings.',
      'Avoid very warm oranges and neon brights that can overpower your natural balance.',
    ],
    Autumn: [
      'Lean into rich earthy colors like olive, rust, camel, forest green, and warm burgundy.',
      'Pick textured fabrics and matte finishes to complement your muted depth.',
      'Avoid icy cool tones and stark brights that can feel disconnected from your features.',
    ],
    Winter: [
      'Go for jewel tones and crisp cool shades like emerald, cobalt, fuchsia, and true black.',
      'Use high-contrast combinations such as black/white or navy/icy accents.',
      'Avoid dusty pastels and muddy earthy tones that can make you look less vibrant.',
    ],
  }
  return bySeason[season]
}

export function generateQuizResult(scores: AggregatedScores, profile: DominantProfile): QuizResult {
  const season = inferSeason(profile, scores)
  const subtype = inferSubtype(scores)
  const seasonKey = `${subtype.toLowerCase()}_${season.toLowerCase()}`
  const emojiBySeason: Record<Season, string> = {
    Spring: '🌸',
    Summer: '🌿',
    Autumn: '🍂',
    Winter: '❄️',
  }
  const descriptionBySeason: Record<Season, string> = {
    Spring: 'Fresh, warm, bright colors suit you best.',
    Summer: 'Cool, light, softly muted colors suit you best.',
    Autumn: 'Rich, warm, muted colors suit you best.',
    Winter: 'Bold, cool, high-contrast colors suit you best.',
  }

  return {
    season,
    subtype,
    seasonKey,
    title: `You lean towards ${subtype} ${season} ${emojiBySeason[season]}`,
    description: descriptionBySeason[season],
    explanation: getWhyLines(season, profile),
    tips: getTips(season),
    profile,
  }
}
