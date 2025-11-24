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
            message_type: 'general'
        },
        {
            id: '20241124143100_124',
            telegram_message_id: '124',
            created_at: '2024-11-24T14:31:00',
            content: 'Форвардированное сообщение из канала',
            tags: '#новости',
            message_type: 'forwarded'
        }
    ];
    displayNote(currentIndex);
}

// Display note
function displayNote(index) {
    if (index < 0 || index >= notes.length) return;

    const note = notes[index];

    // Update date/time
    const date = new Date(note.created_at);
    const dateTimeEl = document.getElementById('dateTime');
    dateTimeEl.textContent = formatDateTime(date);

    // Update note type
    const noteTypeEl = document.getElementById('noteType');
    noteTypeEl.textContent = note.message_type;
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
}

// Format date/time
function formatDateTime(date) {
    const today = new Date();
    const isToday = date.toDateString() === today.toDateString();

    const timeStr = date.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit'
    });

    if (isToday) {
        return `Сегодня, ${timeStr}`;
    }

    const dateStr = date.toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'short'
    });

    return `${dateStr}, ${timeStr}`;
}

// Show empty state
function showEmptyState() {
    document.getElementById('dateTime').textContent = '';
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

// Action button placeholders
document.querySelectorAll('.action-buttons .btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        const action = e.target.textContent.toLowerCase();
        tg.showAlert(`Action: ${action} (coming soon)`);

        if (tg.HapticFeedback) {
            tg.HapticFeedback.impactOccurred('medium');
        }
    });
});

// Archive button placeholder
document.querySelector('.btn-archive').addEventListener('click', () => {
    tg.showAlert('Archive (coming soon)');

    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('medium');
    }
});

// Initialize
fetchNotes();
