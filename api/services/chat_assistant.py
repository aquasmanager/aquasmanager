"""
services/chat_assistant.py

Assistant conversationnel, branché sur le modèle de langage choisi par
l'utilisateur (services/llm_provider.py : Ollama en local ou service
compatible OpenAI), avec accès en lecture aux données de l'app via
tool-calling (désactivable). Le calcul de dosage est un outil de calcul déterministe
(pas une connaissance générique du LLM) : un mauvais dosage peut nuire
aux coraux/poissons, donc la formule vient d'ici, jamais d'une "mémoire"
du modèle sur tel ou tel produit.
"""

import json
import logging
import unicodedata
from typing import Any, Optional

from sqlalchemy.orm import Session

from services.llm_provider import LLMError, chat, connection_from, get_assistant_settings, llm_message
from models.aquarium import Aquarium
from models.water_parameter import WaterParameter
from models.sensor import Sensor
from models.equipment import Equipment

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Tu es l'assistant intégré à AquasManager, une application de gestion d'aquarium. "
    "Réponds en français, de façon concise et factuelle. "
    "Utilise TOUJOURS les outils fournis pour obtenir les valeurs réelles (paramètres d'eau, "
    "capteurs, équipements) plutôt que de deviner ou d'inventer une valeur. "
    "Pour un calcul de dosage, utilise TOUJOURS l'outil calculate_dosing avec des valeurs "
    "précises (demande-les à l'utilisateur si tu ne les as pas) : n'invente jamais une formule "
    "de dosage de mémoire, les produits varient trop d'une marque à l'autre. "
    "Si un aquarium, paramètre ou équipement demandé n'existe pas, dis-le clairement au lieu "
    "d'inventer une réponse."
)

SYSTEM_PROMPT_NO_DATA = (
    "Tu es l'assistant intégré à AquasManager, une application de gestion d'aquarium. "
    "Réponds en français, de façon concise et factuelle. Tu n'as pas accès aux données de "
    "l'utilisateur : ne donne jamais de valeur mesurée ni de dosage chiffré, et invite-le à "
    "vérifier ses relevés dans l'application."
)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_aquariums",
            "description": "Liste tous les aquariums avec leur nom et leur volume en litres.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_water_parameter",
            "description": (
                "Récupère la dernière valeur mesurée d'un paramètre d'eau saisi manuellement "
                "(KH, Ca, Mg, NO3, PO4, Sr...) pour un aquarium donné, avec sa cible configurée."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "aquarium_name": {"type": "string", "description": "Nom (ou partie du nom) de l'aquarium"},
                    "parameter_name": {"type": "string", "description": "Symbole ou nom du paramètre, ex: KH, Ca, calcium, NO3, nitrate"},
                },
                "required": ["aquarium_name", "parameter_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sensor_value",
            "description": (
                "Récupère la dernière valeur mesurée par un capteur physique (température, "
                "niveau...) pour un aquarium donné."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "aquarium_name": {"type": "string", "description": "Nom (ou partie du nom) de l'aquarium"},
                    "sensor_name": {
                        "type": "string",
                        "description": "Nom (ou partie du nom) du capteur, ex: Température",
                    },
                },
                "required": ["aquarium_name", "sensor_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_equipment_status",
            "description": "Récupère l'état (ON/OFF) et le mode (AUTO/MANUAL) d'un équipement pour un aquarium donné.",
            "parameters": {
                "type": "object",
                "properties": {
                    "aquarium_name": {"type": "string", "description": "Nom (ou partie du nom) de l'aquarium"},
                    "equipment_name": {"type": "string", "description": "Nom (ou partie du nom) de l'équipement"},
                },
                "required": ["aquarium_name", "equipment_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_dosing",
            "description": (
                "Calcule la quantité de produit à ajouter pour amener un paramètre d'eau (déjà "
                "suivi dans l'application) de sa valeur actuelle réelle à une valeur cible, à "
                "partir du taux de dosage indiqué sur le produit (ex: '10 mL relève 100L de "
                "1°dKH'). La valeur actuelle et le volume du bac sont récupérés automatiquement "
                "depuis l'application (ne les invente jamais, ne les demande pas à "
                "l'utilisateur). Ne jamais inventer le taux de dosage du produit : le demander à "
                "l'utilisateur s'il n'est pas connu (généralement indiqué sur l'étiquette)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "aquarium_name": {"type": "string", "description": "Nom (ou partie du nom) de l'aquarium"},
                    "parameter_name": {"type": "string", "description": "Symbole ou nom du paramètre, ex: KH, Ca, calcium, Mg"},
                    "target_value": {"type": "number", "description": "Valeur cible du paramètre"},
                    "product_dose_amount": {
                        "type": "number",
                        "description": "Quantité de produit de référence (ex: 10 pour '10 mL')",
                    },
                    "product_raises_value": {
                        "type": "number",
                        "description": "De combien cette dose relève le paramètre (ex: 1 pour '1°dKH')",
                    },
                    "product_raises_per_liters": {
                        "type": "number",
                        "description": "Pour combien de litres cette dose est prévue (ex: 100 pour '100L')",
                    },
                },
                "required": [
                    "aquarium_name",
                    "parameter_name",
                    "target_value",
                    "product_dose_amount",
                    "product_raises_value",
                    "product_raises_per_liters",
                ],
            },
        },
    },
]


