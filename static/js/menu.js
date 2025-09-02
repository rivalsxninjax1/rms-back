// Menu Manager
class MenuManager {
    constructor() {
        this.categories = [];
        this.menuItems = [];
        this.filteredItems = [];
        this.currentCategory = 'all';
        this.currentItem = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadMenu();
    }

    bindEvents() {
        // Item modal close button
        const itemClose = document.getElementById('itemClose');
        if (itemClose) {
            itemClose.addEventListener('click', () => this.hideItemModal());
        }

        // Quantity controls in item modal
        const qtyMinus = document.getElementById('qtyMinus');
        const qtyPlus = document.getElementById('qtyPlus');
        const itemQuantity = document.getElementById('itemQuantity');

        if (qtyMinus) {
            qtyMinus.addEventListener('click', () => {
                const currentQty = parseInt(itemQuantity.value);
                if (currentQty > 1) {
                    itemQuantity.value = currentQty - 1;
                    this.updateItemTotalPrice();
                }
            });
        }

        if (qtyPlus) {
            qtyPlus.addEventListener('click', () => {
                const currentQty = parseInt(itemQuantity.value);
                itemQuantity.value = currentQty + 1;
                this.updateItemTotalPrice();
            });
        }

        if (itemQuantity) {
            itemQuantity.addEventListener('change', () => {
                const qty = parseInt(itemQuantity.value);
                if (qty < 1) itemQuantity.value = 1;
                this.updateItemTotalPrice();
            });
        }

        // Add to cart button in item modal
        const addToCartBtn = document.getElementById('addToCartBtn');
        if (addToCartBtn) {
            addToCartBtn.addEventListener('click', () => this.addCurrentItemToCart());
        }

        // Close modal when clicking outside
        const itemModal = document.getElementById('itemModal');
        if (itemModal) {
            itemModal.addEventListener('click', (e) => {
                if (e.target === itemModal) {
                    this.hideItemModal();
                }
            });
        }
    }

    async loadMenu() {
        try {
            apiUtils.showLoading();
            
            // Load categories and menu items in parallel
            const [categoriesResult, itemsResult] = await Promise.all([
                menuAPI.getCategories(),
                menuAPI.getMenuItems()
            ]);

            this.categories = Array.isArray(categoriesResult.data?.results) ? categoriesResult.data.results : [];
            this.menuItems = Array.isArray(itemsResult.data?.results) ? itemsResult.data.results : [];
            this.filteredItems = Array.isArray(this.menuItems) ? [...this.menuItems] : [];

            this.renderCategories();
            this.renderMenuItems();
            
        } catch (error) {
            console.error('Failed to load menu:', error);
            apiUtils.showToast('Failed to load menu', 'error');
        } finally {
            apiUtils.hideLoading();
        }
    }

