// Checkout Manager
class CheckoutManager {
    constructor() {
        this.stripe = null;
        this.elements = null;
        this.cardElement = null;
        this.currentOrder = null;
        this.isProcessing = false;
        this.init();
    }

    async init() {
        this.bindEvents();
        await this.initializeStripe();
    }

    async initializeStripe() {
        try {
            // Initialize Stripe (you'll need to add your publishable key)
            // For now, we'll simulate Stripe functionality
            console.log('Stripe would be initialized here with publishable key');
            this.stripe = {
                // Mock Stripe object for demonstration
                confirmCardPayment: async (clientSecret, paymentMethod) => {
                    // Simulate payment processing
                    return new Promise((resolve) => {
                        setTimeout(() => {
                            resolve({
                                paymentIntent: {
                                    status: 'succeeded',
                                    id: 'pi_' + Math.random().toString(36).substr(2, 9)
                                }
                            });
                        }, 2000);
                    });
                }
            };
        } catch (error) {
            console.error('Failed to initialize Stripe:', error);
        }
    }

    bindEvents() {
        // Checkout modal close button
        const checkoutClose = document.getElementById('checkoutClose');
        if (checkoutClose) {
            checkoutClose.addEventListener('click', () => this.hideCheckoutModal());
        }

        // Order type radio buttons
        const orderTypeRadios = document.querySelectorAll('input[name="order_type"]');
        orderTypeRadios.forEach(radio => {
            radio.addEventListener('change', () => this.handleOrderTypeChange());
        });

        // Tip amount input
        const tipAmount = document.getElementById('tipAmount');
        if (tipAmount) {
            tipAmount.addEventListener('input', () => this.updateCheckoutTotals());
        }

        // Checkout form submission
        const checkoutForm = document.getElementById('checkoutForm');
        if (checkoutForm) {
            checkoutForm.addEventListener('submit', (e) => this.handleCheckoutSubmit(e));
        }

        // Close modal when clicking outside
        const checkoutModal = document.getElementById('checkoutModal');
        if (checkoutModal) {
            checkoutModal.addEventListener('click', (e) => {
                if (e.target === checkoutModal) {
                    this.hideCheckoutModal();
                }
            });
        }
    }

    showCheckoutModal() {
        if (!authManager.isAuthenticated()) {
            authManager.showAuthModal('login');
            return;
        }

        if (cartManager.isEmpty()) {
            apiUtils.showToast('Your cart is empty', 'warning');
            return;
        }

        const checkoutModal = document.getElementById('checkoutModal');
        if (checkoutModal) {
            this.populateCheckoutModal();
            checkoutModal.classList.add('show');
        }
    }

    hideCheckoutModal() {
        const checkoutModal = document.getElementById('checkoutModal');
        if (checkoutModal) {
            checkoutModal.classList.remove('show');
        }
        this.resetCheckoutForm();
    }

    populateCheckoutModal() {
        // Set default order type
        const dineInRadio = document.querySelector('input[name="order_type"][value="dine_in"]');
        if (dineInRadio) {
            dineInRadio.checked = true;
        }

        // Show/hide table section based on order type
        this.handleOrderTypeChange();

        // Reset tip amount
        const tipAmount = document.getElementById('tipAmount');
        if (tipAmount) {
            tipAmount.value = '';
        }

        // Update totals
        this.updateCheckoutTotals();
    }

    handleOrderTypeChange() {
        const selectedOrderType = document.querySelector('input[name="order_type"]:checked')?.value;
        const tableSection = document.getElementById('tableSection');
        const tableNumber = document.getElementById('tableNumber');

        if (tableSection && tableNumber) {
            if (selectedOrderType === 'dine_in') {
                tableSection.style.display = 'block';
                tableNumber.required = true;
            } else {
                tableSection.style.display = 'none';
                tableNumber.required = false;
                tableNumber.value = '';
            }
        }
    }

