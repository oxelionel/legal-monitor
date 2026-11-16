"""Regras transparentes e configuráveis de classificação de relevância.

As regras ficam armazenadas na tabela ``settings`` (chave ``classification_rules``)
e podem ser alteradas pela página de Monitoramento. Os valores padrão abaixo são
documentados em ``docs/features.md``.
"""
from __future__ import annotations

import copy

from sqlalchemy.orm import Session

from database.models import Setting

SETTINGS_KEY = "classification_rules"

EVIDENCE_LABELS = {
    "documento": "CPF/CNPJ",
    "nome": "Nome / razão social",
    "nome_fantasia": "Nome fantasia",
    "expressao": "Expressão monitorada",
    "palavra_chave": "Palavra-chave",
    "aproximada": "Correspondência aproximada",
    "area": "Área jurídica coincidente",
}

DEFAULT_RULES: dict = {
    # Pontos atribuídos à primeira ocorrência de cada tipo de evidência
    "weights": {
        "documento": 60,
        "nome": 50,
        "nome_fantasia": 40,
        "expressao": 30,
        "palavra_chave": 15,
        "aproximada": 20,
        "area": 10,
    },
    # Pontos extras por ocorrência adicional do mesmo termo (com teto por termo)
    "repeat_bonus": 2,
    "repeat_bonus_cap": 10,
    # Similaridade mínima (0 a 1) para correspondência aproximada
    "fuzzy_threshold": 0.86,
    # Pontuação mínima de cada nível. Abaixo de BAIXA, nada é registrado.
    "thresholds": {"ALTA": 50, "MÉDIA": 25, "BAIXA": 10},
    # Evidências que, isoladamente, já caracterizam ALTA relevância
    "strong_types": ["documento", "nome"],
    # Se verdadeiro, a coincidência de área jurídica sozinha gera correspondência
    "area_only_counts": False,
    "max_score": 100,
}


def get_rules(session: Session) -> dict:
    stored = session.get(Setting, SETTINGS_KEY)
    rules = copy.deepcopy(DEFAULT_RULES)
    if stored and isinstance(stored.value, dict):
        for key, value in stored.value.items():
            if isinstance(value, dict) and isinstance(rules.get(key), dict):
                rules[key].update(value)
            else:
                rules[key] = value
    return rules


def validate_rules(rules: dict) -> dict:
    t = rules["thresholds"]
    if not (0 < t["BAIXA"] < t["MÉDIA"] < t["ALTA"] <= rules.get("max_score", 100)):
        raise ValueError("Os limites devem obedecer: 0 < BAIXA < MÉDIA < ALTA ≤ 100.")
    if not 0.5 <= float(rules["fuzzy_threshold"]) <= 1:
        raise ValueError("A similaridade mínima deve estar entre 0,50 e 1,00.")
    if any(float(w) < 0 for w in rules["weights"].values()):
        raise ValueError("Os pesos não podem ser negativos.")
    return rules


def save_rules(session: Session, rules: dict) -> dict:
    validate_rules(rules)
    stored = session.get(Setting, SETTINGS_KEY)
    if stored:
        stored.value = copy.deepcopy(rules)
    else:
        session.add(Setting(key=SETTINGS_KEY, value=copy.deepcopy(rules)))
    return rules


def reset_rules(session: Session) -> dict:
    stored = session.get(Setting, SETTINGS_KEY)
    if stored:
        session.delete(stored)
    return copy.deepcopy(DEFAULT_RULES)


def classify(score: float, evidence_types: set[str], rules: dict) -> str | None:
    """Converte pontuação + tipos de evidência em nível de relevância."""
    if evidence_types & set(rules.get("strong_types", [])):
        return "ALTA"
    t = rules["thresholds"]
    if score >= t["ALTA"]:
        return "ALTA"
    if score >= t["MÉDIA"]:
        return "MÉDIA"
    if score >= t["BAIXA"]:
        return "BAIXA"
    return None
