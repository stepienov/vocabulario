package com.vocabulario.app.ui.components

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R

/**
 * Wordmark logo — picks light/dark asset from the active Material theme.
 * Asset is a tightly cropped horizontal wordmark (not a square canvas).
 */
@Composable
fun BrandLogo(
    modifier: Modifier = Modifier,
    height: Dp = 28.dp,
    maxWidth: Dp = 200.dp,
) {
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    Image(
        painter = painterResource(
            if (dark) R.drawable.logo_wordmark_dark else R.drawable.logo_wordmark_light,
        ),
        contentDescription = stringResource(R.string.app_name),
        modifier = modifier
            .height(height)
            .widthIn(max = maxWidth),
        contentScale = ContentScale.Fit,
    )
}
