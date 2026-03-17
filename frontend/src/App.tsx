import { Routes, Route } from 'react-router-dom'
import Onboarding from './pages/Onboarding'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Dashboard from './pages/Dashboard'
import Wardrobe from './pages/Wardrobe'
import ColorQuiz from './pages/ColorQuiz'
import Trends from './pages/Trends'
import Shopping from './pages/Shopping'
import Outfits from './pages/Outfits'
import Analytics from './pages/Analytics'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Onboarding />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/wardrobe" element={<Wardrobe />} />
      <Route path="/color-quiz" element={<ColorQuiz />} />
      <Route path="/trends" element={<Trends />} />
      <Route path="/shopping" element={<Shopping />} />
      <Route path="/outfits" element={<Outfits />} />
      <Route path="/analytics" element={<Analytics />} />
    </Routes>
  )
}

export default App