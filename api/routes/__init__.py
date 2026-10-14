import importlib
import pkgutil
from fastapi import FastAPI
from pathlib import Path

# Routes du cœur (ce dossier) puis routes sous licence commerciale (pro/routes)
ROUTE_PACKAGES = ("routes", "pro.routes")


def include_routes(app: FastAPI):
    root = Path(__file__).resolve().parent.parent
    for package in ROUTE_PACKAGES:
        package_dir = root.joinpath(*package.split("."))
        for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
            module = importlib.import_module(f"{package}.{module_name}")
            if hasattr(module, "router"):
                app.include_router(module.router)
            # Routeurs supplémentaires d'un même module (ex : profil du cédant)
            for extra in getattr(module, "EXTRA_ROUTERS", ()):
                app.include_router(extra)
