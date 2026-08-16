from app.lsp.lang_utils import articles_for
from app.services.distractors import in_learning_lemma, lemma_keys


def test_similar_lemma_matches_articled_learning_card():
    articles = articles_for("es")
    keys = lemma_keys("el banco", articles) | lemma_keys("casa", articles)
    assert in_learning_lemma("banco", keys, articles)
    assert in_learning_lemma("el banco", keys, articles)
    assert in_learning_lemma("El Banco", keys, articles)
    assert not in_learning_lemma("mesa", keys, articles)
    assert not in_learning_lemma("", keys, articles)


def test_l1_to_l2_uses_same_lemma_keys():
    articles = articles_for("es")
    keys = lemma_keys("la casa", articles)
    assert in_learning_lemma("casa", keys, articles)
    assert not in_learning_lemma("casas", keys, articles)
