import { useState, useEffect } from 'react'
import { apiClient, type Item, type User } from '../lib/api'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorMessage from '../components/ErrorMessage'
import Card from '../components/Card'
import ItemCard from '../components/ItemCard'
import Modal from '../components/Modal'
import ItemForm from '../components/ItemForm'
import Toast, { type ToastType } from '../components/Toast'

interface DashboardProps {
  onNavigateToDetail: (itemId: string) => void
  refreshTrigger?: number
}

function Dashboard({ onNavigateToDetail, refreshTrigger }: DashboardProps) {
  const [items, setItems] = useState<Item[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null)

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [itemsData, usersData] = await Promise.all([
        apiClient.get<Item[]>('/items'),
        apiClient.get<User[]>('/users'),
      ])
      // Merge user data onto items
      const userMap = new Map(usersData.map(u => [u.id, u]))
      const itemsWithUsers = itemsData.map(item => ({
        ...item,
        user: userMap.get(item.user_id)
      }))
      setItems(itemsWithUsers)
      setUsers(usersData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [refreshTrigger])

  const handleCreateItem = async (data: {
    title: string
    description: string
    status: 'active' | 'completed' | 'pending'
    user_id: string
  }) => {
    // Prevent double-submission
    if (isSubmitting) return
    setIsSubmitting(true)

    // Create optimistic item with temporary ID
    const userMap = new Map(users.map(u => [u.id, u]))
    const optimisticItem: Item = {
      id: `temp-${Date.now()}`,
      title: data.title,
      description: data.description,
      status: data.status,
      user_id: data.user_id,
      created_at: new Date().toISOString(),
      user: userMap.get(data.user_id)
    }

    // Optimistically add to list
    setItems([optimisticItem, ...items])
    setIsCreateModalOpen(false)

    try {
      const newItem = await apiClient.post<Item>('/items', data)
      // Replace optimistic item with real item
      const itemWithUser = {
        ...newItem,
        user: userMap.get(newItem.user_id)
      }
      setItems(prevItems =>
        prevItems.map(item => item.id === optimisticItem.id ? itemWithUser : item)
      )
      setToast({ message: 'Item created successfully!', type: 'success' })
    } catch (err) {
      // Revert optimistic update on error
      setItems(prevItems => prevItems.filter(item => item.id !== optimisticItem.id))
      setToast({
        message: err instanceof Error ? err.message : 'Failed to create item',
        type: 'error'
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  if (loading) {
    return <LoadingSpinner fullPage />
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={fetchData} />
  }

  const totalItems = items.length
  const activeItems = items.filter((item) => item.status === 'active').length
  const completedItems = items.filter((item) => item.status === 'completed').length

  return (
    <div>
      <div className="mb-8 flex justify-between items-start">
        <div>
          <h2 className="text-3xl font-bold text-gray-900 mb-2">Dashboard</h2>
          <p className="text-gray-600">
            Welcome to the AI Agent Analytics Platform. Monitor and manage your items in real-time.
          </p>
        </div>
        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 font-medium flex items-center gap-2"
        >
          <svg
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>
          Create New Item
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Card>
          <h3 className="text-sm font-medium text-gray-600 mb-1">Total Items</h3>
          <p className="text-3xl font-bold text-primary">{totalItems}</p>
          <p className="text-xs text-gray-500 mt-1">All tracked items</p>
        </Card>

        <Card>
          <h3 className="text-sm font-medium text-gray-600 mb-1">Active Items</h3>
          <p className="text-3xl font-bold text-blue-600">{activeItems}</p>
          <p className="text-xs text-gray-500 mt-1">Currently in progress</p>
        </Card>

        <Card>
          <h3 className="text-sm font-medium text-gray-600 mb-1">Completed Items</h3>
          <p className="text-3xl font-bold text-accent">{completedItems}</p>
          <p className="text-xs text-gray-500 mt-1">Successfully finished</p>
        </Card>
      </div>

      {/* Items List */}
      <div>
        <h3 className="text-xl font-semibold text-gray-900 mb-4">All Items</h3>
        {items.length === 0 ? (
          <Card>
            <div className="text-center py-8">
              <p className="text-gray-500 mb-4">No items yet. Create your first item to get started!</p>
              <button
                onClick={() => setIsCreateModalOpen(true)}
                className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 font-medium"
              >
                Create Item
              </button>
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                onClick={(item) => onNavigateToDetail(item.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create New Item"
      >
        <ItemForm
          users={users}
          onSubmit={handleCreateItem}
          onCancel={() => setIsCreateModalOpen(false)}
        />
      </Modal>

      {/* Toast Notification */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  )
}

export default Dashboard
