"""
Manual Microservice implementation - Client calls and Server routes.
"""
from typing import Optional, List, Dict, Any
import requests
from fastapi import APIRouter

router = APIRouter()
BASE_URL = "https://internal-api.service.local/api/v1"

class ManualServiceClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def get_user_profile(self, user_id: int, include_billing: bool = False) -> Dict[str, Any]:
        """Fetch user profile with optional billing details."""
        url = f"{BASE_URL}/users/{user_id}"
        params = {"include_billing": include_billing}
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()

    def create_order(self, customer_id: int, items: List[Dict[str, Any]], discount_code: Optional[str] = None) -> Dict[str, Any]:
        """Place a customer order with items and optional promo code."""
        url = f"{BASE_URL}/orders"
        payload = {
            "customer_id": customer_id,
            "items": items,
            "discount_code": discount_code
        }
        response = requests.post(url, headers=self.headers, json=payload)
        return response.json()

    def update_inventory_stock(self, product_id: int, quantity: int, reason: str = "restock") -> Dict[str, Any]:
        """Update inventory stock count with tracking reason."""
        url = f"{BASE_URL}/inventory/{product_id}"
        payload = {"quantity": quantity, "reason": reason}
        response = requests.put(url, headers=self.headers, json=payload)
        return response.json()

    def delete_user_account(self, user_id: int, purge_data: bool = True) -> bool:
        """Delete user account and optionally purge GDPR records."""
        url = f"{BASE_URL}/users/{user_id}"
        params = {"purge_data": purge_data}
        response = requests.delete(url, headers=self.headers, params=params)
        return response.status_code == 204

    def search_catalog(self, query: str, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        """Search products catalog with pagination."""
        url = f"{BASE_URL}/catalog/search"
        params = {"query": query, "page": page, "page_size": page_size}
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()

    def legacy_ping(self) -> Dict[str, str]:
        """Old healthcheck endpoint - only in manual microservice."""
        url = f"{BASE_URL}/health"
        response = requests.get(url, headers=self.headers)
        return response.json()


# Server route handlers
@router.get("/api/v1/payments/{payment_id}")
def get_payment(payment_id: str, detailed: bool = False) -> Dict[str, Any]:
    """Retrieve payment details."""
    return {"payment_id": payment_id, "detailed": detailed, "status": "completed"}


@router.post("/api/v1/webhooks/stripe")
def handle_stripe_webhook(event_type: str, payload: Dict[str, Any]) -> Dict[str, str]:
    """Process incoming stripe payment webhook."""
    return {"status": "accepted", "event": event_type}