    renderCategories() {
        const categoryFilters = document.getElementById('categoryFilters');
        if (!categoryFilters) return;

        const categoriesHTML = [
            '<button class="category-btn active" data-category="all">All Items</button>',
            ...this.categories.map(category => 
                `<button class="category-btn" data-category="${category.id}">${category.name}</button>`
            )
        ].join('');

        categoryFilters.innerHTML = categoriesHTML;

        // Bind category filter events
        const categoryBtns = categoryFilters.querySelectorAll('.category-btn');
        categoryBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const category = e.target.dataset.category;
                this.filterByCategory(category);
                
                // Update active state
                categoryBtns.forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
            });
        });
    }

    filterByCategory(categoryId) {
        this.currentCategory = categoryId;
        
        if (categoryId === 'all') {
            this.filteredItems = [...this.menuItems];
        } else {
            this.filteredItems = this.menuItems.filter(item => 
                item.category && item.category.toString() === categoryId.toString()
            );
        }
        
        this.renderMenuItems();
    }

    renderMenuItems() {
        const itemsGrid = document.getElementById('itemsGrid');
        if (!itemsGrid) return;

        if (this.filteredItems.length === 0) {
            itemsGrid.innerHTML = '<div class="no-items"><p>No items found in this category.</p></div>';
            return;
        }

        const itemsHTML = this.filteredItems.map(item => `
            <div class="menu-item fade-in" data-item-id="${item.id}">
                <img src="${item.image || '/static/images/placeholder.svg'}" alt="${item.name}" class="menu-item-image" loading="lazy">
                <div class="menu-item-content">
                    <h4 class="menu-item-title">${item.name}</h4>
                    <p class="menu-item-description">${item.description || 'Delicious menu item'}</p>
                    <div class="menu-item-footer">
                        <span class="menu-item-price">$${parseFloat(item.price).toFixed(2)}</span>
                        <button class="add-item-btn" onclick="menuManager.showItemModal(${item.id})">
                            <i class="fas fa-plus"></i> Add
                        </button>
                    </div>
                </div>
            </div>
        `).join('');

        itemsGrid.innerHTML = itemsHTML;

        // Add click event to menu items for modal
        const menuItemElements = itemsGrid.querySelectorAll('.menu-item');
        menuItemElements.forEach(element => {
            element.addEventListener('click', (e) => {
                // Don't trigger if clicking the add button
                if (!e.target.closest('.add-item-btn')) {
                    const itemId = parseInt(element.dataset.itemId);
                    this.showItemModal(itemId);
                }
            });
        });
    }

    async showItemModal(itemId) {
        try {
            // Find item in current menu items or fetch from API
            let item = this.menuItems.find(i => i.id === itemId);
            
            if (!item) {
                const result = await menuAPI.getMenuItem(itemId);
                item = result.data;
            }

            this.currentItem = item;
            this.populateItemModal(item);
            
            const itemModal = document.getElementById('itemModal');
            if (itemModal) {
                itemModal.classList.add('show');
            }
            
        } catch (error) {
            console.error('Failed to load item details:', error);
            apiUtils.showToast('Failed to load item details', 'error');
        }
    }

    populateItemModal(item) {
        // Update modal content
        const itemTitle = document.getElementById('itemTitle');
        const itemImage = document.getElementById('itemImage');
        const itemDescription = document.getElementById('itemDescription');
        const itemPrice = document.getElementById('itemPrice');
        const itemExtras = document.getElementById('itemExtras');
        const itemQuantity = document.getElementById('itemQuantity');

        if (itemTitle) itemTitle.textContent = item.name;
        if (itemImage) {
            itemImage.src = item.image || '/static/images/placeholder.svg';
            itemImage.alt = item.name;
        }
        if (itemDescription) itemDescription.textContent = item.description || 'Delicious menu item';
        if (itemPrice) itemPrice.textContent = parseFloat(item.price).toFixed(2);
        if (itemQuantity) itemQuantity.value = 1;

        // Render extras if available
        if (itemExtras) {
            if (item.extras && item.extras.length > 0) {
                const extrasHTML = item.extras.map(extra => `
                    <div class="extra-option">
                        <label>
                            <input type="checkbox" name="extras" value="${extra.id}" data-price="${extra.price}">
                            <span>${extra.name}</span>
                        </label>
                        <span class="extra-price">+$${parseFloat(extra.price).toFixed(2)}</span>
                    </div>
                `).join('');
                
                itemExtras.innerHTML = `
                    <h5>Extras</h5>
                    ${extrasHTML}
                `;

                // Bind extra checkbox events
                const extraCheckboxes = itemExtras.querySelectorAll('input[type="checkbox"]');
                extraCheckboxes.forEach(checkbox => {
                    checkbox.addEventListener('change', () => this.updateItemTotalPrice());
                });
            } else {
                itemExtras.innerHTML = '';
            }
        }

        this.updateItemTotalPrice();
    }

    updateItemTotalPrice() {
        if (!this.currentItem) return;

        const itemQuantity = document.getElementById('itemQuantity');
        const itemTotalPrice = document.getElementById('itemTotalPrice');
        const itemExtras = document.getElementById('itemExtras');

        if (!itemQuantity || !itemTotalPrice) return;

        let basePrice = parseFloat(this.currentItem.price);
        let extrasPrice = 0;

        // Calculate extras price
        if (itemExtras) {
            const checkedExtras = itemExtras.querySelectorAll('input[type="checkbox"]:checked');
            checkedExtras.forEach(extra => {
                extrasPrice += parseFloat(extra.dataset.price || 0);
            });
        }

        const quantity = parseInt(itemQuantity.value) || 1;
        const totalPrice = (basePrice + extrasPrice) * quantity;

        itemTotalPrice.textContent = totalPrice.toFixed(2);
    }

    hideItemModal() {
        const itemModal = document.getElementById('itemModal');
        if (itemModal) {
            itemModal.classList.remove('show');
        }
        this.currentItem = null;
    }

    async addCurrentItemToCart() {
        if (!this.currentItem) return;

        const itemQuantity = document.getElementById('itemQuantity');
        const itemExtras = document.getElementById('itemExtras');

        const quantity = parseInt(itemQuantity.value) || 1;
        const selectedExtras = [];

        // Get selected extras
        if (itemExtras) {
            const checkedExtras = itemExtras.querySelectorAll('input[type="checkbox"]:checked');
            checkedExtras.forEach(extra => {
                const extraId = parseInt(extra.value);
                const extraData = this.currentItem.extras?.find(e => e.id === extraId);
                if (extraData) {
                    selectedExtras.push({
                        id: extraData.id,
                        name: extraData.name,
                        price: extraData.price
                    });
                }
            });
        }

        const cartItemData = {
            menu_item_id: this.currentItem.id,
            menu_item: this.currentItem,
            quantity: quantity,
            extras: selectedExtras,
            price: this.currentItem.price
        };

        try {
            await cartManager.addItem(cartItemData);
            this.hideItemModal();
            
            // Optionally open cart sidebar to show added item
            setTimeout(() => {
                cartManager.openCart();
            }, 500);
            
        } catch (error) {
            console.error('Failed to add item to cart:', error);
            apiUtils.showToast('Failed to add item to cart', 'error');
        }
    }

    // Search functionality
    async searchItems(query) {
        if (!query.trim()) {
            this.filteredItems = [...this.menuItems];
            this.renderMenuItems();
            return;
        }

        try {
            const result = await menuAPI.searchItems(query);
            this.filteredItems = result.data;
            this.renderMenuItems();
            
            // Update category filter to show "All Items" as active
            const categoryBtns = document.querySelectorAll('.category-btn');
            categoryBtns.forEach(btn => {
                btn.classList.toggle('active', btn.dataset.category === 'all');
            });
            
        } catch (error) {
            console.error('Search failed:', error);
            apiUtils.showToast('Search failed', 'error');
        }
    }

    // Utility methods
    getMenuItems() {
        return this.menuItems;
    }

    getCategories() {
        return this.categories;
    }

    getCurrentCategory() {
        return this.currentCategory;
    }

    refreshMenu() {
        this.loadMenu();
    }
}

