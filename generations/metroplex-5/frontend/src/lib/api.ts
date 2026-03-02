/**
 * API client for communicating with the FastAPI backend
 */

const API_BASE_URL = '/api'

// Type definitions
export interface User {
  id: string
  name: string
  email: string
  created_at: string
}

export interface Item {
  id: string
  title: string
  description: string | null
  status: 'active' | 'completed' | 'pending'
  user_id: string
  created_at: string
  user?: User
}

export class ApiClient {
  private baseUrl: string
  private defaultTimeout: number = 10000 // 10 seconds

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  /**
   * Fetch with timeout support
   */
  private async fetchWithTimeout(
    url: string,
    options: RequestInit = {},
    timeout: number = this.defaultTimeout
  ): Promise<Response> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
      const response = await fetch(url, { ...options, signal: controller.signal })
      return response
    } catch (error) {
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          throw new Error('Request timed out. Please check your connection and try again.')
        }
        if (error.name === 'TypeError') {
          throw new Error('Network error. Please check your internet connection.')
        }
      }
      throw error
    } finally {
      clearTimeout(timeoutId)
    }
  }

  /**
   * Parse error response and return user-friendly message
   */
  private async parseErrorResponse(response: Response): Promise<string> {
    const errorBody = await response.text()
    let errorMessage = `API error: ${response.statusText}`

    if (response.status === 404) {
      return 'Resource not found.'
    }
    if (response.status === 500) {
      return 'Server error. Please try again later.'
    }

    try {
      const errorData = JSON.parse(errorBody)
      errorMessage = errorData.detail || errorData.message || errorMessage
    } catch {
      errorMessage = errorBody || errorMessage
    }
    return errorMessage
  }

  async get<T>(endpoint: string): Promise<T> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}${endpoint}`)
    if (!response.ok) {
      const errorMessage = await this.parseErrorResponse(response)
      throw new Error(errorMessage)
    }
    return response.json()
  }

  async post<T>(endpoint: string, data: unknown): Promise<T> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) {
      const errorMessage = await this.parseErrorResponse(response)
      throw new Error(errorMessage)
    }
    return response.json()
  }

  async put<T>(endpoint: string, data: unknown): Promise<T> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}${endpoint}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) {
      const errorMessage = await this.parseErrorResponse(response)
      throw new Error(errorMessage)
    }
    return response.json()
  }

  async delete<T>(endpoint: string): Promise<T> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}${endpoint}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      const errorMessage = await this.parseErrorResponse(response)
      throw new Error(errorMessage)
    }
    return response.json()
  }

  async healthCheck(): Promise<{ status: string }> {
    return this.get('/health')
  }
}

export const apiClient = new ApiClient()
