import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

interface UserProfile {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  phone?: string
  role: string
}

interface SystemSettings {
  restaurant_name: string
  restaurant_address: string
  restaurant_phone: string
  restaurant_email: string
  tax_rate: number
  service_charge: number
  currency: string
  timezone: string
  order_timeout: number
  auto_accept_orders: boolean
  email_notifications: boolean
  sms_notifications: boolean
}

const TIMEZONES = [
  { value: 'UTC', label: 'UTC' },
  { value: 'America/New_York', label: 'Eastern Time' },
  { value: 'America/Chicago', label: 'Central Time' },
  { value: 'America/Denver', label: 'Mountain Time' },
  { value: 'America/Los_Angeles', label: 'Pacific Time' }
]

const CURRENCIES = [
  { value: 'USD', label: 'US Dollar ($)' },
  { value: 'EUR', label: 'Euro (€)' },
  { value: 'GBP', label: 'British Pound (£)' },
  { value: 'CAD', label: 'Canadian Dollar (C$)' }
]

export default function Settings() {
  const [activeTab, setActiveTab] = useState<'profile' | 'restaurant' | 'notifications' | 'security'>('profile')
  const [isEditing, setIsEditing] = useState(false)
  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const queryClient = useQueryClient()

  // Profile state
  const [profileForm, setProfileForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: ''
  })

  // Restaurant settings state
  const [restaurantForm, setRestaurantForm] = useState({
    restaurant_name: '',
    restaurant_address: '',
    restaurant_phone: '',
    restaurant_email: '',
    tax_rate: 0,
    service_charge: 0,
    currency: 'USD',
    timezone: 'UTC',
    order_timeout: 30
  })

  // Notification settings state
  const [notificationForm, setNotificationForm] = useState({
    auto_accept_orders: false,
    email_notifications: true,
    sms_notifications: false
  })

  // Password change state
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  })

  // Fetch user profile
  const { data: userProfile, isLoading: profileLoading } = useQuery({
    queryKey: ['user', 'profile'],
    queryFn: () => api.get('/auth/user/').then((res: any) => res.data)
  })

  // Update profile form when user data is loaded
  useEffect(() => {
    if (userProfile) {
      setProfileForm({
        first_name: userProfile.first_name || '',
        last_name: userProfile.last_name || '',
        email: userProfile.email || '',
        phone: userProfile.phone || ''
      })
    }
  }, [userProfile])

  // Fetch system settings
  const { data: systemSettings, isLoading: settingsLoading } = useQuery({
    queryKey: ['settings', 'system'],
    queryFn: () => api.get('/settings/').then((res: any) => res.data)
  })

  // Update settings forms when system data is loaded
  useEffect(() => {
    if (systemSettings) {
      setRestaurantForm({
        restaurant_name: systemSettings.restaurant_name || '',
        restaurant_address: systemSettings.restaurant_address || '',
        restaurant_phone: systemSettings.restaurant_phone || '',
        restaurant_email: systemSettings.restaurant_email || '',
        tax_rate: systemSettings.tax_rate || 0,
        service_charge: systemSettings.service_charge || 0,
        currency: systemSettings.currency || 'USD',
        timezone: systemSettings.timezone || 'UTC',
        order_timeout: systemSettings.order_timeout || 30
      })
      setNotificationForm({
        auto_accept_orders: systemSettings.auto_accept_orders || false,
        email_notifications: systemSettings.email_notifications || true,
        sms_notifications: systemSettings.sms_notifications || false
      })
    }
  }, [systemSettings])

  // Update profile mutation
  const updateProfileMutation = useMutation({
    mutationFn: (data: any) => api.patch('/auth/user/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user', 'profile'] })
      setIsEditing(false)
    }
  })

  // Update settings mutation
  const updateSettingsMutation = useMutation({
    mutationFn: (data: any) => api.patch('/settings/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'system'] })
    }
  })

  // Change password mutation
  const changePasswordMutation = useMutation({
    mutationFn: (data: any) => api.post('/auth/change-password/', data),
    onSuccess: () => {
      setShowPasswordForm(false)
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' })
    }
  })

  const handleProfileSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateProfileMutation.mutate(profileForm)
  }

  const handleRestaurantSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateSettingsMutation.mutate(restaurantForm)
  }

  const handleNotificationSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateSettingsMutation.mutate(notificationForm)
  }

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      alert('New passwords do not match')
      return
    }
    changePasswordMutation.mutate({
      old_password: passwordForm.current_password,
      new_password: passwordForm.new_password
    })
  }

  const TabButton = ({ id, label, isActive, onClick }: {
    id: string
    label: string
    isActive: boolean
    onClick: () => void
  }) => (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium rounded-lg ${
        isActive
          ? 'bg-blue-600 text-white'
          : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
      }`}
    >
      {label}
    </button>
  )

  const FormField = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      {children}
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
      </div>

      {/* Tab Navigation */}
      <div className="flex space-x-2">
        <TabButton
          id="profile"
          label="Profile"
          isActive={activeTab === 'profile'}
          onClick={() => setActiveTab('profile')}
        />
        <TabButton
          id="restaurant"
          label="Restaurant"
          isActive={activeTab === 'restaurant'}
          onClick={() => setActiveTab('restaurant')}
        />
        <TabButton
          id="notifications"
          label="Notifications"
          isActive={activeTab === 'notifications'}
          onClick={() => setActiveTab('notifications')}
        />
        <TabButton
          id="security"
          label="Security"
          isActive={activeTab === 'security'}
          onClick={() => setActiveTab('security')}
        />
      </div>

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-lg font-medium text-gray-900">Profile Information</h2>
            <button
              onClick={() => setIsEditing(!isEditing)}
              className="px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-700"
            >
              {isEditing ? 'Cancel' : 'Edit'}
            </button>
          </div>

          {profileLoading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : (
            <form onSubmit={handleProfileSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField label="First Name">
                  <input
                    type="text"
                    value={profileForm.first_name}
                    onChange={(e) => setProfileForm({ ...profileForm, first_name: e.target.value })}
                    disabled={!isEditing}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  />
                </FormField>

                <FormField label="Last Name">
                  <input
                    type="text"
                    value={profileForm.last_name}
                    onChange={(e) => setProfileForm({ ...profileForm, last_name: e.target.value })}
                    disabled={!isEditing}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  />
                </FormField>

                <FormField label="Email">
                  <input
                    type="email"
                    value={profileForm.email}
                    onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })}
                    disabled={!isEditing}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  />
                </FormField>

                <FormField label="Phone">
                  <input
                    type="tel"
                    value={profileForm.phone}
                    onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })}
                    disabled={!isEditing}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  />
                </FormField>
              </div>

              {isEditing && (
                <div className="flex justify-end space-x-3">
                  <button
                    type="button"
                    onClick={() => setIsEditing(false)}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={updateProfileMutation.isPending}
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {updateProfileMutation.isPending ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              )}
            </form>
          )}
        </div>
      )}

      {/* Restaurant Tab */}
      {activeTab === 'restaurant' && (
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-lg font-medium text-gray-900 mb-6">Restaurant Settings</h2>

          {settingsLoading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : (
            <form onSubmit={handleRestaurantSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField label="Restaurant Name">
                  <input
                    type="text"
                    value={restaurantForm.restaurant_name}
                    onChange={(e) => setRestaurantForm({ ...restaurantForm, restaurant_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </FormField>

                <FormField label="Phone">
                  <input
                    type="tel"
                    value={restaurantForm.restaurant_phone}
                    onChange={(e) => setRestaurantForm({ ...restaurantForm, restaurant_phone: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </FormField>

                <FormField label="Email">
                  <input
                    type="email"
                    value={restaurantForm.restaurant_email}
                    onChange={(e) => setRestaurantForm({ ...restaurantForm, restaurant_email: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </FormField>

                <FormField label="Currency">
                  <select
                    value={restaurantForm.currency}
                    onChange={(e) => setRestaurantForm({ ...restaurantForm, currency: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    {CURRENCIES.map(currency => (
                      <option key={currency.value} value={currency.value}>{currency.label}</option>
                    ))}
                  </select>
                </FormField>

                <FormField label="Timezone">
                  <select
                    value={restaurantForm.timezone}
                    onChange={(e) => setRestaurantForm({ ...restaurantForm, timezone: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    {TIMEZONES.map(timezone => (
                      <option key={timezone.value} value={timezone.value}>{timezone.label}</option>
                    ))}
                  </select>
                </FormField>

                <FormField label="Tax Rate (%)">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="100"
                    value={restaurantForm.tax_rate}
                    onChange={(e) => setRestaurantForm({ ...restaurantForm, tax_rate: parseFloat(e.target.value) || 0 })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </FormField>

                <FormField label="Service Charge (%)">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="100"
                    value={restaurantForm.service_charge}
                    onChange={(e) => setRestaurantForm({ ...restaurantForm, service_charge: parseFloat(e.target.value) || 0 })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </FormField>

                <FormField label="Order Timeout (minutes)">
                  <input
                    type="number"
                    min="1"
                    value={restaurantForm.order_timeout}
                    onChange={(e) => setRestaurantForm({ ...restaurantForm, order_timeout: parseInt(e.target.value) || 30 })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </FormField>
              </div>

              <FormField label="Address">
                <textarea
                  value={restaurantForm.restaurant_address}
                  onChange={(e) => setRestaurantForm({ ...restaurantForm, restaurant_address: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </FormField>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={updateSettingsMutation.isPending}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {updateSettingsMutation.isPending ? 'Saving...' : 'Save Settings'}
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* Notifications Tab */}
      {activeTab === 'notifications' && (
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-lg font-medium text-gray-900 mb-6">Notification Settings</h2>

          <form onSubmit={handleNotificationSubmit} className="space-y-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-900">Auto Accept Orders</h3>
                  <p className="text-sm text-gray-500">Automatically accept new orders without manual confirmation</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={notificationForm.auto_accept_orders}
                    onChange={(e) => setNotificationForm({ ...notificationForm, auto_accept_orders: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-900">Email Notifications</h3>
                  <p className="text-sm text-gray-500">Receive email notifications for orders and updates</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={notificationForm.email_notifications}
                    onChange={(e) => setNotificationForm({ ...notificationForm, email_notifications: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-900">SMS Notifications</h3>
                  <p className="text-sm text-gray-500">Receive SMS notifications for urgent updates</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={notificationForm.sms_notifications}
                    onChange={(e) => setNotificationForm({ ...notificationForm, sms_notifications: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={updateSettingsMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {updateSettingsMutation.isPending ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Security Tab */}
      {activeTab === 'security' && (
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-medium text-gray-900">Password</h2>
              <button
                onClick={() => setShowPasswordForm(!showPasswordForm)}
                className="px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-700"
              >
                {showPasswordForm ? 'Cancel' : 'Change Password'}
              </button>
            </div>

            {showPasswordForm && (
              <form onSubmit={handlePasswordSubmit} className="space-y-4">
                <FormField label="Current Password">
                  <input
                    type="password"
                    value={passwordForm.current_password}
                    onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </FormField>

                <FormField label="New Password">
                  <input
                    type="password"
                    value={passwordForm.new_password}
                    onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </FormField>

                <FormField label="Confirm New Password">
                  <input
                    type="password"
                    value={passwordForm.confirm_password}
                    onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </FormField>

                <div className="flex justify-end space-x-3">
                  <button
                    type="button"
                    onClick={() => setShowPasswordForm(false)}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={changePasswordMutation.isPending}
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {changePasswordMutation.isPending ? 'Changing...' : 'Change Password'}
                  </button>
                </div>
              </form>
            )}
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Account Information</h2>
            <div className="space-y-3">
              <div className="flex justify-between">
                 <span className="text-sm text-gray-500">Username:</span>
                 <span className="text-sm font-medium">{(userProfile as UserProfile)?.username}</span>
               </div>
               <div className="flex justify-between">
                 <span className="text-sm text-gray-500">Role:</span>
                 <span className="text-sm font-medium capitalize">{(userProfile as UserProfile)?.role}</span>
               </div>
               <div className="flex justify-between">
                 <span className="text-sm text-gray-500">Account ID:</span>
                 <span className="text-sm font-medium">{(userProfile as UserProfile)?.id}</span>
               </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}