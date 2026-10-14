from datetime import datetime, timedelta

from middleware.database import SessionLocal
from services import notify
from services.parameter_trends import check_trend_alerts


def test_trend_projection_and_preventive_alert(api, aquarium, uid, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "dispatch_alert", lambda subject, message, priority="default": sent.append((subject, message)))
    kh = api.post("/water-parameters/", {"aquarium_id": aquarium["id"], "name": f"KH {uid}", "unit": "dKH",
                                         "target_min": 7.5, "target_max": 9}, code=201)
    ca = api.post("/water-parameters/", {"aquarium_id": aquarium["id"], "name": f"Ca {uid}", "unit": "mg/L"}, code=201)
    now = datetime.now()
    # KH : baisse régulière de 0,2 dKH/jour sur 8 jours, dernière valeur 8,2 → sous 7,5 dans ~3,5 j
    for day, value in enumerate([9.8, 9.6, 9.4, 9.2, 9.0, 8.8, 8.6, 8.4, 8.2]):
        ts = (now - timedelta(days=8 - day)).isoformat(timespec="seconds")
        api.post(f"/water-parameters/{kh['id']}/readings", {"value": value, "timestamp": ts}, code=201)
    # Ca : 2 relevés seulement → pas de tendance
    for day in (1, 0):
        api.post(f"/water-parameters/{ca['id']}/readings", {"value": 420, "timestamp": (now - timedelta(days=day)).isoformat(timespec="seconds")}, code=201)

    trends = {t["name"]: t for t in api.get("/water-parameters/trends", params={"aquarium_id": aquarium["id"]})}
    assert f"Ca {uid}" not in trends
    trend = trends[f"KH {uid}"]
    assert trend["direction"] == "falling" and abs(trend["slope_per_day"] + 0.2) < 0.01 and trend["reliable"]
    assert trend["limit"] == "min" and 3 < trend["days_to_limit"] < 4 and trend["predicted_date"]

    # Encore dans la cible mais sortie prévue dans ~3,5 j : pas d'alerte (seuil 3 j) ...
    db = SessionLocal()
    try:
        assert check_trend_alerts(db, now) == 0
        # ... un jour plus tard (sortie dans ~2,5 j) : une alerte, pas répétée
        assert check_trend_alerts(db, now + timedelta(days=1)) == 1
        assert check_trend_alerts(db, now + timedelta(days=1, hours=2)) == 0
    finally:
        db.close()
    assert sent and f"KH {uid}" in sent[-1][0] and "sous 7.5 dKH" in sent[-1][1]
