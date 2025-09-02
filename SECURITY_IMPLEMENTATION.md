# Security Implementation Guide

This document outlines the comprehensive security measures implemented in the RMS Backend application.

## 🛡️ Security Features Implemented

### 1. Rate Limiting & DDoS Protection

#### Custom Rate Limiting Middleware
- **Location**: `core/rate_limiting.py`
- **Features**:
  - IP-based rate limiting with sliding window algorithm
  - User-based rate limiting for authenticated users
  - Endpoint-specific rate limits
  - Progressive penalties for repeat offenders
  - Whitelist/blacklist support
  - Detailed logging and monitoring
  - Temporary banning for severe violations

#### Rate Limit Configuration
```python
# Default limits (requests per minute)
RATE_LIMIT_DEFAULTS = {
    'anonymous': 60,        # 60 requests per minute
    'authenticated': 300,   # 300 requests per minute
    'burst': 10,           # 10 requests per 10 seconds
}

# Endpoint-specific limits
RATE_LIMIT_ENDPOINTS = {
    '/api/auth/login/': {'anonymous': 5, 'authenticated': 10},
    '/api/auth/register/': {'anonymous': 3, 'authenticated': 5},
    '/api/auth/password-reset/': {'anonymous': 2, 'authenticated': 3},
    '/api/orders/': {'anonymous': 20, 'authenticated': 100},
    '/api/reservations/': {'anonymous': 10, 'authenticated': 50},
}
```

#### Progressive Penalties
- **5 violations/hour**: Rate limits reduced by 50% for 30 minutes
- **10 violations/hour**: Temporary ban for 1 hour
- All violations are logged for security monitoring

### 2. Security Headers Middleware

#### Implemented Headers
- **X-Frame-Options**: `DENY` - Prevents clickjacking
- **X-Content-Type-Options**: `nosniff` - Prevents MIME type sniffing
- **X-XSS-Protection**: `1; mode=block` - XSS protection
- **Referrer-Policy**: `strict-origin-when-cross-origin` - Controls referrer information
- **Permissions-Policy**: Restricts access to sensitive browser features
- **Content-Security-Policy**: Basic CSP to prevent XSS and injection attacks
- **Strict-Transport-Security**: HSTS for HTTPS enforcement (production only)

### 3. Authentication & Authorization

#### JWT Token Security
- **Access Token Lifetime**: 15 minutes (configurable)
- **Refresh Token Lifetime**: 7 days (configurable)
- **Token Rotation**: Enabled for enhanced security
- **Blacklist After Rotation**: Prevents token reuse
- **Algorithm**: HS256 with secure signing key

#### Password Security
- **Minimum Length**: 12 characters
- **Validation**: User attribute similarity, common passwords, numeric-only prevention
- **Hashing**: Django's built-in PBKDF2 with SHA256

### 4. Database Security

#### Model Constraints & Validation
- **Check Constraints**: Ensure data integrity (prices, quantities, percentages)
- **Unique Constraints**: Prevent duplicate data
- **Foreign Key Constraints**: Maintain referential integrity
- **Indexes**: Optimized for performance and security queries

#### Examples of Implemented Constraints
```python
# Price validation
CheckConstraint(
    check=Q(price__gte=0.01) & Q(price__lte=99999.99),
    name='valid_price_range'
)

# Quantity validation
CheckConstraint(
    check=Q(quantity__gte=1) & Q(quantity__lte=999),
    name='valid_quantity_range'
)

# Tax percentage validation
CheckConstraint(
    check=Q(tax_percent__gte=0) & Q(tax_percent__lte=100),
    name='valid_tax_percent'
)
```

### 5. Input Validation & Sanitization

#### Model-Level Validation
- **Phone Number Validation**: Regex pattern enforcement
- **Email Validation**: Built-in Django email validation
- **Decimal Field Validation**: Min/max value validators
- **Choice Field Validation**: Restricted to predefined options

#### Custom Validation Methods
```python
def clean(self):
    """Custom validation logic"""
    if self.start_time and self.end_time:
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time")
    super().clean()
```

