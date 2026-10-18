import itertools
from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from services import group_orders as go


class FakeHub:
    """Hub minimal en mémoire (mêmes règles de visibilité que le vrai)."""

    def __init__(self):
        self.orders, self.ids = {}, itertools.count(1)

    def __call__(self, method, path, token=None, client=None, params=None, json=None):
        parts = [p for p in path.split("/") if p]
        if method == "GET" and not parts:
            deps = params["departments"].split(",")
            return [self._public(o) for o in self.orders.values() if o["department"] in deps]
        if method == "POST" and not parts:
            oid = f"o{next(self.ids)}"
            self.orders[oid] = {**json, "id": oid, "token": f"t-{oid}", "status": "open", "members": []}
            return {**self._detail(oid, f"t-{oid}"), "token": f"t-{oid}"}
        oid = parts[0]
        if oid not in self.orders:
            raise HTTPException(status_code=404, detail="Commande groupée introuvable.")
        order = self.orders[oid]
        if method == "GET":
            return self._detail(oid, token)
        if method == "PATCH" and len(parts) == 1:
            if token != order["token"]:
                raise HTTPException(status_code=403, detail="Seul l'organisateur.")
            order.update(json)
            return self._detail(oid, token)
        if method == "DELETE" and len(parts) == 1:
            del self.orders[oid]
            return None
        if method == "POST" and parts[1:] == ["participants"]:
            pid = f"p{next(self.ids)}"
            order["members"].append({**json, "id": pid, "token": f"t-{pid}"})
            return {**self._detail(oid, f"t-{pid}"), "token": f"t-{pid}"}
        if method == "PATCH" and parts[1] == "participants":
            member = next(m for m in order["members"] if m["id"] == parts[2])
            if token != member["token"]:
                raise HTTPException(status_code=403, detail="Seul le participant.")
            member.update(json)
            return self._detail(oid, token)
        if method == "DELETE" and parts[1] == "participants":
            order["members"] = [m for m in order["members"] if m["id"] != parts[2]]
            return None
        if method == "POST" and parts[1:] == ["report"]:
            return {"status": "reported"}
        raise AssertionError(f"{method} {path}")

    def _public(self, o):
        keys = ("id", "title", "shop", "department", "area", "deadline", "organizer", "status")
        return {**{k: o[k] for k in keys}, "participants": len(o["members"])}

    def _detail(self, oid, token):
        o = self.orders[oid]
        base = {**self._public(o), "role": None, "contact": None, "members": []}
        if token == o["token"]:
            return {**base, "role": "owner", "contact": o["contact"],
                    "members": [{k: m[k] for k in ("id", "name", "contact")} for m in o["members"]]}
        mine = [m for m in o["members"] if m["token"] == token]
        if mine:
            return {**base, "role": "participant", "contact": o["contact"],
                    "members": [{k: mine[0][k] for k in ("id", "name", "contact")}]}
        return base


@pytest.fixture()
def fake_hub(monkeypatch):
    fake = FakeHub()
    monkeypatch.setattr(go, "hub", fake)
    monkeypatch.setattr(go, "enabled", lambda: True)
    sent = []
    monkeypatch.setattr("services.notify.dispatch_alert", lambda subject, message, priority="default": sent.append(message))
    fake.sent = sent
    return fake


def test_group_order_flow(api, fake_hub):
    deadline = (date.today() + timedelta(days=7)).isoformat()
    created = api.post("/group-orders/", {"title": "Coraux De Jong", "shop": "Récif Passion", "department": "69",
                                          "area": "Lyon 7e", "deadline": deadline, "organizer": "Manu",
                                          "contact": "manu@example.org"}, code=201)
    assert created["my_role"] == "owner" and "token" not in created
    mine = api.get("/group-orders/mine")
    assert any(o["id"] == created["id"] and o["contact"] == "manu@example.org" for o in mine)

    # Annonce d'un autre passionné du secteur, rejointe d'ici
    other = fake_hub("POST", "", json={"title": "Poissons Ocean", "shop": "Aqua", "department": "01", "area": "Bourg",
                                       "deadline": deadline, "organizer": "Julie", "contact": "julie@example.org"})
    api.put("/group-orders/settings", {"departments": ["69", "01"], "notify": True})
    assert {o["id"] for o in api.get("/group-orders/")} >= {created["id"], other["id"]}
    seen = api.get(f"/group-orders/{other['id']}")
    assert seen["contact"] is None and seen["my_role"] is None

    items = [{"name": "Amphiprion ocellaris", "url": "https://example.org/clown", "quantity": 2}]
    joined = api.post(f"/group-orders/{other['id']}/join",
                      {"name": "Manu", "contact": "06 00", "message": "2 clowns", "items": items}, code=201)
    # Les lignes d'articles sont transmises au hub
    assert fake_hub.orders[other["id"]]["members"][0]["items"] == items
    api.post(f"/group-orders/{other['id']}/join",
             {"name": "Manu", "contact": "06 00", "items": [{"name": "X", "quantity": 0}]}, code=422)
    # Demande modifiée après coup : articles ajoutés / retirés
    more = items + [{"name": "Sel récifal 20 kg", "url": None, "quantity": 1}]
    api.patch(f"/group-orders/{other['id']}/join", {"items": more, "message": None})
    assert fake_hub.orders[other["id"]]["members"][0]["items"] == more
    assert joined["my_role"] == "participant" and joined["contact"] == "julie@example.org"
    api.post(f"/group-orders/{other['id']}/join", {"name": "Manu", "contact": "06 00"}, code=409)  # déjà inscrit
    api.patch(f"/group-orders/{other['id']}", {"status": "closed"}, code=403)  # pas l'organisateur

    closed = api.patch(f"/group-orders/{created['id']}", {"status": "closed"})
    assert closed["status"] == "closed"
    api.delete(f"/group-orders/{other['id']}/join")
    api.delete(f"/group-orders/{created['id']}")
    assert api.get("/group-orders/mine") == []


def test_group_order_news_notifications(fake_hub):
    from middleware.database import SessionLocal

    db_session = SessionLocal()
    deadline = (date.today() + timedelta(days=7)).isoformat()
    conf = go.get_settings(db_session)
    conf.departments, conf.notify, conf.seen_ids = ["38"], True, []
    db_session.commit()
    fake_hub("POST", "", json={"title": "Commande Grenoble", "shop": "Aqua", "department": "38", "area": "Grenoble",
                               "deadline": deadline, "organizer": "Léo", "contact": "leo@example.org"})
    messages = go.check_news(db_session)
    assert any("Commande Grenoble" in m for m in messages)
    assert go.check_news(db_session) == []  # déjà signalée
    db_session.close()
