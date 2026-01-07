// app.js - New minimal design app logic
import { api } from './api.js';
import { state } from './state.js';
import { ui } from './ui.js';

// Initialize app
async function init() {
    api.init();
    await loadNotes();
    setupEventListeners();
    ui.render();
}

// Load notes from API
async function loadNotes() {
    try {
        const userId = api.getUserId();
        const data = await api.fetchNotes(userId);
        state.setNotes(data.notes || []);
    } catch (error) {
        console.log('Loading demo data due to error:', error);
        loadDemoData();
    }
}

// Fallback demo data
function loadDemoData() {
    const demoNotes = [
        {
            id: 'demo_1',
            created_at: '2025-11-28T14:30:00',
            content: 'Думик\nЧем больше сможете взять с сообщества, чем больше готовы вложить.\nКак я могу быть полезен?\nКакая моя позиция тут?',
            tags: '#wndr3',
            status: 'focus'
        },
        {
            id: 'demo_2',
            created_at: '2025-11-15T14:31:00',
            content: 'Позиция в сообществе — это про вклад, не статус. Чем больше даёшь, тем крепче связи.',
            tags: '#wndr3, #community',
            status: 'new'
        },
        {
            id: 'demo_3',
            created_at: '2025-10-20T10:00:00',
            content: 'Какая-то мысль без тегов которую записал на бегу и забыл пометить',
            tags: '',
            status: 'new'
        },
        {
            id: 'demo_4',
            created_at: '2025-09-10T10:00:00',
            content: 'Running community needs better coordination. Maybe a simple app to sync group runs?',
            tags: '#ayda, #running',
            status: 'done'
        }
    ];
    state.setNotes(demoNotes);
}

// Setup event listeners using event delegation
function setupEventListeners() {
    // Header events: Toggle and Back button
    ui.elements.header.addEventListener('click', (e) => {
        // Toggle buttons
        if (e.target.matches('.toggle-btn')) {
            const mode = e.target.dataset.mode;
            state.setMode(mode);
            ui.render();
            api.haptic('light');
        }

        // Back button
        if (e.target.matches('#btnBack')) {
            if (state.mode === 'related' || state.mode === 'reply_related') {
                handleExitRelated();
            } else {
                state.goBack();
                ui.render();
                api.haptic('light');
            }
        }
    });

    // Body events: Tag and Date clicks
    ui.elements.body.addEventListener('click', (e) => {
        // Tag click
        if (e.target.matches('.card-tag')) {
            const tag = e.target.dataset.tag;
            state.filterByTag(tag);
            ui.render();
            api.haptic('light');
        }

        // No tag click
        if (e.target.matches('.card-notag')) {
            state.filterByNoTag();
            ui.render();
            api.haptic('light');
        }

        // Date click - open date picker
        if (e.target.matches('.card-date')) {
            ui.showDatePicker();
        }
    });

    // Actions events
    ui.elements.actions.addEventListener('click', async (e) => {
        // Find the actual button (may be SVG child element)
        const btn = e.target.closest('button');
        if (!btn) return;

        // Focus toggle
        if (btn.matches('#btnFocus')) {
            await handleToggleFocus();
        }

        // Done
        if (btn.matches('#btnDone')) {
            await handleDone();
        }

        // Prev (main mode)
        if (btn.matches('#btnPrev')) {
            handlePrev();
        }

        // Next (main mode)
        if (btn.matches('#btnNext')) {
            handleNext();
        }

        // Related button (enter tags related mode)
        if (btn.matches('#btnRelated') && !btn.disabled) {
            await handleEnterRelated();
        }

        // Reply related button (enter reply related mode)
        if (btn.matches('#btnReplyRelated') && !btn.disabled) {
            await handleEnterReplyRelated();
        }

        // Back arrow in related modes (exit)
        if (btn.matches('#btnBackArrow')) {
            handleExitRelated();
        }

        // Prev related (in tags related mode)
        if (btn.matches('#btnPrevRelated') && !btn.disabled) {
            handlePrevRelated();
        }

        // Next related (in tags related mode)
        if (btn.matches('#btnNextRelated') && !btn.disabled) {
            handleNextRelated();
        }

        // Reply navigation: up
        if (btn.matches('#btnReplyUp')) {
            await handleReplyUp();
        }

        // Reply navigation: down
        if (btn.matches('#btnReplyDown')) {
            await handleReplyDown();
        }

        // Reply navigation: branch
        if (btn.matches('#btnReplyBranch')) {
            console.log('Branch button clicked!');
            await handleReplyBranch();
        }

        // Open channel
        if (btn.matches('#btnChannel')) {
            handleOpenChannel();
        }
    });

    // Date picker events
    ui.elements.btnCloseDatePicker.addEventListener('click', () => {
        ui.hideDatePicker();
    });

    // Click outside to close
    ui.elements.datePickerOverlay.addEventListener('click', (e) => {
        if (e.target === ui.elements.datePickerOverlay) {
            ui.hideDatePicker();
        }
    });

    // Year/Month selection in date picker
    ui.elements.datePickerYears.addEventListener('click', (e) => {
        if (e.target.matches('.picker-btn')) {
            const year = parseInt(e.target.dataset.year);
            ui.updatePickerSelection('year', year);
        }
    });

    ui.elements.datePickerMonths.addEventListener('click', (e) => {
        if (e.target.matches('.picker-btn')) {
            const month = parseInt(e.target.dataset.month);
            ui.updatePickerSelection('month', month);
        }
    });

    // Apply date filter
    ui.elements.btnApplyDate.addEventListener('click', () => {
        if (state.pickerMonth && state.pickerYear) {
            state.filterByDate(state.pickerMonth, state.pickerYear);
            ui.hideDatePicker();
            ui.render();
            api.haptic('light');
        }
    });
}