### 6. Error Handling & Logging

#### Comprehensive Error Handling
- **Location**: `core/middleware.py`
- **Features**:
  - Structured error logging with context
  - Security event tracking
  - Suspicious activity monitoring
  - Appropriate error responses (JSON/HTML)

#### Security Logging
```python
# Security events logged:
- Failed authentication attempts
- Rate limit violations
- Suspicious activity patterns
- Permission denied events
- Database errors
```

#### Log Files
- `logs/django.log`: General application logs
- `logs/django_errors.log`: Error-specific logs
- `logs/security.log`: Security-related events

### 7. Session Security

#### Session Configuration
- **Engine**: `cached_db` for performance and security
- **Cookie Age**: 7 days (configurable)
- **HttpOnly**: Prevents JavaScript access
- **Secure**: HTTPS-only cookies (production)
- **SameSite**: `Lax` for CSRF protection

### 8. CSRF Protection

#### Configuration
- **Cookie Security**: HttpOnly, Secure, SameSite
- **Trusted Origins**: Configurable via environment
- **Token Validation**: Automatic for state-changing requests

### 9. CORS Security

#### Configuration
- **Allow All Origins**: Disabled (security best practice)
- **Allowed Origins**: Explicitly configured
- **Credentials**: Allowed for authenticated requests
- **Headers**: Restricted to necessary headers only

### 10. File Upload Security

#### Restrictions
- **Max Memory Size**: 2.5MB (configurable)
- **File Permissions**: 644 for files, 755 for directories
- **Storage Backend**: Secure file system storage
- **Path Validation**: Prevents directory traversal

## 🔧 Configuration

### Environment Variables

#### Rate Limiting
```bash
RATE_LIMIT_ANONYMOUS=60
RATE_LIMIT_AUTHENTICATED=300
RATE_LIMIT_BURST=10
RATE_LIMIT_LOGIN_ANON=5
RATE_LIMIT_REGISTER_ANON=3
RATE_LIMIT_WHITELIST="127.0.0.1,::1"
RATE_LIMIT_BLACKLIST=""
```

#### Security Headers
```bash
SECURE_HSTS_SECONDS=31536000
SECURE_SSL_REDIRECT=1
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
```

#### JWT Configuration
```bash
JWT_ACCESS_MINUTES=15
JWT_REFRESH_DAYS=7
DJANGO_SECRET_KEY=your-secret-key-here
```

## 🚨 Security Monitoring

### Automated Monitoring
- Rate limit violation tracking
- Failed authentication attempt logging
- Suspicious activity pattern detection
- Database error monitoring

### Manual Monitoring
- Regular log file review
- Security event analysis
- Performance impact assessment
- Rate limit effectiveness evaluation

## 🛠️ Maintenance

### Regular Tasks
1. **Log Rotation**: Automatic with 15MB max size, 10 backups
2. **Cache Cleanup**: Redis-based caching with TTL
3. **Security Updates**: Regular dependency updates
4. **Configuration Review**: Periodic security settings audit

### Performance Considerations
- Rate limiting uses Redis for efficient storage
- Sliding window algorithm minimizes memory usage
- Database indexes optimize security queries
- Middleware ordering optimized for performance

## 📋 Security Checklist

- ✅ Rate limiting implemented
- ✅ Security headers configured
- ✅ JWT authentication secured
- ✅ Database constraints enforced
- ✅ Input validation implemented
- ✅ Error handling comprehensive
- ✅ Logging configured
- ✅ Session security enabled
- ✅ CSRF protection active
- ✅ CORS properly configured
- ✅ File upload restrictions in place

## 🔄 Next Steps

1. **Implement Caching Strategy**: For better performance
2. **Add API Documentation**: Security-focused API docs
3. **Security Testing**: Penetration testing and vulnerability assessment
4. **Monitoring Dashboard**: Real-time security monitoring
5. **Incident Response Plan**: Security incident handling procedures

---

**Note**: This security implementation follows industry best practices and OWASP guidelines. Regular security audits and updates are recommended to maintain the security posture.