from types import SimpleNamespace

from pywebpush import WebPushException

from services import push


def test_push_subscription_and_delivery(api, monkeypatch):
    sent = []

    def fake_webpush(subscription_info, data, **kwargs):
        if subscription_info["endpoint"].endswith("expired"):
            raise WebPushException("gone", response=SimpleNamespace(status_code=410))
        sent.append((subscription_info["endpoint"], data))

    monkeypatch.setattr(push, "webpush", fake_webpush)
    key = api.get("/push/public-key")["public_key"]
    assert len(key) == 87  # point P-256 non compressé en base64url

    good = {"endpoint": "https://push.example.org/abc", "keys": {"p256dh": "B" * 87, "auth": "a" * 22}}
    expired = {"endpoint": "https://push.example.org/expired", "keys": {"p256dh": "B" * 87, "auth": "a" * 22}}
    api.post("/push/subscriptions", good, code=201)
    api.post("/push/subscriptions", good, code=201)  # même appareil : pas de doublon
    api.post("/push/subscriptions", expired, code=201)

    assert push.send_push("Alerte", "KH bas dans le bac récifal", wait=True) == 2
    assert len(sent) == 1 and '"KH bas' in sent[0][1]
    # L'abonnement révoqué (410) a été supprimé
    assert push.send_push("Alerte", "encore", wait=True) == 1

    api.post("/push/unsubscribe", {"endpoint": good["endpoint"]}, code=204)
    assert push.send_push("Alerte", "plus personne", wait=True) == 0
