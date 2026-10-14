"""
Les datetimes sont stockés naïfs en UTC (datetime.now() sur un pod en UTC).
Sérialisés sans fuseau, le navigateur les lit comme de l'heure locale (-2h
l'été à Paris) : on les marque explicitement UTC ("Z") à la sortie.
"""

import re
from typing import Any

from fastapi.responses import JSONResponse

_NAIVE_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$")


def mark_naive_datetimes_utc(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(" ", "T", 1) + "Z" if _NAIVE_ISO_RE.match(value) else value
    if isinstance(value, dict):
        return {k: mark_naive_datetimes_utc(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mark_naive_datetimes_utc(v) for v in value]
    return value


class UTCJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return super().render(mark_naive_datetimes_utc(content))
