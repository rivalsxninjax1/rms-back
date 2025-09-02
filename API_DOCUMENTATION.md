# Comprehensive REST API Documentation

This document describes the comprehensive REST API endpoints implemented for the Restaurant Management System.

## Overview

The API provides full CRUD operations for all major entities in the system:
- **Menu Management**: Categories, Items, Modifiers
- **Order Management**: Carts, Orders, Order Items
- **Core Services**: Organizations, Locations, Service Types, Tables, Reservations

All APIs follow REST conventions and use Django REST Framework with proper serialization, validation, and error handling.

## Authentication

- **Public APIs**: Menu browsing, cart operations (guest users)
- **Authenticated APIs**: Order creation, reservations, user-specific data
- **Admin APIs**: Full management operations (staff only)

## Base URLs

- **Core API**: `/core/api/`
- **Menu API**: `/menu/api/`
- **Orders API**: `/orders/api/`

## Base URL
```
http://localhost:8000/api/
```

## Menu API Endpoints

### Public Menu APIs

### Menu Categories
- **GET** `/api/menu/categories/` - List all active menu categories
- **GET** `/api/menu/categories/{id}/` - Get specific category details
- **GET** `/api/menu/categories/{id}/items/` - Get all items in a category

#### Menu Categories
```
GET /menu/api/categories/
- List all active menu categories
- Response: Array of category objects with nested items

GET /menu/api/categories/{id}/
- Get specific category details
- Response: Category object with full details

GET /menu/api/categories/{id}/items/
- Get all menu items for a category
- Response: Array of menu item objects
```

### Menu Items
- **GET** `/api/menu/items/` - List all available menu items
- **GET** `/api/menu/items/{id}/` - Get specific item details
- **GET** `/api/menu/items/search/?q={query}` - Search menu items

#### Menu Items
```
GET /menu/api/items/
- List all available menu items
- Query parameters:
  - category: Filter by category ID
  - search: Search in name/description
  - vegetarian: Filter vegetarian items (true/false)
  - min_price: Minimum price filter
  - max_price: Maximum price filter
- Response: Array of menu item objects

GET /menu/api/items/{id}/
- Get specific menu item details
- Response: Menu item object with modifiers

GET /menu/api/items/{id}/modifiers/
- Get all modifier groups for a menu item
- Response: Array of modifier group objects

GET /menu/api/items/featured/
- Get featured menu items
- Response: Array of featured items (top 8)

GET /menu/api/items/popular/
- Get popular menu items
- Response: Array of popular items (top 6)
```

### Modifier Groups
- **GET** `/api/menu/modifier-groups/` - List all modifier groups
- **GET** `/api/menu/modifier-groups/{id}/` - Get specific modifier group

#### Modifiers
```
GET /menu/api/modifier-groups/
- List all active modifier groups
- Response: Array of modifier group objects

GET /menu/api/modifier-groups/{id}/
- Get specific modifier group
- Response: Modifier group object with modifiers

GET /menu/api/modifiers/
- List all available modifiers
- Response: Array of modifier objects
```

### Admin Menu APIs

#### Category Management
```
GET /menu/api/admin/categories/
POST /menu/api/admin/categories/
GET /menu/api/admin/categories/{id}/
PUT /menu/api/admin/categories/{id}/
PATCH /menu/api/admin/categories/{id}/
DELETE /menu/api/admin/categories/{id}/
- Full CRUD operations for menu categories
- Requires admin permissions
```

#### Item Management
```
GET /menu/api/admin/items/
POST /menu/api/admin/items/
GET /menu/api/admin/items/{id}/
PUT /menu/api/admin/items/{id}/
PATCH /menu/api/admin/items/{id}/
DELETE /menu/api/admin/items/{id}/
- Full CRUD operations for menu items
- Requires admin permissions

POST /menu/api/admin/items/{id}/toggle_availability/
- Toggle menu item availability
- Response: Updated menu item object
```

