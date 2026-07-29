package com.vocabulario.app.ui.favorites

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.FavoriteResponse
import com.vocabulario.app.data.api.userMessage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import javax.inject.Inject

data class FavoritesUiState(
    val items: List<FavoriteResponse> = emptyList(),
    val loading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class FavoritesViewModel @Inject constructor(
    private val repository: LearningRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(FavoritesUiState())
    val state: StateFlow<FavoritesUiState> = _state.asStateFlow()
    private var pollJob: Job? = null

    fun load() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            runCatching { repository.listFavorites() }
                .onSuccess { items ->
                    _state.value = FavoritesUiState(loading = false, items = items)
                    startPollingIfNeeded(items)
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        loading = false,
                        error = it.userMessage("Błąd ładowania ulubionych"),
                    )
                }
        }
    }

    private fun startPollingIfNeeded(items: List<FavoriteResponse>) {
        pollJob?.cancel()
        if (items.none { it.enrichment_status == "pending" }) return
        pollJob = viewModelScope.launch {
            while (isActive) {
                delay(3_000)
                val refreshed = runCatching { repository.listFavorites() }.getOrNull() ?: continue
                _state.value = _state.value.copy(items = refreshed)
                if (refreshed.none { it.enrichment_status == "pending" }) break
            }
        }
    }
}
