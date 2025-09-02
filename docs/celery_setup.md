# Celery Task Queue Setup and Configuration

This document describes the Celery task queue implementation for post-payment processing in the RMS backend.

## Overview

The Celery task queue system handles asynchronous post-payment processing tasks including:

- Order confirmation emails
- Staff notifications
- POS system synchronization
- Payment analytics recording
- Loyalty rewards processing
- Inventory level updates

## Architecture

### Task Queues

Tasks are organized into specialized queues for better resource management:

- `default`: General purpose tasks
- `post_payment`: Main post-payment orchestration
- `emails`: Email sending tasks
- `pos_sync`: POS system synchronization
- `analytics`: Analytics and reporting
- `loyalty`: Loyalty program processing
- `inventory`: Inventory management

### Task Routing

Tasks are automatically routed to appropriate queues based on their function:

```python
CELERY_TASK_ROUTES = {
    'payments.tasks.send_order_confirmation_email_task': {'queue': 'emails'},
    'payments.tasks.sync_order_to_pos_task': {'queue': 'pos_sync'},
    # ... other routes
}
```

### Retry Policies

Each task type has specific retry policies:

- **Email tasks**: 3 retries, 60s delay
- **POS sync**: 5 retries, 120s delay
- **Analytics**: 2 retries, 30s delay
- **Loyalty**: 3 retries, 60s delay
- **Inventory**: 3 retries, 45s delay

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements/celery.txt
```

### 2. Redis Setup

Install and start Redis server:

```bash
# macOS with Homebrew
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis-server

# Docker
docker run -d -p 6379:6379 redis:7-alpine
```

### 3. Environment Variables

Add to your `.env` file:

```env
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
CELERY_TASK_TIME_LIMIT=300
CELERY_WORKER_PREFETCH_MULTIPLIER=1

# Email configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=1
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourrestaurant.com
```

## Running Celery Services

### Development

#### Option 1: Management Command

```bash
# Start worker with all queues
python manage.py start_celery_workers

# Start with beat scheduler and flower monitoring
python manage.py start_celery_workers --beat --flower

# Custom configuration
python manage.py start_celery_workers --workers 2 --queues emails,pos_sync
```

#### Option 2: Manual Commands

```bash
# Start worker
celery -A rms_backend worker --loglevel=info --concurrency=4

# Start beat scheduler (in separate terminal)
celery -A rms_backend beat --loglevel=info

# Start flower monitoring (in separate terminal)
celery -A rms_backend flower --port=5555
```

#### Option 3: Docker Compose

```bash
# Start all services
docker-compose -f docker-compose.celery.yml up -d

# View logs
docker-compose -f docker-compose.celery.yml logs -f celery_worker

# Stop services
docker-compose -f docker-compose.celery.yml down
```

### Production

For production deployment, use a process manager like systemd or supervisor:

#### Systemd Service Example

```ini
# /etc/systemd/system/celery-worker.service
[Unit]
Description=Celery Worker Service
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
EnvironmentFile=/path/to/your/.env
WorkingDirectory=/path/to/rms-backend
ExecStart=/path/to/venv/bin/celery -A rms_backend worker --detach --loglevel=info
ExecStop=/path/to/venv/bin/celery -A rms_backend control shutdown
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=300

[Install]
WantedBy=multi-user.target
```

## Task Implementation

### Creating New Tasks

```python
# payments/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from orders.models import Order
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def my_custom_task(self, order_id, additional_data=None):
    """Custom post-payment processing task."""
    try:
        order = Order.objects.get(id=order_id)
        
        # Your task logic here
        process_custom_logic(order, additional_data)
        
        logger.info(f"Custom task completed for order {order_id}")
        return {'success': True, 'order_id': order_id}
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
        raise
    except Exception as exc:
        logger.error(f"Custom task failed for order {order_id}: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

### Task Best Practices

1. **Idempotency**: Tasks should be safe to run multiple times
2. **Error Handling**: Always handle exceptions gracefully
3. **Logging**: Log important events and errors
4. **Timeouts**: Set appropriate task time limits
5. **Retries**: Implement retry logic for transient failures

## Monitoring

### Flower Web Interface

Access Flower at `http://localhost:5555` to monitor:

- Active workers and queues
- Task execution statistics
- Failed task details
- Real-time task monitoring

### Logging

Celery logs are written to:

- `logs/celery_worker.log`: Worker process logs
- `logs/celery_beat.log`: Beat scheduler logs
- `logs/celery_flower.log`: Flower monitoring logs

### Health Checks

```bash
# Check worker status
celery -A rms_backend inspect active

# Check registered tasks
celery -A rms_backend inspect registered

# Check queue lengths
celery -A rms_backend inspect active_queues
```

## Testing

### Running Task Tests

```bash
# Run all task tests
python manage.py test payments.tests.test_tasks

# Run specific test class
python manage.py test payments.tests.test_tasks.TestEmailTasks

# Run with coverage
coverage run --source='.' manage.py test payments.tests.test_tasks
coverage report
```

### Manual Task Testing

```python
# Django shell
python manage.py shell

# Test task execution
from payments.tasks import send_order_confirmation_email_task
from orders.models import Order

order = Order.objects.first()
result = send_order_confirmation_email_task.delay(order.id, 'test@example.com')
print(f"Task ID: {result.id}")
print(f"Result: {result.get()}")
```

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Check Redis server is running: `redis-cli ping`
   - Verify connection URL in settings

2. **Tasks Not Executing**
   - Check worker is running and consuming from correct queues
   - Verify task routing configuration

3. **Email Tasks Failing**
   - Check SMTP credentials and settings
   - Verify email templates exist

4. **High Memory Usage**
   - Reduce worker concurrency
   - Enable task result expiration
   - Monitor task execution patterns

### Debug Mode

```bash
# Start worker in debug mode
celery -A rms_backend worker --loglevel=debug --concurrency=1

# Enable task tracing
export CELERY_TRACE=1
celery -A rms_backend worker --loglevel=info
```

## Performance Tuning

### Worker Configuration

```python
# Optimize for your workload
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # For long-running tasks
CELERY_TASK_ACKS_LATE = True  # Ensure task completion
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000  # Prevent memory leaks
```

### Queue Priorities

```python
# Set queue priorities
CELERY_TASK_ROUTES = {
    'payments.tasks.send_order_confirmation_email_task': {
        'queue': 'emails',
        'priority': 8,  # High priority
    },
    'payments.tasks.record_payment_analytics_task': {
        'queue': 'analytics',
        'priority': 3,  # Low priority
    },
}
```

### Scaling

- **Horizontal**: Add more worker processes/machines
- **Vertical**: Increase worker concurrency
- **Queue-specific**: Dedicated workers for specific queues

```bash
# Queue-specific workers
celery -A rms_backend worker --queues=emails --concurrency=2
celery -A rms_backend worker --queues=pos_sync --concurrency=1
```

## Security Considerations

1. **Redis Security**: Use password authentication and network isolation
2. **Task Data**: Avoid passing sensitive data in task arguments
3. **Rate Limiting**: Implement task rate limiting for external APIs
4. **Monitoring**: Monitor for unusual task patterns or failures

## Integration with Payment Flow

The Celery tasks integrate seamlessly with the payment processing flow:

1. **Payment Success**: Stripe webhook triggers `mark_order_as_paid()`
2. **Post-Payment Hooks**: `run_post_payment_hooks()` is called
3. **Async Tasks**: Individual tasks are queued for background processing
4. **Monitoring**: All tasks are tracked and can be monitored via Flower

This ensures fast payment confirmation while handling time-consuming operations asynchronously.