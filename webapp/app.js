// Initialize Telegram Web App
const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

// Sample data (will be replaced with API call)
let notes = [];
let currentIndex = 0;

// Fetch notes from backend
async function fetchNotes() {
    try {
        // Try to get user_id from URL params (for browser testing)
        const urlParams = new URLSearchParams(window.location.search);
        const urlUserId = urlParams.get('user_id');

        // Use Telegram ID if available, otherwise URL param, otherwise 'demo'
        const userId = tg.initDataUnsafe?.user?.id || urlUserId || 'demo';

        const response = await fetch(`/api/notes?user_id=${userId}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        notes = data.notes || [];

        if (notes.length > 0) {
            displayNote(currentIndex);
        } else {
            showEmptyState();
        }
    } catch (error) {
        console.error('Error fetching notes:', error);
        // Fallback to demo data
        loadDemoData();
    }
}

// Load demo data for testing
function loadDemoData() {
    notes = [
        {
            id: '20241124143000_123',
            telegram_message_id: '123',
            created_at: '2024-11-24T14:30:00',
            content: 'Это тестовая заметка с тегами',
            tags: '#важно, #работа',
            message_type: 'general',
            status: 'focus'
        },
        {
            id: '20241124143100_124',
            telegram_message_id: '124',
            created_at: '2024-11-24T14:31:00',
            content: 'Форвардированное сообщение из канала',
            tags: '#новости',
            message_type: 'forwarded',
            status: 'new'
        }
    ];
    displayNote(currentIndex);
}

// Display note
function displayNote(index) {
    if (index < 0 || index >= notes.length) return;

    const note = notes[index];

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
        tagsEl.innerHTML = tagList.map(tag =>
            `<span class="tag">${tag}</span>`
        ).join('');
    } else {
        tagsEl.innerHTML = '';
    }

    // Update note text
    const noteTextEl = document.getElementById('noteText');
    noteTextEl.textContent = note.content;

    // Update Focus button state
    const focusBtn = document.querySelector('.btn-focus');
    if (note.status === 'focus') {
        focusBtn.textContent = 'Unfocus';
        focusBtn.style.fontWeight = 'bold';
    } else {
        focusBtn.textContent = 'Focus';
        focusBtn.style.fontWeight = 'normal';
    }
}

// Format date for the pill (e.g., "May 17" or "Today")
function formatDatePill(date) {
    const today = new Date();
    const isToday = date.toDateString() === today.toDateString();

    if (isToday) {
        return 'Today';
    }

    return date.toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric'
    });
}

// Show empty state
function showEmptyState() {
    document.getElementById('datePill').style.display = 'none';
    document.getElementById('noteType').textContent = '';
    document.getElementById('tags').innerHTML = '';
    document.getElementById('noteText').textContent = 'Нет заметок для отображения';
}

// Next button handler
document.getElementById('nextBtn').addEventListener('click', () => {
    currentIndex = (currentIndex + 1) % notes.length;
    displayNote(currentIndex);

    // Haptic feedback
    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('light');
    }
});

// Update note status
async function updateStatus(noteId, newStatus) {
    try {
        const userId = tg.initDataUnsafe?.user?.id || new URLSearchParams(window.location.search).get('user_id') || 'demo';

        // Optimistic update
        const noteIndex = notes.findIndex(n => n.id === noteId);
        if (noteIndex === -1) return;

        const note = notes[noteIndex];
        note.status = newStatus;

        // If status is archived or done, remove from list
        if (['archived', 'done'].includes(newStatus)) {
            notes.splice(noteIndex, 1);
            // Adjust currentIndex if needed
            if (currentIndex >= notes.length) {
                currentIndex = Math.max(0, notes.length - 1);
            }
        }

        // Re-render
        if (notes.length > 0) {
            displayNote(currentIndex);
        } else {
            showEmptyState();
        }

        // Send to API
        if (userId !== 'demo') {
            const response = await fetch(`/api/notes/${noteId}/status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    status: newStatus,
                    user_id: userId
                })
            });

            if (!response.ok) {
                throw new Error('Failed to update status');
            }
        }

    } catch (error) {
        console.error('Error updating status:', error);
        tg.showAlert('Error updating status');
    }
}

// Action buttons
document.querySelector('.btn-done').addEventListener('click', () => {
    if (notes.length === 0) return;
    const note = notes[currentIndex];
    updateStatus(note.id, 'done');
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
});

document.querySelector('.btn-flow').addEventListener('click', () => {
    if (notes.length === 0) return;
    const note = notes[currentIndex];
    updateStatus(note.id, 'flow');
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
});

document.querySelector('.btn-focus').addEventListener('click', () => {
    if (notes.length === 0) return;
    const note = notes[currentIndex];
    const newStatus = note.status === 'focus' ? '' : 'focus';
    updateStatus(note.id, newStatus);
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
});

document.querySelector('.btn-reply').addEventListener('click', () => {
    if (notes.length === 0) return;

    // Close WebApp. User is back in chat.
    // Ideally we would trigger a reply, but WebApp API limitations apply.
    tg.close();
});

// Archive button
document.querySelector('.btn-archive').addEventListener('click', () => {
    if (notes.length === 0) return;

    tg.showConfirm("Archive this note?", (confirmed) => {
        if (confirmed) {
            const note = notes[currentIndex];
            updateStatus(note.id, 'archived');
            if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('heavy');
        }
    });
});

// Initialize
fetchNotes();
