"""
Product Analytics module in client application.
"""
from manual_service.service import ManualServiceClient

def inspect_product_metrics(product_id: int):
    client = ManualServiceClient(api_key="analytics-key")
    views = client.get_product_views(product_id=product_id, view_id="overview")
    return views
