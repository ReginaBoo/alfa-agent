import './index.css'
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MiniPanel } from './components/MiniPanel/MiniPanel'
import { isElectron } from './utils'
import { MainPanel } from './components/MainPanel/MainPanel'
import { ProjectDashboard } from './components/MainPanel/pages/ProjectDashboard/ProjectDashboard';
import { Dashboard } from './components/MainPanel/pages/Dashboard/Dashboard';
import { LoginPage } from './components/LoginPage/LoginPage';
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'


function AuthChecker() {
  const navigate = useNavigate()

  useEffect(() => {
    axios.defaults.withCredentials = true

    axios
      .get('/api/auth/me', {
        withCredentials: true,
      })
      .catch(() => {
        navigate('/login')
      })
  }, [navigate])

  return null
}

function App() {
  return (
    <div>
      {isElectron ? <MiniPanel /> : <BrowserRouter>
        <AuthChecker />
          <Routes>
            {/* 1. Страница логина без MainPanel */}
            <Route path="/login" element={<LoginPage />} />

            {/* 2. Все остальные страницы оборачиваем в MainPanel */}
            <Route
              path="/*"
              element={
                <MainPanel>
                  <Routes>
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/project/:projectId" element={<ProjectDashboard />} />
                  </Routes>
                </MainPanel>
              }
            />
          </Routes>
      </BrowserRouter>}
    </div>
  )
}

export default App
