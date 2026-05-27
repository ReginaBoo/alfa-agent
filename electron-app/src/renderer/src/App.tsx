import './index.css'
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MiniPanel } from './components/MiniPanel/MiniPanel'
import { isElectron } from './utils'
import { MainPanel } from './components/MainPanel/MainPanel'
import { ProjectDashboard } from './components/MainPanel/pages/ProjectDashboard/ProjectDashboard';
import { Dashboard } from './components/MainPanel/pages/Dashboard/Dashboard';
import { LoginPage } from './components/LoginPage/LoginPage';

function App() {
  return (
    <div>
      {isElectron ? <MiniPanel /> : <BrowserRouter>
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
                  <Route path="/project/:id" element={<ProjectDashboard />} />
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
