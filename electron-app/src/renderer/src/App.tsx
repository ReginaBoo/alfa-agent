import './index.css'
import { MiniPanel } from './components/MiniPanel/MiniPanel'
import { isElectron } from './utils'

const WebDashboard = () => (
  <div style={{ padding: '40px', textAlign: 'center' }}>
    <h1>Alfa Logistic Web Portal</h1>
    <p>Здесь будет полная статистика, доступная через Chrome/Edge</p>
  </div>
);


function App() {
  return (
    <div>
      {isElectron ? <MiniPanel /> : <WebDashboard />}
    </div>
  )
}

export default App
