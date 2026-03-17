import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'

function Outfits() {
  const navigate = useNavigate()

  return (
    <AppShell
      title="Daily outfit generation"
      subtitle="The LangChain ReAct agent will call into your wardrobe, trend, and weather tools. For now, capture the inputs and preview example outfits."
    >
      <div className="grid md:grid-cols-3 gap-4 mb-2">
        <div className="md:col-span-1 space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Occasion
            </label>
            <input
              type="text"
              placeholder="e.g. client meeting, brunch, date night"
              className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-pink-400"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Weather
            </label>
            <input
              type="text"
              placeholder="68°F, partly cloudy"
              className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-pink-400"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Vibe
            </label>
            <input
              type="text"
              placeholder="modern, classic, playful..."
              className="w-full px-3 py-2 rounded-2xl border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-pink-400"
            />
          </div>
          <button
            className="w-full mt-1 px-4 py-2 rounded-full text-sm font-semibold text-white shadow-sm hover:opacity-90 transition"
            style={{
              background: 'linear-gradient(135deg, #f43f7f, #ec4899)',
            }}
          >
            Generate 4 outfits
          </button>
        </div>

        <div className="md:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="rounded-2xl border border-gray-100 bg-pink-50/60 px-4 py-3 flex flex-col justify-between"
            >
              <div>
                <p className="text-xs font-semibold text-gray-900 mb-1">
                  Outfit {i}
                </p>
                <p className="text-[11px] text-gray-600 mb-2">
                  • Top: Neutral knit sweater
                  <br />
                  • Bottom: Cream wide-leg trousers
                  <br />
                  • Layer: Camel wool blazer
                  <br />
                  • Shoes: Minimal leather loafers
                </p>
              </div>
              <p className="text-[11px] text-gray-500">
                AI reasoning and scoring will appear here once the Groq-powered ReAct
                agent and LLM-as-a-judge pipeline are wired in.
              </p>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  )
}

export default Outfits

