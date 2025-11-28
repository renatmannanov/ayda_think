// Initialize Telegram Web App
const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

// State
let allNotes = []; // Full list from API (includes archived/done)
let activeNotes = []; // Notes eligible for display (New/Flow/Focus)
let filteredNotes = []; // Currently displayed list (after filters)
let currentIndex = 0;

// Filter State
let activeFilters = {
    year: '',
    month: '',
    tags: [] // Array of selected tags
};

// Fetch notes from backend
async function fetchNotes() {
    try {
        const urlParams = new URLSearchParams(window.location.search);
        const urlUserId = urlParams.get('user_id');
        const userId = tg.initDataUnsafe?.user?.id || urlUserId || 'demo';

        const response = await fetch(`/api/notes?user_id=${userId}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        allNotes = data.notes || [];

        updateStats();
        extractFilterOptions();
        applyFilters();

    } catch (error) {
        console.error('Error fetching notes:', error);
        // Show error to user for debugging
        alert(`Ошибка загрузки: ${error.message}\nUser ID: ${tg.initDataUnsafe?.user?.id || 'unknown'}`);
        loadDemoData();
    }
}

// Load demo data
function loadDemoData() {
    allNotes = [
        { id: '1', created_at: '2024-11-24T14:30:00', content: 'Active Note 1', tags: '#work', status: 'focus', message_type: 'general' },
        { id: '2', created_at: '2024-11-24T14:31:00', content: 'Active Note 2', tags: '#news', status: 'new', message_type: 'forwarded' },
        { id: '3', created_at: '2023-05-20T10:00:00', content: 'Archived Note', tags: '#old', status: 'archived', message_type: 'general' },
        { id: '4', created_at: '2024-11-20T10:00:00', content: 'Done Note', tags: '#done', status: 'done', message_type: 'general' }
    ];
    updateStats();
    extractFilterOptions();
    applyFilters();
}

// Update Stats Bar
function updateStats() {
    const total = allNotes.length;
    const focus = allNotes.filter(n => n.status === 'focus').length;
    const done = allNotes.filter(n => n.status === 'done').length;
    const archived = allNotes.filter(n => n.status === 'archived').length;

    document.getElementById('statTotal').textContent = total;
    document.getElementById('statFocus').textContent = focus;
    document.getElementById('statDone').textContent = done;
    document.getElementById('statArchive').textContent = archived;
}

// Extract unique years and tags
function extractFilterOptions() {
    const years = new Set();
    const tags = new Set();

    // Extract from ALL notes to give full filter options? 
    // Or only from Active notes? Usually better to show options relevant to what CAN be seen.
    // Let's use Active Notes for filter options to avoid filtering for something that is archived.
    // Wait, user might want to find archived notes later? 
    // Current requirement: "Archive/Done logic (hide from view)". 
    // So we only filter Active notes.

    const notesToScan = allNotes.filter(n => !['archived', 'done'].includes(n.status));

    notesToScan.forEach(note => {
        if (note.created_at) {
            const date = new Date(note.created_at);
            years.add(date.getFullYear());
        }
        if (note.tags) {
            note.tags.split(',').forEach(tag => {
                const trimmed = tag.trim();
                if (trimmed) tags.add(trimmed);
            });
        }
    });

    // Populate Year Dropdown
    const yearSelect = document.getElementById('filterYear');
    while (yearSelect.options.length > 1) yearSelect.remove(1);

    Array.from(years).sort((a, b) => b - a).forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        yearSelect.appendChild(option);
    });

    // Populate Tags List
    const tagsList = document.getElementById('filterTagsList');
    tagsList.innerHTML = '';

    const noTagsEl = document.createElement('div');
    noTagsEl.className = 'filter-tag';
    noTagsEl.textContent = 'No Tags';
    noTagsEl.dataset.tag = '__no_tags__';
    noTagsEl.onclick = () => toggleTagFilter('__no_tags__', noTagsEl);
    tagsList.appendChild(noTagsEl);

    Array.from(tags).sort().forEach(tag => {
        const tagEl = document.createElement('div');
        tagEl.className = 'filter-tag';
        tagEl.textContent = tag;
        tagEl.dataset.tag = tag;
        tagEl.onclick = () => toggleTagFilter(tag, tagEl);
        tagsList.appendChild(tagEl);
    });
}

// Toggle tag selection
function toggleTagFilter(tag, element) {
    const index = activeFilters.tags.indexOf(tag);
    if (index === -1) {
        activeFilters.tags.push(tag);
        element.classList.add('selected');
    } else {
        activeFilters.tags.splice(index, 1);
        element.classList.remove('selected');
    }
}

// Apply filters
function applyFilters() {
    // 1. Filter out Archived/Done first (Base Set)
    activeNotes = allNotes.filter(n => !['archived', 'done'].includes(n.status));

    const hasDateFilter = activeFilters.year !== '' || activeFilters.month !== '';
    const hasTagFilter = activeFilters.tags.length > 0;
    const isFiltering = hasDateFilter || hasTagFilter;

    // 2. Apply User Filters
    filteredNotes = activeNotes.filter(note => {
        // Date
        if (activeFilters.year) {
            const date = new Date(note.created_at);
            if (date.getFullYear().toString() !== activeFilters.year) return false;
        }
        if (activeFilters.month) {
            const date = new Date(note.created_at);
            if (date.getMonth().toString() !== activeFilters.month) return false;
        }

        // Tags
        if (hasTagFilter) {
            const noteTags = note.tags ? note.tags.split(',').map(t => t.trim()) : [];
            const hasNoTags = noteTags.length === 0;
            const matches = activeFilters.tags.some(selectedTag => {
                if (selectedTag === '__no_tags__') return hasNoTags;
                return noteTags.includes(selectedTag);
            });
            if (!matches) return false;
        }

        return true;
    });

    // 3. Sort
    if (isFiltering) {
        // Chronological (Oldest -> Newest)
        filteredNotes.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    } else {
        // Default: Focus first, then Newest -> Oldest
        filteredNotes.sort((a, b) => {
            if (a.status === 'focus' && b.status !== 'focus') return -1;
            if (a.status !== 'focus' && b.status === 'focus') return 1;
            return new Date(b.created_at) - new Date(a.created_at);
        });
    }

    // Reset index
    currentIndex = 0;
    if (filteredNotes.length > 0) {
        displayNote(currentIndex);
    } else {
        showEmptyState();
    }

    // Update filter badge
    const badge = document.getElementById('filterBadge');
    if (isFiltering) {
        badge.classList.add('active');
    } else {
        badge.classList.remove('active');
    }
}

// Display note
function displayNote(index) {
    if (index < 0 || index >= filteredNotes.length) return;

    const note = filteredNotes[index];

    // Update date pill
    const date = new Date(note.created_at);
    const datePillEl = document.getElementById('datePill');
    datePillEl.textContent = formatDatePill(date);

    // Update note type
    const noteTypeEl = document.getElementById('noteType');
    noteTypeEl.textContent = note.message_type || 'General';
    noteTypeEl.className = `note-type ${note.message_type}`;

    // Update tags
    const tagsEl = document.getElementById('tags');
    if (note.tags) {
        const tagList = note.tags.split(',').map(t => t.trim()).filter(t => t);
        tagsEl.innerHTML = tagList.map(tag => `<span class="tag">${tag}</span>`).join('');
    } else {
        tagsEl.innerHTML = '';
    }

    // Update note text
    const noteTextEl = document.getElementById('noteText');
    noteTextEl.textContent = note.content;

    // Update Focus button
    const focusBtn = document.querySelector('.btn-focus');
    if (note.status === 'focus') {
        focusBtn.textContent = 'Unfocus';
        focusBtn.style.fontWeight = 'bold';
    } else {
        focusBtn.textContent = 'Focus';
        focusBtn.style.fontWeight = 'normal';
    }
}

function formatDatePill(date) {
    const today = new Date();
    const isToday = date.toDateString() === today.toDateString();
    if (isToday) return 'Today';
    return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
}

function showEmptyState() {
    document.getElementById('datePill').style.display = 'none';
    document.getElementById('noteType').textContent = '';
    document.getElementById('tags').innerHTML = '';
    document.getElementById('noteText').textContent = 'Нет заметок для отображения';
}

// Next button
document.getElementById('nextBtn').addEventListener('click', () => {
    if (filteredNotes.length === 0) return;
    currentIndex = (currentIndex + 1) % filteredNotes.length;
    displayNote(currentIndex);
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
});

// Update Status
async function updateStatus(noteId, newStatus) {
    try {
        const userId = tg.initDataUnsafe?.user?.id || new URLSearchParams(window.location.search).get('user_id') || 'demo';

        const noteIndex = allNotes.findIndex(n => n.id === noteId);
        if (noteIndex === -1) return;

        const note = allNotes[noteIndex];
        note.status = newStatus;

        updateStats();
        applyFilters(); // Re-filter and re-render

        if (userId !== 'demo') {
            await fetch(`/api/notes/${noteId}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus, user_id: userId })
            });
        }
    } catch (error) {
        console.error('Error updating status:', error);
        tg.showAlert('Error updating status');
    }
}

