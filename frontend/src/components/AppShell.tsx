import type { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

type AppShellProps = {
  title: string
  subtitle?: string
  children: ReactNode
}

const navItems = [
  { label: 'Wardrobe', to: '/wardrobe' },
  { label: 'Color', to: '/color-quiz' },
  { label: 'Trends', to: '/trends' },
  { label: 'Shopping', to: '/shopping' },
  { label: 'Outfits', to: '/outfits' },
  { label: 'Analytics', to: '/analytics' },
]

function AppShell({ title, subtitle, children }: AppShellProps) {
  const navigate = useNavigate()

  return (
    <div
      className="min-h-screen"
      style={{
        background:
          'radial-gradient(circle at top, #ffe3f3 0%, #fdf2ff 40%, #ffffff 76%)',
      }}
    >
      <div className="max-w-6xl mx-auto px-4 md:px-8 py-5 md:py-8">
        {/* Top bar */}
        <header className="flex items-center justify-between gap-4 mb-6 md:mb-8">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2"
          >
            <div className="w-9 h-9 rounded-full bg-pink-100 flex items-center justify-center shadow-sm">
              <span className="text-pink-500 text-lg">✦</span>
            </div>
            <span
              className="text-lg md:text-xl font-semibold text-gray-900 tracking-tight"
              style={{ fontFamily: 'Georgia, serif' }}
            >
              StyleSync
            </span>
          </button>

          <nav className="hidden md:flex items-center gap-4 text-sm font-medium">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  [
                    'px-3 py-1.5 rounded-full transition-colors',
                    isActive
                      ? 'bg-pink-500 text-white shadow-sm'
                      : 'text-gray-600 hover:bg-pink-50',
                  ].join(' ')
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/login')}
              className="hidden md:inline-flex text-xs text-gray-500 hover:text-gray-700"
            >
              Log out
            </button>
            <div className="w-8 h-8 rounded-full bg-pink-100 flex items-center justify-center text-xs text-pink-500">
              ME
            </div>
          </div>
        </header>

        {/* Mobile nav */}
        <nav className="md:hidden flex items-center gap-2 mb-5 overflow-x-auto pb-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                [
                  'whitespace-nowrap px-3 py-1.5 rounded-full text-xs font-medium transition-colors',
                  isActive
                    ? 'bg-pink-500 text-white shadow-sm'
                    : 'text-gray-600 bg-white/70 border border-pink-100',
                ].join(' ')
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Main card */}
        <main className="bg-white/80 backdrop-blur-sm rounded-3xl shadow-xl px-5 py-6 md:px-8 md:py-8">
          <div className="mb-6">
            <p className="text-[10px] md:text-xs tracking-[0.2em] uppercase text-pink-500 mb-2">
              Buy less. Style more.
            </p>
            <h1
              className="text-2xl md:text-3xl font-bold text-gray-900 mb-2"
              style={{ fontFamily: 'Georgia, serif' }}
            >
              {title}
            </h1>
            {subtitle && (
              <p className="text-xs md:text-sm text-gray-600 max-w-2xl">
                {subtitle}
              </p>
            )}
          </div>

          {children}
        </main>
      </div>
    </div>
  )
}

export default AppShell

