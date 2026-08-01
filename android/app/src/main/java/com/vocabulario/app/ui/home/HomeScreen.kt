package com.vocabulario.app.ui.home

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.automirrored.outlined.DriveFileMove
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.DashboardForecastDay
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.api.WordListResponse
import androidx.compose.ui.graphics.Color
import com.vocabulario.app.data.posLabelPl
import com.vocabulario.app.ui.components.AddToListSheet
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppCard
import com.vocabulario.app.ui.components.AppChipShape
import com.vocabulario.app.ui.components.AppDialogShape
import com.vocabulario.app.ui.components.TagChip
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

private val ScreenPad = 20.dp
private val TileRadius = RoundedCornerShape(28.dp)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onPractice: () -> Unit,
    onSettings: () -> Unit,
    onOpenCard: (String) -> Unit = {},
    viewModel: HomeViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    val scheme = MaterialTheme.colorScheme
    val lifecycleOwner = LocalLifecycleOwner.current

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                viewModel.onHomeResumed()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    // Learning steps bywają w minutach — odświeżaj dashboard w tle.
    LaunchedEffect(state.tab) {
        if (state.tab != HomeTab.DASHBOARD) return@LaunchedEffect
        while (isActive) {
            delay(30_000)
            viewModel.loadStats()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(scheme.background)
            .statusBarsPadding()
            .navigationBarsPadding(),
    ) {
        HomeHeader(onSettings = onSettings)
        HomeTabs(
            selected = state.tab,
            onSelect = viewModel::selectTab,
        )
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
        ) {
            when (state.tab) {
                HomeTab.DASHBOARD -> DashboardTab(state = state)
                HomeTab.ADD -> AddTab(
                    state = state,
                    onQueryChange = viewModel::onQueryChange,
                    onSearch = viewModel::search,
                    onAdd = viewModel::openAddSheet,
                    onOpenList = viewModel::openListFromChip,
                )
                HomeTab.LISTS -> ListsTab(
                    state = state,
                    onSelectList = viewModel::selectList,
                    onCreateList = viewModel::createEmptyList,
                    onCreateListAndMove = viewModel::createListAndMoveWord,
                    onRenameList = viewModel::renameList,
                    onDeleteList = viewModel::deleteList,
                    onDeleteWord = viewModel::deleteWord,
                    onMoveWord = viewModel::moveWord,
                )
            }
        }
        Button(
            onClick = onPractice,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = ScreenPad, vertical = 16.dp)
                .height(54.dp),
            shape = AppButtonShape,
            colors = ButtonDefaults.buttonColors(
                containerColor = scheme.primary,
                contentColor = scheme.onPrimary,
            ),
            elevation = ButtonDefaults.buttonElevation(defaultElevation = 0.dp),
        ) {
            Text("Ucz się", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        }
    }

    state.addTarget?.let { target ->
        AddToListSheet(
            lemma = target.lemma,
            gloss = target.gloss,
            lists = state.lists,
            pickListOpen = state.pickListOpen,
            showCreateListPrompt = state.showCreateListPrompt,
            createListName = state.createListName,
            createNameError = listNameConflictMessage(state.lists, state.createListName),
            onDismiss = viewModel::dismissAddSheet,
            onLearning = viewModel::addToLearning,
            onOther = viewModel::openOtherLists,
            onPickList = viewModel::addToList,
            onCreateNameChange = viewModel::onCreateListNameChange,
            onCreateAndAdd = viewModel::createListAndAdd,
            onShowCreatePrompt = viewModel::openCreateListPrompt,
        )
    }
}

@Composable
private fun HomeHeader(onSettings: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = ScreenPad, vertical = 16.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            "vocabulario.",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = scheme.onBackground,
        )
        IconButton(
            onClick = onSettings,
            modifier = Modifier
                .size(44.dp)
                .clip(CircleShape)
                .background(scheme.surfaceVariant),
        ) {
            Icon(
                Icons.Outlined.Settings,
                contentDescription = "Ustawienia",
                tint = scheme.onSurface,
            )
        }
    }
}

