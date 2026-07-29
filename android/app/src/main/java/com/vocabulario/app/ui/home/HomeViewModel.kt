package com.vocabulario.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.api.userMessage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HomeUiState(
    val query: String = "",
    val searchExpanded: Boolean = false,
    val loading: Boolean = false,
    val candidates: List<LookupCandidate> = emptyList(),
    val source: String? = null,
    val activeProfile: LanguageProfileResponse? = null,
    val error: String? = null,
    val addedWordModal: String? = null,
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val repository: LearningRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(HomeUiState())
    val state: StateFlow<HomeUiState> = _state.asStateFlow()

    init {
        loadProfile()
    }

    fun loadProfile() {
        viewModelScope.launch {
            runCatching { repository.getActiveProfile() }
                .onSuccess { _state.value = _state.value.copy(activeProfile = it) }
        }
    }

    fun onQueryChange(value: String) {
        _state.value = _state.value.copy(query = value, error = null)
    }

    fun search() {
        val text = _state.value.query.trim()
        if (text.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(
                loading = true,
                error = null,
                searchExpanded = true,
            )
            runCatching { repository.lookup(text) }
                .onSuccess { response ->
                    _state.value = _state.value.copy(
                        loading = false,
                        candidates = response.candidates,
                        source = response.source,
                    )
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        loading = false,
                        error = it.userMessage("Błąd wyszukiwania"),
                    )
                }
        }
    }

    fun addToLearning(candidate: LookupCandidate) {
        if (candidate.in_learning) return
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            runCatching {
                repository.createCard(
                    candidate.lemma,
                    candidate.pos,
                    candidate.gloss,
                    candidate.lexical_entry_id,
                )
            }.onSuccess { card ->
                _state.value = _state.value.copy(
                    loading = false,
                    addedWordModal = card.lemma_l2,
                    candidates = _state.value.candidates.map {
                        if (it.lemma == candidate.lemma && it.pos == candidate.pos) {
                            it.copy(in_learning = true, learning_card_id = card.id)
                        } else it
                    },
                )
            }.onFailure {
                _state.value = _state.value.copy(
                    loading = false,
                    error = it.userMessage("Błąd dodawania do nauki"),
                )
            }
        }
    }

    fun addFavorite(candidate: LookupCandidate) {
        if (candidate.is_favorite) return
        viewModelScope.launch {
            runCatching { repository.addFavorite(candidate.lemma, candidate.pos, candidate.gloss) }
                .onSuccess {
                    _state.value = _state.value.copy(
                        candidates = _state.value.candidates.map {
                            if (it.lemma == candidate.lemma && it.pos == candidate.pos) {
                                it.copy(is_favorite = true)
                            } else it
                        },
                    )
                }
                .onFailure { _state.value = _state.value.copy(error = it.userMessage("Błąd ulubionych")) }
        }
    }

    fun dismissAddedModal() {
        _state.value = _state.value.copy(addedWordModal = null)
    }
}
