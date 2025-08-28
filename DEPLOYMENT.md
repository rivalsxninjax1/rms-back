# RMS - Restaurant Management System

## Deployment Guide

### System Requirements

- Python 3.13+
- Node.js 20+
- SQLite3 (development) / PostgreSQL (production)
- Redis (for Celery background tasks)

### Development Setup

1. **Clone and Setup Environment**
   ```bash
   git clone <repository-url>
   cd rms-main
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env file with your settings
   ```

3. **Database Setup**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. **Frontend Setup**
   ```bash
   cd rms-admin
   npm install
   npm run build
   cd ..
   ```

5. **Static Files**
   ```bash
   python manage.py collectstatic --noinput
   ```

6. **Run Development Server**
   ```bash
   python manage.py runserver
   ```

### Production Deployment

1. **Environment Variables**
   - `DEBUG=0`
   - `DJANGO_SECRET_KEY=<your-secret-key>`
   - `DATABASE_URL=postgres://...` (PostgreSQL)
   - `ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com`
   - `CSRF_TRUSTED_ORIGINS=https://yourdomain.com`

2. **Database Migration**
   ```bash
   python manage.py migrate --no-input
   ```

3. **Static Files**
   ```bash
   python manage.py collectstatic --no-input
   ```

4. **Process Management**
   ```bash
   # Web server
   gunicorn rms_backend.wsgi:application --bind 0.0.0.0:8000

   # Background tasks (optional)
   celery -A rms_backend worker --loglevel=info
   ```

### Features Available

✅ **Core System**
- Django 5.1.2 backend with REST API
- React admin panel with Vite & TypeScript
- SQLite (dev) / PostgreSQL (prod) support
- WhiteNoise for static file serving

✅ **Applications**
- User authentication & accounts
- Menu management with categories & items
- Order processing & tracking
- Inventory management
- Reservations system
- Loyalty & engagement tracking
- Payment processing (Stripe integration)
- Reporting & analytics
- Billing system
- Coupon & discount system

✅ **Admin Features**
- Comprehensive Django admin interface
- Custom admin views for reports
- User management with permissions
- Order tracking & management

✅ **API & Documentation**
- RESTful API with DRF
- API documentation with Swagger/Redoc
- JWT authentication support
- CORS configuration

✅ **Frontend**
- React admin dashboard
- TypeScript for type safety
- Tailwind CSS for styling
- React Router for navigation
- Axios for API calls
- Zustand for state management

### URLs & Access

- **Main Site**: http://localhost:8000/
- **Admin Panel**: http://localhost:8000/admin/
  - Username: `admin`
  - Password: `admin123`
- **API Documentation**: http://localhost:8000/api/docs/
- **React Admin**: Build files served via Django static files

### Security Features

- CSRF protection
- SQL injection protection
- XSS protection
- Secure cookie settings
- CORS configuration
- Rate limiting ready

### Monitoring & Logging

- Comprehensive logging configuration
- Error tracking
- Payment transaction logging
- Request/response logging

### Known Issues & Improvements

1. **Static File Warnings**: Multiple static files with same names - normal but can be cleaned up
2. **Missing Images**: Some placeholder images need to be added
3. **Frontend**: Currently uses React Router v5 for compatibility
4. **Testing**: Unit tests need to be added
5. **Documentation**: API documentation is available but could be expanded

### Troubleshooting

1. **Migration Issues**: Run `python manage.py migrate --fake-initial` if needed
2. **Static Files**: Clear `staticfiles/` and run `collectstatic` again
3. **Frontend Build Issues**: Check Node.js version compatibility
4. **Database Issues**: Verify database permissions and connection settings

### Next Steps

1. Add comprehensive unit tests
2. Set up CI/CD pipeline
3. Add monitoring (Sentry, etc.)
4. Optimize database queries
5. Add caching layer
6. Set up backup strategy
7. Add email notifications
8. Implement real-time features with WebSockets
