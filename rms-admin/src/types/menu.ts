import type { ID } from './common'

export interface MenuCategory {
  id: ID
  name: string
  description?: string
  is_active?: boolean
}

export interface MenuItem {
  id: ID
  name: string
  description?: string
  price: number
  category: ID
  is_available?: boolean
}