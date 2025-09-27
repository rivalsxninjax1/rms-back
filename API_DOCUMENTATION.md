# API Documentation

This document describes the REST API used by the storefront and admin SPA. It reflects the actual routes configured in rms_backend/urls.py:40–101.

Base API URL
- `https://<host>/api/` (all routers mounted here unless noted)
- Accounts routes live under `https://<host>/accounts/`

Auth Overview
- Public: menu browse, carts (guest session), coupons preview, loyalty ranks.
- JWT: login/register/profile; send `Authorization: Bearer <access>` for protected endpoints.
- Session JSON (legacy storefront): simple login/logout with HTTP-only cookie.
- Staff-only: writes on menu, coupons, loyalty profiles, reports, some payments and integrations.

OpenAPI/Docs
- Schema: `GET /api/schema/`
- Swagger UI: `GET /api/docs/`
- Redoc: `GET /api/redoc/`

Headers & Conventions
- `Authorization: Bearer <access>` for JWT-protected endpoints.
- JSON requests and responses; datetimes are ISO 8601.
- Pagination: DRF PageNumber (`?page=1&?page_size=20`, max 100 where enabled).
- Filtering/ordering/search: DRF conventions where specified below.

Accounts (JWT + Session)
- POST `/accounts/api/login/` — obtain `{access, refresh, user}`. Accepts username or email + password.
- POST `/accounts/api/register/` — create user; returns `{user, access, refresh}`.
- POST `/accounts/api/logout/` — blacklist `refresh`, end session (JWT required).
- POST `/accounts/api/token/refresh/` — refresh token.
- POST `/accounts/api/token/session/` — exchange current session for JWT (session cookie required).
- POST `/accounts/api/token/verify/` — verify token.
- GET/PUT `/accounts/api/profile/` — get/update current user profile (JWT).
- POST `/accounts/api/change-password/` — change password (JWT).
- POST `/accounts/api/password-reset/` — request reset email.
- POST `/accounts/api/password-reset/confirm/` — confirm reset with token.
- Legacy session JSON (cookie-based):
  - POST `/accounts/login/` — `{username,password}` → sets session cookie.
  - POST `/accounts/register/` — creates user + logs in.
  - POST `/accounts/logout/`
  - GET `/accounts/auth/whoami/` — `{ok,is_auth,user,csrf}` ping for storefront.
  - GET `/accounts/me/` — session user info.

Menu
- GET `/api/categories/` — active categories (AllowAny; search=`name,description`, order by `sort_order,name`).
- GET `/api/categories/{id}/` — category details.
- GET `/api/categories/with_items/` — categories with available items (cached 15m).
- GET `/api/categories/{id}/items/` — available items for a category.
- GET `/api/items/` — list items (AllowAny). Filters: `search`, `category_id`, `is_vegan`, `is_gluten_free`, `min_price`, `max_price`. Ordering: `name,sort_order,created_at`.
- GET `/api/items/{id}/` — item detail.
- GET `/api/items/{id}/modifiers/` — modifier groups for item.
- GET `/api/items/featured/` — featured items.
- GET `/api/modifier-groups/` — groups; GET `/api/modifier-groups/{id}/`; GET `/api/modifier-groups/{id}/modifiers/`.
- GET `/api/modifiers/` — modifiers; GET `/api/modifiers/{id}/`.
- Admin-only utilities on items:
  - GET `/api/items/export_csv/` — CSV export (staff).
  - POST `/api/items/import_csv/` — upload CSV (staff, file=`file`).
- Display bundle:
  - GET `/api/display/` — `{categories, featured_items, totals, last_updated}` (cached 30m).
  - POST `/api/display/clear_cache/` (staff), GET `/api/display/stats/`.

Carts (Orders)
- Router base: `/api/carts/` (AllowAny; session-backed for guests).
- GET `/api/carts/` — get/create current cart; returns one cart with items and totals.
- POST `/api/carts/add_item/` — body `{menu_item_id, quantity, selected_modifiers?, notes?}`.
- PATCH `/api/carts/update_item/` — body `{cart_item_id, quantity, notes?}` (quantity=0 removes item).
- DELETE `/api/carts/remove_item/` — body `{cart_item_id}`.
- DELETE `/api/carts/clear/` — clear cart.
- GET `/api/carts/summary/` — quick numbers and amounts.
- POST `/api/carts/merge/` — body `{anonymous_cart_uuid}`; requires JWT (merges into user cart).
- GET `/api/carts/modifiers/?menu_item=<id>` — modifiers for a specific item or for items in cart.
- POST `/api/carts/apply_coupon/` — body `{coupon_code}`.
- POST `/api/carts/remove_coupon/` — remove any applied coupon.
- POST `/api/carts/set_tip/` — body `{tip_amount}` or `{tip_percentage}` (one of them).
- GET `/api/carts/analytics/` — cart-level analytics.
- POST `/api/carts/validate_integrity/` — validate cart structure/prices.

