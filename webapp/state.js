// state.js - New minimal design state management
export const state = {
    // Data
    allNotes: [],
    filteredNotes: [],

    // Navigation
    currentIndex: 0,

    // View mode: 'all' | 'focus' | 'tag' | 'notag' | 'date' | 'related'
    mode: 'all',
    previousMode: 'all',

    // Filters
    currentTag: null,
    selectedMonth: null,
    selectedYear: null,

    // Date picker temp state
    pickerMonth: null,
    pickerYear: null,

    // Related mode state (tags)
    parentNoteId: null,         // ID of the note we're viewing relations for
    relatedNotes: [],           // Array of related notes
    relatedIndex: 0,            // Current position in related notes

    // Reply related mode state
    replyChain: [],             // All notes in the reply chain
    replyIndex: 0,              // Current position in chain
    replyBranches: [],          // Available branches at current level
    replyBranchIndex: 0,        // Current branch index
    replyStats: null,           // { up, down, branches, total }

    // Set notes from API
    setNotes(notes) {
        this.allNotes = notes;
        this.applyFilters();
    },

    // Get current note
    getCurrentNote() {
        if (this.mode === 'related') {
            return this.relatedNotes[this.relatedIndex] || null;
        }
        if (this.mode === 'reply_related') {
            return this.replyChain[this.replyIndex] || null;
        }
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
    },

    // Related mode methods
    setRelatedNotes(notes, parentNoteId) {
        this.relatedNotes = notes;
        this.parentNoteId = parentNoteId;
        this.relatedIndex = 0;
    },

    enterRelatedMode() {
        const currentNote = this.getCurrentNote();
        if (!currentNote) return false;

        this.previousMode = this.mode;
        this.mode = 'related';
        this.parentNoteId = currentNote.id;
        // relatedNotes will be set by API call
        return true;
    },

    exitRelatedMode() {
        const originalNoteId = this.parentNoteId;
        this.mode = this.previousMode;
        this.relatedNotes = [];
        this.relatedIndex = 0;

        // Return to original note in filteredNotes
        if (originalNoteId) {
            this.applyFilters();
            const idx = this.filteredNotes.findIndex(n => n.id === originalNoteId);
            if (idx >= 0) {
                this.currentIndex = idx;
            }
        }
        this.parentNoteId = null;
    },

    nextRelated() {
        if (this.relatedNotes.length === 0) return;
        this.relatedIndex = (this.relatedIndex + 1) % this.relatedNotes.length;
    },

    prevRelated() {
        if (this.relatedNotes.length === 0) return;
        this.relatedIndex = (this.relatedIndex - 1 + this.relatedNotes.length) % this.relatedNotes.length;
    },

    // Get count of related notes for current note (by tags)
    getRelatedCount() {
        const currentNote = this.getCurrentNote();
        if (!currentNote || !currentNote.tags) return 0;

        const currentTags = new Set(currentNote.tags.split(',').map(t => t.trim()).filter(Boolean));
        if (currentTags.size === 0) return 0;

        // Count notes with at least one common tag
        return this.allNotes.filter(note => {
            if (note.id === currentNote.id) return false;
            if (!note.tags) return false;

            const noteTags = note.tags.split(',').map(t => t.trim()).filter(Boolean);
            return noteTags.some(tag => currentTags.has(tag));
        }).length;
    },

    // Reply related mode methods
    enterReplyRelatedMode() {
        const currentNote = this.getCurrentNote();
        if (!currentNote) return false;

        this.previousMode = this.mode;
        this.mode = 'reply_related';
        this.parentNoteId = currentNote.id;
        // replyChain will be set by API call
        return true;
    },

    setReplyChain(chain, currentIndex, stats, branches = []) {
        this.replyChain = chain;
        this.replyIndex = currentIndex;
        this.replyStats = stats;
        this.replyBranches = branches;
        this.replyBranchIndex = 0;
        this.currentBranchChildId = null;  // Reset branch tracking
    },

    exitReplyRelatedMode() {
        const originalNoteId = this.parentNoteId;
        this.mode = this.previousMode;
        this.replyChain = [];
        this.replyIndex = 0;
        this.replyStats = null;
        this.replyBranches = [];
        this.replyBranchIndex = 0;
        this.currentBranchChildId = null;

        // Return to original note in filteredNotes
        if (originalNoteId) {
            this.applyFilters();
            const idx = this.filteredNotes.findIndex(n => n.id === originalNoteId);
            if (idx >= 0) {
                this.currentIndex = idx;
            }
        }
        this.parentNoteId = null;
    },

    // Get count of reply connections for current note
    getReplyCount() {
        const currentNote = this.getCurrentNote();
        if (!currentNote) return 0;

        const msgId = currentNote.telegram_message_id;
        if (!msgId) return 0;

        // Count: parent (if exists) + children
        let count = 0;

        // Check if this note has a parent (use string comparison)
        if (currentNote.reply_to_message_id) {
            const parent = this.allNotes.find(n =>
                String(n.telegram_message_id) === String(currentNote.reply_to_message_id)
            );
            if (parent) count++;
        }

        // Count children (notes that reply to this one, use string comparison)
        const children = this.allNotes.filter(n =>
            String(n.reply_to_message_id) === String(msgId)
        );
        count += children.length;

        return count;
    }
};
