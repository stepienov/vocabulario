package com.vocabulario.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.vocabulario.app.data.api.WordListResponse

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddToListSheet(
    lemma: String,
    gloss: String?,
    lists: List<WordListResponse>,
    pickListOpen: Boolean,
    showCreateListPrompt: Boolean,
    createListName: String,
    createNameError: String?,
    onDismiss: () -> Unit,
    onLearning: () -> Unit,
    onOther: () -> Unit,
    onPickList: (String) -> Unit,
    onCreateNameChange: (String) -> Unit,
    onCreateAndAdd: () -> Unit,
    onShowCreatePrompt: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
        containerColor = scheme.surface,
        tonalElevation = 0.dp,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp)
                .padding(bottom = 28.dp, top = 4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                lemma,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            if (!gloss.isNullOrBlank()) {
                Text(
                    gloss,
                    style = MaterialTheme.typography.bodyMedium,
                    color = scheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
            Spacer(Modifier.height(22.dp))

            when {
                !pickListOpen -> {
                    Button(
                        onClick = onLearning,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp),
                        shape = AppButtonShape,
                        colors = ButtonDefaults.buttonColors(containerColor = scheme.primary),
                    ) {
                        Text("Uczę się", fontWeight = FontWeight.SemiBold)
                    }
                    Spacer(Modifier.height(10.dp))
                    OutlinedButton(
                        onClick = onOther,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp),
                        shape = AppButtonShape,
                        border = BorderStroke(1.dp, scheme.outline),
                    ) {
                        Text("Inna lista", fontWeight = FontWeight.SemiBold, color = scheme.onSurface)
                    }
                }
                showCreateListPrompt -> {
                    OutlinedTextField(
                        value = createListName,
                        onValueChange = onCreateNameChange,
                        placeholder = { Text("Nazwa listy") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(14.dp),
                        isError = createNameError != null,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = scheme.surfaceVariant,
                            unfocusedContainerColor = scheme.surfaceVariant,
                            unfocusedBorderColor = scheme.outline.copy(alpha = 0f),
                        ),
                    )
                    if (createNameError != null) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            createNameError,
                            style = MaterialTheme.typography.labelMedium,
                            color = scheme.error,
                            modifier = Modifier.fillMaxWidth(),
                            textAlign = TextAlign.Start,
                        )
                    }
                    Spacer(Modifier.height(14.dp))
                    Button(
                        onClick = onCreateAndAdd,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp),
                        shape = AppButtonShape,
                        enabled = createListName.trim().isNotBlank() && createNameError == null,
                    ) {
                        Text("Stwórz i dodaj", fontWeight = FontWeight.SemiBold)
                    }
                }
                else -> {
                    lists.filterNot { it.is_system }.forEach { list ->
                        Surface(
                            onClick = { onPickList(list.id) },
                            shape = RoundedCornerShape(16.dp),
                            color = scheme.surfaceVariant,
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(bottom = 8.dp),
                        ) {
                            Text(
                                list.name,
                                modifier = Modifier.padding(horizontal = 16.dp, vertical = 16.dp),
                                style = MaterialTheme.typography.titleSmall,
                            )
                        }
                    }
                    TextButton(onClick = onShowCreatePrompt) {
                        Text("Nowa lista", color = scheme.primary)
                    }
                }
            }
        }
    }
}