// Action Buttons
document.querySelector('.btn-done').addEventListener('click', () => {
    if (filteredNotes.length === 0) return;
    updateStatus(filteredNotes[currentIndex].id, 'done');
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
});

document.querySelector('.btn-flow').addEventListener('click', () => {
    if (filteredNotes.length === 0) return;
    updateStatus(filteredNotes[currentIndex].id, 'flow');
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
});

document.querySelector('.btn-focus').addEventListener('click', () => {
    if (filteredNotes.length === 0) return;
    const note = filteredNotes[currentIndex];
    const newStatus = note.status === 'focus' ? '' : 'focus';
    updateStatus(note.id, newStatus);
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
});

document.querySelector('.btn-reply').addEventListener('click', () => {
    tg.close();
});

document.querySelector('.btn-archive').addEventListener('click', () => {
    if (filteredNotes.length === 0) return;
    tg.showConfirm("Archive this note?", (confirmed) => {
        if (confirmed) {
            updateStatus(filteredNotes[currentIndex].id, 'archived');
            if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('heavy');
        }
    });
});

// Filter Overlay Handlers
const overlay = document.getElementById('filterOverlay');
const btnFilterToggle = document.getElementById('btnFilterToggle');
const btnCloseFilter = document.getElementById('btnCloseFilter');
const btnApplyFilters = document.getElementById('btnApplyFilters');

btnFilterToggle.addEventListener('click', () => {
    overlay.style.display = 'flex';
});

btnCloseFilter.addEventListener('click', () => {
    overlay.style.display = 'none';
});

btnApplyFilters.addEventListener('click', () => {
    activeFilters.year = document.getElementById('filterYear').value;
    activeFilters.month = document.getElementById('filterMonth').value;
    applyFilters();
    overlay.style.display = 'none';
});

// Initialize
fetchNotes();
