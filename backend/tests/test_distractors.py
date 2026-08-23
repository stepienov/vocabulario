from app.lsp.lang_utils import articles_for
from app.services.distractors import in_learning_lemma, lemma_keys, quiz_pos_matches


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


def test_quiz_pos_matches_never_treats_unknown_as_wildcard():
    assert not quiz_pos_matches("unknown", "noun")
    assert not quiz_pos_matches("verb", None)
    assert not quiz_pos_matches("phrase", "")
    assert quiz_pos_matches("phrase", "phrase")
    assert not quiz_pos_matches("phrase", "noun")
    assert not quiz_pos_matches("phrase", "adj")
    assert not quiz_pos_matches("phrase", "verb")
    assert quiz_pos_matches("phrase", "verb", family=True)
    assert quiz_pos_matches("construction", "phrase", family=True)
    assert not quiz_pos_matches("verb", "noun", family=True)
    assert not quiz_pos_matches("adj", "verb", family=True)
    assert quiz_pos_matches("adjective", "adj")
