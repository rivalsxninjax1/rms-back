// Cart Manager
class CartManager {
    constructor() {
        this.cart = {
            items: [],
            subtotal: 0,
            tax: 0,
            total: 0,
            item_count: 0
        };
        this.isOpen = false;
        this.autoSaveTimeout = null;
        this.autoClearTimeout = null;
        this.CART_TIMEOUT = 25 * 60 * 1000; // 25 minutes in milliseconds
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadCart();
        this.startAutoClearTimer();
    }

    bindEvents() {
        // Cart toggle button
        const cartToggle = document.getElementById('cartToggle');
        if (cartToggle) {
            cartToggle.addEventListener('click', () => this.toggleCart());
        }

        // Cart close button
        const cartClose = document.getElementById('cartClose');
        if (cartClose) {
            cartClose.addEventListener('click', () => this.closeCart());
        }

        // Checkout button
        const checkoutBtn = document.getElementById('checkoutBtn');
        if (checkoutBtn) {
            checkoutBtn.addEventListener('click', () => this.proceedToCheckout());
        }

        // Close cart when clicking outside
        const cartSidebar = document.getElementById('cartSidebar');
        document.addEventListener('click', (e) => {
            if (this.isOpen && cartSidebar && !cartSidebar.contains(e.target) && !e.target.closest('#cartToggle')) {
                this.closeCart();
            }
        });

        // Listen for auth events
        window.addEventListener('auth:login', () => {
            this.loadCart();
        });

        window.addEventListener('auth:logout', () => {
            this.clearLocalCart();
        });
    }

    toggleCart() {
        if (this.isOpen) {
            this.closeCart();
        } else {
            this.openCart();
        }
    }

    openCart() {
        const cartSidebar = document.getElementById('cartSidebar');
        if (cartSidebar) {
            cartSidebar.classList.add('open');
            this.isOpen = true;
        }
    }

    closeCart() {
        const cartSidebar = document.getElementById('cartSidebar');
        if (cartSidebar) {
            cartSidebar.classList.remove('open');
            this.isOpen = false;
        }
    }

    async loadCart() {
        try {
            if (authManager.isAuthenticated()) {
                // Load cart from backend for authenticated users
                const result = await cartAPI.getCart();
                this.cart = result.data;
            } else {
                // Load cart from localStorage for guests
                const savedCart = localStorage.getItem('guestCart');
                if (savedCart) {
                    this.cart = JSON.parse(savedCart);
                } else {
                    this.cart = {
                        items: [],
                        subtotal: 0,
                        tax: 0,
                        total: 0,
                        item_count: 0
                    };
                }
            }
            this.updateCartUI();
        } catch (error) {
            console.error('Failed to load cart:', error);
            // Fallback to empty cart
            this.cart = {
                items: [],
                subtotal: 0,
                tax: 0,
                total: 0,
                item_count: 0
            };
            this.updateCartUI();
        }
    }

    async addItem(itemData) {
        try {
            this.resetAutoClearTimer();
            
            if (authManager.isAuthenticated()) {
                // Add to backend cart
                const result = await cartAPI.addItem(itemData);
                this.cart = result.data;
            } else {
                // Add to local cart
                this.addToLocalCart(itemData);
            }
            
            this.updateCartUI();
            this.saveLocalCart();
            apiUtils.showToast('Item added to cart!', 'success');
            
        } catch (error) {
            console.error('Failed to add item to cart:', error);
            apiUtils.showToast('Failed to add item to cart', 'error');
        }
    }

    addToLocalCart(itemData) {
        const existingItemIndex = this.cart.items.findIndex(item => 
            item.menu_item.id === itemData.menu_item_id && 
            JSON.stringify(item.extras) === JSON.stringify(itemData.extras || [])
        );

        if (existingItemIndex > -1) {
            // Update existing item quantity
            this.cart.items[existingItemIndex].quantity += itemData.quantity || 1;
        } else {
            // Add new item (we'll need to fetch item details)
            this.cart.items.push({
                id: Date.now(), // Temporary ID for local cart
                menu_item: itemData.menu_item,
                quantity: itemData.quantity || 1,
                extras: itemData.extras || [],
                price: itemData.price || itemData.menu_item.price
            });
        }
        
        this.calculateTotals();
    }

