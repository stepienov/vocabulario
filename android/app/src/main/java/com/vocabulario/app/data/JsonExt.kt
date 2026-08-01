package com.vocabulario.app.data

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

/** Safe: JSON null is not Kotlin null, so `?.jsonObject` still throws. */
fun JsonElement?.asJsonObject(): JsonObject? = this as? JsonObject

fun JsonElement?.asJsonArray(): JsonArray? = this as? JsonArray

fun JsonElement?.asJsonString(): String? = (this as? JsonPrimitive)?.contentOrNull
