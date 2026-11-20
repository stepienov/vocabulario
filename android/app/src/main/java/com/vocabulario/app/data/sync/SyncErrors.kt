package com.vocabulario.app.data.sync

import com.vocabulario.app.data.api.apiErrorCode
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.serialization.SerializationException
import retrofit2.HttpException
import java.io.IOException

/** Klasyfikacja wyjątku; anulowanie rodzica nie może tu trafić — wołający propaguje je wcześniej. */
fun Throwable.toSyncFailure(): SyncFailure = when (this) {
    is HttpException -> classifyFailure(
        status = code(),
        apiCode = apiErrorCode(),
        retryAfterSec = response()?.headers()?.get("Retry-After")?.trim()?.toLongOrNull(),
    )
    is IOException, is TimeoutCancellationException -> classifyFailure(null, null, transport = true)
    is SerializationException -> SyncFailure(FailureKind.PROTOCOL, "bad_response", retryable = false)
    else -> classifyFailure(
        status = null,
        apiCode = message?.takeIf { m -> m.isNotEmpty() && m.all { it.isLowerCase() || it == '_' } },
    )
}
