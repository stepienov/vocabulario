package com.vocabulario.app.data

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject

/** Canonical system list name stored in the API/DB (identity only — never show raw to users). */
const val SYSTEM_LIST_NAME = "Uczę się"

private val PENDING_INBOX_CANONICAL_NAMES = setOf("pending", "oczekujące")

/** User-facing list names reserved for system lists (learning + offline pending inbox). */
fun isReservedListName(name: String, pendingDisplayName: String): Boolean {
    val trimmed = name.trim()
    if (trimmed.isBlank()) return false
    val lower = trimmed.lowercase()
    return trimmed.equals(SYSTEM_LIST_NAME, ignoreCase = true) ||
        trimmed.equals(pendingDisplayName, ignoreCase = true) ||
        lower in PENDING_INBOX_CANONICAL_NAMES
}

/**
 * Języki interfejsu i nauki — 16 kodów LSP (endonimy).
 */
val SUPPORTED_UI_LANGS = listOf(
    "en" to "English",
    "es" to "Español",
    "fr" to "Français",
    "de" to "Deutsch",
    "it" to "Italiano",
    "pt-br" to "Português (Brasil)",
    "pt-pt" to "Português (Portugal)",
    "zh" to "中文",
    "ja" to "日本語",
    "ko" to "한국어",
    "ar" to "العربية",
    "ru" to "Русский",
    "hi" to "हिन्दी",
    "tr" to "Türkçe",
    "vi" to "Tiếng Việt",
    "pl" to "Polski",
)

/** Języki nauki — ta sama lista co UI (16 LSP). */
val SUPPORTED_LEARNING_LANGS = SUPPORTED_UI_LANGS

private val SUPPORTED_UI_LANG_CODES = SUPPORTED_UI_LANGS.map { it.first }.toSet()

/** Map a device locale onto a supported UI/learning code, or null if unsupported. */
fun matchSupportedUiLang(language: String, country: String = ""): String? {
    val lang = language.trim().lowercase()
    if (lang.isBlank()) return null
    val region = country.trim().lowercase()
    val tag = if (region.isBlank()) lang else "$lang-$region"
    if (tag in SUPPORTED_UI_LANG_CODES) return tag
    when {
        lang == "pt" && region == "pt" -> return "pt-pt"
        lang == "pt" -> return "pt-br"
        lang == "zh" -> return "zh"
    }
    return lang.takeIf { it in SUPPORTED_UI_LANG_CODES }
}

/** Phone language if we support it, otherwise English. */
fun deviceUiLang(): String {
    val locale = android.content.res.Resources.getSystem().configuration.locales[0]
        ?: java.util.Locale.getDefault()
    return matchSupportedUiLang(locale.language, locale.country) ?: "en"
}

fun langDisplayName(code: String): String =
    SUPPORTED_LEARNING_LANGS.firstOrNull { it.first == code.lowercase() }?.second
        ?: SUPPORTED_UI_LANGS.firstOrNull { it.first == code.lowercase() }?.second
        ?: code.uppercase()

/** Canonical POS bucket for filters/sort (`unknown` when missing / unrecognized). */
fun normalizePosKey(pos: String?): String {
    val key = pos?.lowercase()?.trim().orEmpty()
    if (key.isEmpty()) return "unknown"
    if (key in CANONICAL_POS_KEYS) return key
    val canonical = when {
        key in POS_SHORT_ALIASES -> POS_SHORT_ALIASES[key]!!
        "rzeczownik" in key || "sustantivo" in key || "sostantivo" in key ||
            "substantivo" in key || "substantiv" in key || "noun" in key || "nom " in key ||
            "существ" in key || "名詞" in key || "名词" in key || "명사" in key ||
            "isim" in key || "danh từ" in key || "संज्ञा" in key || "اسم" in key -> "noun"
        "czasownik" in key || "verbo" in key || "verbe" in key || "verb" in key ||
            "глагол" in key || "动词" in key || "動詞" in key || "동사" in key ||
            "fiil" in key || "động từ" in key || "क्रिया" in key || "فعل" in key -> "verb"
        "przymiotnik" in key || "adjetivo" in key || "adjectif" in key ||
            "aggettivo" in key || "adjektiv" in key || "adjective" in key || "adj" in key ||
            "прилаг" in key || "形容词" in key || "形容詞" in key || "형용사" in key ||
            "sıfat" in key || "tính từ" in key || "विशेषण" in key || "صفة" in key -> "adj"
        "przysłówek" in key || "adverbio" in key || "adverbe" in key || "avverbio" in key ||
            "adverb" in key || "нареч" in key || "副词" in key || "副詞" in key ||
            "부사" in key || "zarf" in key || "trạng từ" in key -> "adv"
        else -> key
    }
    return if (canonical in CANONICAL_POS_KEYS) canonical else "unknown"
}

private val DISTRACTOR_BLOCKLIST = setOf(
    "pos", "noun", "verb", "adj", "adjective", "adverb", "adv", "prep", "conj", "pron",
    "det", "interj", "imported", "unknown", "lemma", "gloss", "null",
    "rzeczownik", "czasownik", "przymiotnik", "przysłówek",
    "sustantivo", "verbo", "adjetivo", "adverbio",
)

