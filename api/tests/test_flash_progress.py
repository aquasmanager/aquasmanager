import asyncio
import os
import stat

from middleware.database import SessionLocal
from models.controller import Controller
from models.logs import LogModel
from services import controller as controller_service

FAKE_ESPHOME = """#!/bin/sh
echo "INFO Reading configuration $2..."
echo "INFO Generating C++ source..."
echo "INFO Compiling app..."
printf '[1/4] Building a\\r[2/4] Building b\\r[3/4] Building c\\r[4/4] Linking\\n'
echo "INFO Successfully compiled program."
echo "INFO Connecting to 192.168.1.50 port 3232..."
printf 'Uploading: [=====     ] 50%% \\rUploading: [==========] 100%% Done...\\n'
echo "INFO OTA successful"
exit ${FAKE_ESPHOME_EXIT:-0}
"""


def _fake_esphome(tmp_path, monkeypatch, exit_code):
    script = tmp_path / "esphome"
    script.write_text(FAKE_ESPHOME)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_ESPHOME_EXIT", str(exit_code))


async def _flash(controller_id):
    await controller_service.queue_flash(controller_id, "esp")
    await controller_service.run_esphome_ota(controller_id, "esphome:\n  name: esp\n", "192.168.1.50")


def test_flash_success_updates_progress_and_controller(api, controller, tmp_path, monkeypatch):
    _fake_esphome(tmp_path, monkeypatch, 0)
    api.patch(f"/controllers/{controller['id']}", {"zone": "décante"})  # rien d'important, contrôleur existant
    asyncio.run(_flash(controller["id"]))

    state = controller_service.FLASH_STATE[controller["id"]]
    assert state["status"] == "success" and state["percent"] == 100
    db = SessionLocal()
    try:
        ctrl = db.get(Controller, controller["id"])
        assert ctrl.is_dirty is False and ctrl.last_sync is not None and ctrl.status == "ONLINE"
        assert db.query(LogModel).filter(LogModel.controller_id == controller["id"], LogModel.component == "flash").count() == 1
    finally:
        db.close()
    assert any(s["controller_id"] == controller["id"] for s in api.get("/controllers/flash-status"))


def test_flash_failure_keeps_error_tail(api, controller, tmp_path, monkeypatch):
    _fake_esphome(tmp_path, monkeypatch, 2)
    asyncio.run(_flash(controller["id"]))

    state = controller_service.FLASH_STATE[controller["id"]]
    assert state["status"] == "failed"
    assert "OTA successful" in state["error"]
    db = SessionLocal()
    try:
        assert db.get(Controller, controller["id"]).status == "FLASH_FAILED"
    finally:
        db.close()