## Orders API Endpoints

### Cart Management
- **GET** `/api/orders/carts/` - Get current user's cart
- **POST** `/api/orders/carts/` - Create new cart
- **POST** `/api/orders/carts/{id}/add_item/` - Add item to cart
- **PUT** `/api/orders/carts/{id}/update_item/` - Update cart item
- **DELETE** `/api/orders/carts/{id}/remove_item/` - Remove item from cart
- **POST** `/api/orders/carts/{id}/clear/` - Clear all items from cart
- **POST** `/api/orders/carts/{id}/set_tip/` - Set tip amount

### Cart Management
```
GET /orders/api/carts/
- List user's carts (or session carts for guests)
- Response: Array of cart objects

POST /orders/api/carts/
- Create new cart
- Request body: Cart data
- Response: Created cart object

GET /orders/api/carts/{id}/
- Get specific cart with items
- Response: Cart object with nested items

PUT /orders/api/carts/{id}/
PATCH /orders/api/carts/{id}/
- Update cart details
- Response: Updated cart object

DELETE /orders/api/carts/{id}/
- Delete cart
- Response: 204 No Content
```

### Cart Item Operations
```
POST /orders/api/carts/{id}/add_item/
- Add item to cart with server-side price calculation
- Request body:
  {
    "menu_item_id": 123,
    "quantity": 2,
    "modifiers": [
      {"modifier_id": 456, "quantity": 1}
    ]
  }
- Response: Created cart item object

POST /orders/api/carts/{id}/update_item/
- Update cart item quantity
- Request body: {"item_id": 789, "quantity": 3}
- Response: Updated cart item object

POST /orders/api/carts/{id}/remove_item/
- Remove item from cart
- Request body: {"item_id": 789}
- Response: Success message

POST /orders/api/carts/{id}/clear/
- Clear all items from cart
- Response: Success message

POST /orders/api/carts/{id}/set_tip/
- Set tip amount for cart
- Request body: {"tip_amount": "5.00"}
- Response: Updated cart object
```

### Order Management
- **GET** `/api/orders/orders/` - List user's orders
- **POST** `/api/orders/orders/` - Create order from cart
- **GET** `/api/orders/orders/{id}/` - Get specific order details
- **POST** `/api/orders/orders/{id}/cancel/` - Cancel order
- **GET** `/api/orders/orders/my_orders/` - Get current user's orders

### Order Management
```
GET /orders/api/orders/
- List user's orders
- Response: Array of order list objects

POST /orders/api/orders/
- Create order from cart
- Request body:
  {
    "cart_id": 123,
    "customer_name": "John Doe",
    "customer_email": "john@example.com",
    "customer_phone": "+1234567890",
    "service_type_id": 1,
    "table_id": 5,
    "special_instructions": "No onions"
  }
- Response: Created order object

GET /orders/api/orders/{id}/
- Get specific order details
- Response: Full order object with items

POST /orders/api/orders/{id}/cancel/
- Cancel order (if possible)
- Response: Updated order object

GET /orders/api/orders/my_orders/
- Get current user's recent orders
- Response: Array of recent orders (last 20)
```

## Core API Endpoints

### Organizations & Locations
- **GET** `/api/core/organizations/` - List all organizations
- **GET** `/api/core/locations/` - List all locations
- **GET** `/api/core/locations/{id}/` - Get specific location details

### Organization & Location
```
GET /core/api/organizations/
- List active organizations
- Response: Array of organization objects

GET /core/api/locations/
- List active locations
- Response: Array of location objects
```

### Service Types & Tables
- **GET** `/api/core/service-types/` - List all service types
- **GET** `/api/core/tables/` - List available tables
- **GET** `/api/core/tables/{id}/availability/` - Check table availability

### Service Types
```
GET /core/api/service-types/
- List active service types
- Response: Array of service type objects

GET /core/api/service-types/{id}/availability/
- Check availability for a service type on specific date
- Query parameters: date (YYYY-MM-DD)
- Response: Availability data with time slots
```