@Composable
private fun HomeTabs(selected: HomeTab, onSelect: (HomeTab) -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val tabs = listOf(
        HomeTab.DASHBOARD to "dashboard",
        HomeTab.ADD to "dodaj",
        HomeTab.LISTS to "listy",
    )
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp),
        ) {
            tabs.forEach { (tab, label) ->
                val active = selected == tab
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .clickable { onSelect(tab) }
                        .padding(top = 8.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(
                        label,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = if (active) FontWeight.Bold else FontWeight.Medium,
                        color = if (active) scheme.onBackground else scheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(10.dp))
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(3.dp)
                            .padding(horizontal = 18.dp)
                            .clip(RoundedCornerShape(2.dp))
                            .background(if (active) scheme.onBackground else scheme.outline.copy(alpha = 0f)),
                    )
                }
            }
        }
        HorizontalDivider(color = scheme.outline, thickness = 1.dp)
    }
}

@Composable
private fun DashboardTab(state: HomeUiState) {
    val stats = state.stats
    val scheme = MaterialTheme.colorScheme

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = ScreenPad, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        // Dziś — 3 kluczowe metryki
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = TileRadius,
            color = scheme.surface,
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 10.dp, vertical = 14.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                TodayStat(
                    label = "Gotowe do powtórki teraz",
                    value = stats?.due_count?.toString() ?: "–",
                    modifier = Modifier.weight(1f),
                )
                TodayStat(
                    label = "Nowe słowa poznane dziś",
                    value = stats?.new_done_today?.toString() ?: "–",
                    modifier = Modifier.weight(1f),
                )
                TodayStat(
                    label = "Powtórzone dziś",
                    value = stats?.reviews_done_today?.toString() ?: "–",
                    modifier = Modifier.weight(1f),
                )
            }
        }

        // Status — kompaktowa lista
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = TileRadius,
            color = scheme.surfaceVariant,
        ) {
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp)) {
                StatusLine(
                    label = "Aktualnie uczysz się",
                    value = stats?.let { "${it.srs_learning} słów" } ?: "–",
                )
                HorizontalDivider(color = scheme.outline.copy(alpha = 0.25f))
                StatusLine(
                    label = "Do nauki masz jeszcze",
                    value = stats?.let { "${it.new_reserve} nowych słów" } ?: "–",
                )
                HorizontalDivider(color = scheme.outline.copy(alpha = 0.25f))
                StatusLine(
                    label = "Nauczyłeś się do tej pory",
                    value = stats?.let { "${it.srs_mastered} słów" } ?: "–",
                )
            }
        }

        // Wykres 7 dni — stała wysokość, reszta miejsca bez scrolla
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f, fill = true),
            shape = TileRadius,
            color = scheme.surface,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 14.dp, vertical = 12.dp),
            ) {
                Text(
                    "Słowa do powtórki w najbliższych dniach",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = scheme.onSurface,
                )
                Spacer(Modifier.height(10.dp))
                ReviewForecastBars(
                    days = stats?.forecast.orEmpty(),
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                )
            }
        }

        state.error?.let {
            Text(it, color = scheme.error, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun TodayStat(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(
            value,
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = scheme.onSurface,
            textAlign = TextAlign.Center,
        )
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            color = scheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            maxLines = 3,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun StatusLine(
    label: String,
    value: String,
) {
    val scheme = MaterialTheme.colorScheme
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 10.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            color = scheme.onSurface,
            modifier = Modifier.weight(1f),
        )
        Text(
            value,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
            color = scheme.onSurface,
        )
    }
}

@Composable
private fun ReviewForecastBars(
    days: List<DashboardForecastDay>,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val maxCount = (days.maxOfOrNull { it.due_count } ?: 0).coerceAtLeast(1)
    val barMaxHeight = 120.dp

    if (days.isEmpty()) {
        Box(modifier = modifier, contentAlignment = Alignment.Center) {
            Text("—", color = scheme.onSurfaceVariant)
        }
        return
    }

    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.Bottom,
    ) {
        days.take(7).forEachIndexed { index, day ->
            val fraction = day.due_count.toFloat() / maxCount.toFloat()
            val barHeight = if (day.due_count == 0) 4.dp else (barMaxHeight * fraction).coerceAtLeast(8.dp)
            // Odcienie primary: dziś najmocniejszy, dalej jaśniej
            val alpha = (1f - index * 0.09f).coerceIn(0.38f, 1f)
            val barColor: Color = scheme.primary.copy(alpha = alpha)

            Column(
                modifier = Modifier.weight(1f),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Bottom,
            ) {
                Text(
                    "${day.due_count}",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = scheme.onSurface,
                )
                Spacer(Modifier.height(4.dp))
                Box(
                    modifier = Modifier
                        .fillMaxWidth(0.72f)
                        .height(barHeight)
                        .clip(RoundedCornerShape(topStart = 8.dp, topEnd = 8.dp))
                        .background(barColor),
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    day.label,
                    style = MaterialTheme.typography.labelSmall,
                    color = scheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }
        }
    }
}

@Composable
private fun AddTab(
    state: HomeUiState,
    onQueryChange: (String) -> Unit,
    onSearch: () -> Unit,
    onAdd: (LookupCandidate) -> Unit,
    onOpenList: (String?, String?) -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = ScreenPad),
    ) {
        Spacer(Modifier.height(20.dp))
        OutlinedTextField(
            value = state.query,
            onValueChange = onQueryChange,
            placeholder = { Text("Szukaj słowa…") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            shape = AppButtonShape,
            leadingIcon = {
                Icon(Icons.Default.Search, contentDescription = null, tint = scheme.onSurfaceVariant)
            },
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { onSearch() }),
            colors = OutlinedTextFieldDefaults.colors(
                focusedContainerColor = scheme.surfaceVariant,
                unfocusedContainerColor = scheme.surfaceVariant,
                disabledContainerColor = scheme.surfaceVariant,
                focusedBorderColor = scheme.outline,
                unfocusedBorderColor = scheme.outline.copy(alpha = 0f),
                cursorColor = scheme.primary,
            ),
        )
        Spacer(Modifier.height(16.dp))
        if (state.loading) {
            CircularProgressIndicator(
                modifier = Modifier
                    .align(Alignment.CenterHorizontally)
                    .padding(24.dp),
                color = scheme.primary,
                strokeWidth = 3.dp,
            )
        }
        state.error?.let { Text(it, color = scheme.error) }
        LazyColumn(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(10.dp),
            contentPadding = PaddingValues(bottom = 12.dp),
        ) {
            items(state.candidates) { candidate ->
                CandidateRow(
                    candidate = candidate,
                    onAdd = { onAdd(candidate) },
                    onOpenList = onOpenList,
                )
            }
            if (state.candidates.isEmpty() && !state.loading && state.query.isBlank()) {
                item {
                    Text(
                        "Wpisz słowo",
                        style = MaterialTheme.typography.bodyLarge,
                        color = scheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 56.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun CandidateRow(
    candidate: LookupCandidate,
    onAdd: () -> Unit,
    onOpenList: (String?, String?) -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    AppCard(
        content = {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        candidate.lemma,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = scheme.onSurface,
                    )
                    Spacer(Modifier.height(2.dp))
                    Text(
                        candidate.gloss,
                        style = MaterialTheme.typography.bodyMedium,
                        color = scheme.onSurfaceVariant,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Spacer(Modifier.height(8.dp))
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        candidate.pos?.let { TagChip(posLabelPl(it).ifBlank { it }) }
                        if (candidate.onList) {
                            TagChip(
                                text = candidate.list_name ?: "lista",
                                onClick = { onOpenList(candidate.list_id, candidate.list_name) },
                            )
                        }
                    }
                    if (candidate.isCreating) {
                        Spacer(Modifier.height(8.dp))
                        CreatingCardHint()
                    }
                }
                when {
                    candidate.isCreating -> {
                        CircularProgressIndicator(
                            modifier = Modifier.size(28.dp),
                            strokeWidth = 3.dp,
                            color = scheme.primary,
                        )
                    }
                    candidate.onList -> {
                        Icon(
                            Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = scheme.primary,
                            modifier = Modifier.size(26.dp),
                        )
                    }
                    else -> {
                        Surface(
                            onClick = onAdd,
                            shape = CircleShape,
                            color = scheme.primary,
                            contentColor = scheme.onPrimary,
                            modifier = Modifier.size(40.dp),
                        ) {
                            Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                                Icon(Icons.Default.Add, contentDescription = "Dodaj", modifier = Modifier.size(22.dp))
                            }
                        }
                    }
                }
            }
        },
    )
}

@Composable
private fun CreatingCardHint() {
    val transition = rememberInfiniteTransition(label = "creating")
    val alpha by transition.animateFloat(
        initialValue = 0.35f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(750, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "creatingAlpha",
    )
    Text(
        "Tworzę kartę",
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.primary.copy(alpha = alpha),
    )
}

private enum class ListEditDialog { None, Menu, Rename, DeleteConfirm }
private enum class WordEditDialog { None, DeleteConfirm, Move }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ListsTab(
    state: HomeUiState,
    onSelectList: (String) -> Unit,
    onCreateList: (String) -> Unit,
    onCreateListAndMove: (String, String) -> Unit,
    onRenameList: (String, String) -> Unit,
    onDeleteList: (String) -> Unit,
    onDeleteWord: (String) -> Unit,
    onMoveWord: (String, String) -> Unit,
) {
    var showCreate by remember { mutableStateOf(false) }
    var newName by remember { mutableStateOf("") }
    var createThenMoveCardId by remember { mutableStateOf<String?>(null) }
    var expandedId by remember { mutableStateOf<String?>(null) }
    var listDialog by remember { mutableStateOf(ListEditDialog.None) }
    var renameDraft by remember { mutableStateOf("") }
    var wordDialog by remember { mutableStateOf(WordEditDialog.None) }
    var wordTargetId by remember { mutableStateOf<String?>(null) }
    var moveTargetId by remember { mutableStateOf<String?>(null) }
    var moveMenuOpen by remember { mutableStateOf(false) }
    val scheme = MaterialTheme.colorScheme
    val selectedList = state.lists.firstOrNull { it.id == state.selectedListId }
    val moveTargets = state.lists.filter { it.id != state.selectedListId }

    fun closeListDialogs() {
        listDialog = ListEditDialog.None
        renameDraft = ""
    }

    fun closeWordDialogs() {
        wordDialog = WordEditDialog.None
        wordTargetId = null
        moveTargetId = null
        moveMenuOpen = false
    }

    fun closeCreateDialog() {
        showCreate = false
        newName = ""
        createThenMoveCardId = null
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = ScreenPad),
    ) {
        Spacer(Modifier.height(16.dp))
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(bottom = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            items(state.lists) { list ->
                ListChip(
                    list = list,
                    selected = list.id == state.selectedListId,
                    showMenu = list.id == state.selectedListId && !list.is_system,
                    onClick = {
                        expandedId = null
                        closeWordDialogs()
                        closeListDialogs()
                        onSelectList(list.id)
                    },
                    onMenu = {
                        renameDraft = list.name
                        listDialog = ListEditDialog.Menu
                    },
                )
            }
            item {
                Surface(
                    onClick = { showCreate = true },
                    shape = AppChipShape,
                    color = scheme.surfaceVariant,
                    contentColor = scheme.onSurface,
                ) {
                    Text(
                        "+ nowa",
                        modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                        style = MaterialTheme.typography.labelLarge,
                        color = scheme.onSurface,
                    )
                }
            }
        }

        when {
            state.loading -> {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(40.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    CircularProgressIndicator(color = scheme.primary, strokeWidth = 3.dp)
                }
            }
            state.listWords.isEmpty() -> {
                Text(
                    "Pusta lista",
                    style = MaterialTheme.typography.bodyLarge,
                    color = scheme.onSurfaceVariant,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 40.dp),
                    textAlign = TextAlign.Center,
                )
            }
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    contentPadding = PaddingValues(bottom = 12.dp),
                ) {
                    items(state.listWords, key = { it.id }) { card ->
                        ListWordTile(
                            card = card,
                            expanded = expandedId == card.id,
                            onToggle = {
                                if (card.enrichment_status == "pending" || card.id.startsWith("pending-")) {
                                    return@ListWordTile
                                }
                                expandedId = if (expandedId == card.id) null else card.id
                                closeWordDialogs()
                            },
                            onDelete = {
                                wordTargetId = card.id
                                wordDialog = WordEditDialog.DeleteConfirm
                            },
                            onMove = {
                                wordTargetId = card.id
                                if (moveTargets.isNotEmpty()) {
                                    moveTargetId = moveTargets.firstOrNull()?.id
                                    wordDialog = WordEditDialog.Move
                                } else {
                                    newName = ""
                                    createThenMoveCardId = card.id
                                    showCreate = true
                                }
                            },
                        )
                    }
                }
            }
        }
    }

    if (showCreate) {
        val trimmedCreate = newName.trim()
        val createNameError = listNameConflictMessage(state.lists, trimmedCreate)
        val movingWord = createThenMoveCardId != null
        AlertDialog(
            onDismissRequest = { closeCreateDialog() },
            shape = AppDialogShape,
            containerColor = scheme.surface,
            title = {
                Text("Nowa lista", fontWeight = FontWeight.Bold, color = scheme.onSurface)
            },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (movingWord) {
                        Text(
                            "Nie masz innej listy — utwórz nową, a słowo zostanie do niej przeniesione.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = scheme.onSurfaceVariant,
                        )
                    }
                    OutlinedTextField(
                        value = newName,
                        onValueChange = { newName = it },
                        placeholder = { Text("Nazwa", color = scheme.onSurfaceVariant) },
                        singleLine = true,
                        shape = RoundedCornerShape(14.dp),
                        modifier = Modifier.fillMaxWidth(),
                        isError = createNameError != null,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = scheme.onSurface,
                            unfocusedTextColor = scheme.onSurface,
                            focusedContainerColor = scheme.surfaceVariant,
                            unfocusedContainerColor = scheme.surfaceVariant,
                            unfocusedBorderColor = scheme.outline.copy(alpha = 0f),
                            cursorColor = scheme.primary,
                        ),
                    )
                    if (createNameError != null) {
                        Text(
                            createNameError,
                            style = MaterialTheme.typography.labelMedium,
                            color = scheme.error,
                        )
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        val moveCardId = createThenMoveCardId
                        if (moveCardId != null) {
                            onCreateListAndMove(newName, moveCardId)
                            expandedId = null
                        } else {
                            onCreateList(newName)
                        }
                        closeCreateDialog()
                    },
                    shape = AppButtonShape,
                    enabled = trimmedCreate.isNotBlank() && createNameError == null,
                ) { Text("Utwórz") }
            },
            dismissButton = {
                OutlinedButton(onClick = { closeCreateDialog() }, shape = AppButtonShape) {
                    Text("Anuluj", color = scheme.error)
                }
            },
        )
    }

    when (listDialog) {
        ListEditDialog.Menu -> {
            AlertDialog(
                onDismissRequest = { closeListDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text(
                        selectedList?.name ?: "Lista",
                        fontWeight = FontWeight.Bold,
                        color = scheme.onSurface,
                    )
                },
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = {
                                renameDraft = selectedList?.name.orEmpty()
                                listDialog = ListEditDialog.Rename
                            },
                            modifier = Modifier.fillMaxWidth(),
                            shape = AppButtonShape,
                        ) { Text("Zmień nazwę") }
                        OutlinedButton(
                            onClick = { listDialog = ListEditDialog.DeleteConfirm },
                            modifier = Modifier.fillMaxWidth(),
                            shape = AppButtonShape,
                        ) { Text("Usuń", color = scheme.error) }
                    }
                },
                confirmButton = {},
                dismissButton = {
                    TextButton(onClick = { closeListDialogs() }) {
                        Text("Wróć", color = scheme.onSurfaceVariant)
                    }
                },
            )
        }
        ListEditDialog.Rename -> {
            val trimmedRename = renameDraft.trim()
            val renameNameError = listNameConflictMessage(
                state.lists,
                trimmedRename,
                excludeId = selectedList?.id,
            )
            AlertDialog(
                onDismissRequest = { closeListDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text("Zmień nazwę", fontWeight = FontWeight.Bold, color = scheme.onSurface)
                },
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = renameDraft,
                            onValueChange = { renameDraft = it },
                            singleLine = true,
                            shape = RoundedCornerShape(14.dp),
                            modifier = Modifier.fillMaxWidth(),
                            isError = renameNameError != null,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = scheme.onSurface,
                                unfocusedTextColor = scheme.onSurface,
                                focusedContainerColor = scheme.surfaceVariant,
                                unfocusedContainerColor = scheme.surfaceVariant,
                                unfocusedBorderColor = scheme.outline.copy(alpha = 0f),
                            ),
                        )
                        if (renameNameError != null) {
                            Text(
                                renameNameError,
                                style = MaterialTheme.typography.labelMedium,
                                color = scheme.error,
                            )
                        }
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            val id = selectedList?.id
                            if (id != null) onRenameList(id, renameDraft)
                            closeListDialogs()
                        },
                        shape = AppButtonShape,
                        enabled = trimmedRename.isNotBlank() && renameNameError == null,
                    ) { Text("OK") }
                },
                dismissButton = {
                    OutlinedButton(onClick = { closeListDialogs() }, shape = AppButtonShape) {
                        Text("Anuluj", color = scheme.onSurface)
                    }
                },
            )
        }
        ListEditDialog.DeleteConfirm -> {
            AlertDialog(
                onDismissRequest = { closeListDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text("Usunąć listę?", fontWeight = FontWeight.Bold, color = scheme.onSurface)
                },
                text = {
                    Text(
                        "Lista „${selectedList?.name.orEmpty()}” i jej słowa zostaną usunięte.",
                        color = scheme.onSurfaceVariant,
                    )
                },
                confirmButton = {
                    Button(
                        onClick = {
                            val id = selectedList?.id
                            if (id != null) onDeleteList(id)
                            expandedId = null
                            closeListDialogs()
                        },
                        shape = AppButtonShape,
                        colors = ButtonDefaults.buttonColors(containerColor = scheme.error),
                    ) { Text("Usuń") }
                },
                dismissButton = {
                    OutlinedButton(onClick = { closeListDialogs() }, shape = AppButtonShape) {
                        Text("Wróć", color = scheme.onSurface)
                    }
                },
            )
        }
        ListEditDialog.None -> Unit
    }

    when (wordDialog) {
        WordEditDialog.DeleteConfirm -> {
            AlertDialog(
                onDismissRequest = { closeWordDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text(
                        "Czy potwierdzasz usunięcie słowa?",
                        fontWeight = FontWeight.Bold,
                        color = scheme.onSurface,
                    )
                },
                confirmButton = {
                    Button(
                        onClick = {
                            wordTargetId?.let(onDeleteWord)
                            expandedId = null
                            closeWordDialogs()
                        },
                        shape = AppButtonShape,
                        colors = ButtonDefaults.buttonColors(containerColor = scheme.error),
                    ) { Text("Usuń") }
                },
                dismissButton = {
                    OutlinedButton(onClick = { closeWordDialogs() }, shape = AppButtonShape) {
                        Text("Wróć", color = scheme.onSurface)
                    }
                },
            )
        }
        WordEditDialog.Move -> {
            val selectedMove = moveTargets.firstOrNull { it.id == moveTargetId } ?: moveTargets.firstOrNull()
            AlertDialog(
                onDismissRequest = { closeWordDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text("Przenieś słowo do listy", fontWeight = FontWeight.Bold, color = scheme.onSurface)
                },
                text = {
                    ExposedDropdownMenuBox(
                        expanded = moveMenuOpen,
                        onExpandedChange = { moveMenuOpen = it },
                    ) {
                        OutlinedTextField(
                            value = selectedMove?.name.orEmpty(),
                            onValueChange = {},
                            readOnly = true,
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = moveMenuOpen) },
                            modifier = Modifier
                                .fillMaxWidth()
                                .menuAnchor(MenuAnchorType.PrimaryNotEditable),
                            shape = RoundedCornerShape(14.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = scheme.onSurface,
                                unfocusedTextColor = scheme.onSurface,
                                focusedContainerColor = scheme.surfaceVariant,
                                unfocusedContainerColor = scheme.surfaceVariant,
                            ),
                        )
                        ExposedDropdownMenu(
                            expanded = moveMenuOpen,
                            onDismissRequest = { moveMenuOpen = false },
                        ) {
                            moveTargets.forEach { list ->
                                DropdownMenuItem(
                                    text = { Text(list.name) },
                                    onClick = {
                                        moveTargetId = list.id
                                        moveMenuOpen = false
                                    },
                                )
                            }
                        }
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            val cardId = wordTargetId
                            val target = moveTargetId ?: selectedMove?.id
                            if (cardId != null && target != null) onMoveWord(cardId, target)
                            expandedId = null
                            closeWordDialogs()
                        },
                        shape = AppButtonShape,
                        enabled = (moveTargetId ?: selectedMove?.id) != null,
                    ) { Text("Przenieś") }
                },
                dismissButton = {
                    OutlinedButton(onClick = { closeWordDialogs() }, shape = AppButtonShape) {
                        Text("Anuluj", color = scheme.error)
                    }
                },
            )
        }
        WordEditDialog.None -> Unit
    }
}

