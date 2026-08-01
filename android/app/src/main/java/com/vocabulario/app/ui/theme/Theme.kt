package com.vocabulario.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.vocabulario.app.R

val GradeAgain = Color(0xFF8B3A3A)
val GradeHard = Color(0xFFB85C5C)
val GradeLearning = Color(0xFFC4894A)
val GradeKnown = Color(0xFF5A9E6F)
val ProgressMuted = Color(0xFF6B7280)

val DmSans = FontFamily(
    Font(R.font.dmsans_regular, FontWeight.Normal),
    Font(R.font.dmsans_medium, FontWeight.Medium),
    Font(R.font.dmsans_semibold, FontWeight.SemiBold),
    Font(R.font.dmsans_bold, FontWeight.Bold),
)

/** Light: Coinbase-like cool blue + soft gray canvas */
private val Blue = Color(0xFF0052FF)
private val BlueSoft = Color(0xFFE8F0FF)
private val LightBg = Color(0xFFF4F5F7)
private val LightInk = Color(0xFF0A0B0D)
private val LightMuted = Color(0xFF6B7280)
private val LightBorder = Color(0xFFE5E7EB)

/** Dark: true-black layers + teal accent */
private val Teal = Color(0xFF2DD4BF)
private val TealContainer = Color(0xFF163A36)
private val DarkBg = Color(0xFF000000)
private val DarkSurface = Color(0xFF17171A)
private val DarkSurface2 = Color(0xFF222228)
private val DarkInk = Color(0xFFF4F4F5)
private val DarkMuted = Color(0xFFA1A1AA)
private val DarkBorder = Color(0xFF2E2E36)

private val LightColors = lightColorScheme(
    primary = Blue,
    onPrimary = Color.White,
    primaryContainer = BlueSoft,
    onPrimaryContainer = Color(0xFF0033A0),
    secondary = Color(0xFF2563EB),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFEFF4FF),
    onSecondaryContainer = Color(0xFF1E3A8A),
    background = LightBg,
    onBackground = LightInk,
    surface = Color.White,
    onSurface = LightInk,
    surfaceVariant = Color(0xFFEEF0F3),
    onSurfaceVariant = LightMuted,
    outline = LightBorder,
    outlineVariant = Color(0xFFF0F1F3),
    error = GradeHard,
    onError = Color.White,
)

private val DarkColors = darkColorScheme(
    primary = Teal,
    onPrimary = Color(0xFF042F2E),
    primaryContainer = TealContainer,
    onPrimaryContainer = Color(0xFFCCFBF1),
    secondary = Color(0xFF5EEAD4),
    onSecondary = Color(0xFF042F2E),
    secondaryContainer = Color(0xFF1F2A2A),
    onSecondaryContainer = Color(0xFFCCFBF1),
    background = DarkBg,
    onBackground = DarkInk,
    surface = DarkSurface,
    onSurface = DarkInk,
    surfaceVariant = DarkSurface2,
    onSurfaceVariant = DarkMuted,
    outline = DarkBorder,
    outlineVariant = Color(0xFF1F1F24),
    error = GradeHard,
    onError = DarkInk,
)

private fun type(
    size: Int,
    weight: FontWeight,
    line: Int,
    tracking: Double = 0.0,
) = TextStyle(
    fontFamily = DmSans,
    fontSize = size.sp,
    fontWeight = weight,
    lineHeight = line.sp,
    letterSpacing = tracking.sp,
)

private val AppTypography = Typography(
    displaySmall = type(32, FontWeight.Bold, 40, -0.5),
    headlineMedium = type(26, FontWeight.Bold, 32, -0.3),
    headlineSmall = type(22, FontWeight.SemiBold, 28),
    titleLarge = type(20, FontWeight.SemiBold, 28),
    titleMedium = type(16, FontWeight.SemiBold, 24),
    titleSmall = type(14, FontWeight.SemiBold, 20),
    bodyLarge = type(16, FontWeight.Normal, 24),
    bodyMedium = type(14, FontWeight.Normal, 22),
    bodySmall = type(13, FontWeight.Normal, 18),
    labelLarge = type(14, FontWeight.SemiBold, 20, 0.1),
    labelMedium = type(12, FontWeight.Medium, 16, 0.2),
    labelSmall = type(11, FontWeight.Medium, 14, 0.2),
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(12.dp),
    small = RoundedCornerShape(14.dp),
    medium = RoundedCornerShape(20.dp),
    large = RoundedCornerShape(28.dp),
    extraLarge = RoundedCornerShape(32.dp),
)

@Composable
fun VocabularioTheme(
    themeMode: String = "system",
    content: @Composable () -> Unit,
) {
    val darkTheme = when (themeMode) {
        "dark" -> true
        "light" -> false
        else -> isSystemInDarkTheme()
    }
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = AppTypography,
        shapes = AppShapes,
        content = content,
    )
}
