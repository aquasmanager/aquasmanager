from datetime import datetime, timedelta

from middleware.database import SessionLocal
from models.sensor_reading import SensorReading


def test_sensor_history_is_bucketed(api, aquarium, controller, uid):
    sensor = api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "sensor",
                                    "name": f"Temp hist {uid}", "pin_id": controller["pins"]["4"], "unit": "temperature"},
                      code=201)
    now = datetime.now()
    db = SessionLocal()
    try:
        # Une mesure par minute pendant 2 h, plus une vieille mesure hors période
        for minute in range(120):
            db.add(SensorReading(sensor_id=sensor["id"], value=25 + (minute % 10) / 10, timestamp=now - timedelta(minutes=minute)))
        db.add(SensorReading(sensor_id=sensor["id"], value=99, timestamp=now - timedelta(days=3)))
        db.commit()
    finally:
        db.close()

    history = api.get(f"/sensors/{sensor['id']}/history", params={"period": "24h"})
    assert history["bucket_seconds"] == 300
    assert 24 <= len(history["points"]) <= 26  # 2 h en tranches de 5 min
    assert history["stats"]["max"] < 99
    point = history["points"][0]
    assert point["min"] <= point["avg"] <= point["max"]
    assert history["points"][0]["t"].endswith("Z")

    week = api.get(f"/sensors/{sensor['id']}/history", params={"period": "7d"})
    assert week["stats"]["max"] == 99
    api.get(f"/sensors/{sensor['id']}/history", params={"period": "1y"}, code=422)
