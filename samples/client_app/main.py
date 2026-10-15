"""
Consumer Application - Main Entry Point.
Currently calling ManualServiceClient from manual_service.service.
"""
import os
from manual_service.service import ManualServiceClient

def run_daily_batch():
    api_key = os.getenv("API_KEY", "prod-key-999")
    client = ManualServiceClient(api_key=api_key)

    print("Fetching user profile...")
    user = client.get_user_profile(user_id=101, include_billing=True)
    print(f"User retrieved: {user}")

    print("Searching catalog for winter jackets...")
    results = client.search_catalog(query="winter jackets", page_size=25)
    print(f"Found {len(results)} items.")

    print("Updating inventory...")
    stock = client.update_inventory_stock(product_id=55, quantity=100, reason="restock")
    print(f"Inventory updated: {stock}")

if __name__ == "__main__":
    run_daily_batch()
