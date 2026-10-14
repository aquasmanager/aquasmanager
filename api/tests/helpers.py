from middleware.database import SessionLocal
from models.controller_pin import ControllerPin


def pin_state(pin_id: int) -> tuple[str, str, str]:
    db = SessionLocal()
    try:
        pin = db.get(ControllerPin, pin_id)
        return pin.mode.value, pin.bus.value, pin.label
    finally:
        db.close()


def equipment_payload(aquarium, controller, pin: str, name: str, **extra) -> dict:
    return {
        "name": name,
        "aquarium_id": aquarium["id"],
        "controller_id": controller["id"],
        "pin_id": controller["pins"][pin],
        "physical_contact": "NO",
        "status": "OFF",
        "mode": "AUTO",
        **extra,
    }


# Image PNG 1×1 (signatures)
PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


def make_coral(api, aquarium, uid):
    return api.post("/corals/", {
        "aquarium_id": aquarium["id"], "name": f"Acropora {uid}", "cites": "FR2026ABC123", "type": "SPS",
        "scientific_name": "Acropora millepora", "family": "Acroporidae", "origin": "Mariculture Indonésie",
        "light_range": {"min": 6, "max": 9}, "brewing_range": {"min": 6, "max": 9},
        "aggressiveness_level": 3, "resistance_level": 4, "location_level": 8, "date_acquisition": "2025-06-01",
    }, code=201)


def seller_headers(api, client, uid):
    """Compte au rôle « seller » (bourse) et son en-tête d'authentification."""
    api.post("/register", {"username": f"bourse{uid}", "password": "Password123!", "role": "seller",
                           "must_change_password": False}, code=201)
    token = client.post("/login", data={"username": f"bourse{uid}", "password": "Password123!"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