def _find_aquarium(db: Session, name: str) -> Optional[Aquarium]:
    aquariums = db.query(Aquarium).all()
    name_lower = name.strip().lower()
    for a in aquariums:
        if a.name.lower() == name_lower:
            return a
    for a in aquariums:
        if name_lower in a.name.lower() or a.name.lower() in name_lower:
            return a
    return None


def _tool_list_aquariums(db: Session, args: dict) -> str:
    aquariums = db.query(Aquarium).all()
    if not aquariums:
        return "Aucun aquarium enregistré."
    return "; ".join(f"{a.name} ({a.volume} L)" for a in aquariums)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _match_parameter(params: list[WaterParameter], query: str) -> Optional[WaterParameter]:
    """Symbole (Ca) ou nom complet (calcium, magnesium sans accent)."""
    wanted = _normalize(query)
    if not wanted:
        return None
    return next(
        (p for p in params if wanted in (_normalize(p.name), _normalize(p.full_name or ""))),
        None,
    )


def _tool_get_water_parameter(db: Session, args: dict) -> str:
    aquarium = _find_aquarium(db, str(args.get("aquarium_name", "")))
    if not aquarium:
        return f"Aucun aquarium correspondant à '{args.get('aquarium_name')}'."

    params = db.query(WaterParameter).filter(WaterParameter.aquarium_id == aquarium.id).all()
    param = _match_parameter(params, str(args.get("parameter_name", "")))
    if not param:
        available = ", ".join(p.name for p in params) or "aucun"
        return f"Paramètre '{args.get('parameter_name')}' non suivi pour {aquarium.name}. Paramètres suivis : {available}."

    if param.last_value is None:
        return f"{param.name} n'a aucun relevé enregistré pour {aquarium.name}."

    target = ""
    if param.target_min is not None or param.target_max is not None:
        target = f" (cible : {param.target_min if param.target_min is not None else '--'} - {param.target_max if param.target_max is not None else '--'} {param.unit or ''})"
    return (
        f"{param.name} = {param.last_value} {param.unit or ''} pour {aquarium.name}, "
        f"dernier relevé le {param.last_reading_at}{target}."
    )


def _tool_get_sensor_value(db: Session, args: dict) -> str:
    aquarium = _find_aquarium(db, str(args.get("aquarium_name", "")))
    if not aquarium:
        return f"Aucun aquarium correspondant à '{args.get('aquarium_name')}'."

    sensor_name = str(args.get("sensor_name", "")).strip().lower()
    sensors = db.query(Sensor).filter(Sensor.aquarium_id == aquarium.id).all()
    sensor = next((s for s in sensors if sensor_name in s.name.lower() or s.name.lower() in sensor_name), None)
    if not sensor:
        available = ", ".join(s.name for s in sensors) or "aucun"
        return f"Capteur '{args.get('sensor_name')}' non trouvé pour {aquarium.name}. Capteurs disponibles : {available}."

    if sensor.last_value is None:
        return f"{sensor.name} n'a aucune valeur enregistrée pour {aquarium.name}."
    return f"{sensor.name} = {sensor.last_value} {sensor.unit or ''} pour {aquarium.name}."


def _tool_get_equipment_status(db: Session, args: dict) -> str:
    aquarium = _find_aquarium(db, str(args.get("aquarium_name", "")))
    if not aquarium:
        return f"Aucun aquarium correspondant à '{args.get('aquarium_name')}'."

    eq_name = str(args.get("equipment_name", "")).strip().lower()
    equipments = db.query(Equipment).filter(Equipment.aquarium_id == aquarium.id).all()
    eq = next((e for e in equipments if eq_name in e.name.lower() or e.name.lower() in eq_name), None)
    if not eq:
        available = ", ".join(e.name for e in equipments) or "aucun"
        return f"Équipement '{args.get('equipment_name')}' non trouvé pour {aquarium.name}. Équipements disponibles : {available}."

    return f"{eq.name} est {eq.status.value} (mode {eq.mode.value}) pour {aquarium.name}."