    updateCheckoutTotals() {
        const cart = cartManager.getCart();
        const tipAmount = document.getElementById('tipAmount');
        const checkoutSubtotal = document.getElementById('checkoutSubtotal');
        const checkoutTax = document.getElementById('checkoutTax');
        const checkoutTip = document.getElementById('checkoutTip');
        const checkoutTotal = document.getElementById('checkoutTotal');

        const subtotal = cart.subtotal || 0;
        const tax = cart.tax || 0;
        const tip = parseFloat(tipAmount?.value || 0);
        const total = subtotal + tax + tip;

        if (checkoutSubtotal) checkoutSubtotal.textContent = subtotal.toFixed(2);
        if (checkoutTax) checkoutTax.textContent = tax.toFixed(2);
        if (checkoutTip) checkoutTip.textContent = tip.toFixed(2);
        if (checkoutTotal) checkoutTotal.textContent = total.toFixed(2);
    }

    async handleCheckoutSubmit(e) {
        e.preventDefault();
        
        if (this.isProcessing) return;
        
        try {
            this.isProcessing = true;
            apiUtils.showLoading();

            // Collect form data
            const formData = new FormData(e.target);
            const orderData = this.collectOrderData(formData);

            // Validate required fields
            if (!this.validateOrderData(orderData)) {
                return;
            }

            // Create order
            const orderResult = await ordersAPI.createOrder(orderData);
            this.currentOrder = orderResult.data;

            // Process payment
            await this.processPayment(orderData.total);

        } catch (error) {
            console.error('Checkout failed:', error);
            const message = apiUtils.handleError(error);
            apiUtils.showToast(message, 'error');
        } finally {
            this.isProcessing = false;
            apiUtils.hideLoading();
        }
    }

    collectOrderData(formData) {
        const cart = cartManager.getCart();
        const tipAmount = parseFloat(formData.get('tip_amount') || 0);
        const total = (cart.total || 0) + tipAmount;

        return {
            order_type: formData.get('order_type'),
            table_number: formData.get('table_number') || null,
            tip_amount: tipAmount,
            special_instructions: formData.get('special_instructions') || '',
            subtotal: cart.subtotal || 0,
            tax: cart.tax || 0,
            total: total,
            items: cart.items.map(item => ({
                menu_item_id: item.menu_item.id,
                quantity: item.quantity,
                extras: item.extras || [],
                price: item.price || item.menu_item.price
            }))
        };
    }

    validateOrderData(orderData) {
        if (orderData.order_type === 'dine_in' && !orderData.table_number) {
            apiUtils.showToast('Please enter a table number for dine-in orders', 'error');
            return false;
        }

        if (orderData.items.length === 0) {
            apiUtils.showToast('Your cart is empty', 'error');
            return false;
        }

        if (orderData.total <= 0) {
            apiUtils.showToast('Invalid order total', 'error');
            return false;
        }

        return true;
    }

    async processPayment(amount) {
        try {
            // In a real implementation, you would:
            // 1. Create a payment intent on the server
            // 2. Confirm the payment with Stripe
            // 3. Handle the payment result

            // For demonstration, we'll simulate the payment process
            const paymentResult = await this.simulateStripePayment(amount);
            
            if (paymentResult.paymentIntent.status === 'succeeded') {
                await this.handlePaymentSuccess(paymentResult.paymentIntent.id);
            } else {
                throw new Error('Payment failed');
            }

        } catch (error) {
            console.error('Payment processing failed:', error);
            throw error;
        }
    }

