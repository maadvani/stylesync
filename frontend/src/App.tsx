function App() {
  return (
    <div className="min-h-screen flex items-center justify-center"
      style={{ background: 'linear-gradient(135deg, #fff0f5 0%, #fce4ec 50%, #f8f0ff 100%)' }}>

      {/* Centered phone-width card — looks great on desktop, ready for mobile */}
      <div className="w-full max-w-sm bg-white rounded-3xl shadow-xl overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-2">
          <div className="w-10 h-10 rounded-full bg-pink-100 flex items-center justify-center">
            <span className="text-pink-500 text-lg">✦</span>
          </div>
          <span className="text-lg font-semibold text-gray-900">StyleSync</span>
          <div className="w-10" />
        </div>

        {/* Clothes rack image */}
        <div className="relative mx-4 mt-4 rounded-2xl overflow-hidden" style={{ height: '320px' }}>
          <img
            src="https://images.unsplash.com/photo-1558769132-cb1aea458c5e?w=600"
            alt="Wardrobe"
            className="w-full h-full object-cover"
          />
          <div className="absolute bottom-0 left-0 right-0 h-24"
            style={{ background: 'linear-gradient(to top, #fce4ec, transparent)' }} />
        </div>

        {/* Text content */}
        <div className="flex flex-col items-center text-center px-8 pt-6 pb-4">
          <h1 className="text-3xl font-bold italic text-gray-900 mb-3"
            style={{ fontFamily: 'Georgia, serif' }}>
            Ready to sync your style?
          </h1>
          <p className="text-gray-500 text-base mb-6">
            Digitize your wardrobe, discover your colors, and style more with less.
          </p>

          {/* Pagination dots */}
          <div className="flex gap-2 mb-6">
            <div className="w-6 h-2 rounded-full bg-pink-500" />
            <div className="w-2 h-2 rounded-full bg-pink-200" />
            <div className="w-2 h-2 rounded-full bg-pink-200" />
          </div>
        </div>

        {/* Bottom buttons */}
        <div className="flex flex-col items-center gap-3 px-6 pb-8">
          <button
            className="w-full py-4 rounded-full text-white font-semibold text-lg transition hover:opacity-90"
            style={{ background: 'linear-gradient(135deg, #f43f7f, #ec4899)' }}>
            Get Started
          </button>
          <p className="text-gray-500 text-sm">
            Already have an account?{' '}
            <span className="text-pink-500 font-semibold cursor-pointer hover:underline">
              Log In
            </span>
          </p>
        </div>

      </div>
    </div>
  )
}

export default App