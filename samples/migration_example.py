"""
Exemple de migration de code :
Passage des appels au microservice manuel vers le microservice autogénéré.
Ce fichier sert de modèle (few-shot) pour orienter l'outil de migration.
"""

# ==============================================================================
# AVANT LA MIGRATION (Microservice Manuel)
# ==============================================================================
from manual_service.service import ManualServiceClient

def sync_user_data(user_id: int):
    # Instanciation du client manuel avec api_key
    client = ManualServiceClient(api_key="secret-api-key-123")

    # 1. Récupération profil utilisateur
    profile = client.get_user_profile(user_id=user_id, include_billing=True)

    # 2. Recherche dans le catalogue avec query et page_size
    items = client.search_catalog(query="shoes", page_size=10)

    # 3. Création de commande avec customer_id et discount_code
    order = client.create_order(
        customer_id=user_id,
        items=[{"sku": "SHOE-1", "qty": 1}],
        discount_code="PROMO20"
    )

    # 4. Consultation des vues produit
    views = client.get_product_views(product_id=456, view_id="desktop")

    return profile, items, order, views


# ==============================================================================
# APRÈS LA MIGRATION (Microservice Autogénéré)
# ==============================================================================
from autogen_service.service import SyncApiClient
from autogen_service.service_dependency import get_sync_api_client
from bp2i_airflow_library.dependencies import depends

def sync_user_data(user_id: int):
    # Instanciation via dépendance FastAPI autogénérée :
    client = SyncApiClient = depends(get_sync_api_client)
    # Ou instanciation directe :
    # client = SyncApiClient(token="secret-api-key-123")

    # 1. getUserById via la sous-classe client.users avec id au lieu de user_id
    profile = client.users.get_user_by_id(id=user_id)

    # 2. getCatalogSearch avec q au lieu de query et limit au lieu de page_size
    items = client.get_catalog_search(q="shoes", limit=10)

    # 3. postOrders avec voucher au lieu de discount_code
    order = client.post_orders(
        customer_id=user_id,
        items=[{"sku": "SHOE-1", "qty": 1}],
        voucher="PROMO20"
    )

    # 4. get_product_views via la sous-classe client.views vers le client autogénéré
    views = client.views.get_product_views(product_id=456, view_id="desktop")

    return profile, items, order, views
