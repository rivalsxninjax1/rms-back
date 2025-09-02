// API Configuration
const API_BASE_URL = window.location.origin;
const API_ENDPOINTS = {
    // Authentication
    login: '/accounts/api/login/',
    register: '/accounts/api/register/',
    logout: '/accounts/api/logout/',
    profile: '/accounts/api/profile/',
    
    // Menu
    menu: '/api/display/',
    categories: '/api/categories/',
    menuItems: '/api/items/',
    
    // Cart
    cart: '/api/carts/',
    cartItems: '/api/carts/',
    cartClear: '/api/carts/clear/',
    cartAddItem: '/api/carts/add_item/',
    cartUpdateItem: '/api/carts/update_item/',
    cartRemoveItem: '/api/carts/remove_item/',
    
    // Orders
    orders: '/api/orders/',
    orderCreate: '/api/orders/create/',
    
    // Payments
    paymentIntent: '/api/payments/create-payment-intent/',
    paymentConfirm: '/api/payments/confirm-payment/',
};

// API Client Class
class APIClient {
    constructor() {
        this.token = localStorage.getItem('authToken');
        this.csrfToken = this.getCSRFToken();
    }

    // Get CSRF token from cookies
    getCSRFToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Get default headers
    getHeaders(includeAuth = true) {
        const headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken,
        };

        if (includeAuth && this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        return headers;
    }

    // Generic request method
    async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;
        const config = {
            credentials: 'include',
            headers: this.getHeaders(options.includeAuth !== false),
            ...options,
        };

        try {
            const response = await fetch(url, config);
            
            // Handle different response types
            let data;
            const contentType = response.headers.get('content-type');
            
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                data = await response.text();
            }

            if (!response.ok) {
                throw new Error(data.message || data.detail || `HTTP error! status: ${response.status}`);
            }

            return { data, status: response.status, response };
        } catch (error) {
            console.error('API Request Error:', error);
            throw error;
        }
    }

    // GET request
    async get(endpoint, params = {}) {
        const url = new URL(`${API_BASE_URL}${endpoint}`);
        Object.keys(params).forEach(key => {
            if (params[key] !== null && params[key] !== undefined) {
                url.searchParams.append(key, params[key]);
            }
        });
        
        return this.request(url.pathname + url.search, {
            method: 'GET',
        });
    }

    // POST request
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    // PUT request
    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    // PATCH request
    async patch(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    // DELETE request
    async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE',
        });
    }

    // Set authentication token
    setToken(token) {
        this.token = token;
        if (token) {
            localStorage.setItem('authToken', token);
        } else {
            localStorage.removeItem('authToken');
        }
    }

    // Clear authentication
    clearAuth() {
        this.token = null;
        localStorage.removeItem('authToken');
    }
}

// Create global API client instance
const api = new APIClient();

// Authentication API methods
const authAPI = {
    async login(credentials) {
        const result = await api.post(API_ENDPOINTS.login, credentials);
        if (result.data.access) {
            api.setToken(result.data.access);
        }
        return result;
    },

    async register(userData) {
        const result = await api.post(API_ENDPOINTS.register, userData);
        if (result.data.access) {
            api.setToken(result.data.access);
        }
        return result;
    },

    async logout() {
        try {
            await api.post(API_ENDPOINTS.logout);
        } catch (error) {
            console.warn('Logout API call failed:', error);
        } finally {
            api.clearAuth();
        }
    },

    async getProfile() {
        return api.get(API_ENDPOINTS.profile);
    },

    isAuthenticated() {
        return !!api.token;
    }
};

// Menu API methods
const menuAPI = {
    async getCategories() {
        return api.get(API_ENDPOINTS.categories);
    },

    async getMenuItems(categoryId = null) {
        const params = categoryId ? { category: categoryId } : {};
        return api.get(API_ENDPOINTS.menuItems, params);
    },

    async getMenuItem(itemId) {
        return api.get(`${API_ENDPOINTS.menuItems}${itemId}/`);
    },

    async searchItems(query) {
        return api.get(API_ENDPOINTS.menuItems, { search: query });
    }
};

// Cart API methods
const cartAPI = {
    async getCart() {
        return api.get(API_ENDPOINTS.cart);
    },

    async addItem(itemData) {
        return api.post(API_ENDPOINTS.cartAddItem, itemData);
    },

    async updateItem(itemId, data) {
        return api.post(API_ENDPOINTS.cartUpdateItem, { item_id: itemId, ...data });
    },

    async removeItem(itemId) {
        return api.post(API_ENDPOINTS.cartRemoveItem, { item_id: itemId });
    },

    async clearCart() {
        return api.post(API_ENDPOINTS.cartClear);
    },

    async getCartItems() {
        return api.get(API_ENDPOINTS.cartItems);
    }
};

// Orders API methods
const ordersAPI = {
    async createOrder(orderData) {
        return api.post(API_ENDPOINTS.orderCreate, orderData);
    },

    async getOrders() {
        return api.get(API_ENDPOINTS.orders);
    },

    async getOrder(orderId) {
        return api.get(`${API_ENDPOINTS.orders}${orderId}/`);
    }
};

// Payments API methods
const paymentsAPI = {
    async createPaymentIntent(amount, currency = 'usd') {
        return api.post(API_ENDPOINTS.paymentIntent, {
            amount: Math.round(amount * 100), // Convert to cents
            currency
        });
    },

    async confirmPayment(paymentIntentId, paymentMethodId) {
        return api.post(API_ENDPOINTS.paymentConfirm, {
            payment_intent_id: paymentIntentId,
            payment_method_id: paymentMethodId
        });
    }
};

// Utility functions
const apiUtils = {
    // Handle API errors with user-friendly messages
    handleError(error) {
        console.error('API Error:', error);
        
        let message = 'An unexpected error occurred. Please try again.';
        
        if (error.message) {
            if (error.message.includes('401')) {
                message = 'Please log in to continue.';
                // Redirect to login or show login modal
                window.dispatchEvent(new CustomEvent('auth:required'));
            } else if (error.message.includes('403')) {
                message = 'You do not have permission to perform this action.';
            } else if (error.message.includes('404')) {
                message = 'The requested resource was not found.';
            } else if (error.message.includes('500')) {
                message = 'Server error. Please try again later.';
            } else {
                message = error.message;
            }
        }
        
        return message;
    },

    // Show loading state
    showLoading() {
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.classList.add('show');
        }
    },

    // Hide loading state
    hideLoading() {
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.classList.remove('show');
        }
    },

    // Show toast notification
    showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;

        toastContainer.appendChild(toast);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 5000);
    }
};

// Export for use in other modules
window.api = api;
window.authAPI = authAPI;
window.menuAPI = menuAPI;
window.cartAPI = cartAPI;
window.ordersAPI = ordersAPI;
window.paymentsAPI = paymentsAPI;
window.apiUtils = apiUtils;

// Initialize API client
document.addEventListener('DOMContentLoaded', () => {
    // Update CSRF token on page load
    api.csrfToken = api.getCSRFToken();
    
    // Listen for auth required events
    window.addEventListener('auth:required', () => {
        // Show login modal or redirect
        const loginBtn = document.getElementById('loginBtn');
        if (loginBtn) {
            loginBtn.click();
        }
    });
});