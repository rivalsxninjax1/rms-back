// Main Application Controller
class App {
    constructor() {
        this.isInitialized = false;
        this.components = {};
        this.init();
    }

    async init() {
        try {
            // Wait for DOM to be ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.initializeApp());
            } else {
                await this.initializeApp();
            }
        } catch (error) {
            console.error('Failed to initialize app:', error);
        }
    }

    async initializeApp() {
        try {
            // Show loading state
            this.showInitialLoading();

            // Initialize components in order
            await this.initializeComponents();

            // Bind global events
            this.bindGlobalEvents();

            // Load initial data
            await this.loadInitialData();

            // Hide loading state
            this.hideInitialLoading();

            this.isInitialized = true;
            console.log('App initialized successfully');

        } catch (error) {
            console.error('App initialization failed:', error);
            this.showInitializationError();
        }
    }

    async initializeComponents() {
        // Components should already be initialized by their respective files
        // We just need to ensure they're available
        this.components = {
            auth: window.authManager,
            cart: window.cartManager,
            menu: window.menuManager,
            checkout: window.checkoutManager
        };

        // Verify all components are available
        for (const [name, component] of Object.entries(this.components)) {
            if (!component) {
                throw new Error(`Component ${name} not available`);
            }
        }
    }

    bindGlobalEvents() {
        // Global keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleGlobalKeydown(e));

        // Handle browser back/forward
        window.addEventListener('popstate', (e) => this.handlePopState(e));

        // Handle online/offline status
        window.addEventListener('online', () => this.handleOnlineStatus(true));
        window.addEventListener('offline', () => this.handleOnlineStatus(false));

        // Handle visibility change (tab switching)
        document.addEventListener('visibilitychange', () => this.handleVisibilityChange());

        // Global click handler for cart toggle
        const cartToggle = document.getElementById('cartToggle');
        if (cartToggle) {
            cartToggle.addEventListener('click', () => {
                if (this.components.cart) {
                    this.components.cart.toggleCart();
                }
            });
        }

        // Global click handler for checkout button
        const checkoutBtn = document.getElementById('checkoutBtn');
        if (checkoutBtn) {
            checkoutBtn.addEventListener('click', () => {
                if (this.components.checkout) {
                    this.components.checkout.showCheckoutModal();
                }
            });
        }

        // Search functionality
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    if (this.components.menu) {
                        this.components.menu.handleSearch(e.target.value);
                    }
                }, 300);
            });
        }

        // Mobile menu toggle
        const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
        const navMenu = document.querySelector('.nav-menu');
        if (mobileMenuToggle && navMenu) {
            mobileMenuToggle.addEventListener('click', () => {
                navMenu.classList.toggle('show');
                mobileMenuToggle.classList.toggle('active');
            });
        }
    }

    async loadInitialData() {
        try {
            // Load menu data
            if (this.components.menu) {
                await this.components.menu.loadMenu();
            }

            // Check authentication status
            if (this.components.auth) {
                await this.components.auth.checkAuthStatus();
            }

            // Load cart data
            if (this.components.cart) {
                await this.components.cart.loadCart();
            }

        } catch (error) {
            console.error('Failed to load initial data:', error);
            // Don't throw here, app can still function with limited data
        }
    }

    handleGlobalKeydown(e) {
        // Escape key - close modals
        if (e.key === 'Escape') {
            this.closeAllModals();
        }

        // Ctrl/Cmd + K - focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.focus();
            }
        }

        // Ctrl/Cmd + Shift + C - toggle cart
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'C') {
            e.preventDefault();
            if (this.components.cart) {
                this.components.cart.toggleCart();
            }
        }
    }

    handlePopState(e) {
        // Handle browser navigation
        // Close any open modals when user navigates back
        this.closeAllModals();
    }

    handleOnlineStatus(isOnline) {
        const statusIndicator = document.getElementById('connectionStatus');
        if (statusIndicator) {
            statusIndicator.textContent = isOnline ? 'Online' : 'Offline';
            statusIndicator.className = isOnline ? 'status-online' : 'status-offline';
        }

        if (!isOnline) {
            apiUtils.showToast('You are offline. Some features may not work.', 'warning');
        } else {
            apiUtils.showToast('Connection restored', 'success');
        }
    }

    handleVisibilityChange() {
        if (document.hidden) {
            // Tab is hidden - pause any timers or animations
            console.log('App hidden');
        } else {
            // Tab is visible - resume operations
            console.log('App visible');
            // Refresh cart and auth status when user returns
            if (this.components.auth) {
                this.components.auth.checkAuthStatus();
            }
        }
    }

    closeAllModals() {
        // Close all open modals
        const modals = document.querySelectorAll('.modal-overlay.show');
        modals.forEach(modal => {
            modal.classList.remove('show');
        });

        // Close cart if open
        const cartSidebar = document.getElementById('cartSidebar');
        if (cartSidebar && cartSidebar.classList.contains('open')) {
            if (this.components.cart) {
                this.components.cart.toggleCart();
            }
        }
    }

    showInitialLoading() {
        const loadingHTML = `
            <div id="appLoading" class="app-loading">
                <div class="loading-content">
                    <div class="loading-spinner"></div>
                    <h3>Loading Restaurant...</h3>
                    <p>Preparing your dining experience</p>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('afterbegin', loadingHTML);
    }

    hideInitialLoading() {
        const loading = document.getElementById('appLoading');
        if (loading) {
            loading.style.opacity = '0';
            setTimeout(() => {
                if (loading.parentNode) {
                    loading.parentNode.removeChild(loading);
                }
            }, 300);
        }
    }

    showInitializationError() {
        const errorHTML = `
            <div class="app-error">
                <div class="error-content">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>Oops! Something went wrong</h3>
                    <p>We're having trouble loading the restaurant. Please refresh the page to try again.</p>
                    <button onclick="window.location.reload()" class="btn btn-primary">
                        Refresh Page
                    </button>
                </div>
            </div>
        `;
        document.body.innerHTML = errorHTML;
    }

    // Public methods for external access
    getComponent(name) {
        return this.components[name];
    }

    isReady() {
        return this.isInitialized;
    }

    // Utility method to refresh all data
    async refresh() {
        if (!this.isInitialized) return;
        
        try {
            apiUtils.showLoading();
            await this.loadInitialData();
            apiUtils.showToast('Data refreshed', 'success');
        } catch (error) {
            console.error('Failed to refresh data:', error);
            apiUtils.showToast('Failed to refresh data', 'error');
        } finally {
            apiUtils.hideLoading();
        }
    }
}

// Initialize the app
const app = new App();

// Make app globally available
window.app = app;

// Add app loading styles
const appStyles = `
<style>
.app-loading {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    transition: opacity 0.3s ease;
}

.loading-content {
    text-align: center;
    color: white;
}

.loading-spinner {
    width: 60px;
    height: 60px;
    border: 4px solid rgba(255,255,255,0.3);
    border-top: 4px solid white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 20px;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.loading-content h3 {
    margin-bottom: 10px;
    font-size: 1.5rem;
    font-weight: 600;
}

.loading-content p {
    opacity: 0.8;
    font-size: 1rem;
}

.app-error {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: #f8f9fa;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
}

.error-content {
    text-align: center;
    max-width: 400px;
    padding: 40px;
}

.error-content i {
    font-size: 4rem;
    color: #e74c3c;
    margin-bottom: 20px;
}

.error-content h3 {
    margin-bottom: 15px;
    color: #333;
    font-size: 1.5rem;
}

.error-content p {
    margin-bottom: 25px;
    color: #666;
    line-height: 1.6;
}

.status-online {
    color: #28a745;
}

.status-offline {
    color: #dc3545;
}

.mobile-menu-toggle {
    display: none;
    flex-direction: column;
    cursor: pointer;
    padding: 5px;
}

.mobile-menu-toggle span {
    width: 25px;
    height: 3px;
    background: #333;
    margin: 3px 0;
    transition: 0.3s;
}

.mobile-menu-toggle.active span:nth-child(1) {
    transform: rotate(-45deg) translate(-5px, 6px);
}

.mobile-menu-toggle.active span:nth-child(2) {
    opacity: 0;
}

.mobile-menu-toggle.active span:nth-child(3) {
    transform: rotate(45deg) translate(-5px, -6px);
}

@media (max-width: 768px) {
    .mobile-menu-toggle {
        display: flex;
    }
    
    .nav-menu {
        display: none;
        position: absolute;
        top: 100%;
        left: 0;
        width: 100%;
        background: white;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        flex-direction: column;
        padding: 20px;
    }
    
    .nav-menu.show {
        display: flex;
    }
    
    .loading-content h3 {
        font-size: 1.3rem;
    }
    
    .error-content {
        padding: 30px 20px;
    }
}
</style>
`;

// Inject styles
document.head.insertAdjacentHTML('beforeend', appStyles);

// Export for debugging
window.App = App;