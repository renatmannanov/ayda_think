// state.js
export const state = {
    allNotes: [],
    activeNotes: [],
    filteredNotes: [],
    currentIndex: 0,

    filters: {
        year: '',
        month: '',
        tags: []
    },

    setNotes(notes) {
        this.allNotes = notes;
    },

    getNote(index) {
        return this.filteredNotes[index];
    },

    getCurrentNote() {
        return this.filteredNotes[this.currentIndex];
    },

    updateNoteStatus(noteId, newStatus) {
        const note = this.allNotes.find(n => n.id === noteId);
        if (note) {
            note.status = newStatus;
        }
    },

    applyFilters() {
        // 1. Filter out Archived/Done first (Base Set)
        this.activeNotes = this.allNotes.filter(n => !['archived', 'done'].includes(n.status));

        const hasDateFilter = this.filters.year !== '' || this.filters.month !== '';
        const hasTagFilter = this.filters.tags.length > 0;
        const isFiltering = hasDateFilter || hasTagFilter;

        // 2. Apply User Filters
        this.filteredNotes = this.activeNotes.filter(note => {
            // Date
            if (this.filters.year) {
                const date = new Date(note.created_at);
                if (date.getFullYear().toString() !== this.filters.year) return false;
            }
            if (this.filters.month) {
                const date = new Date(note.created_at);
                if (date.getMonth().toString() !== this.filters.month) return false;
            }

            // Tags
            if (hasTagFilter) {
                const noteTags = note.tags ? note.tags.split(',').map(t => t.trim()) : [];
                const hasNoTags = noteTags.length === 0;
                const matches = this.filters.tags.some(selectedTag => {
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
            this.filteredNotes.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
        } else {
            // Default: Focus first, then Newest -> Oldest
            this.filteredNotes.sort((a, b) => {
                if (a.status === 'focus' && b.status !== 'focus') return -1;
                if (a.status !== 'focus' && b.status === 'focus') return 1;
                return new Date(b.created_at) - new Date(a.created_at);
            });
        }

        // Reset index
        this.currentIndex = 0;

        return isFiltering;
    },

    nextNote() {
        if (this.filteredNotes.length === 0) return;
        this.currentIndex = (this.currentIndex + 1) % this.filteredNotes.length;
    },

    toggleTagFilter(tag) {
        const index = this.filters.tags.indexOf(tag);
        if (index === -1) {
            this.filters.tags.push(tag);
            return true; // added
        } else {
            this.filters.tags.splice(index, 1);
            return false; // removed
        }
    },

    extractFilterOptions() {
        const years = new Set();
        const tags = new Set();

        const notesToScan = this.allNotes.filter(n => !['archived', 'done'].includes(n.status));

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

        return {
            years: Array.from(years).sort((a, b) => b - a),
            tags: Array.from(tags).sort()
        };
    }
};
