import AuthGate from './components/AuthGate'
import PipelineGate from './components/PipelineGate'
import DataExplorer from './components/DataExplorer'
import './index.css'

function App() {
  return (
    <AuthGate>
      <PipelineGate>
        <DataExplorer />
      </PipelineGate>
    </AuthGate>
  )
}

export default App
