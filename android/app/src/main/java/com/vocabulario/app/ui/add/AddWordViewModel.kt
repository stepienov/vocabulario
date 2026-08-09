package com.vocabulario.app.ui.add

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.api.LookupResponse
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.i18n.UiStrings
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AddWordUiState(
    val query: String = "",
    val loading: Boolean = false,
    val candidates: List<LookupCandidate> = emptyList(),
    val source: String? = null,
    val createdCard: CardResponse? = null,
    val error: String? = null,
    val message: String? = null,
)

@HiltViewModel
class AddWordViewModel @Inject constructor(
    private val repository: LearningRepository,
    private val strings: UiStrings,
) : ViewModel() {

    private val _state = MutableStateFlow(AddWordUiState())
    val state: StateFlow<AddWordUiState> = _state.asStateFlow()

    fun onQueryChange(value: String) {
        _state.value = _state.value.copy(query = value, error = null)
    }

    fun lookup() {
        val text = _state.value.query.trim()
        if (text.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null, createdCard = null)
            runCatching { repository.lookup(text) }
                .onSuccess { response: LookupResponse ->
                    _state.value = _state.value.copy(
                        loading = false,
                        candidates = response.candidates,
                        source = response.source,
                    )
                }
                .onFailure {
                    _state.value = _state.value.copy(
                        loading = false,
                        error = it.userMessage(strings.get(R.string.err_search)),
                    )
                }
        }
    }

    fun addToLearning(candidate: LookupCandidate) {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            runCatching {
                repository.createCard(
                    lemma = candidate.lemma,
                    pos = candidate.pos,
                    gloss = candidate.gloss,
                    lexicalEntryId = candidate.lexical_entry_id,
                )
            }.onSuccess { card ->
                _state.value = _state.value.copy(
                    loading = false,
                    createdCard = card,
                    message = strings.get(R.string.msg_added_learning, card.lemma_l2),
                )
            }.onFailure {
                _state.value = _state.value.copy(
                    loading = false,
                    error = it.userMessage(strings.get(R.string.err_create_card)),
                )
            }
        }
    }

    fun clearCard() {
        _state.value = _state.value.copy(createdCard = null)
    }
}
