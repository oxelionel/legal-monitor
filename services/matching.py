"""Motor de correspondência entre publicações e clientes monitorados.

Funções puras (sem acesso ao banco), o que facilita testes e a futura
reutilização em uma API ou em um worker assíncrono.

Etapas para cada par (publicação, cliente):
1. Normalização do texto (minúsculas, sem acentos e pontuação).
2. Busca exata de CPF/CNPJ (somente dígitos).
3. Busca exata do nome/razão social (completo e sem sufixos societários).
4. Busca exata do nome fantasia.
5. Busca de expressões (termos com várias palavras) e palavras-chave isoladas,
   respeitando limites de palavra.
6. Busca aproximada (similaridade de sequência) para nomes e expressões não
   encontrados de forma exata — tolera erros de digitação/OCR.
7. Bônus contextual quando a área jurídica coincide.
8. Soma da pontuação, classificação e geração da justificativa.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher

from services.classification import DEFAULT_RULES, EVIDENCE_LABELS, classify
from services.text import normalize, only_digits

CORPORATE_SUFFIXES = {
    "ltda", "sa", "s a", "eireli", "me", "epp", "mei", "cia", "companhia",
    "limitada", "sociedade anonima", "ss", "s s",
}

_DOC_CANDIDATE = re.compile(r"\d[\d.\-/ ]{9,22}\d")


@dataclass
class ClientProfile:
    id: int
    name: str
    trade_name: str | None = None
    document: str | None = None
    legal_area: str | None = None
    keywords: list[str] = field(default_factory=list)


@dataclass
class PublicationText:
    id: int | None
    title: str
    content: str
    legal_area: str | None = None


@dataclass
class Evidence:
    type: str
    term: str
    occurrences: int
    points: float
    similarity: float | None = None
    excerpt: str | None = None

    @property
    def label(self) -> str:
        return EVIDENCE_LABELS.get(self.type, self.type)


@dataclass
class MatchResult:
    client_id: int
    publication_id: int | None
    score: float
    relevance: str
    evidences: list[Evidence]
    justification: str

    def terms_as_json(self) -> list[dict]:
        return [asdict(e) for e in self.evidences]


# --------------------------------------------------------------------------- helpers

def strip_corporate_suffix(name_norm: str) -> str:
    tokens = name_norm.split()
    while tokens:
        tail2 = " ".join(tokens[-2:])
        if len(tokens) >= 2 and tail2 in CORPORATE_SUFFIXES:
            tokens = tokens[:-2]
        elif tokens[-1] in CORPORATE_SUFFIXES:
            tokens = tokens[:-1]
        else:
            break
    return " ".join(tokens)


def _pattern(term_norm: str) -> re.Pattern:
    return re.compile(r"(?<![0-9a-z])" + re.escape(term_norm) + r"(?![0-9a-z])")


def count_occurrences(text_norm: str, term_norm: str) -> int:
    if not term_norm:
        return 0
    return len(_pattern(term_norm).findall(text_norm))


def find_documents(raw_text: str) -> set[str]:
    """Extrai sequências que possam ser CPF (11) ou CNPJ (14 dígitos)."""
    found = set()
    for candidate in _DOC_CANDIDATE.findall(raw_text):
        digits = only_digits(candidate)
        if len(digits) in (11, 14):
            found.add(digits)
    return found


def best_fuzzy(text_tokens: list[str], term_norm: str) -> tuple[float, str]:
    """Maior similaridade entre o termo e janelas de mesmo tamanho do texto."""
    term_tokens = term_norm.split()
    n = len(term_tokens)
    if n == 0 or len(text_tokens) < n:
        return 0.0, ""
    best, best_window = 0.0, ""
    matcher = SequenceMatcher(autojunk=False)
    matcher.set_seq2(term_norm)
    for i in range(len(text_tokens) - n + 1):
        window = " ".join(text_tokens[i : i + n])
        if abs(len(window) - len(term_norm)) > max(3, len(term_norm) * 0.25):
            continue
        matcher.set_seq1(window)
        if matcher.real_quick_ratio() < best or matcher.quick_ratio() < best:
            continue
        ratio = matcher.ratio()
        if ratio > best:
            best, best_window = ratio, window
    return best, best_window


def _excerpt(raw_text: str, term: str, width: int = 70) -> str | None:
    """Trecho do texto original ao redor da primeira ocorrência (aproximada)."""
    norm_raw = normalize(raw_text)
    term_norm = normalize(term)
    m = _pattern(term_norm).search(norm_raw)
    if not m:
        return None
    start, end = max(0, m.start() - width), min(len(norm_raw), m.end() + width)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(norm_raw) else ""
    return f"{prefix}{norm_raw[start:end]}{suffix}"


# --------------------------------------------------------------------------- engine

def _points(weight: float, occurrences: int, rules: dict) -> float:
    bonus = min(rules["repeat_bonus_cap"], rules["repeat_bonus"] * max(0, occurrences - 1))
    return float(weight) + float(bonus)


def find_evidences(pub: PublicationText, client: ClientProfile, rules: dict | None = None) -> list[Evidence]:
    rules = rules or DEFAULT_RULES
    w = rules["weights"]
    raw = f"{pub.title}\n{pub.content}"
    text_norm = normalize(raw)
    text_tokens = text_norm.split()
    evidences: list[Evidence] = []
    used_terms: set[str] = set()

    # 1. Documento
    if client.document:
        doc = only_digits(client.document)
        if doc and doc in find_documents(raw):
            occurrences = sum(1 for c in _DOC_CANDIDATE.findall(raw) if only_digits(c) == doc)
            evidences.append(Evidence("documento", client.document, occurrences, _points(w["documento"], occurrences, rules)))

    # 2. Nome / razão social (completo ou sem sufixo societário)
    fuzzy_candidates: list[tuple[str, str, str]] = []  # (tipo_original, termo exibido, termo normalizado)
    name_norm = normalize(client.name)
    name_core = strip_corporate_suffix(name_norm)
    name_variants = [v for v in dict.fromkeys([name_norm, name_core]) if v and (len(v.split()) >= 2 or len(v) >= 8)]
    name_found = False
    for variant in name_variants:
        occ = count_occurrences(text_norm, variant)
        if occ:
            evidences.append(Evidence("nome", client.name, occ, _points(w["nome"], occ, rules), excerpt=_excerpt(raw, variant)))
            name_found = True
            break
    used_terms.update(name_variants)
    if not name_found and name_variants:
        fuzzy_candidates.append(("nome", client.name, name_variants[-1]))

    # 3. Nome fantasia
    if client.trade_name:
        trade_norm = normalize(client.trade_name)
        if trade_norm and trade_norm not in used_terms and len(trade_norm) >= 3:
            occ = count_occurrences(text_norm, trade_norm)
            if occ:
                evidences.append(
                    Evidence("nome_fantasia", client.trade_name, occ, _points(w["nome_fantasia"], occ, rules),
                             excerpt=_excerpt(raw, trade_norm))
                )
            elif len(trade_norm) >= 6:
                fuzzy_candidates.append(("nome_fantasia", client.trade_name, trade_norm))
            used_terms.add(trade_norm)

    # 4. Expressões e palavras-chave
    for term in client.keywords:
        term_norm = normalize(term)
        if not term_norm or term_norm in used_terms:
            continue
        used_terms.add(term_norm)
        kind = "expressao" if len(term_norm.split()) > 1 else "palavra_chave"
        occ = count_occurrences(text_norm, term_norm)
        if occ:
            evidences.append(Evidence(kind, term, occ, _points(w[kind], occ, rules), excerpt=_excerpt(raw, term_norm)))
        elif kind == "expressao" or len(term_norm) >= 8:
            fuzzy_candidates.append((kind, term, term_norm))

    # 5. Correspondência aproximada
    threshold = float(rules["fuzzy_threshold"])
    for _kind, term, term_norm in fuzzy_candidates:
        ratio, window = best_fuzzy(text_tokens, term_norm)
        if ratio >= threshold and ratio < 1:
            evidences.append(
                Evidence("aproximada", term, 1, round(float(w["aproximada"]) * ratio, 2), similarity=round(ratio, 3),
                         excerpt=f"…{window}…")
            )

    # 6. Contexto: área jurídica
    if client.legal_area and pub.legal_area and client.legal_area == pub.legal_area:
        if evidences or rules.get("area_only_counts"):
            evidences.append(Evidence("area", client.legal_area, 1, float(w["area"])))

    return evidences


def build_justification(score: float, relevance: str, evidences: list[Evidence], rules: dict) -> str:
    parts = [f"Pontuação {score:.0f}/{rules.get('max_score', 100)} → relevância {relevance}."]
    strong = [e.label for e in evidences if e.type in rules.get("strong_types", [])]
    if strong:
        parts.append(f"Evidência forte ({', '.join(strong)}) classifica automaticamente como ALTA.")
    for e in evidences:
        extra = f", similaridade {e.similarity:.0%}" if e.similarity else ""
        occ = f", {e.occurrences} ocorrência(s)" if e.type != "area" else ""
        parts.append(f"• {e.label}: “{e.term}” (+{e.points:.0f}{occ}{extra}).")
    return "\n".join(parts)


def evaluate(pub: PublicationText, client: ClientProfile, rules: dict | None = None) -> MatchResult | None:
    """Avalia um par publicação × cliente. Retorna ``None`` se não houver correspondência."""
    rules = rules or DEFAULT_RULES
    evidences = find_evidences(pub, client, rules)
    if not evidences:
        return None
    types = {e.type for e in evidences}
    if types == {"area"} and not rules.get("area_only_counts"):
        return None
    score = min(float(rules.get("max_score", 100)), round(sum(e.points for e in evidences), 2))
    relevance = classify(score, types, rules)
    if relevance is None:
        return None
    return MatchResult(
        client_id=client.id,
        publication_id=pub.id,
        score=score,
        relevance=relevance,
        evidences=evidences,
        justification=build_justification(score, relevance, evidences, rules),
    )
