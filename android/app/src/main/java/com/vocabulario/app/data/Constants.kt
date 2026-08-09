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

fun langDisplayName(code: String): String =
    SUPPORTED_LEARNING_LANGS.firstOrNull { it.first == code.lowercase() }?.second
        ?: SUPPORTED_UI_LANGS.firstOrNull { it.first == code.lowercase() }?.second
        ?: code.uppercase()

/** Część mowy — etykieta zależna od języka UI (krótka). */
fun posLabel(pos: String?, uiLang: String = "en"): String {
    val key = normalizePosKey(pos)
    if (key == "unknown" && pos.isNullOrBlank()) return ""
    val map = POS_LABELS[uiLang.lowercase()] ?: POS_LABELS["en"]!!
    return map[key] ?: if (key == "unknown") "" else pos.orEmpty()
}

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

/** @deprecated użyj [posLabel] */
fun posLabelPl(pos: String?): String = posLabel(pos, "pl")

private val POS_LABELS: Map<String, Map<String, String>> = mapOf(
    "pl" to mapOf(
        "verb" to "czasownik", "noun" to "rzeczownik", "adj" to "przymiotnik",
        "adv" to "przysłówek", "prep" to "przyimek", "conj" to "spójnik",
        "pron" to "zaimek", "interj" to "wykrzyknik", "det" to "przedimek",
    ),
    "en" to mapOf(
        "verb" to "verb", "noun" to "noun", "adj" to "adj.",
        "adv" to "adv.", "prep" to "prep.", "conj" to "conj.",
        "pron" to "pron.", "interj" to "interj.", "det" to "det.",
    ),
    "es" to mapOf(
        "verb" to "verbo", "noun" to "sustantivo", "adj" to "adj.",
        "adv" to "adv.", "prep" to "prep.", "conj" to "conj.",
        "pron" to "pron.", "interj" to "interj.", "det" to "det.",
    ),
    "de" to mapOf(
        "verb" to "Verb", "noun" to "Nomen", "adj" to "Adj.",
        "adv" to "Adv.", "prep" to "Präp.", "conj" to "Konj.",
        "pron" to "Pron.", "interj" to "Interj.", "det" to "Art.",
    ),
    "fr" to mapOf(
        "verb" to "verbe", "noun" to "nom", "adj" to "adj.",
        "adv" to "adv.", "prep" to "prép.", "conj" to "conj.",
        "pron" to "pron.", "interj" to "interj.", "det" to "dét.",
    ),
    "pt" to mapOf(
        "verb" to "verbo", "noun" to "substantivo", "adj" to "adj.",
        "adv" to "adv.", "prep" to "prep.", "conj" to "conj.",
        "pron" to "pron.", "interj" to "interj.", "det" to "det.",
    ),
    "ru" to mapOf(
        "verb" to "глагол", "noun" to "существ.", "adj" to "прил.",
        "adv" to "нареч.", "prep" to "предл.", "conj" to "союз",
        "pron" to "мест.", "interj" to "межд.", "det" to "арт.",
    ),
    "zh" to mapOf(
        "verb" to "动词", "noun" to "名词", "adj" to "形容词",
        "adv" to "副词", "prep" to "介词", "conj" to "连词",
        "pron" to "代词", "interj" to "感叹词", "det" to "限定词",
    ),
    "hi" to mapOf(
        "verb" to "क्रिया", "noun" to "संज्ञा", "adj" to "विशेषण",
        "adv" to "क्रियाविशेषण", "prep" to "संबंध", "conj" to "समुच्चय",
        "pron" to "सर्वनाम", "interj" to "विस्मयादिबोधक", "det" to "निर्धारक",
    ),
    "ar" to mapOf(
        "verb" to "فعل", "noun" to "اسم", "adj" to "صفة",
        "adv" to "ظرف", "prep" to "حرف جر", "conj" to "رابط",
        "pron" to "ضمير", "interj" to "تعجب", "det" to "أداة",
    ),
    "it" to mapOf(
        "verb" to "verbo", "noun" to "sostantivo", "adj" to "agg.",
        "adv" to "avv.", "prep" to "prep.", "conj" to "cong.",
        "pron" to "pron.", "interj" to "inter.", "det" to "det.",
    ),
    "ja" to mapOf(
        "verb" to "動詞", "noun" to "名詞", "adj" to "形容詞",
        "adv" to "副詞", "prep" to "前置詞", "conj" to "接続詞",
        "pron" to "代名詞", "interj" to "感動詞", "det" to "限定詞",
    ),
    "ko" to mapOf(
        "verb" to "동사", "noun" to "명사", "adj" to "형용사",
        "adv" to "부사", "prep" to "전치사", "conj" to "접속사",
        "pron" to "대명사", "interj" to "감탄사", "det" to "한정사",
    ),
    "tr" to mapOf(
        "verb" to "fiil", "noun" to "isim", "adj" to "sıfat",
        "adv" to "zarf", "prep" to "edat", "conj" to "bağlaç",
        "pron" to "zamir", "interj" to "ünlem", "det" to "belirteç",
    ),
    "vi" to mapOf(
        "verb" to "động từ", "noun" to "danh từ", "adj" to "tính từ",
        "adv" to "trạng từ", "prep" to "giới từ", "conj" to "liên từ",
        "pron" to "đại từ", "interj" to "thán từ", "det" to "mạo từ",
    ),
    "pt-br" to mapOf(
        "verb" to "verbo", "noun" to "substantivo", "adj" to "adj.",
        "adv" to "adv.", "prep" to "prep.", "conj" to "conj.",
        "pron" to "pron.", "interj" to "interj.", "det" to "det.",
    ),
    "pt-pt" to mapOf(
        "verb" to "verbo", "noun" to "substantivo", "adj" to "adj.",
        "adv" to "adv.", "prep" to "prep.", "conj" to "conj.",
        "pron" to "pron.", "interj" to "interj.", "det" to "det.",
    ),
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