def _tool_calculate_dosing(db: Session, args: dict) -> str:
    # La valeur actuelle et le volume du bac sont récupérés ici, jamais
    # transmis par le LLM : un petit modèle local peut inventer un chiffre
    # plausible mais faux (déjà observé en test avec le volume), et une
    # erreur de dosage peut nuire aux coraux/poissons.
    aquarium = _find_aquarium(db, str(args.get("aquarium_name", "")))
    if not aquarium:
        return f"Aucun aquarium correspondant à '{args.get('aquarium_name')}'."

    params = db.query(WaterParameter).filter(WaterParameter.aquarium_id == aquarium.id).all()
    param = _match_parameter(params, str(args.get("parameter_name", "")))
    if not param:
        available = ", ".join(p.name for p in params) or "aucun"
        return f"Paramètre '{args.get('parameter_name')}' non suivi pour {aquarium.name}. Paramètres suivis : {available}."
    if param.last_value is None:
        return f"{param.name} n'a aucun relevé enregistré pour {aquarium.name}, impossible de calculer le dosage."

    try:
        target_value = float(args["target_value"])
        product_dose_amount = float(args["product_dose_amount"])
        product_raises_value = float(args["product_raises_value"])
        product_raises_per_liters = float(args["product_raises_per_liters"])
    except (KeyError, TypeError, ValueError):
        return "Paramètres de calcul de dosage invalides ou manquants."

    if product_raises_value <= 0 or product_raises_per_liters <= 0:
        return "Le taux de dosage du produit doit être positif."

    current_value = param.last_value
    tank_volume_liters = aquarium.volume
    delta = target_value - current_value
    if delta <= 0:
        return (
            f"{param.name} est déjà à {current_value:g} {param.unit or ''} pour {aquarium.name}, "
            f"au niveau ou au-dessus de la cible {target_value:g} : aucun dosage nécessaire."
        )

    dose = product_dose_amount * (delta / product_raises_value) * (tank_volume_liters / product_raises_per_liters)
    return (
        f"{param.name} actuel de {aquarium.name} : {current_value:g} {param.unit or ''} "
        f"(relevé le {param.last_reading_at}), pour {tank_volume_liters:g} L. "
        f"Pour passer à {target_value:g} (delta {delta:g}), avec un produit qui relève de "
        f"{product_raises_value:g} pour {product_raises_per_liters:g} L à raison de {product_dose_amount:g} "
        f"unité(s) : dose nécessaire ≈ {dose:.2f} unité(s) de produit. "
        f"Recommandation : fractionner sur plusieurs jours plutôt qu'en une seule dose pour éviter un choc chimique."
    )


TOOL_IMPLEMENTATIONS = {
    "list_aquariums": _tool_list_aquariums,
    "get_water_parameter": _tool_get_water_parameter,
    "get_sensor_value": _tool_get_sensor_value,
    "get_equipment_status": _tool_get_equipment_status,
    "calculate_dosing": _tool_calculate_dosing,
}


def _execute_tool(db: Session, name: str, args: dict) -> str:
    impl = TOOL_IMPLEMENTATIONS.get(name)
    if not impl:
        return f"Outil inconnu : {name}"
    try:
        return impl(db, args)
    except Exception:
        logger.exception("Erreur lors de l'exécution de l'outil %s", name)
        return "Erreur interne lors de l'exécution de cet outil."


class AssistantDisabled(Exception):
    pass


MAX_TOOL_ROUNDS = 4


async def ask_assistant(prompt: str, db: Session) -> str:
    conf = get_assistant_settings(db)
    if not conf.enabled:
        raise AssistantDisabled()
    conn = connection_from(conf)
    tools = TOOLS if conf.data_access else None
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT if tools else SYSTEM_PROMPT_NO_DATA},
        {"role": "user", "content": prompt},
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            message = await chat(conn, messages, tools)
        except LLMError as exc:
            logger.error("Assistant : %s", exc)
            return f"L'assistant est indisponible : {llm_message(exc)}"

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            return message.get("content") or "Je n'ai pas de réponse à donner."

        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": tool_calls})
        for call in tool_calls:
            function = call.get("function", {})
            name = function.get("name", "")
            raw_args = function.get("arguments") or {}
            if isinstance(raw_args, str):
                try:
                    raw_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    raw_args = {}
            result = _execute_tool(db, name, raw_args if isinstance(raw_args, dict) else {})
            if conn.provider == "ollama":
                messages.append({"role": "tool", "content": result, "tool_name": name})
            else:
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": result})

    return "Je n'ai pas réussi à répondre à cette question après plusieurs tentatives."
