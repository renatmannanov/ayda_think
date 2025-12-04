// ui.js
export const ui = {
    elements: {
        statTotal: document.getElementById('statTotal'),
        statFocus: document.getElementById('statFocus'),
        statDone: document.getElementById('statDone'),
        statArchive: document.getElementById('statArchive'),
        filterBadge: document.getElementById('filterBadge'),
        filterOverlay: document.getElementById('filterOverlay'),
        filterYear: document.getElementById('filterYear'),
        filterMonth: document.getElementById('filterMonth'),
        filterTagsList: document.getElementById('filterTagsList'),
        datePill: document.getElementById('datePill'),
        noteType: document.getElementById('noteType'),
        tags: document.getElementById('tags'),
        noteText: document.getElementById('noteText'),
        focusBtn: document.querySelector('.btn-focus'),
        nextBtn: document.getElementById('nextBtn'),
        btnFilterToggle: document.getElementById('btnFilterToggle'),
        btnCloseFilter: document.getElementById('btnCloseFilter'),
        btnApplyFilters: document.getElementById('btnApplyFilters'),
        btnDone: document.querySelector('.btn-done'),
        btnFlow: document.querySelector('.btn-flow'),
        btnReply: document.querySelector('.btn-reply'),
        btnArchive: document.querySelector('.btn-archive')
    },

    updateStats(notes) {
        const total = notes.length;
        const focus = notes.filter(n => n.status === 'focus').length;
        const done = notes.filter(n => n.status === 'done').length;
        const archived = notes.filter(n => n.status === 'archived').length;

        this.elements.statTotal.textContent = total;
        this.elements.statFocus.textContent = focus;
        this.elements.statDone.textContent = done;
        this.elements.statArchive.textContent = archived;
    },

    renderFilterOptions(options, activeTags, onTagToggle) {
        // Populate Year Dropdown
        const yearSelect = this.elements.filterYear;
        while (yearSelect.options.length > 1) yearSelect.remove(1);

        options.years.forEach(year => {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = year;
            yearSelect.appendChild(option);
        });

        // Populate Tags List
        const tagsList = this.elements.filterTagsList;
        tagsList.innerHTML = '';

        const createTagEl = (text, value) => {
            const tagEl = document.createElement('div');
            tagEl.className = 'filter-tag';
            if (activeTags.includes(value)) tagEl.classList.add('selected');
            tagEl.textContent = text;
            tagEl.dataset.tag = value;
            tagEl.onclick = () => {
                const isSelected = onTagToggle(value);
                if (isSelected) tagEl.classList.add('selected');
                else tagEl.classList.remove('selected');
            };
            return tagEl;
        };

        tagsList.appendChild(createTagEl('No Tags', '__no_tags__'));
        options.tags.forEach(tag => tagsList.appendChild(createTagEl(tag, tag)));
    },

    updateFilterBadge(isActive) {
        if (isActive) {
            this.elements.filterBadge.classList.add('active');
        } else {
            this.elements.filterBadge.classList.remove('active');
        }
    },

    displayNote(note) {
        if (!note) {
            this.showEmptyState();
            return;
        }

        // Update date pill
        const date = new Date(note.created_at);
        this.elements.datePill.style.display = 'block';
        this.elements.datePill.textContent = this.formatDatePill(date);

        // Update note type
        this.elements.noteType.textContent = note.message_type || 'General';
        this.elements.noteType.className = `note-type ${note.message_type}`;

        // Update tags
        if (note.tags) {
            const tagList = note.tags.split(',').map(t => t.trim()).filter(t => t);
            this.elements.tags.innerHTML = tagList.map(tag => `<span class="tag">${tag}</span>`).join('');
        } else {
            this.elements.tags.innerHTML = '';
        }

        // Update note text
        this.elements.noteText.textContent = note.content;

        // Update Focus button
        if (note.status === 'focus') {
            this.elements.focusBtn.textContent = 'Unfocus';
            this.elements.focusBtn.style.fontWeight = 'bold';
        } else {
            this.elements.focusBtn.textContent = 'Focus';
            this.elements.focusBtn.style.fontWeight = 'normal';
        }
    },

    showEmptyState() {
        this.elements.datePill.style.display = 'none';
        this.elements.noteType.textContent = '';
        this.elements.tags.innerHTML = '';
        this.elements.noteText.textContent = 'Нет заметок для отображения';
    },

    formatDatePill(date) {
        const today = new Date();
        const isToday = date.toDateString() === today.toDateString();
        if (isToday) return 'Today';
        return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
    },

    toggleFilterOverlay(show) {
        this.elements.filterOverlay.style.display = show ? 'flex' : 'none';
    },

    getFilterValues() {
        return {
            year: this.elements.filterYear.value,
            month: this.elements.filterMonth.value
        };
    }
};
