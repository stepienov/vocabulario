package com.vocabulario.app.ui.theme

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ThemeModeTest {
    private fun contrast(a: Color, b: Color): Float {
        val first = a.luminance()
        val second = b.luminance()
        return (maxOf(first, second) + 0.05f) / (minOf(first, second) + 0.05f)
    }

    @Test
    fun posCategoriesAreConsistentAndFilterColorsRemainReadableInBothThemes() {
        for (scheme in listOf(LightColors, DarkColors)) {
            assertEquals(scheme.secondaryContainer, posChipContainer(scheme, "noun"))
            assertEquals(posChipContainer(scheme, "noun"), posChipContainer(scheme, "rzeczownik"))
            assertEquals(scheme.primaryContainer, posChipContainer(scheme, "phrase"))
            assertEquals(scheme.primaryContainer, posChipContainer(scheme, "construction"))
            assertEquals(scheme.tertiaryContainer, posChipContainer(scheme, "verb"))
            for (key in listOf("noun", "verb", "phrase", "unknown")) {
                val color = posChipContainer(scheme, key)
                assertNotEquals(color, scheme.primary)
                assertTrue("Unreadable $key filter", contrast(color, scheme.onSurface) >= 4.5f)
            }
            assertTrue("Unreadable selected filter", contrast(scheme.primary, scheme.onPrimary) >= 4.5f)
            assertTrue(
                "Unreadable status filter",
                contrast(scheme.secondaryContainer, scheme.onSurface) >= 4.5f,
            )
        }
    }

    @Test
    fun systemFollowsDeviceAndExplicitChoiceOverridesIt() {
        assertTrue(usesDarkTheme("system", systemDark = true))
        assertFalse(usesDarkTheme("system", systemDark = false))
        assertTrue(usesDarkTheme("dark", systemDark = false))
        assertFalse(usesDarkTheme("light", systemDark = true))
    }
}