### Table Management
```
GET /core/api/tables/
- List active tables
- Query parameters:
  - service_type: Filter by service type ID
  - min_capacity: Minimum capacity filter
- Response: Array of table objects

GET /core/api/tables/{id}/
- Get specific table details
- Response: Table object

GET /core/api/tables/{id}/availability/
- Check table availability
- Query parameters:
  - date: Date (YYYY-MM-DD)
  - time: Time (HH:MM)
  - duration: Duration in minutes (default: 120)
- Response: Availability status and conflicts
```

### Reservations
- **GET** `/api/core/reservations/` - List user's reservations
- **POST** `/api/core/reservations/` - Create new reservation
- **GET** `/api/core/reservations/{id}/` - Get specific reservation
- **PUT** `/api/core/reservations/{id}/` - Update reservation
- **DELETE** `/api/core/reservations/{id}/` - Cancel reservation
- **GET** `/api/core/reservations/upcoming/` - Get upcoming reservations
- **GET** `/api/core/reservations/history/` - Get reservation history

### Reservation Management
```
GET /core/api/reservations/
- List user's reservations
- Query parameters:
  - status: Filter by status
  - start_date: Start date filter (YYYY-MM-DD)
  - end_date: End date filter (YYYY-MM-DD)
- Response: Array of reservation list objects

POST /core/api/reservations/
- Create new reservation
- Request body:
  {
    "service_type_id": 1,
    "table_id": 5,
    "reservation_time": "2024-01-15T19:00:00Z",
    "party_size": 4,
    "duration_minutes": 120,
    "customer_name": "John Doe",
    "customer_email": "john@example.com",
    "customer_phone": "+1234567890",
    "special_requests": "Window table preferred"
  }
- Response: Created reservation object

GET /core/api/reservations/{id}/
- Get specific reservation details
- Response: Full reservation object

PUT /core/api/reservations/{id}/
PATCH /core/api/reservations/{id}/
- Update reservation
- Response: Updated reservation object

DELETE /core/api/reservations/{id}/
- Delete reservation
- Response: 204 No Content

POST /core/api/reservations/{id}/cancel/
- Cancel reservation
- Response: Updated reservation object

POST /core/api/reservations/{id}/modify/
- Modify reservation details
- Request body: Updated reservation data
- Response: Updated reservation object

GET /core/api/reservations/upcoming/
- Get upcoming reservations for user
- Response: Array of upcoming reservations (next 5)

GET /core/api/reservations/history/
- Get reservation history for user
- Response: Array of past reservations (last 20)
```

### Admin Core APIs

#### Table Management
```
GET /core/api/admin/tables/
POST /core/api/admin/tables/
GET /core/api/admin/tables/{id}/
PUT /core/api/admin/tables/{id}/
PATCH /core/api/admin/tables/{id}/
DELETE /core/api/admin/tables/{id}/
- Full CRUD operations for tables
- Requires admin permissions

POST /core/api/admin/tables/{id}/toggle_active/
- Toggle table active status
- Response: Updated table object
```

#### Reservation Management
```
GET /core/api/admin/reservations/
POST /core/api/admin/reservations/
GET /core/api/admin/reservations/{id}/
PUT /core/api/admin/reservations/{id}/
PATCH /core/api/admin/reservations/{id}/
DELETE /core/api/admin/reservations/{id}/
- Full CRUD operations for reservations
- Requires admin permissions

POST /core/api/admin/reservations/{id}/mark_seated/
- Mark reservation as seated
- Response: Updated reservation object

POST /core/api/admin/reservations/{id}/mark_completed/
- Mark reservation as completed
- Response: Updated reservation object

POST /core/api/admin/reservations/{id}/mark_no_show/
- Mark reservation as no show
- Response: Updated reservation object
```

## Data Models

