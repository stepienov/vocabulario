package com.vocabulario.app.ui.card

import androidx.compose.material3.SheetValue
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.i18n.localizedPosLabel
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.home.LIST_FILTER_POS_KEYS
import kotlinx.serialization.json.JsonObject

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CardSelfEditSheet(
    card: CardResponse?,
    onDismiss: () -> Unit,
    onSave: (content: JsonObject) -> Unit,
) {
    val c = card ?: return
    val baseline = remember(c.id) { parseSelfEditForm(c) }
    var form by remember(c.id) { mutableStateOf(baseline) }
    val hasChanges = selfEditFormHasChanges(baseline, form)
    val sheetState = rememberModalBottomSheetState(
        skipPartiallyExpanded = true,
        confirmValueChange = { it != SheetValue.Hidden },
    )
    val scheme = MaterialTheme.colorScheme

    BackHandler(onBack = onDismiss)

    ModalBottomSheet(
        onDismissRequest = {},
        sheetState = sheetState,
        shape = AppButtonShape,
        containerColor = scheme.surface,
        tonalElevation = 0.dp,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .padding(bottom = 28.dp)
                .verticalScroll(rememberScrollState())
                .testTag(TestTags.SHEET_SELF_EDIT),
        ) {
            Text(
                stringResource(R.string.correction_self_edit_title),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                form.lemma,
                style = MaterialTheme.typography.titleMedium,
                color = scheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(12.dp))

            PosDropdown(
                value = form.pos,
                onValueChange = { form = form.copy(pos = it) },
            )

            SelfEditField(
                value = form.notes,
                onValueChange = { form = form.copy(notes = it) },
                label = stringResource(R.string.correction_field_notes),
                minLines = 2,
            )

            form.meanings.forEachIndexed { meaningIndex, meaning ->
                SectionTitle(stringResource(R.string.correction_section_meaning, meaningIndex + 1))
                SelfEditField(
                    value = meaning.glossL1,
                    onValueChange = { v ->
                        form = form.copy(
                            meanings = form.meanings.mapIndexed { i, row ->
                                if (i == meaningIndex) row.copy(glossL1 = v) else row
                            },
                        )
                    },
                    label = stringResource(R.string.correction_field_gloss),
                    testTag = if (meaningIndex == 0) TestTags.SELF_EDIT_GLOSS else null,
                )
                PairRowsSection(
                    title = stringResource(R.string.correction_field_examples),
                    rows = meaning.examples,
                    onAdd = {
                        form = form.copy(
                            meanings = form.meanings.mapIndexed { i, row ->
                                if (i == meaningIndex) {
                                    row.copy(examples = row.examples + SelfEditPairRow())
                                } else row
                            },
                        )
                    },
                    onRemove = { rowIndex ->
                        form = form.copy(
                            meanings = form.meanings.mapIndexed { i, row ->
                                if (i == meaningIndex) {
                                    row.copy(examples = row.examples.filterIndexed { j, _ -> j != rowIndex })
                                } else row
                            },
                        )
                    },
                    onChange = { rowIndex, updated ->
                        form = form.copy(
                            meanings = form.meanings.mapIndexed { i, row ->
                                if (i == meaningIndex) {
                                    row.copy(
                                        examples = row.examples.mapIndexed { j, r ->
                                            if (j == rowIndex) updated else r
                                        },
                                    )
                                } else row
                            },
                        )
                    },
                )
                PairRowsSection(
                    title = stringResource(R.string.correction_field_usages),
                    rows = meaning.usages,
                    onAdd = {
                        form = form.copy(
                            meanings = form.meanings.mapIndexed { i, row ->
                                if (i == meaningIndex) {
                                    row.copy(usages = row.usages + SelfEditPairRow())
                                } else row
                            },
                        )
                    },
                    onRemove = { rowIndex ->
                        form = form.copy(
                            meanings = form.meanings.mapIndexed { i, row ->
                                if (i == meaningIndex) {
                                    row.copy(usages = row.usages.filterIndexed { j, _ -> j != rowIndex })
                                } else row
                            },
                        )
                    },
                    onChange = { rowIndex, updated ->
                        form = form.copy(
                            meanings = form.meanings.mapIndexed { i, row ->
                                if (i == meaningIndex) {
                                    row.copy(
                                        usages = row.usages.mapIndexed { j, r ->
                                            if (j == rowIndex) updated else r
                                        },
                                    )
                                } else row
                            },
                        )
                    },
                )
            }

            OutlinedButton(
                onClick = {
                    form = form.copy(meanings = form.meanings + SelfEditMeaningRow())
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(18.dp))
                Text(stringResource(R.string.correction_add_meaning))
            }

            Spacer(Modifier.height(16.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onDismiss, modifier = Modifier.weight(1f)) {
                    Text(stringResource(R.string.action_cancel))
                }
                Button(
                    onClick = { onSave(buildSelfEditContent(c.content, form)) },
                    enabled = hasChanges,
                    modifier = Modifier.weight(1f).testTag(TestTags.BTN_SELF_EDIT_SAVE),
                    shape = AppButtonShape,
                ) {
                    Text(stringResource(R.string.action_save))
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PosDropdown(value: String, onValueChange: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    val options = LIST_FILTER_POS_KEYS.filter { it != "unknown" }
    val label = localizedPosLabel(value).ifBlank { value }.ifBlank {
        stringResource(R.string.correction_field_pos)
    }
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
        modifier = Modifier
            .fillMaxWidth()
            .testTag(TestTags.SELF_EDIT_POS),
    ) {
        OutlinedTextField(
            value = label,
            onValueChange = {},
            readOnly = true,
            label = { Text(stringResource(R.string.correction_field_pos)) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier
                .fillMaxWidth()
                .menuAnchor(MenuAnchorType.PrimaryNotEditable),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { key ->
                DropdownMenuItem(
                    text = { Text(localizedPosLabel(key).ifBlank { key }) },
                    onClick = {
                        onValueChange(key)
                        expanded = false
                    },
                )
            }
        }
    }
    Spacer(Modifier.height(8.dp))
}

@Composable
private fun SectionTitle(text: String) {
    Spacer(Modifier.height(12.dp))
    Text(text, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
    Spacer(Modifier.height(6.dp))
}

@Composable
private fun SelfEditField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    minLines: Int = 1,
    testTag: String? = null,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        modifier = Modifier
            .fillMaxWidth()
            .then(if (testTag != null) Modifier.testTag(testTag) else Modifier),
        minLines = minLines,
        singleLine = minLines == 1,
    )
    Spacer(Modifier.height(8.dp))
}

@Composable
private fun PairRowsSection(
    title: String,
    rows: List<SelfEditPairRow>,
    onAdd: () -> Unit,
    onRemove: (Int) -> Unit,
    onChange: (Int, SelfEditPairRow) -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    SectionTitle(title)
    if (rows.isEmpty()) {
        Text(
            stringResource(R.string.correction_empty_rows_hint),
            style = MaterialTheme.typography.bodySmall,
            color = scheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(6.dp))
    }
    rows.forEachIndexed { index, row ->
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = row.l2,
                    onValueChange = { onChange(index, row.copy(l2 = it)) },
                    label = { Text(stringResource(R.string.correction_field_l2)) },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                )
                SelfEditRemoveButton(onClick = { onRemove(index) })
            }
            Spacer(Modifier.height(6.dp))
            OutlinedTextField(
                value = row.l1,
                onValueChange = { onChange(index, row.copy(l1 = it)) },
                label = { Text(stringResource(R.string.correction_field_l1)) },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
        }
        Spacer(Modifier.height(8.dp))
    }
    OutlinedButton(onClick = onAdd, modifier = Modifier.fillMaxWidth()) {
        Text(stringResource(R.string.correction_add_row))
    }
}

@Composable
private fun SelfEditRemoveButton(onClick: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    Surface(
        onClick = onClick,
        shape = CircleShape,
        color = scheme.error.copy(alpha = 0.15f),
        contentColor = scheme.error,
        modifier = Modifier.size(40.dp),
    ) {
        Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
            Icon(
                Icons.Default.Close,
                contentDescription = stringResource(R.string.action_delete),
                modifier = Modifier.size(20.dp),
            )
        }
    }
}
