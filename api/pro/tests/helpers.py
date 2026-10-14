from tests.helpers import PNG


def set_seller_profile(api):
    """Profil du cédant complet (obligatoire pour établir un certificat)."""
    return api.put("/seller-profile/", {
        "first_name": "Manu", "last_name": "Test", "address": "1 rue des Récifs", "postal_code": "75001",
        "city": "Paris", "email": "vendeur@example.org", "phone": "0600000000",
        "legal_mention": "Boutures issues de colonies détenues légalement.", "signature": PNG,
    })