    async simulateStripePayment(amount) {
        // Simulate Stripe payment processing
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                // Simulate 90% success rate
                if (Math.random() > 0.1) {
                    resolve({
                        paymentIntent: {
                            status: 'succeeded',
                            id: 'pi_' + Math.random().toString(36).substr(2, 9)
                        }
                    });
                } else {
                    reject(new Error('Payment declined'));
                }
            }, 2000);
        });
    }

    async handlePaymentSuccess(paymentIntentId) {
        try {
            // Update order with payment information
            if (this.currentOrder) {
                // In a real implementation, you would update the order status
                console.log('Order completed:', this.currentOrder.id, 'Payment:', paymentIntentId);
            }

            // Clear the cart
            await cartManager.clearCart();

            // Hide checkout modal
            this.hideCheckoutModal();

            // Show success message
            apiUtils.showToast('Order placed successfully! Thank you for your purchase.', 'success');

            // Optionally redirect or show order confirmation
            this.showOrderConfirmation();

        } catch (error) {
            console.error('Failed to complete order:', error);
            apiUtils.showToast('Payment successful but failed to complete order. Please contact support.', 'warning');
        }
    }

    showOrderConfirmation() {
        if (!this.currentOrder) return;

        // Create a simple order confirmation modal or redirect
        const confirmationHTML = `
            <div class="order-confirmation">
                <div class="confirmation-content">
                    <i class="fas fa-check-circle success-icon"></i>
                    <h3>Order Confirmed!</h3>
                    <p>Your order #${this.currentOrder.id || 'N/A'} has been placed successfully.</p>
                    <p>You will receive a confirmation email shortly.</p>
                    <button onclick="this.parentElement.parentElement.remove()" class="btn btn-primary">
                        Continue Shopping
                    </button>
                </div>
            </div>
        `;

        // Create and show confirmation overlay
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay show';
        overlay.innerHTML = confirmationHTML;
        document.body.appendChild(overlay);

        // Auto-remove after 10 seconds
        setTimeout(() => {
            if (overlay.parentNode) {
                overlay.parentNode.removeChild(overlay);
            }
        }, 10000);
    }

    resetCheckoutForm() {
        const checkoutForm = document.getElementById('checkoutForm');
        if (checkoutForm) {
            checkoutForm.reset();
        }

        // Reset to default order type
        const dineInRadio = document.querySelector('input[name="order_type"][value="dine_in"]');
        if (dineInRadio) {
            dineInRadio.checked = true;
        }

        this.handleOrderTypeChange();
        this.currentOrder = null;
    }

    // Utility methods
    getCurrentOrder() {
        return this.currentOrder;
    }

    isProcessingPayment() {
        return this.isProcessing;
    }
}

// Create global checkout manager instance
const checkoutManager = new CheckoutManager();

// Export for global access
window.checkoutManager = checkoutManager;

// Additional styles for checkout
const checkoutStyles = `
<style>
.order-confirmation {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 20px;
}

.confirmation-content {
    background: white;
    padding: 40px;
    border-radius: 15px;
    text-align: center;
    max-width: 400px;
    width: 100%;
    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
}

.success-icon {
    font-size: 4rem;
    color: #28a745;
    margin-bottom: 20px;
}

.confirmation-content h3 {
    margin-bottom: 15px;
    color: #333;
    font-size: 1.5rem;
}

.confirmation-content p {
    margin-bottom: 15px;
    color: #666;
    line-height: 1.6;
}

.btn {
    padding: 12px 24px;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
}

.btn-primary {
    background: #e74c3c;
    color: white;
}

.btn-primary:hover {
    background: #c0392b;
    transform: translateY(-2px);
}

.checkout-section {
    animation: fadeInUp 0.3s ease;
}

@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.payment-btn:disabled {
    background: #6c757d;
    cursor: not-allowed;
    transform: none;
}

.payment-btn:disabled:hover {
    background: #6c757d;
    transform: none;
}

@media (max-width: 768px) {
    .confirmation-content {
        padding: 30px 20px;
    }
    
    .success-icon {
        font-size: 3rem;
    }
    
    .confirmation-content h3 {
        font-size: 1.3rem;
    }
}
</style>
`;

// Inject styles
document.head.insertAdjacentHTML('beforeend', checkoutStyles);