    async updateItemQuantity(itemId, quantity) {
        try {
            this.resetAutoClearTimer();
            
            if (quantity <= 0) {
                return this.removeItem(itemId);
            }

            if (authManager.isAuthenticated()) {
                // Update backend cart
                const result = await cartAPI.updateItem(itemId, { quantity });
                this.cart = result.data;
            } else {
                // Update local cart
                const itemIndex = this.cart.items.findIndex(item => item.id === itemId);
                if (itemIndex > -1) {
                    this.cart.items[itemIndex].quantity = quantity;
                    this.calculateTotals();
                }
            }
            
            this.updateCartUI();
            this.saveLocalCart();
            
        } catch (error) {
            console.error('Failed to update item quantity:', error);
            apiUtils.showToast('Failed to update item', 'error');
        }
    }

    async removeItem(itemId) {
        try {
            this.resetAutoClearTimer();
            
            if (authManager.isAuthenticated()) {
                // Remove from backend cart
                await cartAPI.removeItem(itemId);
                await this.loadCart(); // Reload cart after removal
            } else {
                // Remove from local cart
                this.cart.items = this.cart.items.filter(item => item.id !== itemId);
                this.calculateTotals();
            }
            
            this.updateCartUI();
            this.saveLocalCart();
            apiUtils.showToast('Item removed from cart', 'success');
            
        } catch (error) {
            console.error('Failed to remove item:', error);
            apiUtils.showToast('Failed to remove item', 'error');
        }
    }

    async clearCart() {
        try {
            if (authManager.isAuthenticated()) {
                // Clear backend cart
                await cartAPI.clearCart();
            }
            
            // Clear local cart
            this.cart = {
                items: [],
                subtotal: 0,
                tax: 0,
                total: 0,
                item_count: 0
            };
            
            this.updateCartUI();
            this.saveLocalCart();
            this.stopAutoClearTimer();
            
        } catch (error) {
            console.error('Failed to clear cart:', error);
        }
    }

    clearLocalCart() {
        this.cart = {
            items: [],
            subtotal: 0,
            tax: 0,
            total: 0,
            item_count: 0
        };
        localStorage.removeItem('guestCart');
        this.updateCartUI();
        this.stopAutoClearTimer();
    }

    calculateTotals() {
        let subtotal = 0;
        let itemCount = 0;

        this.cart.items.forEach(item => {
            const itemPrice = parseFloat(item.price || item.menu_item.price);
            const extrasPrice = item.extras ? item.extras.reduce((sum, extra) => sum + parseFloat(extra.price || 0), 0) : 0;
            const totalItemPrice = (itemPrice + extrasPrice) * item.quantity;
            
            subtotal += totalItemPrice;
            itemCount += item.quantity;
        });

        const tax = subtotal * 0.08; // 8% tax rate
        const total = subtotal + tax;

        this.cart.subtotal = subtotal;
        this.cart.tax = tax;
        this.cart.total = total;
        this.cart.item_count = itemCount;
    }

    saveLocalCart() {
        if (!authManager.isAuthenticated()) {
            localStorage.setItem('guestCart', JSON.stringify(this.cart));
        }
    }

    updateCartUI() {
        this.updateCartCount();
        this.updateCartItems();
        this.updateCartTotals();
        this.updateCheckoutButton();
    }

    updateCartCount() {
        const cartCount = document.getElementById('cartCount');
        if (cartCount) {
            cartCount.textContent = this.cart.item_count || 0;
        }
    }

