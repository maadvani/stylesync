import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'

function Analytics() {
  const navigate = useNavigate()

  return (
    <AppShell
      title="Wardrobe analytics"
      subtitle="Powered by your wear-tracking data and trend coverage metrics—surfacing most/least worn pieces, seasonal gaps, and color balance."
    >
      <div className="grid md:grid-cols-3 gap-4 mb-5">
        <div className="rounded-2xl bg-pink-50/70 px-4 py-3">
          <p className="text-xs text-gray-500 mb-1">Wardrobe utilization</p>
          <p className="text-2xl font-semibold text-gray-900">68%</p>
          <p className="text-[11px] text-gray-500 mt-1">
            Percentage of pieces worn at least once in the last 30 days (mock).
          </p>
        </div>
        <div className="rounded-2xl bg-pink-50/70 px-4 py-3">
          <p className="text-xs text-gray-500 mb-1">Most-worn category</p>
          <p className="text-2xl font-semibold text-gray-900">Trousers</p>
          <p className="text-[11px] text-gray-500 mt-1">
            Pulled from `times_worn` in your wardrobe items table.
          </p>
        </div>
        <div className="rounded-2xl bg-pink-50/70 px-4 py-3">
          <p className="text-xs text-gray-500 mb-1">Color palette adherence</p>
          <p className="text-2xl font-semibold text-gray-900">81%</p>
          <p className="text-[11px] text-gray-500 mt-1">
            Share of outfits that stayed within your best colors.
          </p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="rounded-2xl border border-gray-100 px-4 py-4">
          <p className="text-xs font-medium text-gray-700 mb-2">
            Seasonal coverage (mock)
          </p>
          <div className="space-y-2 text-xs text-gray-700">
            <div className="flex items-center justify-between">
              <span>Spring</span>
              <div className="flex-1 mx-3 h-1.5 rounded-full bg-pink-100 overflow-hidden">
                <div className="h-full w-3/4 bg-pink-400" />
              </div>
              <span>75%</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Summer</span>
              <div className="flex-1 mx-3 h-1.5 rounded-full bg-pink-100 overflow-hidden">
                <div className="h-full w-2/3 bg-pink-400" />
              </div>
              <span>66%</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Fall</span>
              <div className="flex-1 mx-3 h-1.5 rounded-full bg-pink-100 overflow-hidden">
                <div className="h-full w-4/5 bg-pink-400" />
              </div>
              <span>82%</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Winter</span>
              <div className="flex-1 mx-3 h-1.5 rounded-full bg-pink-100 overflow-hidden">
                <div className="h-full w-1/2 bg-pink-400" />
              </div>
              <span>52%</span>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-gray-100 px-4 py-4">
          <p className="text-xs font-medium text-gray-700 mb-2">
            Closet gaps (mock)
          </p>
          <ul className="text-xs text-gray-700 space-y-1.5">
            <li>
              • No weather-appropriate outerwear for{' '}
              <span className="font-semibold">rainy days</span>.
            </li>
            <li>
              • Limited options for{' '}
              <span className="font-semibold">business formal</span> presentations.
            </li>
            <li>
              • Strong coverage in <span className="font-semibold">casual neutrals</span>,
              few evening pieces.
            </li>
          </ul>
          <p className="text-[11px] text-gray-500 mt-3">
            These insights will eventually be generated from your outfit history +
            trend coverage tables.
          </p>
        </div>
      </div>

      <button
        onClick={() => navigate('/shopping')}
        className="mt-5 inline-flex items-center justify-center px-4 py-2 rounded-full text-sm font-semibold text-pink-600 bg-pink-50 hover:bg-pink-100 transition"
      >
        See shopping recommendations based on these gaps ↗
      </button>
    </AppShell>
  )
}

export default Analytics

