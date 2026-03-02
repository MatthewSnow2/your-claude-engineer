import { useState, useEffect } from 'react'
import { apiClient, type Item, type User } from '../lib/api'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorMessage from '../components/ErrorMessage'
import Card from '../components/Card'
import StatusBadge from '../components/StatusBadge'
import Modal from '../components/Modal'
import ItemForm from '../components/ItemForm'
import Toast, { type ToastType } from '../components/Toast'

interface ItemDetailProps {
  itemId: string
  onNavigateBack: () => void
}

function ItemDetail({ itemId, onNavigateBack }: ItemDetailProps) {
  const [item, setItem] = useState<Item | null>(null)
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        const [itemData, usersData] = await Promise.all([
          apiClient.get<Item>(`/items/${itemId}`),
          apiClient.get<User[]>('/users'),
        ])
        // Merge user data onto item
        const userMap = new Map(usersData.map(u => [u.id, u]))
        const itemWithUser = {
          ...itemData,
          user: userMap.get(itemData.user_id)
        }
        setItem(itemWithUser)
        setUsers(usersData)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch item')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [itemId, retryCount])

  const handleRetry = () => {
    setRetryCount(prev => prev + 1)
  }

  const handleUpdateItem = async (data: {
    title: string
    description: string
    status: 'active' | 'completed' | 'pending'
    user_id: string
  }) => {
    if (!item) return

    // Store original item for rollback
    const originalItem = { ...item }

    // Optimistically update UI
    const userMap = new Map(users.map(u => [u.id, u]))
    const optimisticItem: Item = {
      ...item,
      title: data.title,
      description: data.description,
      status: data.status,
      user_id: data.user_id,
      user: userMap.get(data.user_id)
    }
    setItem(optimisticItem)
    setIsEditModalOpen(false)

    try {
      // Only send allowed update fields (exclude user_id - backend ALLOWED_UPDATE_FIELDS doesn't include it)
      const updatePayload = {
        title: data.title,
        description: data.description,
        status: data.status
      }
      const updatedItem = await apiClient.put<Item>(`/items/${itemId}`, updatePayload)
      // Update with real server response
      const itemWithUser = {
        ...updatedItem,
        user: userMap.get(updatedItem.user_id)
      }
      setItem(itemWithUser)
      setToast({ message: 'Item updated successfully!', type: 'success' })
    } catch (err) {
      // Revert to original on error
      setItem(originalItem)
      setToast({
        message: err instanceof Error ? err.message : 'Failed to update item',
        type: 'error'
      })
      setIsEditModalOpen(true)
    }
  }

  const handleDeleteItem = async () => {
    if (!confirm('Are you sure you want to delete this item?')) return

    setIsDeleting(true)
    try {
      await apiClient.delete(`/items/${itemId}`)
      setToast({ message: 'Item deleted successfully!', type: 'success' })
      // Navigate back after brief delay to show toast
      setTimeout(() => {
        onNavigateBack()
      }, 500)
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : 'Failed to delete item',
        type: 'error'
      })
      setIsDeleting(false)
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  if (loading) {
    return <LoadingSpinner fullPage />
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={handleRetry} />
  }

  if (!item) {
    return <ErrorMessage message="Item not found" />
  }

  return (
    <div>
      {/* Breadcrumb */}
      <div className="mb-6">
        <button
          onClick={onNavigateBack}
          className="text-primary hover:text-blue-600 font-medium flex items-center gap-1"
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
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Back to Dashboard
        </button>
      </div>

      {/* Item Header */}
      <div className="mb-8">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">{item.title}</h1>
            <div className="flex items-center gap-3">
              <StatusBadge status={item.status} />
              <span className="text-sm text-gray-500">
                Created {formatDate(item.created_at)}
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setIsEditModalOpen(true)}
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
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                />
              </svg>
              Edit
            </button>
            <button
              onClick={handleDeleteItem}
              disabled={isDeleting}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-medium flex items-center gap-2 disabled:opacity-50"
            >
              {isDeleting ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                  Deleting...
                </>
              ) : (
                <>
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
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  </svg>
                  Delete
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Item Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card title="Description">
            {item.description ? (
              <p className="text-gray-700 whitespace-pre-wrap">{item.description}</p>
            ) : (
              <p className="text-gray-500 italic">No description provided</p>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Details">
            <dl className="space-y-3">
              <div>
                <dt className="text-sm font-medium text-gray-500">Status</dt>
                <dd className="mt-1">
                  <StatusBadge status={item.status} />
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Assigned To</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {item.user ? (
                    <div>
                      <p className="font-medium">{item.user.name}</p>
                      <p className="text-gray-600">{item.user.email}</p>
                    </div>
                  ) : (
                    'Unassigned'
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Created</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatDate(item.created_at)}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Item ID</dt>
                <dd className="mt-1 text-sm text-gray-900">#{item.id}</dd>
              </div>
            </dl>
          </Card>
        </div>
      </div>

      {/* Edit Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        title="Edit Item"
      >
        <ItemForm
          item={item}
          users={users}
          onSubmit={handleUpdateItem}
          onCancel={() => setIsEditModalOpen(false)}
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

export default ItemDetail
