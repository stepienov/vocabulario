package com.vocabulario.app.ui.report

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.LegalRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/** Adres wsparcia pochodzi z manifestu dokumentów; zapamiętany adres działa też offline. */
@HiltViewModel
class SupportViewModel @Inject constructor(
    private val legal: LegalRepository,
) : ViewModel() {

    private val _email = MutableStateFlow(legal.supportEmail())
    val email: StateFlow<String?> = _email.asStateFlow()

    init {
        viewModelScope.launch { _email.value = legal.refreshSupportEmail() ?: _email.value }
    }
}