// Handle focus toggle
async function handleToggleFocus() {
    const note = state.getCurrentNote();
    if (!note) return;

    const newStatus = state.toggleFocus();
    ui.render();
    api.haptic('medium');

    // API call
    const userId = api.getUserId();
    if (userId !== 'demo') {
        await api.updateStatus(note.id, newStatus, userId);
    }
}

// Handle done
async function handleDone() {
    const note = state.getCurrentNote();
    if (!note) return;

    state.markDone();
    ui.render();
    api.haptic('medium');

    // API call
    const userId = api.getUserId();
    if (userId !== 'demo') {
        await api.updateStatus(note.id, 'done', userId);
    }
}

// Handle prev
function handlePrev() {
    // Go to previous note (loop around)
    if (state.filteredNotes.length === 0) return;
    state.currentIndex = (state.currentIndex - 1 + state.filteredNotes.length) % state.filteredNotes.length;
    ui.render();
    api.haptic('light');
}

// Handle next
function handleNext() {
    state.nextNote();
    ui.render();
    api.haptic('light');
}

// Handle open channel - open link without closing app
function handleOpenChannel() {
    const note = state.getCurrentNote();
    if (!note) return;

    // Try to construct Telegram link from available data
    if (note.tg_link) {
        // Open in Telegram using the web app's openTelegramLink
        if (window.Telegram?.WebApp?.openTelegramLink) {
            window.Telegram.WebApp.openTelegramLink(note.tg_link);
        } else {
            window.open(note.tg_link, '_blank');
        }
    } else if (note.source_chat_id && note.telegram_message_id) {
        // Try to construct link
        const chatId = note.source_chat_id.toString().replace('-100', '');
        const link = `https://t.me/c/${chatId}/${note.telegram_message_id}`;
        if (window.Telegram?.WebApp?.openTelegramLink) {
            window.Telegram.WebApp.openTelegramLink(link);
        } else {
            window.open(link, '_blank');
        }
    } else {
        api.showAlert('Ссылка на канал недоступна');
    }
}

// Handle enter related mode
async function handleEnterRelated() {
    const note = state.getCurrentNote();
    if (!note) return;

    // Enter related mode
    state.enterRelatedMode();

    // Show loading state
    ui.renderHeader();
    ui.renderLoadingState('Вычисляем связи...');
    ui.elements.actions.innerHTML = ''; // Clear actions during loading
    api.haptic('light');

    // Fetch related notes from API
    const userId = api.getUserId();
    try {
        const relatedNotes = await api.fetchRelatedNotes(note.id, userId);
        state.setRelatedNotes(relatedNotes, note.id);
        ui.render();
        api.haptic('medium');
    } catch (error) {
        console.error('Error fetching related notes:', error);
        state.exitRelatedMode();
        api.showAlert('Ошибка загрузки связей');
        ui.render();
    }
}

// Handle exit related mode (both tags and reply)
function handleExitRelated() {
    if (state.mode === 'reply_related') {
        state.exitReplyRelatedMode();
    } else {
        state.exitRelatedMode();
    }
    ui.render();
    api.haptic('light');
}

// Handle prev related note (tags mode)
function handlePrevRelated() {
    state.prevRelated();
    ui.render();
    api.haptic('light');
}

// Handle next related note (tags mode)
function handleNextRelated() {
    state.nextRelated();
    ui.render();
    api.haptic('light');
}

