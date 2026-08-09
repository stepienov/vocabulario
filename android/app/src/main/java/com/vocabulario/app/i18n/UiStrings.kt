package com.vocabulario.app.i18n

import android.content.Context
import androidx.annotation.StringRes
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/** Localized strings for ViewModels / non-Compose code. Honors the applied app locale. */
@Singleton
class UiStrings @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    fun get(@StringRes id: Int): String = context.getString(id)

    fun get(@StringRes id: Int, vararg args: Any): String = context.getString(id, *args)
}
