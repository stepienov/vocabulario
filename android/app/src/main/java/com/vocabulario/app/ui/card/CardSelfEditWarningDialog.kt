package com.vocabulario.app.ui.card

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.data.api.SelfEditValidateIssue
import com.vocabulario.app.ui.TestTags

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
        title = {
            Text(stringResource(R.string.self_edit_warning_title))
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
                            "• ${issue.label}: ${issue.message}",
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
                secondaryText = stringResource(R.string.self_edit_warning_revert),
                onSecondary = onRevert,
                secondaryModifier = Modifier.testTag(TestTags.BTN_SELF_EDIT_WARNING_REVERT),
                primaryText = stringResource(R.string.self_edit_warning_confirm),
                onPrimary = onConfirm,
                primaryModifier = Modifier.testTag(TestTags.BTN_SELF_EDIT_WARNING_CONFIRM),
            )
        },
        modifier = Modifier.testTag(TestTags.DIALOG_SELF_EDIT_WARNING),
    )
}