// Handle enter reply related mode
async function handleEnterReplyRelated() {
    const note = state.getCurrentNote();
    if (!note) return;

    // Enter reply related mode
    state.enterReplyRelatedMode();

    // Show loading state
    ui.renderHeader();
    ui.renderLoadingState('Вычисляем связи...');
    ui.elements.actions.innerHTML = '';
    api.haptic('light');

    // Fetch reply chain from API
    const userId = api.getUserId();
    try {
        const response = await api.fetchReplyChain(note.id, userId);
        state.setReplyChain(
            response.chain,
            response.current_index,
            response.stats,
            response.branches || []
        );
        ui.render();
        api.haptic('medium');
    } catch (error) {
        console.error('Error fetching reply chain:', error);
        state.exitReplyRelatedMode();
        api.showAlert('Ошибка загрузки цепочки');
        ui.render();
    }
}

// Handle reply navigation: up (to parent)
async function handleReplyUp() {
    const note = state.getCurrentNote();
    if (!note || !note.reply_to_message_id) return;

    // Find parent in chain (use string comparison)
    const parentIndex = state.replyChain.findIndex(n =>
        String(n.telegram_message_id) === String(note.reply_to_message_id)
    );

    if (parentIndex >= 0) {
        // Remember current note as selected branch for the parent
        state.currentBranchChildId = note.id;
        state.replyIndex = parentIndex;
        // Update stats for new position
        const parentNote = state.replyChain[parentIndex];
        state.replyStats = calculateReplyStats(parentNote);
        ui.render();
        api.haptic('light');
    }
}

// Handle reply navigation: down (to first child)
async function handleReplyDown() {
    const note = state.getCurrentNote();
    if (!note) return;

    // Find all children
    const children = state.replyChain.filter(n =>
        String(n.reply_to_message_id) === String(note.telegram_message_id)
    );

    if (children.length === 0) return;

    // Use tracked branch child or first child
    let targetChild = children[0];
    if (state.currentBranchChildId) {
        const tracked = children.find(c => c.id === state.currentBranchChildId);
        if (tracked) targetChild = tracked;
    }

    const childIndex = state.replyChain.findIndex(n => n.id === targetChild.id);
    if (childIndex >= 0) {
        state.replyIndex = childIndex;
        state.currentBranchChildId = null;  // Reset for next level
        // Update stats for new position
        const childNote = state.replyChain[childIndex];
        state.replyStats = calculateReplyStats(childNote);
        ui.render();
        api.haptic('light');
    }
}

// Handle reply navigation: switch branch (just select next branch, don't navigate)
async function handleReplyBranch() {
    const note = state.getCurrentNote();
    if (!note) return;

    console.log('handleReplyBranch called, note:', note.id);

    // Find all children of current note in the full chain
    const children = state.replyChain.filter(n =>
        String(n.reply_to_message_id) === String(note.telegram_message_id)
    );

    console.log('Children found:', children.length, children.map(c => c.id));

    if (children.length <= 1) {
        console.log('Not enough children to switch');
        return;
    }

    // Track which child branch we're currently on
    if (!state.currentBranchChildId) {
        state.currentBranchChildId = children[0]?.id;
    }

    // Find current child index
    let currentChildIdx = children.findIndex(c => c.id === state.currentBranchChildId);
    if (currentChildIdx < 0) currentChildIdx = 0;

    // Cycle to next child
    const nextChildIdx = (currentChildIdx + 1) % children.length;
    const nextChild = children[nextChildIdx];
    state.currentBranchChildId = nextChild.id;

    console.log('Selected branch:', nextChild.id, `(${nextChildIdx + 1}/${children.length})`);

    // Update UI to show which branch is selected (but stay on current note)
    api.haptic('light');
    ui.render();  // Update header to show selected branch
}

// Helper: calculate reply stats for a note
function calculateReplyStats(note) {
    if (!note) return { up: 0, down: 0, branches: 0 };

    // Count ancestors (up)
    let up = 0;
    let current = note;
    while (current.reply_to_message_id) {
        const parent = state.replyChain.find(n =>
            String(n.telegram_message_id) === String(current.reply_to_message_id)
        );
        if (parent) {
            up++;
            current = parent;
        } else break;
    }

    // Count direct children (down) - also used for branches
    const children = state.replyChain.filter(n =>
        String(n.reply_to_message_id) === String(note.telegram_message_id)
    );
    const down = children.length;

    console.log('calculateReplyStats for', note.id, ':', { up, down, branches: down });

    return { up, down, branches: down };
}

// Start the app
init();
