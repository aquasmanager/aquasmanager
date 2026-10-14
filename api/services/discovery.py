"""
Recherche des contrôleurs ESPHome sur le réseau local (mDNS / zeroconf).
"""

import socket
import time
from typing import List
from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
from schemas.controller import Type

class ESPHomeListener(ServiceListener):
    def __init__(self):
        self.found_devices = []

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info and info.addresses:
            ip = socket.inet_ntoa(info.addresses[0])

            # Décodage sécurisé des TXT records
            properties = {}
            for k, v in info.properties.items():
                try:
                    key = k.decode("utf-8") if isinstance(k, bytes) else str(k)
                    val = v.decode("utf-8") if isinstance(v, bytes) else str(v)
                    properties[key] = val
                except (UnicodeDecodeError, AttributeError):
                    continue

            # Extrait le nom propre du nœud (ex: "esp32-bac-principal")
            clean_name = name.split(".")[0]

            # Déduction dynamique de la plateforme (ESP32 vs ESP8266)
            board = properties.get("board", "").lower()
            ctrl_type = Type.ESP8266 if "esp8266" in board else Type.ESP32

            self.found_devices.append({
                "name": clean_name,
                "ip": ip,
                "type": ctrl_type,
                "version": properties.get("version")  # Info optionnelle utile
            })

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass


def scan_network_for_esphome(timeout: int = 3) -> List[dict]:
    """Scanne le réseau local pendant `timeout` secondes à la recherche d'appareils ESPHome."""
    zeroconf = Zeroconf()
    listener = ESPHomeListener()
    # Le navigateur écoute en tâche de fond jusqu'à zeroconf.close()
    ServiceBrowser(zeroconf, "_esphomelib._tcp.local.", listener)

    time.sleep(timeout)
    zeroconf.close()

    return listener.found_devices