// Create global menu manager instance
const menuManager = new MenuManager();

// Export for global access
window.menuManager = menuManager;

// Additional styles for menu items
const menuStyles = `
<style>
.no-items {
    text-align: center;
    padding: 60px 20px;
    color: #666;
    grid-column: 1 / -1;
}

.menu-item {
    cursor: pointer;
    position: relative;
    overflow: hidden;
}

.menu-item::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(231, 76, 60, 0.1);
    opacity: 0;
    transition: opacity 0.3s ease;
    pointer-events: none;
}

.menu-item:hover::before {
    opacity: 1;
}

.menu-item-image {
    transition: transform 0.3s ease;
}

.menu-item:hover .menu-item-image {
    transform: scale(1.05);
}

.add-item-btn {
    position: relative;
    z-index: 2;
}

.extra-option {
    transition: all 0.2s ease;
}

.extra-option:hover {
    background-color: #f8f9fa;
}

.extra-option input[type="checkbox"]:checked + span {
    font-weight: 600;
    color: #e74c3c;
}

@media (max-width: 768px) {
    .menu-item-title {
        font-size: 1.1rem;
    }
    
    .menu-item-description {
        font-size: 0.85rem;
        line-height: 1.4;
    }
    
    .add-item-btn {
        padding: 6px 12px;
        font-size: 0.9rem;
    }
}
</style>
`;

// Inject styles
document.head.insertAdjacentHTML('beforeend', menuStyles);

// Add search functionality to header if search input exists
document.addEventListener('DOMContentLoaded', () => {
    // You can add a search input to the header and bind it here
    const searchInput = document.getElementById('menuSearch');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                menuManager.searchItems(e.target.value);
            }, 300);
        });
    }
});