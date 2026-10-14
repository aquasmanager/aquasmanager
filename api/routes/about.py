"""
about.py (routes)

Version de l'API et licences des composants tiers (page « Licences » de l'interface).
"""

from fastapi import APIRouter, Depends

from middleware.auth import min_role_required
from services.licenses import EXTERNAL_COMPONENTS, python_packages
from version import BUILD, __version__

router = APIRouter(prefix="/about", tags=["about"], dependencies=[Depends(min_role_required("consult"))])


@router.get("/version")
def version():
    return {"version": __version__, "build": BUILD}


@router.get("/licenses")
def licenses():
    return {"external": EXTERNAL_COMPONENTS, "python": python_packages()}