@Composable
private fun ListWordTile(
    card: CardResponse,
    expanded: Boolean,
    onToggle: () -> Unit,
    onDelete: () -> Unit,
    onMove: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val pending = card.enrichment_status == "pending"
    val failed = card.enrichment_status == "failed"
    val statusLabel = when {
        pending -> null
        failed -> "błąd"
        card.srs_status == "new" -> "nowe"
        card.srs_status == "learning" || card.srs_status == "relearning" -> "w nauce"
        card.srs_status == "review" && (card.srs_interval_days ?: 0.0) >= 21.0 -> "opanowane"
        card.srs_status == "review" -> "w nauce"
        else -> null
    }
    val meanings = remember(card.id, card.content) { cardMeaningGlosses(card.content) }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        color = scheme.surfaceVariant,
        contentColor = scheme.onSurface,
    ) {
        Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp)) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(enabled = !pending, onClick = onToggle),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        card.lemma_l2.ifBlank { "—" },
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = scheme.onSurface,
                    )
                    val gloss = card.gloss_primary?.takeIf { it.isNotBlank() }
                    if (gloss != null && !expanded) {
                        Spacer(Modifier.height(4.dp))
                        Text(
                            gloss,
                            style = MaterialTheme.typography.bodyMedium,
                            color = scheme.onSurfaceVariant,
                        )
                    }
                    if (pending) {
                        Spacer(Modifier.height(8.dp))
                        CreatingCardHint()
                    }
                }
                when {
                    pending -> {
                        CircularProgressIndicator(
                            modifier = Modifier.size(22.dp),
                            strokeWidth = 2.5.dp,
                            color = scheme.primary,
                        )
                    }
                    statusLabel != null -> {
                        StatusChip(label = statusLabel, failed = failed)
                    }
                }
            }

            AnimatedVisibility(
                visible = expanded && !pending,
                enter = expandVertically() + fadeIn(),
                exit = shrinkVertically() + fadeOut(),
            ) {
                Column(modifier = Modifier.padding(top = 12.dp)) {
                    HorizontalDivider(color = scheme.outline.copy(alpha = 0.5f))
                    Spacer(Modifier.height(12.dp))
                    if (meanings.isEmpty()) {
                        Text(
                            card.gloss_primary?.takeIf { it.isNotBlank() } ?: "Brak znaczeń",
                            style = MaterialTheme.typography.bodyMedium,
                            color = scheme.onSurfaceVariant,
                        )
                    } else {
                        meanings.forEachIndexed { index, meaning ->
                            if (index > 0) Spacer(Modifier.height(8.dp))
                            Text(
                                "${index + 1}. $meaning",
                                style = MaterialTheme.typography.bodyMedium,
                                color = scheme.onSurface,
                            )
                        }
                    }
                    Spacer(Modifier.height(14.dp))
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Surface(
                            onClick = onDelete,
                            shape = CircleShape,
                            color = scheme.error.copy(alpha = 0.15f),
                            contentColor = scheme.error,
                            modifier = Modifier.size(40.dp),
                        ) {
                            Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                                Icon(Icons.Default.Close, contentDescription = "Usuń", modifier = Modifier.size(20.dp))
                            }
                        }
                        Surface(
                            onClick = onMove,
                            shape = CircleShape,
                            color = scheme.primaryContainer,
                            contentColor = scheme.onPrimaryContainer,
                            modifier = Modifier.size(40.dp),
                        ) {
                            Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                                Icon(
                                    Icons.AutoMirrored.Outlined.DriveFileMove,
                                    contentDescription = "Przenieś",
                                    modifier = Modifier.size(20.dp),
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

private fun cardMeaningGlosses(content: JsonObject): List<String> {
    val meanings = content["meanings"]?.jsonArray ?: return emptyList()
    return meanings.mapNotNull { el ->
        val obj = runCatching { el.jsonObject }.getOrNull() ?: return@mapNotNull null
        obj["gloss_l1"]?.jsonPrimitive?.contentOrNull?.takeIf { it.isNotBlank() }
    }
}

@Composable
private fun StatusChip(label: String, failed: Boolean = false) {
    val scheme = MaterialTheme.colorScheme
    Surface(
        shape = AppChipShape,
        color = if (failed) scheme.error.copy(alpha = 0.18f) else scheme.primaryContainer,
        contentColor = if (failed) scheme.error else scheme.onPrimaryContainer,
    ) {
        Text(
            label,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
            color = if (failed) scheme.error else scheme.onPrimaryContainer,
        )
    }
}

@Composable
private fun ListChip(
    list: WordListResponse,
    selected: Boolean,
    showMenu: Boolean,
    onClick: () -> Unit,
    onMenu: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val bg = if (selected) scheme.onBackground else scheme.surfaceVariant
    val fg = if (selected) scheme.background else scheme.onSurface
    Surface(
        onClick = onClick,
        shape = AppChipShape,
        color = bg,
        contentColor = fg,
    ) {
        Row(
            modifier = Modifier.padding(start = 14.dp, end = if (showMenu) 4.dp else 14.dp, top = 6.dp, bottom = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "${list.name}  ${list.word_count}",
                style = MaterialTheme.typography.labelLarge,
                fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Medium,
                color = fg,
            )
            if (showMenu) {
                IconButton(
                    onClick = onMenu,
                    modifier = Modifier.size(32.dp),
                ) {
                    Icon(
                        Icons.Outlined.MoreVert,
                        contentDescription = "Opcje listy",
                        tint = fg,
                        modifier = Modifier.size(18.dp),
                    )
                }
            }
        }
    }
}
