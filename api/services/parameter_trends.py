"""
Tendance des paramètres d'eau : pente des relevés récents (moindres carrés),
projection et date estimée de sortie de la plage cible. Sert à l'affichage
(« −0,12 dKH/jour, sous la cible dans ~4 jours ») et aux alertes préventives.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models.water_parameter import WaterParameter

logger = logging.getLogger(__name__)

WINDOW_DAYS = 21
MIN_READINGS = 3
MIN_SPAN_DAYS = 2.0
# Au-dessous, la tendance est trop incertaine pour prévoir une date
MIN_R2 = 0.5
ALERT_WITHIN_DAYS = 3
ALERT_REPEAT_DAYS = 3


def compute_trend(param: WaterParameter, now: Optional[datetime] = None) -> Optional[dict]:
    """None s'il n'y a pas assez de relevés récents."""
    now = now or datetime.now()
    since = now - timedelta(days=WINDOW_DAYS)
    points = [(r.timestamp, r.value) for r in param.readings if r.timestamp >= since]
    if len(points) < MIN_READINGS:
        return None
    t0 = points[0][0]
    xs = [(t - t0).total_seconds() / 86400 for t, _ in points]
    ys = [v for _, v in points]
    span = xs[-1] - xs[0]
    if span < MIN_SPAN_DAYS:
        return None

    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sxx
    intercept = mean_y - slope * mean_x
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0

    x_now = (now - t0).total_seconds() / 86400
    fitted_now = intercept + slope * x_now
    # Variation négligeable (< 1 % de la valeur sur une semaine) : stable
    scale = abs(mean_y) or 1.0
    direction = "stable" if abs(slope * 7) < 0.01 * scale else ("rising" if slope > 0 else "falling")

    limit, days_to_limit = None, None
    if direction == "falling" and param.target_min is not None and fitted_now > param.target_min:
        limit, days_to_limit = "min", (param.target_min - fitted_now) / slope
    elif direction == "rising" and param.target_max is not None and fitted_now < param.target_max:
        limit, days_to_limit = "max", (param.target_max - fitted_now) / slope
    reliable = r2 >= MIN_R2
    return {
        "parameter_id": param.id,
        "name": param.name,
        "unit": param.unit,
        "readings_used": n,
        "span_days": round(span, 1),
        "slope_per_day": round(slope, 4),
        "r2": round(r2, 2),
        "reliable": reliable,
        "direction": direction,
        "projected_7d": round(fitted_now + slope * 7, 3),
        "limit": limit if reliable else None,
        "days_to_limit": round(days_to_limit, 1) if reliable and days_to_limit is not None else None,
        "predicted_date": (now + timedelta(days=days_to_limit)).date().isoformat()
        if reliable and days_to_limit is not None
        else None,
    }


def trends_for_aquarium(db: Session, aquarium_id: int) -> list[dict]:
    params = db.query(WaterParameter).filter(WaterParameter.aquarium_id == aquarium_id).all()
    return [t for t in (compute_trend(p) for p in params) if t is not None]


def check_trend_alerts(db: Session, now: Optional[datetime] = None) -> int:
    """Alerte préventive : paramètre encore dans la cible mais qui en sort dans moins de 3 jours."""
    from models.aquarium import Aquarium
    from services import notify

    now = now or datetime.now()
    sent = 0
    for param in db.query(WaterParameter).filter(
        (WaterParameter.target_min.isnot(None)) | (WaterParameter.target_max.isnot(None))
    ):
        if param.in_target is not True:
            continue  # déjà hors cible : alerte classique
        if param.trend_alerted_at and now - param.trend_alerted_at < timedelta(days=ALERT_REPEAT_DAYS):
            continue
        trend = compute_trend(param, now)
        if not trend or trend["days_to_limit"] is None or trend["days_to_limit"] > ALERT_WITHIN_DAYS:
            continue
        aquarium = db.get(Aquarium, param.aquarium_id)
        unit = f" {param.unit}" if param.unit else ""
        bound = param.target_min if trend["limit"] == "min" else param.target_max
        way = "sous" if trend["limit"] == "min" else "au-dessus de"
        days = max(trend["days_to_limit"], 0)
        try:
            notify.dispatch_alert(
                f"Tendance : {param.name} ({aquarium.name if aquarium else '?'})",
                f"{param.name} passera {way} {bound}{unit} dans environ {days:.0f} jour(s) "
                f"(variation de {trend['slope_per_day']:+.3g}{unit}/jour sur {trend['span_days']:.0f} jours). "
                "Pense à ajuster le dosage.",
            )
        except Exception:
            logger.exception("Alerte de tendance impossible")
        param.trend_alerted_at = now
        sent += 1
    if sent:
        db.commit()
    return sent