### Menu Item Object
```json
{
  "id": 123,
  "name": "Margherita Pizza",
  "description": "Fresh tomatoes, mozzarella, basil",
  "price": "18.99",
  "image": "http://example.com/media/pizza.jpg",
  "category": {
    "id": 1,
    "name": "Pizzas"
  },
  "is_vegetarian": true,
  "is_available": true,
  "preparation_time": 15,
  "modifier_groups": [
    {
      "id": 1,
      "name": "Size",
      "is_required": true,
      "max_selections": 1,
      "modifiers": [
        {
          "id": 1,
          "name": "Small",
          "price_adjustment": "0.00"
        },
        {
          "id": 2,
          "name": "Large",
          "price_adjustment": "4.00"
        }
      ]
    }
  ]
}
```

### Cart Object
```json
{
  "id": 456,
  "items": [
    {
      "id": 789,
      "menu_item": {
        "id": 123,
        "name": "Margherita Pizza",
        "price": "18.99"
      },
      "quantity": 2,
      "modifiers": [
        {"modifier_id": 2, "quantity": 1}
      ],
      "unit_price": "22.99",
      "total_price": "45.98"
    }
  ],
  "subtotal": "45.98",
  "tax_amount": "3.68",
  "tip_amount": "5.00",
  "total_amount": "54.66",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z"
}
```

### Order Object
```json
{
  "id": 1001,
  "order_number": "ORD-2024-001001",
  "status": "confirmed",
  "customer_name": "John Doe",
  "customer_email": "john@example.com",
  "customer_phone": "+1234567890",
  "service_type_name": "Dine In",
  "table_number": "5",
  "items": [
    {
      "id": 2001,
      "menu_item_name": "Margherita Pizza",
      "quantity": 2,
      "unit_price": "22.99",
      "total_price": "45.98",
      "modifiers_display": "Large"
    }
  ],
  "subtotal": "45.98",
  "tax_amount": "3.68",
  "tip_amount": "5.00",
  "total_amount": "54.66",
  "payment": {
    "amount": "54.66",
    "currency": "USD",
    "is_paid": true,
    "stripe_payment_intent_id": "pi_1234567890"
  },
  "special_instructions": "No onions",
  "created_at": "2024-01-15T10:40:00Z",
  "estimated_ready_time": "2024-01-15T11:00:00Z"
}
```

### Reservation Object
```json
{
  "id": 501,
  "reservation_time": "2024-01-15T19:00:00Z",
  "end_time": "2024-01-15T21:00:00Z",
  "party_size": 4,
  "status": "confirmed",
  "customer_name": "Jane Smith",
  "customer_email": "jane@example.com",
  "customer_phone": "+1234567890",
  "service_type": {
    "id": 1,
    "name": "Dine In",
    "code": "DINE_IN"
  },
  "table": {
    "id": 5,
    "table_number": "5",
    "capacity": 6
  },
  "special_requests": "Window table preferred",
  "created_at": "2024-01-10T14:30:00Z"
}
```

## Error Handling

All APIs return consistent error responses:

```json
{
  "error": "Error message",
  "details": {
    "field_name": ["Field-specific error message"]
  }
}
```

Common HTTP status codes:
- `200 OK`: Successful GET, PUT, PATCH
- `201 Created`: Successful POST
- `204 No Content`: Successful DELETE
- `400 Bad Request`: Validation errors
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Permission denied
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

## Rate Limiting

- Public APIs: 100 requests per minute per IP
- Authenticated APIs: 1000 requests per minute per user
- Admin APIs: 2000 requests per minute per admin user

## Caching

- Menu data is cached for 15 minutes
- Organization/Location data is cached for 1 hour
- Service types and tables are cached for 30 minutes

## API Versioning

All APIs are currently version 1. Future versions will be accessible via:
- Header: `Accept: application/vnd.api+json;version=2`
- URL: `/v2/menu/api/items/`