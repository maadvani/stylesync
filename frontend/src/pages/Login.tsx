import { useNavigate } from 'react-router-dom'

function Login() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex items-center justify-center"
      style={{ background: 'linear-gradient(135deg, #fff0f5 0%, #fce4ec 50%, #f8f0ff 100%)' }}>

      <div className="w-full max-w-sm bg-white rounded-3xl shadow-xl overflow-hidden px-8 py-10">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <button onClick={() => navigate('/')}
            className="text-gray-400 hover:text-gray-600 text-xl">←</button>
          <span className="text-lg font-semibold text-gray-900">StyleSync</span>
          <div className="w-6" />
        </div>

        {/* Title */}
        <h1 className="text-3xl font-bold text-gray-900 mb-1"
          style={{ fontFamily: 'Georgia, serif' }}>
          Welcome back
        </h1>
        <p className="text-gray-500 text-sm mb-8">Log in to your account</p>

        {/* Form */}
        <div className="flex flex-col gap-4">
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1 block">Email</label>
            <input
              type="email"
              placeholder="you@email.com"
              className="w-full px-4 py-3 rounded-2xl border border-gray-200 text-gray-900 text-sm focus:outline-none focus:border-pink-400"
            />
          </div>

          <div>
            <label className="text-sm font-medium text-gray-700 mb-1 block">Password</label>
            <input
              type="password"
              placeholder="••••••••"
              className="w-full px-4 py-3 rounded-2xl border border-gray-200 text-gray-900 text-sm focus:outline-none focus:border-pink-400"
            />
          </div>

          <p className="text-right text-xs text-pink-500 cursor-pointer hover:underline">
            Forgot password?
          </p>

          <button
            className="w-full py-4 rounded-full text-white font-semibold text-lg mt-2 transition hover:opacity-90"
            style={{ background: 'linear-gradient(135deg, #f43f7f, #ec4899)' }}>
            Log In
          </button>
        </div>

        {/* Divider */}
        <div className="flex items-center gap-3 my-6">
          <div className="flex-1 h-px bg-gray-200" />
          <span className="text-xs text-gray-400">or</span>
          <div className="flex-1 h-px bg-gray-200" />
        </div>

        {/* Sign up link */}
        <p className="text-center text-gray-500 text-sm">
          Don't have an account?{' '}
          <span className="text-pink-500 font-semibold cursor-pointer hover:underline">
            Sign Up
          </span>
        </p>

      </div>
    </div>
  )
}

export default Login