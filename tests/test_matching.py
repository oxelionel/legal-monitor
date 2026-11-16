from services.classification import DEFAULT_RULES, classify
from services.matching import (
    ClientProfile,
    PublicationText,
    count_occurrences,
    evaluate,
    find_documents,
    strip_corporate_suffix,
)
from services.text import normalize, parse_keywords

CLIENT = ClientProfile(id=1, name="Construtora Exemplo Azul Ltda", trade_name="Azul Obras",
                       document="11222333000181", legal_area="Licitações e Contratos",
                       keywords=["pavimentação urbana", "drenagem", "pregão eletrônico"])


def pub(text, area=None):
    return PublicationText(id=1, title="", content=text, legal_area=area)


def test_normalize_removes_accents_and_punctuation():
    assert normalize("  Licitação: PREGÃO-Eletrônico! ") == "licitacao pregao eletronico"


def test_keyword_identification_respects_word_boundaries():
    text = normalize("A drenagem pluvial e a drenagem urbana; não confundir com drenagens.")
    assert count_occurrences(text, "drenagem") == 2
    assert count_occurrences(normalize("subdrenagem"), "drenagem") == 0


def test_parse_keywords_multiple_separators():
    assert parse_keywords("a1b, termo dois;termo três\nTERMO DOIS") == ["a1b", "termo dois", "termo três"]


def test_document_extraction_with_formatting():
    assert "11222333000181" in find_documents("CNPJ nº 11.222.333/0001-81 registrado")


def test_strip_corporate_suffix():
    assert strip_corporate_suffix(normalize("Empresa Exemplo S.A.")) == "empresa exemplo"
    assert strip_corporate_suffix(normalize("Construtora Exemplo Azul Ltda")) == "construtora exemplo azul"


def test_exact_document_match_is_high():
    r = evaluate(pub("Contratada inscrita no CNPJ 11.222.333/0001-81."), CLIENT)
    assert r.relevance == "ALTA"
    assert r.evidences[0].type == "documento"


def test_exact_name_without_suffix_is_high():
    r = evaluate(pub("Convoca a CONSTRUTORA EXEMPLO AZUL para assinatura."), CLIENT)
    assert r.relevance == "ALTA"
    assert any(e.type == "nome" for e in r.evidences)


def test_expression_plus_area_is_medium():
    r = evaluate(pub("Serviços de pavimentação urbana no centro.", "Licitações e Contratos"), CLIENT)
    assert r.relevance == "MÉDIA"
    assert {e.type for e in r.evidences} == {"expressao", "area"}
    assert r.score == 40


def test_single_keyword_is_low():
    r = evaluate(pub("Obras de drenagem previstas para o próximo ano."), CLIENT)
    assert r.relevance == "BAIXA"
    assert r.score == 15


def test_area_alone_does_not_match_by_default():
    assert evaluate(pub("Texto sem relação alguma com o cliente.", "Licitações e Contratos"), CLIENT) is None


def test_area_alone_can_be_enabled():
    rules = {**DEFAULT_RULES, "area_only_counts": True}
    r = evaluate(pub("Texto genérico sem termos.", "Licitações e Contratos"), CLIENT, rules)
    assert r.relevance == "BAIXA"


def test_no_match_returns_none():
    assert evaluate(pub("Concurso público para analista."), CLIENT) is None


def test_fuzzy_match_tolerates_typos():
    r = evaluate(pub("Processo contra CONSTRUTORA EXEMPLO AZUUL, conforme autos."), CLIENT)
    assert r is not None
    fuzzy = [e for e in r.evidences if e.type == "aproximada"]
    assert fuzzy and fuzzy[0].similarity >= DEFAULT_RULES["fuzzy_threshold"]


def test_repeat_bonus_and_justification():
    r = evaluate(pub("Drenagem, drenagem e drenagem."), CLIENT)
    assert r.evidences[0].occurrences == 3
    assert r.score == 15 + 2 * 2
    assert "drenagem" in r.justification and "BAIXA" in r.justification


def test_score_capped_at_100():
    text = "CONSTRUTORA EXEMPLO AZUL LTDA CNPJ 11.222.333/0001-81 Azul Obras pavimentação urbana drenagem"
    assert evaluate(pub(text, "Licitações e Contratos"), CLIENT).score == 100


def test_classify_thresholds():
    rules = DEFAULT_RULES
    assert classify(50, {"expressao"}, rules) == "ALTA"
    assert classify(25, {"expressao"}, rules) == "MÉDIA"
    assert classify(10, {"palavra_chave"}, rules) == "BAIXA"
    assert classify(9, {"palavra_chave"}, rules) is None
    assert classify(5, {"documento"}, rules) == "ALTA"  # evidência forte
