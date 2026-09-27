"""Operational diagnostics without raw API responses, SQL or credentials."""

class PipelineError(RuntimeError):
    """An application-controlled, safe operational description."""


def describe_error(error):
    if isinstance(error, PipelineError):
        return str(error)[:1800]
    name = type(error).__name__
    status = getattr(error, "status_code", None)
    reasons = {
        400: "Requête refusée : paramètres ou format incompatibles.",
        401: "Authentification API refusée.",
        403: "Accès API interdit.",
        404: "Modèle ou ressource introuvable ou inaccessible.",
        429: "Quota ou limite de requêtes atteint.",
        500: "Erreur interne du fournisseur.",
        502: "Passerelle du fournisseur indisponible.",
        503: "Service du fournisseur indisponible.",
        504: "Délai du fournisseur dépassé.",
    }
    if isinstance(status, int):
        return f"{name} — HTTP {status} : {reasons.get(status, 'Échec de la requête API.')}"
    if getattr(error, "pgcode", None) == "42501":
        return f"{name} — PostgreSQL 42501 : permissions insuffisantes pour l’opération demandée."
    hints = {
        "OperationalError": "Connexion à PostgreSQL impossible ou interrompue.",
        "APITimeoutError": "Délai de réponse API dépassé.",
        "APIConnectionError": "Connexion au fournisseur impossible.",
        "JSONDecodeError": "La réponse du modèle n’est pas un JSON valide.",
        "KeyError": "Configuration ou champ requis absent.",
        "ValueError": "Valeur ou réponse invalide.",
    }
    return f"{name} : {hints.get(name, 'Consulter les journaux locaux pour le détail technique.')}"
