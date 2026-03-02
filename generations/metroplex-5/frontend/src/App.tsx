import { useState, useEffect } from 'react'
import Dashboard from './pages/Dashboard'
import ItemDetail from './pages/ItemDetail'

type Page =
  | { type: 'dashboard' }
  | { type: 'detail'; itemId: string }

function App() {
  const [apiStatus, setApiStatus] = useState<string>('checking...')
  const [currentPage, setCurrentPage] = useState<Page>({ type: 'dashboard' })
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  useEffect(() => {
    // Test backend connection
    fetch('/api/health')
      .then(res => res.json())
      .then(data => setApiStatus(data.status))
      .catch(() => setApiStatus('disconnected'))
  }, [])

  const navigateToDetail = (itemId: string) => {
    setCurrentPage({ type: 'detail', itemId })
  }

  const navigateToDashboard = () => {
    setCurrentPage({ type: 'dashboard' })
    // Trigger refresh when navigating back to dashboard
    setRefreshTrigger(prev => prev + 1)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <button
              onClick={navigateToDashboard}
              className="text-2xl font-bold text-gray-900 hover:text-primary transition-colors"
            >
              AI Agent Analytics Platform
            </button>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">API Status:</span>
              <span
                className={`px-2 py-1 rounded text-xs font-medium ${
                  apiStatus === 'healthy'
                    ? 'bg-green-100 text-green-800'
                    : apiStatus === 'disconnected'
                    ? 'bg-red-100 text-red-800'
                    : 'bg-yellow-100 text-yellow-800'
                }`}
              >
                {apiStatus}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {currentPage.type === 'dashboard' ? (
          <Dashboard
            onNavigateToDetail={navigateToDetail}
            refreshTrigger={refreshTrigger}
          />
        ) : (
          <ItemDetail
            itemId={currentPage.itemId}
            onNavigateBack={navigateToDashboard}
          />
        )}
      </main>
    </div>
  )
}

export default App
