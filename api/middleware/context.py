"""
Contexte de la requête en cours (adresse, méthode, chemin), repris par les journaux.
"""

from contextvars import ContextVar

request_context = ContextVar("request_context", default={})
