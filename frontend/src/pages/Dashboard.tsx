import { useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import { getColorSeason } from '../api/user'

const features = [
  {
    title: 'Wardrobe Digitization',
    description: 'Upload 20–30 pieces and let StyleSync categorize everything for you.',
    cta: 'Open wardrobe',
    route: '/wardrobe',
  },
  {
    title: 'Personal Color Analysis',
    description: 'Take a 10-question quiz to discover your seasonal color palette.',
    cta: 'Start color quiz',
    route: '/color-quiz',
  },
  {
    title: 'Daily Trend Intelligence',
    description: 'See which runway and street trends your current closet already covers.',
    cta: 'View trends',
    route: '/trends',
  },
  {
    title: 'Shopping Intelligence',
    description: 'Score new pieces on outfit potential, cost-per-wear, and closet fit.',
    cta: 'Shop smarter',
    route: '/shopping',
  },
  {
    title: 'Daily Outfit Generation',
    description: 'Tell us the occasion, weather, and vibe—get 4–5 styled looks.',
    cta: 'Generate outfits',
    route: '/outfits',
  },
  {
    title: 'Wardrobe Analytics',
    description: 'Visualize color balance, seasons, and most/least worn items.',
    cta: 'View analytics',
    route: '/analytics',
  },
]

const SEASON_LABELS: Record<string, string> = {
  warm_spring: 'Warm Spring',
  soft_autumn: 'Soft Autumn',
  soft_summer: 'Soft Summer',
  cool_winter: 'Cool Winter',
}

function Dashboard() {
  const navigate = useNavigate()
  const [colorSeason, setColorSeason] = useState<string | null>(null)

  useEffect(() => {
    getColorSeason()
      .then((res) => setColorSeason(res.color_season ?? null))
      .catch(() => setColorSeason(null))
  }, [])

  return (
    <AppShell
      title="Welcome to your StyleSync studio"
      subtitle="Digitize your closet, discover your colors, track live trends, and test every purchase with a utility score before you buy."
    >
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6 mb-6">
        <div className="rounded-2xl bg-pink-50/70 border border-pink-100 px-5 py-4 flex-1">
          <p className="text-xs font-semibold text-gray-800 mb-1">
            Start here · Wardrobe upload
          </p>
          <p className="text-xs text-gray-600 mb-3">
            Add 20–30 favorite pieces so StyleSync can learn your real closet.
          </p>
          <button
            onClick={() => navigate('/wardrobe')}
            className="inline-flex items-center justify-center px-4 py-2 rounded-full text-sm font-semibold text-white shadow-sm hover:opacity-90 transition"
            style={{
              background: 'linear-gradient(135deg, #f43f7f, #ec4899)',
            }}
          >
            Start wardrobe digitization
          </button>
        </div>

        <div className="rounded-2xl bg-white border border-gray-100 px-5 py-4 w-full max-w-xs">
          <p className="text-xs font-medium text-gray-700 mb-2">
            Your snapshot
          </p>
          <p className="text-xs text-gray-600">
            • Color season:{' '}
            <span className="font-semibold">
              {colorSeason ? (SEASON_LABELS[colorSeason] ?? colorSeason) : '—'}
            </span>
            {!colorSeason && (
              <>
                <br />
                <button
                  type="button"
                  onClick={() => navigate('/color-quiz')}
                  className="text-pink-500 hover:underline mt-1"
                >
                  Take the quiz →
                </button>
              </>
            )}
            <br />
            • Trend coverage: <span className="font-semibold">Coming soon</span>
          </p>
        </div>
      </div>

      <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {features.map((feature) => (
          <article
            key={feature.title}
            className="bg-white rounded-3xl shadow-lg px-5 py-5 flex flex-col justify-between border border-gray-100"
          >
            <div>
              <h2
                className="text-lg font-semibold text-gray-900 mb-2"
                style={{ fontFamily: 'Georgia, serif' }}
              >
                {feature.title}
              </h2>
              <p className="text-sm text-gray-600 mb-4">{feature.description}</p>
            </div>
            <button
              onClick={() => navigate(feature.route)}
              className="inline-flex items-center justify-center px-4 py-2 rounded-full text-sm font-semibold text-pink-600 bg-pink-50 hover:bg-pink-100 transition self-start"
            >
              {feature.cta}
              <span className="ml-1">↗</span>
            </button>
          </article>
        ))}
      </section>
    </AppShell>
  )
}

export default Dashboard

