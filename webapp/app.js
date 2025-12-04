// app.js
import { api } from './api.js';
import { state } from './state.js';
import { ui } from './ui.js';

// Initialize
async function init() {
    api.init();

    // Event Listeners
    setupEventListeners();

    // Initial Load
    await loadNotes();
}

function setupEventListeners() {
    // Navigation
    ui.elements.nextBtn.addEventListener('click', () => {
        state.nextNote();
        ui.displayNote(state.getCurrentNote());
        api.haptic('light');
    });

    // Actions
    ui.elements.btnDone.addEventListener('click', () => handleStatusUpdate('done', 'medium'));
    ui.elements.btnFlow.addEventListener('click', () => handleStatusUpdate('flow', 'light'));

    ui.elements.focusBtn.addEventListener('click', () => {
        const note = state.getCurrentNote();
        if (!note) return;

        const newStatus = note.status === 'focus' ? '' : 'focus';
        handleStatusUpdate(newStatus, 'medium', true); // true = toggle logic handled here, but we pass new status
    });

    ui.elements.btnArchive.addEventListener('click', () => {
        const note = state.getCurrentNote();
        if (!note) return;

        api.showConfirm("Archive this note?", (confirmed) => {
            if (confirmed) {
                handleStatusUpdate('archived', 'heavy');
            }
        });
    });

    ui.elements.btnReply.addEventListener('click', () => {
        api.close();
    });

    // Filters
    ui.elements.btnFilterToggle.addEventListener('click', () => ui.toggleFilterOverlay(true));
    ui.elements.btnCloseFilter.addEventListener('click', () => ui.toggleFilterOverlay(false));

    ui.elements.btnApplyFilters.addEventListener('click', () => {
        const values = ui.getFilterValues();
        state.filters.year = values.year;
        state.filters.month = values.month;

        const isFiltering = state.applyFilters();
        ui.updateFilterBadge(isFiltering);
        ui.displayNote(state.getCurrentNote());
        ui.toggleFilterOverlay(false);
    });
}

async function handleStatusUpdate(newStatus, hapticType, isToggle = false) {
    const note = state.getCurrentNote();
    if (!note) return;

    // Optimistic Update
    state.updateNoteStatus(note.id, newStatus);

    // Re-calculate stats and filters
    ui.updateStats(state.allNotes);
    const isFiltering = state.applyFilters();
    ui.updateFilterBadge(isFiltering);

    // Re-render
    ui.displayNote(state.getCurrentNote());

    // Haptic
    api.haptic(hapticType);

    // API Call
    const userId = api.getUserId();
    await api.updateStatus(note.id, newStatus, userId);
}

async function loadNotes() {
    try {
        const userId = api.getUserId();
        const data = await api.fetchNotes(userId);

        state.setNotes(data.notes || []);

        // Initial UI Setup
        ui.updateStats(state.allNotes);

        const filterOptions = state.extractFilterOptions();
        ui.renderFilterOptions(
            filterOptions,
            state.filters.tags,
            (tag) => state.toggleTagFilter(tag) // Callback for tag toggle
        );

        state.applyFilters();
        ui.displayNote(state.getCurrentNote());

    } catch (error) {
        // Fallback to demo data if needed, or just show error
        console.log("Loading demo data due to error");
        loadDemoData();
    }
}

function loadDemoData() {
    const demoNotes = [
        { id: '1', created_at: '2024-11-24T14:30:00', content: 'Active Note 1', tags: '#work', status: 'focus', message_type: 'general' },
        { id: '2', created_at: '2024-11-24T14:31:00', content: 'Active Note 2', tags: '#news', status: 'new', message_type: 'forwarded' },
        { id: '3', created_at: '2023-05-20T10:00:00', content: 'Archived Note', tags: '#old', status: 'archived', message_type: 'general' },
        { id: '4', created_at: '2024-11-20T10:00:00', content: 'Done Note', tags: '#done', status: 'done', message_type: 'general' }
    ];

    state.setNotes(demoNotes);
    ui.updateStats(state.allNotes);

    const filterOptions = state.extractFilterOptions();
    ui.renderFilterOptions(
        filterOptions,
        state.filters.tags,
        (tag) => state.toggleTagFilter(tag)
    );

    state.applyFilters();
    ui.displayNote(state.getCurrentNote());
}

// Start
init();