Orders
- Router base: `/api/orders/` (AllowAny; data filtered by user/session).
- GET `/api/orders/` — list orders (JWT: own; anonymous: session orders; staff/roles: all). Filters: `status, delivery_option`.
- POST `/api/orders/` — create order from cart. Body `{cart_uuid, notes?, delivery_option?}`.
- GET `/api/orders/{id}/` — order detail (includes items and totals).
- GET `/api/orders/{id}/track/` — lightweight tracking info.
- GET `/api/orders/recent/` — recent 5 for current user/session.
- POST `/api/orders/{id}/cancel/` — cancel if allowed.
- POST `/api/orders/{id}/refund/` — refund (business rules apply).
- PATCH `/api/orders/{id}/update_status/` — staff/admin; body `{status, reason?, notes?}`.
- GET `/api/orders/{id}/status_history/` — full history with durations.
- GET `/api/orders/{id}/analytics/` — order analytics snapshot.
- POST `/api/orders/cleanup_expired_carts/` — staff only.

Order Items
- Router base: `/api/order-items/`.
- GET `/api/order-items/` — items for accessible orders; filters: `status, order__status`.
- PATCH `/api/order-items/{id}/update_status/` — update single item (kitchen flows).
- GET `/api/order-items/order/{order_id}/` — items for an order.
- GET `/api/order-items/preparation_queue/` — kitchen queue (confirmed/preparing items).

Coupons
- Router base: `/api/coupons/` (list/preview AllowAny; writes staff-only).
- GET `/api/coupons/` — list; filters: `active, discount_type, customer_type`; search: `code,name,description,phrase`.
- GET `/api/coupons/{id}/` — detail.
- GET `/api/coupons/{id}/preview/?order_total=<decimal>&item_count=<int>&user_id?<id>&first?<bool>` — compute discount preview.

Loyalty
- Router base: `/api/loyalty/*`.
- GET `/api/loyalty/ranks/` — public ranks.
- Authenticated:
  - GET `/api/loyalty/profiles/` — own profile (staff lists all).
  - POST `/api/loyalty/profiles/{id}/adjust/` — staff; body `{delta, reason, reference?}`.
  - GET `/api/loyalty/profiles/{id}/ledger/` — entries; also ReadOnly `/api/loyalty/ledger/` with filters.
  - GET `/api/loyalty/profiles/export_csv/` — staff CSV.

Payments
- Mounted at both `/payments/` (legacy views) and `/api/payments/` (for SPA).
- POST `/api/payments/payment-intent/create/` — body `{amount_cents:int, currency?:str, order_id?:int, metadata?:{}}`; returns `{payment_intent_id, client_secret, amount_cents, currency, status}` (JWT).
- GET `/api/payments/payment-intent/{id}/status/` — status for own intent (JWT).
- POST `/api/payments/payment-intent/{id}/cancel/` — cancel if possible (JWT).
- POST `/api/payments/offline/` — record offline payment; body `{order_id, method:'cash'|'pos_card', amount, notes?}` (JWT; typically staff).
- POST `/api/payments/receipt/{order_id}/` — returns PDF response (JWT).
- Stripe webhooks: POST `/api/payments/webhook/` (Stripe only; server-side).
- Legacy checkout (session): POST `/payments/checkout/` — Stripe Checkout session or simulated payment; success/cancel landing pages under `/payments/checkout-success|checkout-cancel/`.

Reservations (Portal + API)
- Portal (customer UI): under `/reserve/`
  - GET `/reserve/api/availability/` — see reservations/urls_portal.py:19–22.
  - POST `/reserve/api/reservations/` — create.
  - POST `/reserve/api/deposits/success/` — deposit callback.
  - POST `/reserve/api/holds/create/` — create a temporary hold.
- API (admin and staff tools):
  - GET `/api/reservations/tables/` — filterable tables; GET `/api/reservations/tables/availability/` for windowed availability.
  - CRUD `/api/reservations/` — ReservationViewSet; actions: `confirm`, `cancel`, `check_in` (admin), `walkin` (POST body `{table_id, minutes?, guest_name?, party_size?, phone?}`) and more. See reservations/views.py:84–220 for request/response details.

