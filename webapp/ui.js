// ui.js - New minimal design UI rendering
import { state } from './state.js';

// Month names for display
const monthNames = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
};

const monthsShort = [
    { value: 1, label: 'Янв' },
    { value: 2, label: 'Фев' },
    { value: 3, label: 'Мар' },
    { value: 4, label: 'Апр' },
    { value: 5, label: 'Май' },
    { value: 6, label: 'Июн' },
    { value: 7, label: 'Июл' },
    { value: 8, label: 'Авг' },
    { value: 9, label: 'Сен' },
    { value: 10, label: 'Окт' },
    { value: 11, label: 'Ноя' },
    { value: 12, label: 'Дек' }
];

// Format date for display
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    const day = date.getDate();
    const month = date.toLocaleString('en-US', { month: 'short' });
    const year = date.getFullYear();
    return `${day} ${month} ${year}`;
}

export const ui = {
    elements: {
        header: document.getElementById('appHeader'),
        body: document.getElementById('appBody'),
        actions: document.getElementById('appActions'),
        datePickerOverlay: document.getElementById('datePickerOverlay'),
        datePickerYears: document.getElementById('datePickerYears'),
        datePickerMonths: document.getElementById('datePickerMonths'),
        btnCloseDatePicker: document.getElementById('btnCloseDatePicker'),
        btnApplyDate: document.getElementById('btnApplyDate')
    },

    // Render header based on current mode
    renderHeader() {
        const { mode, filteredNotes, currentIndex, currentTag, selectedMonth, selectedYear, relatedNotes, relatedIndex } = state;

        if (mode === 'related') {
            // Related mode (tags): show "← К записи" and related counter
            const count = relatedNotes.length;
            const counter = count > 0 ? `связь ${relatedIndex + 1}/${count}` : 'связь 0/0';

            this.elements.header.innerHTML = `
                <button class="btn-back" id="btnBack">← К записи</button>
                <span class="counter">${counter}</span>
            `;
        } else if (mode === 'reply_related') {
            // Reply related mode: show branch info and position
            const { replyChain, replyIndex, replyStats, currentBranchChildId } = state;
            const chainLength = replyChain.length;
            const counter = chainLength > 0 ? `связь ${replyIndex + 1}/${chainLength}` : 'связь 0/0';

            let branchInfo = '';
            const currentNote = state.getCurrentNote();

            if (currentNote) {
                // Case 1: current note has multiple children and we're selecting which one
                if (replyStats && replyStats.down > 1) {
                    const children = replyChain.filter(n =>
                        String(n.reply_to_message_id) === String(currentNote.telegram_message_id)
                    );
                    if (children.length > 1) {
                        let selectedIdx = 0;
                        if (currentBranchChildId) {
                            const idx = children.findIndex(c => c.id === currentBranchChildId);
                            if (idx >= 0) selectedIdx = idx;
                        }
                        branchInfo = `ветка ${selectedIdx + 1}/${children.length}`;
                    }
                }

                // Case 2: current note has siblings (we ARE on a branch)
                if (!branchInfo && currentNote.reply_to_message_id) {
                    const siblings = replyChain.filter(n =>
                        String(n.reply_to_message_id) === String(currentNote.reply_to_message_id)
                    );
                    if (siblings.length > 1) {
                        const myIdx = siblings.findIndex(s => s.id === currentNote.id);
                        if (myIdx >= 0) {
                            branchInfo = `ветка ${myIdx + 1}/${siblings.length}`;
                        }
                    }
                }
            }

            this.elements.header.innerHTML = `
                <button class="btn-back" id="btnBack">← К записи</button>
                ${branchInfo ? `<span class="header-center">${branchInfo}</span>` : ''}
                <span class="counter">${counter}</span>
            `;
        } else if (mode === 'tag' || mode === 'notag' || mode === 'date') {
            // Back mode: show back button and filter title
            const count = filteredNotes.length;
            const counter = count > 0 ? `${currentIndex + 1}/${count}` : '0/0';
            let title = '';
            if (mode === 'tag') title = currentTag;
            if (mode === 'notag') title = '⚠️ без тега';
            if (mode === 'date') title = `${monthNames[selectedMonth]} ${selectedYear}`;

            this.elements.header.innerHTML = `
                <button class="btn-back" id="btnBack">← Назад</button>
                <div class="header-right">
                    <span class="header-title">${title}</span>
                    <span class="counter">${counter}</span>
                </div>
            `;
        } else {
            // Toggle mode: show Все/Фокус toggle
            const count = filteredNotes.length;
            const counter = count > 0 ? `${currentIndex + 1}/${count}` : '0/0';

            this.elements.header.innerHTML = `
                <div class="toggle">
                    <button class="toggle-btn ${mode === 'all' ? 'active' : ''}" data-mode="all">Все</button>
                    <span class="toggle-separator">/</span>
                    <button class="toggle-btn ${mode === 'focus' ? 'active' : ''}" data-mode="focus">Фокус</button>
                </div>
                <span class="counter">${counter}</span>
            `;
        }
    },

    // Render card or empty state
    renderCard() {
        const note = state.getCurrentNote();

        if (!note) {
            this.renderEmptyState();
            return;
        }

        // Parse tags
        let tagsHtml = '';
        if (note.tags && note.tags.trim()) {
            const tagList = note.tags.split(',').map(t => t.trim()).filter(t => t);
            tagsHtml = tagList.map(tag =>
                `<button class="card-tag" data-tag="${tag}">${tag}</button>`
            ).join('');
        } else {
            tagsHtml = `<button class="card-notag">⚠️ без тега</button>`;
        }

        this.elements.body.innerHTML = `
            <div class="card">
                <div class="card-text">${this.escapeHtml(note.content)}</div>
                <div class="card-meta">
                    <div class="card-tags">${tagsHtml}</div>
                    <button class="card-date">${formatDate(note.created_at)}</button>
                </div>
            </div>
        `;
    },

    // Render loading state
    renderLoadingState(message = 'Загрузка...') {
        this.elements.body.innerHTML = `
            <div class="loading-state">
                <div class="spinner"></div>
                <div class="loading-text">${message}</div>
            </div>
        `;
    },

    // Render empty state based on mode
    renderEmptyState() {
        const { mode, currentTag, selectedMonth, selectedYear } = state;

        const states = {
            all: {
                icon: '✓',
                title: 'Всё обработано',
                subtitle: 'Новые мысли появятся когда напишешь в канал'
            },
            focus: {
                icon: '🎯',
                title: 'Нет мыслей в фокусе',
                subtitle: 'Нажми 🎯 чтобы добавить'
            },
            tag: {
                icon: '🏷️',
                title: `Нет записей с ${currentTag}`,
                subtitle: ''
            },
            notag: {
                icon: '✓',
                title: 'Все мысли размечены',
                subtitle: ''
            },
            date: {
                icon: '📅',
                title: `Нет записей за ${monthNames[selectedMonth]} ${selectedYear}`,
                subtitle: ''
            },
            related: {
                icon: '🔗',
                title: 'Нет связанных записей',
                subtitle: 'Добавь теги чтобы находить связи'
            }
        };

        const { icon, title, subtitle } = states[mode] || states.all;

        this.elements.body.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">${icon}</span>
                <h2 class="empty-title">${title}</h2>
                ${subtitle ? `<p class="empty-subtitle">${subtitle}</p>` : ''}
            </div>
        `;
    },

    // Render action buttons
    renderActions() {
        const note = state.getCurrentNote();

        if (!note) {
            this.elements.actions.innerHTML = '';
            return;
        }

        const focusClass = note.status === 'focus' ? 'active' : '';

        if (state.mode === 'related') {
            // Related mode (tags): navigation with ↑ ↓
            const { relatedNotes, relatedIndex } = state;
            const canGoUp = relatedIndex > 0;
            const canGoDown = relatedIndex < relatedNotes.length - 1;

            this.elements.actions.innerHTML = `
                <div class="actions-left">
                    <button class="action-btn focus ${focusClass}" id="btnFocus"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg></button>
                    <button class="action-btn done" id="btnDone"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></button>
                </div>
                <div class="actions-center">
                    <button class="action-btn arrow ${canGoUp ? '' : 'disabled'}" id="btnPrevRelated" ${canGoUp ? '' : 'disabled'}>↑</button>
                    <button class="action-btn arrow ${canGoDown ? '' : 'disabled'}" id="btnNextRelated" ${canGoDown ? '' : 'disabled'}>↓</button>
                </div>
                <div class="actions-right">
                    <button class="action-btn arrow" id="btnBackArrow">←</button>
                    <span class="actions-separator">|</span>
                    <button class="action-btn arrow" id="btnChannel">↗</button>
                </div>
            `;
        } else if (state.mode === 'reply_related') {
            // Reply related mode: tree navigation with ↑N ↓N ↔N
            const stats = state.replyStats || { up: 0, down: 0, branches: 0 };

            const upBtn = stats.up > 0
                ? `<button class="action-btn tree-nav" id="btnReplyUp">↑${stats.up}</button>`
                : `<button class="action-btn tree-nav disabled" disabled>↑0</button>`;

            const downBtn = stats.down > 0
                ? `<button class="action-btn tree-nav" id="btnReplyDown">↓${stats.down}</button>`
                : `<button class="action-btn tree-nav disabled" disabled>↓0</button>`;

            // Always show branch button (disabled if no branches)
            const branchBtn = stats.down > 1
                ? `<button class="action-btn tree-nav" id="btnReplyBranch">↔${stats.down}</button>`
                : `<button class="action-btn tree-nav disabled" disabled>↔0</button>`;

            this.elements.actions.innerHTML = `
                <div class="actions-left">
                    <button class="action-btn focus ${focusClass}" id="btnFocus"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg></button>
                    <button class="action-btn done" id="btnDone"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></button>
                </div>
                <div class="actions-center">
                    ${upBtn}
                    ${downBtn}
                    ${branchBtn}
                </div>
                <div class="actions-right">
                    <button class="action-btn arrow" id="btnBackArrow">←</button>
                    <span class="actions-separator">|</span>
                    <button class="action-btn arrow" id="btnChannel">↗</button>
                </div>
            `;
        } else {
            // Normal mode: show connection buttons #N ↗N
            const tagsCount = state.getRelatedCount();
            const replyCount = state.getReplyCount();
            const isTagsDisabled = tagsCount === 0;
            const isReplyDisabled = replyCount === 0;

            this.elements.actions.innerHTML = `
                <div class="actions-left">
                    <button class="action-btn focus ${focusClass}" id="btnFocus"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg></button>
                    <button class="action-btn done" id="btnDone"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></button>
                </div>
                <div class="actions-center">
                    <button class="action-btn ${isTagsDisabled ? 'disabled' : ''}" id="btnRelated" ${isTagsDisabled ? 'disabled' : ''}>#${tagsCount}</button>
                    <button class="action-btn ${isReplyDisabled ? 'disabled' : ''}" id="btnReplyRelated" ${isReplyDisabled ? 'disabled' : ''}>↗${replyCount}</button>
                </div>
                <div class="actions-right">
                    <button class="action-btn arrow" id="btnPrev">←</button>
                    <span class="actions-separator">|</span>
                    <button class="action-btn arrow" id="btnNext">→</button>
                    <span class="actions-separator">|</span>
                    <button class="action-btn arrow" id="btnChannel">↗</button>
                </div>
            `;
        }
    },

    // Show date picker
    showDatePicker() {
        const years = state.extractYears();
        const currentYear = new Date().getFullYear();
        const currentMonth = new Date().getMonth() + 1;

        // Initialize picker state
        state.pickerYear = state.pickerYear || years[0] || currentYear;
        state.pickerMonth = state.pickerMonth || currentMonth;

        // Render years
        this.elements.datePickerYears.innerHTML = years.map(year =>
            `<button class="picker-btn ${year === state.pickerYear ? 'active' : ''}" data-year="${year}">${year}</button>`
        ).join('');

        // Render months
        this.elements.datePickerMonths.innerHTML = monthsShort.map(m =>
            `<button class="picker-btn ${m.value === state.pickerMonth ? 'active' : ''}" data-month="${m.value}">${m.label}</button>`
        ).join('');

        this.elements.datePickerOverlay.classList.add('active');
    },

    // Hide date picker
    hideDatePicker() {
        this.elements.datePickerOverlay.classList.remove('active');
    },

    // Update date picker selection
    updatePickerSelection(type, value) {
        if (type === 'year') {
            state.pickerYear = value;
            // Re-render years to update active state
            const years = state.extractYears();
            this.elements.datePickerYears.innerHTML = years.map(year =>
                `<button class="picker-btn ${year === state.pickerYear ? 'active' : ''}" data-year="${year}">${year}</button>`
            ).join('');
        } else if (type === 'month') {
            state.pickerMonth = value;
            // Re-render months to update active state
            this.elements.datePickerMonths.innerHTML = monthsShort.map(m =>
                `<button class="picker-btn ${m.value === state.pickerMonth ? 'active' : ''}" data-month="${m.value}">${m.label}</button>`
            ).join('');
        }
    },

    // Render entire UI
    render() {
        this.renderHeader();
        this.renderCard();
        this.renderActions();
    },

    // Utility: escape HTML
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};
