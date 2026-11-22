package com.vocabulario.app

import com.vocabulario.app.data.AccountLink
import com.vocabulario.app.data.AccountLinkKind
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.test.resetMain
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class AccountLinkStateTest {
    @Test
    fun resultSurvivesScreenRecreationAndOldLinkCannotOverwriteNewLink() {
        val dispatcher = StandardTestDispatcher()
        Dispatchers.setMain(dispatcher)
        try {
            runTest(dispatcher) {
                val response = CompletableDeferred<Int?>()
                val state = AccountLinkState { _, _ -> response.await() }
                state.receive(AccountLink(AccountLinkKind.VERIFY, "first"))
                state.submit("", "")
                runCurrent()
                assertTrue(state.busy)
                response.complete(null)
                runCurrent()
                assertTrue(state.done)
                assertFalse(state.busy)

                val oldResponse = CompletableDeferred<Int?>()
                val nextState = AccountLinkState { _, _ -> oldResponse.await() }
                nextState.receive(AccountLink(AccountLinkKind.VERIFY, "old"))
                nextState.submit("", "")
                runCurrent()
                nextState.receive(AccountLink(AccountLinkKind.RESET, "new"))
                oldResponse.complete(R.string.account_link_error)
                runCurrent()
                assertFalse(nextState.busy)
                assertFalse(nextState.done)
                assertNull(nextState.error)
            }
        } finally {
            Dispatchers.resetMain()
        }
    }
}