/** Reject POS labels and JSON debris that leaked into offline practice choices. */
fun isValidPracticeDistractor(text: String): Boolean {
    val trimmed = text.trim()
    if (trimmed.length < 2) return false
    val lower = trimmed.lowercase()
    if (lower in DISTRACTOR_BLOCKLIST) return false
    if (!trimmed.contains(' ') && normalizePosKey(trimmed) in CANONICAL_POS_KEYS) return false
    return true
}

private val POS_SHORT_ALIASES = mapOf(
    "n" to "noun", "nn" to "noun", "v" to "verb", "vb" to "verb",
    "a" to "adj", "adv" to "adv", "prep" to "prep", "conj" to "conj",
    "pron" to "pron", "det" to "det", "interj" to "interj",
)

private val CANONICAL_POS_KEYS = setOf(
    "noun", "verb", "adj", "adv", "prep", "conj", "pron", "det", "interj",
)

val CEFR_LEVELS = listOf("A1", "A2", "B1", "B2", "C1", "C2")

/** Legacy ES tense keys — prefer [LanguagePacks.tenseCatalog]. */
val VERB_TENSES: List<Pair<String, String>> = LanguagePacks.tenseCatalog("es").map { it.key to it.label }

val NON_FINITE_FORMS: List<Pair<String, String>> =
    LanguagePacks.get("es").nonFinite.map { it.key to it.label }

val DEFAULT_CARD_TENSES: List<String> = LanguagePacks.defaultSelectedTenses("es")

val TENSE_KEY_ALIASES = mapOf(
    // ES legacy
    "imperfecto" to "preterito_imperfecto",
    "futuro" to "futuro_simple",
    "condicional" to "condicional_simple",
    // PL — LLM often returns English / diacritic variants
    "present" to "czas_terazniejszy",
    "present_tense" to "czas_terazniejszy",
    "czas_teraźniejszy" to "czas_terazniejszy",
    "past" to "czas_przeszly",
    "past_tense" to "czas_przeszly",
    "czas_przeszły" to "czas_przeszly",
    "future" to "czas_przyszly",
    "future_tense" to "czas_przyszly",
    "czas_przyszły" to "czas_przyszly",
    "imperative" to "tryb_rozkazujacy",
    "tryb_rozkazujący" to "tryb_rozkazujacy",
    "conditional" to "tryb_przypuszczajacy",
    "tryb_przypuszczający" to "tryb_przypuszczajacy",
    "infinitive" to "bezokolicznik",
    "participle" to "imieslow",
    "imiesłów" to "imieslow",
)

fun normalizeTenseKey(key: String): String = TENSE_KEY_ALIASES[key] ?: key

/**
 * Resolve which tense keys from [tenseMap] should be shown given profile selection.
 * Matches pack keys and common aliases; if nothing intersects, falls back so the
 * conjugation block is never empty when data exists.
 */
fun resolveVisibleTenseKeys(
    profileTenses: List<String>,
    tenseMapKeys: Collection<String>,
    catalogKeys: List<String>,
): List<String> {
    if (tenseMapKeys.isEmpty()) return emptyList()
    val mapKeys = tenseMapKeys.toSet()
    val aliasToCanonical = buildMap {
        for ((alias, canonical) in TENSE_KEY_ALIASES) {
            put(alias, canonical)
            put(canonical, canonical)
        }
        for (k in catalogKeys) put(k, k)
        for (k in mapKeys) put(k, k)
    }

    fun resolve(raw: String): String? {
        val n = normalizeTenseKey(raw)
        if (n in mapKeys) return n
        val via = aliasToCanonical[raw] ?: aliasToCanonical[n]
        if (via != null && via in mapKeys) return via
        // Diacritic / case fold soft match
        val folded = n.lowercase()
        return mapKeys.firstOrNull { it.lowercase() == folded }
    }

    if (profileTenses.isNotEmpty()) {
        val matched = profileTenses.mapNotNull(::resolve).distinct()
        if (matched.isNotEmpty()) return matched
    }
    val ordered = catalogKeys.mapNotNull(::resolve).distinct()
    return ordered.ifEmpty { tenseMapKeys.toList() }
}

fun normalizeTenseKeys(keys: Collection<String>): List<String> {
    val seen = LinkedHashSet<String>()
    for (key in keys) {
        val n = normalizeTenseKey(key.trim())
        if (n.isNotEmpty()) seen.add(n)
    }
    return seen.toList()
}

val EXAMPLE_BANDS = listOf("A2", "B2", "C2")

fun examplesForUserLevel(
    examples: JsonArray?,
    userCefr: String,
    maxCount: Int = 2,
): List<JsonObject> {
    if (examples == null) return emptyList()
    val all = examples.mapNotNull { runCatching { it.jsonObject }.getOrNull() }
    if (all.isEmpty()) return emptyList()

    val band = userCefr.take(1).uppercase()
    val bandIdx = EXAMPLE_BANDS.indexOfFirst { it.startsWith(band) }.coerceAtLeast(0)
    for (idx in bandIdx downTo 0) {
        val level = EXAMPLE_BANDS[idx]
        val matched = all.filter {
            it["cefr"].asJsonString()?.uppercase() == level
        }
        if (matched.isNotEmpty()) return matched.take(maxCount)
    }
    return all.take(maxCount)
}

val NEW_CARDS_OPTIONS = listOf(
    5 to "5",
    10 to "10",
    20 to "20",
    50 to "50",
    0 to "∞",
)
