import { AuthProvider } from './AuthContext'
import AuthGate from './components/AuthGate'
import PipelineGate from './components/PipelineGate'
import DataExplorer from './components/DataExplorer'
import './index.css'

function App() {
  return (
    <AuthProvider>
      <AuthGate>
        <PipelineGate>
          <DataExplorer />
        </PipelineGate>
      </AuthGate>
    </AuthProvider>
  )
}

export default App
