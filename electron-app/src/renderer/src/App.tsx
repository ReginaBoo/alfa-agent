import './index.css'
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MiniPanel } from './components/MiniPanel/MiniPanel'
import { isElectron } from './utils'
import { MainPanel } from './components/MainPanel/MainPanel'
import { ProjectDashboard } from './components/MainPanel/pages/ProjectDashboard/ProjectDashboard';
import { Dashboard } from './components/MainPanel/pages/Dashboard/Dashboard';


function App() {
  return (
    <div>
      {isElectron ? <MiniPanel /> : <BrowserRouter> <MainPanel>
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/project/:projectId" element={<ProjectDashboard />} />
          <Route path="*" element={<Dashboard />} />
        </Routes>
      </MainPanel></BrowserRouter>}
    </div>
  )
}

export default App
