package com.vocabulario.app.data.session

import com.vocabulario.app.data.local.db.OwnerPhase
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class OwnerScopeTest {

    private val ownerA = OwnerContext("user-a", generation = 4)

    @Test
    fun onlyActivePhaseWithOwnerGivesContext() {
        assertEquals(ownerA, ownerContextOf("user-a", 4, OwnerPhase.ACTIVE))
        assertNull(ownerContextOf("user-a", 4, OwnerPhase.LOGGING_OUT))
        assertNull(ownerContextOf("user-a", 4, OwnerPhase.SIGNED_OUT))
        assertNull(ownerContextOf(null, 4, OwnerPhase.ACTIVE))
        assertNull(ownerContextOf(" ", 4, OwnerPhase.ACTIVE))
    }

    @Test
    fun noActiveOwnerSkipsWork() = runBlocking {
        var ran = false
        val result = runAsOwner({ null }) { ran = true; "done" }
        assertNull(result)
        assertTrue(!ran)
    }

    @Test
    fun sameOwnerFinishesWork() = runBlocking {
        val result = runAsOwner({ ownerA }) {
            ensureOwner { ownerA }
            "done"
        }
        assertEquals("done", result)
    }

    @Test
    fun newGenerationSupersedesWorkAfterHttp() = runBlocking {
        var current: OwnerContext? = ownerA
        var wroteAfterCheck = false
        val result = runAsOwner({ current }) {
            current = ownerA.copy(generation = 5)
            ensureOwner { current }
            wroteAfterCheck = true
            "done"
        }
        assertNull(result)
        assertTrue(!wroteAfterCheck)
    }

    @Test
    fun logoutSupersedesWork() = runBlocking {
        var current: OwnerContext? = ownerA
        val result = runAsOwner({ current }) {
            current = null
            ensureOwner { current }
            "done"
        }
        assertNull(result)
    }

    @Test
    fun nestedWorkKeepsOuterOwner() = runBlocking {
        var current: OwnerContext? = ownerA
        val result = runAsOwner({ current }) {
            current = OwnerContext("user-b", generation = 5)
            // Zagnieżdżona praca nie przechwytuje nowego właściciela, tylko dziedziczy zakres A.
            val inner = runAsOwner({ current }) { ensureOwner { current }; "inner" }
            assertNull(inner)
            "outer"
        }
        assertEquals("outer", result)
    }

    @Test
    fun checkWithoutScopeDoesNothing() = runBlocking {
        ensureOwner { null }
    }
}
