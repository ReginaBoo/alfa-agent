import './index.css'
import { MiniPanel } from './components/MiniPanel/MiniPanel'
import { isElectron } from './utils'
import { MainPanel } from './components/MainPanel/MainPanel'



function App() {
  return (
    <div>
      {isElectron ? <MiniPanel /> : <MainPanel />}
    </div>
  )
}

export default App
