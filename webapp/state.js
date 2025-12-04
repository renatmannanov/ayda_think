// state.js - New minimal design state management
export const state = {
    // Data
    allNotes: [],
    filteredNotes: [],

    // Navigation
    currentIndex: 0,

    // View mode: 'all' | 'focus' | 'tag' | 'notag' | 'date'
    mode: 'all',
    previousMode: 'all',

    // Filters
    currentTag: null,
    selectedMonth: null,
    selectedYear: null,

    // Date picker temp state
    pickerMonth: null,
    pickerYear: null,

    // Set notes from API
    setNotes(notes) {
        this.allNotes = notes;
        this.applyFilters();
    },

    // Get current note
    getCurrentNote() {
        return this.filteredNotes[this.currentIndex] || null;
    },

    // Update note status locally
    updateNoteStatus(noteId, newStatus) {
        const note = this.allNotes.find(n => n.id === noteId);
        if (note) {
            note.status = newStatus;
        }
    },

    // Mode switching
    setMode(newMode) {
        this.previousMode = this.mode;
        this.mode = newMode;
        this.currentIndex = 0;
        this.applyFilters();
    },

    // Go back to previous mode
    goBack() {
        this.mode = this.previousMode;
        this.currentTag = null;
        this.selectedMonth = null;
        this.selectedYear = null;
        this.currentIndex = 0;
        this.applyFilters();
    },

    // Switch to tag mode
    filterByTag(tag) {
        this.previousMode = this.mode;
        this.currentTag = tag;
        this.mode = 'tag';
        this.currentIndex = 0;
        this.applyFilters();
    },

    // Switch to notag mode
    filterByNoTag() {
        this.previousMode = this.mode;
        this.mode = 'notag';
        this.currentIndex = 0;
        this.applyFilters();
    },

    // Switch to date mode
    filterByDate(month, year) {
        this.previousMode = this.mode;
        this.selectedMonth = month;
        this.selectedYear = year;
        this.mode = 'date';
        this.currentIndex = 0;
        this.applyFilters();
    },

    // Apply filters based on current mode
    applyFilters() {
        switch (this.mode) {
            case 'all':
                // Show notes with status 'new', 'focus' or empty (not done/archived)
                this.filteredNotes = this.allNotes.filter(n =>
                    !n.status || n.status === 'new' || n.status === '' || n.status === 'focus'
                );
                break;

            case 'focus':
                // Show notes with focus status
                this.filteredNotes = this.allNotes.filter(n => n.status === 'focus');
                break;

            case 'tag':
                // Show all notes with specific tag (any status)
                this.filteredNotes = this.allNotes.filter(n => {
                    if (!n.tags) return false;
                    const noteTags = n.tags.split(',').map(t => t.trim());
                    return noteTags.includes(this.currentTag);
                });
                break;

            case 'notag':
                // Show all notes without tags (any status)
                this.filteredNotes = this.allNotes.filter(n =>
                    !n.tags || n.tags.trim() === ''
                );
                break;

            case 'date':
                // Show all notes for specific month/year (any status)
                this.filteredNotes = this.allNotes.filter(n => {
                    if (!n.created_at) return false;
                    const date = new Date(n.created_at);
                    return date.getMonth() + 1 === this.selectedMonth &&
                        date.getFullYear() === this.selectedYear;
                });
                break;

            default:
                this.filteredNotes = [];
        }

        // Sort: newest first
        this.filteredNotes.sort((a, b) =>
            new Date(b.created_at) - new Date(a.created_at)
        );
    },

    // Navigation
    nextNote() {
        if (this.filteredNotes.length === 0) return;
        this.currentIndex = (this.currentIndex + 1) % this.filteredNotes.length;
    },

    // Toggle focus on current note
    toggleFocus() {
        const note = this.getCurrentNote();
        if (!note) return null;

        const newStatus = note.status === 'focus' ? 'new' : 'focus';
        this.updateNoteStatus(note.id, newStatus);
        return newStatus;
    },

    // Mark current note as done
    markDone() {
        const note = this.getCurrentNote();
        if (!note) return null;

        this.updateNoteStatus(note.id, 'done');
        this.applyFilters();

        // Adjust index if needed
        if (this.currentIndex >= this.filteredNotes.length) {
            this.currentIndex = Math.max(0, this.filteredNotes.length - 1);
        }

        return 'done';
    },

    // Extract available years from data
    extractYears() {
        const years = new Set();
        this.allNotes.forEach(note => {
            if (note.created_at) {
                const year = new Date(note.created_at).getFullYear();
                years.add(year);
            }
        });
        return Array.from(years).sort((a, b) => b - a);
    },

    // Extract all unique tags from data
    extractTags() {
        const tags = new Set();
        this.allNotes.forEach(note => {
            if (note.tags) {
                note.tags.split(',').forEach(tag => {
                    const trimmed = tag.trim();
                    if (trimmed) tags.add(trimmed);
                });
            }
        });
        return Array.from(tags).sort();
    }
};
