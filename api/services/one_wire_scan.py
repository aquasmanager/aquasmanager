"""
Détection des sondes 1-Wire (DS18B20...) branchées sur un contrôleur ESPHome.

Les adresses ne sont listées par le firmware que dans son dump_config
(niveau CONFIG), jamais publié sur MQTT (log_topic en INFO). On passe donc
par l'API native ESPHome : un abonnement aux logs avec dump_config=True
fait rejouer ce dump, comme `esphome logs`.
"""

import asyncio
import re
from typing import Iterable

from aioesphomeapi import APIClient, LogLevel

ESPHOME_API_PORT = 6053

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# [C][gpio.one_wire:087]: ... (cf. esphome/components/logger/log_buffer.h)
_TAG_RE = re.compile(r"^\[[A-Z]{0,2}\]\[([^\]:]+):\d+\]")
_PIN_RE = re.compile(r"Pin:\s*GPIO(\d+)")
# one_wire_bus.cpp::dump_devices_ : "    0x%s (%s)"
_DEVICE_RE = re.compile(r"\b0x([0-9a-fA-F]{16})\s+\(([^)]+)\)")


def parse_one_wire_scan(messages: Iterable[str]) -> dict:
    """{"config_received": dump_config reçu, "buses": [{"pin_number", "devices"}],
    "devices": [{"address", "model", "pin_number"}]}"""
    devices: dict[str, dict] = {}
    buses: dict[int | None, int] = {}
    current_pin: int | None = None
    config_received = False

    for raw in messages:
        # Un message peut regrouper plusieurs lignes CONFIG ("Logger:\n  Max
        # Level: ..."), seule la première porte l'en-tête [C][tag:ligne].
        lines = _ANSI_RE.sub("", raw).strip().split("\n")
        tag_match = _TAG_RE.match(lines[0])
        if not tag_match:
            continue
        config_received = True
        if "one_wire" not in tag_match.group(1):
            continue

        for line in lines:
            if "1-wire bus:" in line:
                current_pin = None
            elif pin_match := _PIN_RE.search(line):
                current_pin = int(pin_match.group(1))
                buses.setdefault(current_pin, 0)
            elif device_match := _DEVICE_RE.search(line):
                address = f"0x{device_match.group(1).lower()}"
                if address not in devices:
                    buses[current_pin] = buses.get(current_pin, 0) + 1
                devices.setdefault(address, {
                    "address": address,
                    "model": device_match.group(2),
                    "pin_number": current_pin,
                })

    return {
        "config_received": config_received,
        "buses": [{"pin_number": pin, "devices": count} for pin, count in buses.items()],
        "devices": list(devices.values()),
    }


async def read_config_logs(
    ip: str, listen_seconds: float = 12.0, connect_timeout: float = 10.0, quiet_seconds: float = 2.0
) -> list[str]:
    """Rejoue le dump_config du firmware (niveau CONFIG) via l'API native ESPHome.
    Écoute jusqu'à listen_seconds, ou s'arrête quand le contrôleur se tait depuis
    quiet_seconds : un firmware chargé (modules, relais) envoie un long dump."""
    client = APIClient(ip, ESPHOME_API_PORT, None, client_info="AquasManager")
    messages: list[str] = []
    loop = asyncio.get_running_loop()
    last = [loop.time()]

    def on_log(msg) -> None:
        messages.append(msg.message.decode("utf-8", errors="replace"))
        last[0] = loop.time()

    await asyncio.wait_for(client.connect(login=True), timeout=connect_timeout)
    try:
        client.subscribe_logs(on_log, log_level=LogLevel.LOG_LEVEL_CONFIG, dump_config=True)
        start = loop.time()
        while loop.time() - start < listen_seconds:
            await asyncio.sleep(0.25)
            if messages and loop.time() - last[0] >= quiet_seconds:
                break
    finally:
        await client.disconnect()
    return messages


async def scan_one_wire_devices(ip: str) -> dict:
    return parse_one_wire_scan(await read_config_logs(ip))


# --- Bus I2C -------------------------------------------------------------------------
# i2c_bus_*.cpp::dump_config : « Results from bus scan: » puis « Found device at
# address 0x20 » (ou « Found no devices »), seulement si scan: true (cas du firmware
# généré dès qu'il y a une horloge ou un module d'extension).
_I2C_FOUND_RE = re.compile(r"Found (?:i2c )?device at address (0x[0-9a-fA-F]{1,2})", re.IGNORECASE)


def parse_i2c_scan(messages: Iterable[str]) -> dict:
    """{"enabled": bus I2C présent dans le firmware, "addresses": ["0x20", ...]}"""
    enabled, addresses = False, []
    for raw in messages:
        lines = _ANSI_RE.sub("", raw).strip().split("\n")
        tag_match = _TAG_RE.match(lines[0])
        if not tag_match or not tag_match.group(1).startswith("i2c"):
            continue
        enabled = True
        for line in lines:
            if found := _I2C_FOUND_RE.search(line):
                address = f"0x{int(found.group(1), 16):02x}"
                if address not in addresses:
                    addresses.append(address)
    return {"enabled": enabled, "addresses": sorted(addresses)}


async def scan_i2c_devices(ip: str) -> dict:
    return parse_i2c_scan(await read_config_logs(ip))
