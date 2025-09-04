import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import api from '../lib/api'

interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_staff: boolean
  is_superuser: boolean
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<boolean>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>()(persist(
  (set) => ({
    user: null,
    isAuthenticated: false,
    isLoading: false,

    login: async (username: string, password: string) => {
      set({ isLoading: true })
      try {
        const response = await api.post('/auth/login/', {
          username,
          password
        })
        
        if (response.data.user) {
          set({
            user: response.data.user,
            isAuthenticated: true,
            isLoading: false
          })
          return true
        }
        
        set({ isLoading: false })
        return false
      } catch (error) {
        console.error('Login failed:', error)
        set({ isLoading: false })
        return false
      }
    },

    logout: async () => {
      try {
        await api.post('/auth/logout/')
      } catch (error) {
        console.error('Logout error:', error)
      } finally {
        set({
          user: null,
          isAuthenticated: false
        })
      }
    },

    checkAuth: async () => {
      set({ isLoading: true })
      try {
        const response = await api.get('/auth/user/')
        if (response.data.user) {
          set({
            user: response.data.user,
            isAuthenticated: true,
            isLoading: false
          })
        } else {
          set({
            user: null,
            isAuthenticated: false,
            isLoading: false
          })
        }
      } catch (error) {
        console.error('Auth check failed:', error)
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false
        })
      }
    },

    clearAuth: () => {
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false
      })
    }
  }),
  {
    name: 'auth-storage',
    partialize: (state) => ({
      user: state.user,
      isAuthenticated: state.isAuthenticated
    })
  }
))