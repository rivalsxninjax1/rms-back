"""
DoorDash API Integration Service

This module provides integration with DoorDash Drive API for order management.
Replace placeholder API keys with actual keys from DoorDash Developer Portal.
"""

import requests
import logging
from typing import Dict, Any, Optional
from django.conf import settings


logger = logging.getLogger(__name__)


class DoorDashService:
    """
    DoorDash API integration for order management and delivery.
    
    Documentation: https://developer.doordash.com/en-US/docs/drive/reference/
    """
    
    def __init__(self):
        # TODO: Replace with actual DoorDash API credentials
        self.api_key = getattr(settings, 'DOORDASH_API_KEY', 'DD_API_KEY_PLACEHOLDER')
        self.api_secret = getattr(settings, 'DOORDASH_API_SECRET', 'DD_SECRET_PLACEHOLDER')
        self.environment = getattr(settings, 'DOORDASH_ENVIRONMENT', 'sandbox')
        
        # API endpoints
        if self.environment == 'production':
            self.base_url = 'https://openapi.doordash.com'
        else:
            self.base_url = 'https://openapi.doordash.com'  # DoorDash uses same URL for sandbox
        
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def create_delivery_quote(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a delivery quote for an order.
        
        Args:
            order_data: Order information including pickup/delivery addresses
            
        Returns:
            Quote response with pricing and estimated times
        """
        endpoint = f"{self.base_url}/drive/v2/quotes"
        
        payload = {
            "external_delivery_id": order_data.get('external_id'),
            "pickup_address": {
                "street": order_data['pickup_address']['street'],
                "city": order_data['pickup_address']['city'],
                "state": order_data['pickup_address']['state'],
                "zip_code": order_data['pickup_address']['zip_code']
            },
            "dropoff_address": {
                "street": order_data['dropoff_address']['street'],
                "city": order_data['dropoff_address']['city'],
                "state": order_data['dropoff_address']['state'],
                "zip_code": order_data['dropoff_address']['zip_code']
            },
            "pickup_time": order_data.get('pickup_time'),
            "dropoff_time": order_data.get('dropoff_time'),
            "order_value": order_data.get('order_value', 0),
        }
        
        try:
            response = requests.post(endpoint, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"DoorDash quote request failed: {e}")
            return {
                'error': 'Failed to get delivery quote from DoorDash',
                'details': str(e),
                'mock_data': {
                    'external_delivery_id': order_data.get('external_id'),
                    'fee': 4.99,
                    'currency': 'USD',
                    'estimated_pickup_time': '2025-08-28T18:30:00Z',
                    'estimated_dropoff_time': '2025-08-28T19:00:00Z'
                }
            }
    
    def create_delivery(self, delivery_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a delivery request with DoorDash.
        
        Args:
            delivery_data: Complete delivery information
            
        Returns:
            Delivery confirmation with tracking information
        """
        endpoint = f"{self.base_url}/drive/v2/deliveries"
        
        payload = {
            "external_delivery_id": delivery_data.get('external_id'),
            "pickup_address": delivery_data['pickup_address'],
            "pickup_business_name": delivery_data.get('pickup_business_name', 'Sample Restaurant'),
            "pickup_phone_number": delivery_data.get('pickup_phone', '+1234567890'),
            "pickup_instructions": delivery_data.get('pickup_instructions', ''),
            "dropoff_address": delivery_data['dropoff_address'],
            "dropoff_contact": {
                "first_name": delivery_data['customer']['first_name'],
                "last_name": delivery_data['customer']['last_name'],
                "phone_number": delivery_data['customer']['phone']
            },
            "dropoff_instructions": delivery_data.get('dropoff_instructions', ''),
            "order_value": delivery_data.get('order_value', 0),
            "items": delivery_data.get('items', []),
            "pickup_time": delivery_data.get('pickup_time'),
            "dropoff_time": delivery_data.get('dropoff_time'),
        }
        
        try:
            response = requests.post(endpoint, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"DoorDash delivery creation failed: {e}")
            return {
                'error': 'Failed to create delivery with DoorDash',
                'details': str(e),
                'mock_data': {
                    'delivery_id': f"mock_dd_{delivery_data.get('external_id', 'unknown')}",
                    'status': 'created',
                    'tracking_url': f"https://doordash.com/consumer/orders/track/{delivery_data.get('external_id')}"
                }
            }
    
    def get_delivery_status(self, delivery_id: str) -> Dict[str, Any]:
        """
        Get the current status of a delivery.
        
        Args:
            delivery_id: DoorDash delivery ID
            
        Returns:
            Current delivery status and tracking information
        """
        endpoint = f"{self.base_url}/drive/v2/deliveries/{delivery_id}"
        
        try:
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"DoorDash status request failed: {e}")
            return {
                'error': 'Failed to get delivery status from DoorDash',
                'details': str(e),
                'mock_data': {
                    'delivery_id': delivery_id,
                    'status': 'in_progress',
                    'dasher_name': 'John D.',
                    'dasher_phone': '+1555123456',
                    'estimated_pickup_time': '2025-08-28T18:30:00Z',
                    'estimated_dropoff_time': '2025-08-28T19:00:00Z'
                }
            }
    
    def cancel_delivery(self, delivery_id: str) -> Dict[str, Any]:
        """
        Cancel a delivery request.
        
        Args:
            delivery_id: DoorDash delivery ID
            
        Returns:
            Cancellation confirmation
        """
        endpoint = f"{self.base_url}/drive/v2/deliveries/{delivery_id}/cancel"
        
        try:
            response = requests.put(endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"DoorDash cancellation failed: {e}")
            return {
                'error': 'Failed to cancel delivery with DoorDash',
                'details': str(e),
                'mock_data': {
                    'delivery_id': delivery_id,
                    'status': 'cancelled',
                    'cancellation_fee': 0
                }
            }
    
    def webhook_handler(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming webhooks from DoorDash.
        
        Args:
            webhook_data: Webhook payload from DoorDash
            
        Returns:
            Processing result
        """
        event_type = webhook_data.get('event_name')
        delivery_id = webhook_data.get('delivery_id')
        
        logger.info(f"Received DoorDash webhook: {event_type} for delivery {delivery_id}")
        
        # Process different event types
        if event_type == 'delivery_status_update':
            # Handle delivery status updates
            status = webhook_data.get('data', {}).get('status')
            logger.info(f"Delivery {delivery_id} status updated to: {status}")
            
        elif event_type == 'delivery_pickup':
            # Handle pickup confirmation
            logger.info(f"Delivery {delivery_id} has been picked up")
            
        elif event_type == 'delivery_dropoff':
            # Handle dropoff confirmation
            logger.info(f"Delivery {delivery_id} has been delivered")
            
        elif event_type == 'delivery_cancelled':
            # Handle cancellation
            logger.info(f"Delivery {delivery_id} has been cancelled")
        
        return {'status': 'processed', 'event': event_type}


# Example usage functions
def create_doordash_order(order_instance):
    """
    Helper function to create a DoorDash delivery for an order instance.
    
    Args:
        order_instance: Django Order model instance
    """
    service = DoorDashService()
    
    # Extract order data
    order_data = {
        'external_id': f"order_{order_instance.id}",
        'pickup_address': {
            'street': '123 Main St',
            'city': 'City',
            'state': 'State',
            'zip_code': '12345'
        },
        'dropoff_address': {
            'street': '456 Customer Ave',
            'city': 'City',
            'state': 'State', 
            'zip_code': '12346'
        },
        'customer': {
            'first_name': 'John',
            'last_name': 'Customer',
            'phone': '+1555987654'
        },
        'order_value': float(order_instance.grand_total()) * 100,  # Convert to cents
        'items': [
            {
                'name': item.menu_item.name,
                'quantity': item.quantity,
                'price': float(item.unit_price) * 100  # Convert to cents
            }
            for item in order_instance.items.all()
        ]
    }
    
    # Get quote first
    quote = service.create_delivery_quote(order_data)
    
    if 'error' not in quote:
        # Create delivery if quote is successful
        delivery = service.create_delivery(order_data)
        return delivery
    
    return quote