    updateCartItems() {
        const cartItems = document.getElementById('cartItems');
        if (!cartItems) return;

        if (this.cart.items.length === 0) {
            cartItems.innerHTML = '<div class="empty-cart"><p>Your cart is empty</p></div>';
            return;
        }

        cartItems.innerHTML = this.cart.items.map(item => {
            const itemPrice = parseFloat(item.price || item.menu_item.price);
            const extrasPrice = item.extras ? item.extras.reduce((sum, extra) => sum + parseFloat(extra.price || 0), 0) : 0;
            const totalItemPrice = (itemPrice + extrasPrice) * item.quantity;
            
            return `
                <div class="cart-item" data-item-id="${item.id}">
                    <img src="${item.menu_item.image || '/static/images/placeholder.jpg'}" alt="${item.menu_item.name}" class="cart-item-image">
                    <div class="cart-item-info">
                        <div class="cart-item-name">${item.menu_item.name}</div>
                        <div class="cart-item-price">$${totalItemPrice.toFixed(2)}</div>
                        ${item.extras && item.extras.length > 0 ? `
                            <div class="cart-item-extras">
                                ${item.extras.map(extra => `<small>+ ${extra.name}</small>`).join(', ')}
                            </div>
                        ` : ''}
                        <div class="cart-item-controls">
                            <button class="qty-control" onclick="cartManager.updateItemQuantity(${item.id}, ${item.quantity - 1})">
                                <i class="fas fa-minus"></i>
                            </button>
                            <span class="cart-item-quantity">${item.quantity}</span>
                            <button class="qty-control" onclick="cartManager.updateItemQuantity(${item.id}, ${item.quantity + 1})">
                                <i class="fas fa-plus"></i>
                            </button>
                            <button class="remove-item" onclick="cartManager.removeItem(${item.id})">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    updateCartTotals() {
        const cartSubtotal = document.getElementById('cartSubtotal');
        const cartTax = document.getElementById('cartTax');
        const cartTotal = document.getElementById('cartTotal');

        if (cartSubtotal) cartSubtotal.textContent = (this.cart.subtotal || 0).toFixed(2);
        if (cartTax) cartTax.textContent = (this.cart.tax || 0).toFixed(2);
        if (cartTotal) cartTotal.textContent = (this.cart.total || 0).toFixed(2);
    }

    updateCheckoutButton() {
        const checkoutBtn = document.getElementById('checkoutBtn');
        if (checkoutBtn) {
            checkoutBtn.disabled = this.cart.items.length === 0;
        }
    }

    proceedToCheckout() {
        if (this.cart.items.length === 0) {
            apiUtils.showToast('Your cart is empty', 'warning');
            return;
        }

        if (!authManager.isAuthenticated()) {
            // Show login modal first
            authManager.showAuthModal('login');
            return;
        }

        // Show checkout modal
        if (window.checkoutManager) {
            window.checkoutManager.showCheckoutModal();
        }
    }

    // Auto-clear functionality
    startAutoClearTimer() {
        this.stopAutoClearTimer();
        
        if (this.cart.items.length > 0) {
            this.autoClearTimeout = setTimeout(() => {
                this.clearCart();
                apiUtils.showToast('Cart cleared due to inactivity', 'warning');
            }, this.CART_TIMEOUT);
        }
    }

    resetAutoClearTimer() {
        this.startAutoClearTimer();
    }

    stopAutoClearTimer() {
        if (this.autoClearTimeout) {
            clearTimeout(this.autoClearTimeout);
            this.autoClearTimeout = null;
        }
    }

    // Utility methods
    getCart() {
        return this.cart;
    }

    getItemCount() {
        return this.cart.item_count || 0;
    }

    getTotal() {
        return this.cart.total || 0;
    }

    isEmpty() {
        return this.cart.items.length === 0;
    }
}

// Create global cart manager instance
const cartManager = new CartManager();

// Export for global access
window.cartManager = cartManager;

// Additional styles for cart items
const cartStyles = `
<style>
.empty-cart {
    text-align: center;
    padding: 40px 20px;
    color: #666;
}

.cart-item-extras {
    font-size: 0.8rem;
    color: #666;
    margin-top: 4px;
}

.cart-item-extras small {
    display: inline-block;
    margin-right: 8px;
}

.qty-control {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8rem;
}

.remove-item {
    display: flex;
    align-items: center;
    justify-content: center;
}
</style>
`;

// Inject styles
document.head.insertAdjacentHTML('beforeend', cartStyles);