Core (Org/Location/Service Types)
- Router base: `/api/core/` (read-only for storefront context).
- GET `/api/core/organizations/`
- GET `/api/core/locations/` and `/api/core/locations/{id}/`
- GET `/api/core/service-types/` and `/api/core/service-types/{id}/availability/?date=YYYY-MM-DD`
- GET `/api/core/tables/` and `/api/core/tables/{id}/availability/?date=YYYY-MM-DD&time=HH:MM&duration=120`

Reports (Admin)
- Router base: `/api/reports/`
- GET `/api/reports/daily-sales/` — admin list; actions: `/payments` (date range) and `/export_csv`.
- GET `/api/reports/shifts/` — admin list; actions: `open`, `close`, `z_report`.
- GET `/api/analytics/orders/` — order analytics; actions: `revenue_trends`, `customer_insights`.
- GET `/api/analytics/menu/` — item/category performance.
- GET `/api/audit-logs/` — admin audit logs.

Integrations (Admin)
- POST `/api/integrations/menu/sync/` — push menu to providers.
- POST `/api/integrations/inventory/availability/` — toggle item availability.
- GET `/api/integrations/orders/recent/` — deprecated placeholder.
- GET `/api/integrations/reports/sales/` — placeholder.
- POST `/api/integrations/order/status/` — push external status.
- Provider webhooks (server-side): `/api/integrations/ubereats/webhook/`, `/api/integrations/doordash/webhook/`, `/api/integrations/grubhub/webhook/`.

WebSockets (ASGI)
- Orders: `ws://<host>/ws/orders/` — live order events (admin SPA).
- Reports: `ws://<host>/ws/reports/` — reporting events.

Key Payloads
- Add to cart (POST `/api/carts/add_item/`):
  - `{ "menu_item_id": 123, "quantity": 2, "selected_modifiers": [{"modifier_id": 456, "quantity": 1}], "notes": "no onions" }`
- Update cart item (PATCH `/api/carts/update_item/`):
  - `{ "cart_item_id": 789, "quantity": 3, "notes": "extra spicy" }`
- Create order (POST `/api/orders/`):
  - `{ "cart_uuid": "uuid-string", "notes": "leave at door", "delivery_option": "TAKEAWAY" }`
- Create payment intent (POST `/api/payments/payment-intent/create/`):
  - `{ "amount_cents": 5466, "currency": "usd", "order_id": 1001, "metadata": {"source": "web"} }`
- Loyalty adjust (POST `/api/loyalty/profiles/{id}/adjust/`):
  - `{ "delta": 50, "reason": "Manual bonus", "reference": "PROMO2024" }`

Auth & Roles
- Anonymous: carts, menu browse, coupon preview, order creation from own cart, order tracking for own session.
- Authenticated: profile, own orders, payments, loyalty profile.
- Staff/roles (Manager, Cashier, Kitchen, Host): broad order visibility and status updates.

Errors & Status Codes
- Errors use `{ "error" | "detail": <message> }` plus field errors when applicable.
- Common HTTP codes: 200, 201, 204, 400, 401, 403, 404, 409, 500.

Notes & Limits
- Login/register/password reset are rate-limited via DRF throttle scopes (`login`, `register`, `password_reset`). Configure rates in REST_FRAMEWORK settings.
- Menu display and category-with-items responses are cached (15–30 minutes). Admin cache clear is provided.

Environment
- Stripe: `STRIPE_SECRET_KEY`, `STRIPE_CURRENCY`, `STRIPE_WEBHOOK_SECRET` for live payment flows.
- Integrations optional secrets: `DELIVERECT_WEBHOOK_SECRET`, `OTTER_WEBHOOK_SECRET`, `CHOWLY_WEBHOOK_SECRET`, `CHECKMATE_WEBHOOK_SECRET`, `CUBOH_WEBHOOK_SECRET`.

Quick Start (Storefront Flow)
- Browse menu: `GET /api/display/` or `GET /api/categories/` then `GET /api/items/?category_id=...`.
- Build cart as guest: `GET /api/carts/` then `POST /api/carts/add_item/` repeatedly.
- Show summary: `GET /api/carts/summary/`.
- Optional login: `POST /accounts/api/login/` then `POST /api/carts/merge/` with previous `anonymous_cart_uuid`.
- Create order: `POST /api/orders/` with `cart_uuid`.
- Pay: `POST /api/payments/payment-intent/create/` then confirm on client with Stripe using `client_secret`.

