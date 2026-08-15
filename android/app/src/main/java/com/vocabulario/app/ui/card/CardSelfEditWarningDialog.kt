package com.vocabulario.app.ui.card

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.data.api.SelfEditValidateIssue
import com.vocabulario.app.ui.TestTags

@StringRes
internal fun selfEditFieldLabelRes(field: String): Int {
    val f = field.lowercase()
    return when {
        f == "pos" || f.endsWith(".pos") -> R.string.correction_field_pos
        f == "lemma" || f == "lemma_l2" || f.endsWith(".lemma") -> R.string.correction_field_lemma
        "gloss" in f -> R.string.correction_field_gloss
        "note" in f -> R.string.correction_field_notes
        "ipa" in f || "pronun" in f -> R.string.correction_field_ipa
        "example" in f -> R.string.correction_field_examples
        "usage" in f -> R.string.correction_field_usages
        "synonym" in f -> R.string.correction_field_synonyms_l1
        "similar" in f -> R.string.correction_field_similar
        "conjug" in f -> R.string.correction_field_conjugation_json
        "meaning" in f -> R.string.correction_section_meanings
        else -> R.string.correction_section_other
    }
}

@Composable
fun CardSelfEditWarningDialog(
    visible: Boolean,
    lemma: String,
    issues: List<SelfEditValidateIssue>,
    onConfirm: () -> Unit,
    onRevert: () -> Unit,
) {
    if (!visible) return
    CardBlockingAlertDialog(
        onDismissRequest = {},
        warning = true,
        title = {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    Icons.Default.Warning,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.error,
                    modifier = Modifier.size(22.dp),
                )
                Text(stringResource(R.string.self_edit_warning_title))
            }
        },
        text = {
            Column {
                Text(
                    lemma,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    stringResource(R.string.self_edit_warning_body, lemma),
                    style = MaterialTheme.typography.bodyMedium,
                )
                if (issues.isNotEmpty()) {
                    Spacer(Modifier.height(12.dp))
                    issues.forEach { issue ->
                        Text(
                            "• ${stringResource(selfEditFieldLabelRes(issue.field))}",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.Medium,
                            modifier = Modifier.padding(bottom = 6.dp),
                        )
                    }
                }
            }
        },
        buttons = {
            CardDialogButtonRow(
                secondaryText = stringResource(R.string.action_cancel),
                onSecondary = onRevert,
                secondaryModifier = Modifier.testTag(TestTags.BTN_SELF_EDIT_WARNING_REVERT),
                primaryText = stringResource(R.string.action_ok),
                onPrimary = onConfirm,
                primaryModifier = Modifier.testTag(TestTags.BTN_SELF_EDIT_WARNING_CONFIRM),
            )
        },
        modifier = Modifier.testTag(TestTags.DIALOG_SELF_EDIT_WARNING),
    )
}
