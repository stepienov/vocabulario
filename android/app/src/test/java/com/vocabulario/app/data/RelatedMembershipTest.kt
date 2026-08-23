package com.vocabulario.app.data

import com.vocabulario.app.data.api.WordListResponse
import com.vocabulario.app.data.local.db.CachedCardEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RelatedMembershipTest {

    private fun card(
        id: String,
        lemma: String,
        pos: String,
        deckId: String? = null,
    ) = CachedCardEntity(
        id = id,
        profileId = "p",
        deckId = deckId,
        lemmaL2 = lemma,
        glossPrimary = lemma,
        pos = pos,
        contentJson = "{}",
        enrichmentStatus = "ready",
        status = "new",
        nextReviewAt = null,
    )

    @Test
    fun alcanceMatchesElAlcanceOnLearningList() {
        val index = buildRelatedMembershipIndex(
            cards = listOf(card("c1", "el alcance", "noun")),
            lists = listOf(
                WordListResponse(id = "sys", name = "Learning", is_system = true),
            ),
        )
        val hit = index.find("alcance", "noun")
        assertEquals("el alcance", hit?.displayLemma)
        assertEquals(true, hit?.isSystemList)
        assertEquals("Learning", hit?.listName)
        assertNull(index.find("alcance", "verb"))
    }

    @Test
    fun formatLemmaWithArticle_joinsSpaceExceptElisionAndAl() {
        assertEquals("el alcance", formatLemmaWithArticle("alcance", "el"))
        assertEquals("lo studente", formatLemmaWithArticle("studente", "lo"))
        assertEquals("l'homme", formatLemmaWithArticle("homme", "l'"))
        assertEquals("الكتاب", formatLemmaWithArticle("كتاب", "ال"))
        assertEquals("book", formatLemmaWithArticle("book", null))
        assertEquals("el alcance", formatLemmaWithArticle("el alcance", "el"))
    }
}
