// Authentication Manager
class AuthManager {
    constructor() {
        this.currentUser = null;
        this.isLoggedIn = false;
        this.init();
    }

    init() {
        this.bindEvents();
        this.checkAuthStatus();
    }

    bindEvents() {
        // Login button
        const loginBtn = document.getElementById('loginBtn');
        if (loginBtn) {
            loginBtn.addEventListener('click', () => this.showAuthModal('login'));
        }

        // Optional separate Sign up button
        const signupBtn = document.getElementById('signupBtn');
        if (signupBtn) {
            signupBtn.addEventListener('click', () => this.showAuthModal('register'));
        }

        // Auth modal close buttons
        const authClose = document.getElementById('authClose');
        if (authClose) {
            authClose.addEventListener('click', () => this.hideAuthModal());
        }

        // Auth toggle (switch between login/register)
        // Use both direct binding (if present at load) and event delegation for robustness
        const authToggle = document.getElementById('authToggle');
        if (authToggle) {
            authToggle.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleAuthMode();
            });
        }
        document.addEventListener('click', (e) => {
            const t = e.target;
            if (t && t.id === 'authToggle') {
                e.preventDefault();
                this.toggleAuthMode();
            }
        });

        // Login form submission
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        }

        // Register form submission
        const registerForm = document.getElementById('registerForm');
        if (registerForm) {
            registerForm.addEventListener('submit', (e) => this.handleRegister(e));
        }

        // Close modal when clicking outside
        const authModal = document.getElementById('authModal');
        if (authModal) {
            authModal.addEventListener('click', (e) => {
                if (e.target === authModal) {
                    this.hideAuthModal();
                }
            });
        }

        // Listen for auth required events
        window.addEventListener('auth:required', () => {
            this.showAuthModal('login');
        });
    }

    async checkAuthStatus() {
        if (authAPI.isAuthenticated()) {
            try {
                const result = await authAPI.getProfile();
                this.setUser(result.data);
            } catch (error) {
                console.warn('Failed to get user profile:', error);
                this.logout();
            }
        }
    }

    showAuthModal(mode = 'login') {
        const authModal = document.getElementById('authModal');
        const authTitle = document.getElementById('authTitle');
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');
        const authToggle = document.getElementById('authToggle');
        const authToggleText = document.getElementById('authToggleText');

        if (!authModal) return;

        // Reset forms
        if (loginForm) loginForm.reset();
        if (registerForm) registerForm.reset();

        if (mode === 'login') {
            authTitle.textContent = 'Login';
            loginForm.classList.remove('hidden');
            registerForm.classList.add('hidden');
            authToggleText.innerHTML = 'Don\'t have an account? <a href="#" id="authToggle">Sign up</a>';
        } else {
            authTitle.textContent = 'Sign Up';
            loginForm.classList.add('hidden');
            registerForm.classList.remove('hidden');
            authToggleText.innerHTML = 'Already have an account? <a href="#" id="authToggle">Login</a>';
        }

        // Re-bind toggle event after innerHTML change
        const newAuthToggle = document.getElementById('authToggle');
        if (newAuthToggle) {
            newAuthToggle.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleAuthMode();
            });
        }

        authModal.classList.add('show');
    }

    hideAuthModal() {
        const authModal = document.getElementById('authModal');
        if (authModal) {
            authModal.classList.remove('show');
        }
    }

    toggleAuthMode() {
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');
        const authTitle = document.getElementById('authTitle');
        const authToggleText = document.getElementById('authToggleText');

        if (loginForm.classList.contains('hidden')) {
            // Switch to login
            authTitle.textContent = 'Login';
            loginForm.classList.remove('hidden');
            registerForm.classList.add('hidden');
            authToggleText.innerHTML = 'Don\'t have an account? <a href="#" id="authToggle">Sign up</a>';
        } else {
            // Switch to register
            authTitle.textContent = 'Sign Up';
            loginForm.classList.add('hidden');
            registerForm.classList.remove('hidden');
            authToggleText.innerHTML = 'Already have an account? <a href="#" id="authToggle">Login</a>';
        }

        // Re-bind toggle event
        const newAuthToggle = document.getElementById('authToggle');
        if (newAuthToggle) {
            newAuthToggle.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleAuthMode();
            });
        }
    }

    async handleLogin(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const credentials = {
            email: formData.get('email'),
            password: formData.get('password')
        };

        try {
            apiUtils.showLoading();
            const result = await authAPI.login(credentials);
            
            this.setUser(result.data.user || result.data);
            this.hideAuthModal();
            apiUtils.showToast('Login successful!', 'success');
            
            // Refresh cart after login
            if (window.cartManager) {
                await window.cartManager.loadCart();
            }
            
        } catch (error) {
            const message = apiUtils.handleError(error);
            apiUtils.showToast(message, 'error');
        } finally {
            apiUtils.hideLoading();
        }
    }

    async handleRegister(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const password = formData.get('password');
        const confirmPassword = formData.get('confirm_password');

        // Validate passwords match
        if (password !== confirmPassword) {
            apiUtils.showToast('Passwords do not match', 'error');
            return;
        }

        const userData = {
            username: formData.get('username'),
            first_name: formData.get('first_name'),
            last_name: formData.get('last_name'),
            email: formData.get('email'),
            password: password
        };

        try {
            apiUtils.showLoading();
            const result = await authAPI.register(userData);
            
            this.setUser(result.data.user || result.data);
            this.hideAuthModal();
            apiUtils.showToast('Registration successful!', 'success');
            
            // Refresh cart after registration
            if (window.cartManager) {
                await window.cartManager.loadCart();
            }
            
        } catch (error) {
            const message = apiUtils.handleError(error);
            apiUtils.showToast(message, 'error');
        } finally {
            apiUtils.hideLoading();
        }
    }

    setUser(userData) {
        this.currentUser = userData;
        this.isLoggedIn = true;
        this.updateUI();
        
        // Dispatch login event
        window.dispatchEvent(new CustomEvent('auth:login', {
            detail: { user: userData }
        }));
    }

    async logout() {
        try {
            await authAPI.logout();
        } catch (error) {
            console.warn('Logout error:', error);
        }
        
        this.currentUser = null;
        this.isLoggedIn = false;
        this.updateUI();
        
        // Clear cart
        if (window.cartManager) {
            window.cartManager.clearLocalCart();
        }
        
        // Dispatch logout event
        window.dispatchEvent(new CustomEvent('auth:logout'));
        
        apiUtils.showToast('Logged out successfully', 'success');
    }

    updateUI() {
        const loginBtn = document.getElementById('loginBtn');
        
        if (this.isLoggedIn && this.currentUser) {
            // Update login button to show user name and logout option
            if (loginBtn) {
                loginBtn.innerHTML = `
                    <div class="user-menu">
                        <span class="user-name">${this.currentUser.first_name || this.currentUser.email}</span>
                        <div class="user-dropdown">
                            <button class="dropdown-item" onclick="authManager.logout()">Logout</button>
                        </div>
                    </div>
                `;
                loginBtn.classList.add('logged-in');
            }
        } else {
            // Reset to login button
            if (loginBtn) {
                loginBtn.textContent = 'Login';
                loginBtn.classList.remove('logged-in');
                loginBtn.onclick = () => this.showAuthModal('login');
            }
        }
    }

    // Utility methods
    requireAuth(callback) {
        if (this.isLoggedIn) {
            callback();
        } else {
            this.showAuthModal('login');
        }
    }

    getUser() {
        return this.currentUser;
    }

    getUserId() {
        return this.currentUser ? this.currentUser.id : null;
    }

    isAuthenticated() {
        return this.isLoggedIn;
    }
}

// Create global auth manager instance
const authManager = new AuthManager();

// Export for global access
window.authManager = authManager;
window.openSignUpModal = () => authManager.showAuthModal('register');

// Additional CSS for user menu (inject into head)
const userMenuStyles = `
<style>
.user-menu {
    position: relative;
    cursor: pointer;
}

.user-name {
    display: inline-block;
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.user-dropdown {
    position: absolute;
    top: 100%;
    right: 0;
    background: white;
    border: 1px solid #e9ecef;
    border-radius: 8px;
    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    min-width: 120px;
    display: none;
    z-index: 1000;
}

.user-menu:hover .user-dropdown {
    display: block;
}

.dropdown-item {
    display: block;
    width: 100%;
    padding: 10px 15px;
    border: none;
    background: none;
    text-align: left;
    cursor: pointer;
    transition: background-color 0.2s;
}

.dropdown-item:hover {
    background-color: #f8f9fa;
}

.login-btn.logged-in {
    background: #28a745;
}

.login-btn.logged-in:hover {
    background: #218838;
}
</style>
`;

// Inject styles
document.head.insertAdjacentHTML('beforeend', userMenuStyles);
