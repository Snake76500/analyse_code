"""
Order processing service in the client application.
Calls ManualServiceClient to place orders and manage user accounts.
"""
from typing import List, Dict, Any
from manual_service.service import ManualServiceClient

class OrderManager:
    def __init__(self, api_key: str):
        self.client = ManualServiceClient(api_key=api_key)

    def submit_checkout(self, customer_id: int, cart_items: List[Dict[str, Any]], promo_code: str = "SPRING10"):
        print(f"Submitting order for customer {customer_id}...")
        order_response = self.client.create_order(
            customer_id=customer_id,
            items=cart_items,
            discount_code=promo_code
        )
        return order_response

    def close_account(self, user_id: int):
        print(f"Purging user account {user_id}...")
        success = self.client.delete_user_account(user_id=user_id, purge_data=True)
        return success
