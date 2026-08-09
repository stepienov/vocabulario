package com.vocabulario.app.data

/**
 * Wyciąga listę haseł z wklejki / pliku tekstowego (CSV/TSV/Anki plain text).
 */
object ImportTextParser {

    fun parse(raw: String): List<String> {
        val lines = raw.replace("\r\n", "\n").replace('\r', '\n').lines()
        var guidCol: Int? = null
        var tagsCol: Int? = null
        val out = LinkedHashSet<String>()

        for (line in lines) {
            val trimmed = line.trim()
            if (trimmed.isEmpty()) continue
            if (trimmed.startsWith("#")) {
                when {
                    trimmed.startsWith("#guid column:", ignoreCase = true) ->
                        guidCol = trimmed.substringAfter(':').trim().toIntOrNull()?.let { it - 1 }
                    trimmed.startsWith("#tags column:", ignoreCase = true) ->
                        tagsCol = trimmed.substringAfter(':').trim().toIntOrNull()?.let { it - 1 }
                }
                continue
            }
            val word = extractWord(trimmed, guidCol = guidCol, tagsCol = tagsCol) ?: continue
            if (word.isNotBlank()) out.add(word)
        }
        return out.toList()
    }

    private fun extractWord(line: String, guidCol: Int?, tagsCol: Int?): String? {
        val cols = splitColumns(line)
        if (cols.isEmpty()) return null

        // Anki Notes z GUID — bierzemy pierwsze krótkie pole po decku (czasownik L2 u typowych talii)
        if (guidCol != null && cols.size >= 5) {
            val candidates = cols.drop(3).filterIndexed { idx, _ ->
                val abs = idx + 3
                abs != tagsCol
            }
            for (c in candidates) {
                val cleaned = stripHtml(c).trim().trim('"')
                if (isLikelyLemma(cleaned)) return cleaned
            }
        }

        if (cols.size >= 2) {
            val first = stripHtml(cols[0]).trim().trim('"')
            if (isLikelyLemma(first) || first.isNotBlank()) return first.take(80)
        }

        val single = stripHtml(cols[0]).trim().trim('"')
        return single.takeIf { it.isNotBlank() }?.take(80)
    }

    private fun splitColumns(line: String): List<String> {
        return when {
            line.contains('\t') -> line.split('\t')
            line.contains(';') -> line.split(';')
            Regex("""^"[^"]*",|,[^,]""").containsMatchIn(line) ->
                line.split(',').map { it.trim().trim('"') }
            else -> listOf(line)
        }
    }

    private fun stripHtml(s: String): String =
        s.replace(Regex("<[^>]+>"), " ")
            .replace(Regex("""\[anki:tts[^\]]*].*?\[/anki:tts]""", RegexOption.IGNORE_CASE), " ")
            .replace(Regex("\\s+"), " ")
            .trim()

    private fun isLikelyLemma(s: String): Boolean {
        if (s.isBlank() || s.length > 40) return false
        if (s.contains('<') || s.contains('>')) return false
        if (s.count { it.isWhitespace() } > 2) return false
        // guid-like
        if (s.length >= 8 && s.any { it in "#$%^&*|{}[]" }) return false
        return s.any { it.isLetter() }
    }
}
