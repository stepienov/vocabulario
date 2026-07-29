package com.vocabulario.app.data.api

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import retrofit2.HttpException

private val json = Json { ignoreUnknownKeys = true }

fun Throwable.userMessage(default: String): String {
    if (this is HttpException) {
        val body = response()?.errorBody()?.string()
        if (!body.isNullOrBlank()) {
            return parseApiError(body) ?: "$default (${code()})"
        }
        return "$default (${code()})"
    }
    return message ?: default
}

private fun parseApiError(body: String): String? {
  return runCatching {
    val element = json.parseToJsonElement(body)
    when (element) {
      is JsonObject -> {
        element["detail"]?.let { detail ->
          when (detail) {
            is JsonArray -> detail.joinToString("\n") { item ->
              item.jsonObject["msg"]?.jsonPrimitive?.content ?: item.toString()
            }
            else -> detail.jsonPrimitive.content
          }
        }
      }
      else -> null
    }
  }.getOrNull()
}
