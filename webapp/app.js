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
            if (state.mode === 'related') {
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
        // Focus toggle
        if (e.target.matches('#btnFocus')) {
            await handleToggleFocus();
        }

        // Done
        if (e.target.matches('#btnDone')) {
            await handleDone();
        }

        // Next
        if (e.target.matches('#btnNext')) {
            handleNext();
        }

        // Related button (enter related mode)
        if (e.target.matches('#btnRelated') && !e.target.disabled) {
            await handleEnterRelated();
        }

        // Back arrow in related mode (exit)
        if (e.target.matches('#btnBackArrow')) {
            handleExitRelated();
        }

        // Next related (in related mode)
        if (e.target.matches('#btnNextRelated')) {
            handleNextRelated();
        }

        // Open channel
        if (e.target.matches('#btnChannel')) {
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

// Handle exit related mode
function handleExitRelated() {
    state.exitRelatedMode();
    ui.render();
    api.haptic('light');
}

// Handle next related note
function handleNextRelated() {
    state.nextRelated();
    ui.render();
    api.haptic('light');
}

// Start the app
init();
