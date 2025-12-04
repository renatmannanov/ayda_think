// api.js
export const api = {
    // Initialize Telegram Web App
    tg: window.Telegram.WebApp,

    init() {
        this.tg.expand();
        this.tg.ready();
    },

    getUserId() {
        const urlParams = new URLSearchParams(window.location.search);
        const urlUserId = urlParams.get('user_id');
        return this.tg.initDataUnsafe?.user?.id || urlUserId || 'demo';
    },

    async fetchNotes(userId) {
        try {
            const response = await fetch(`/api/notes?user_id=${userId}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching notes:', error);
            throw error;
        }
    },

    async updateStatus(noteId, newStatus, userId) {
        if (userId === 'demo') return;
        
        try {
            await fetch(`/api/notes/${noteId}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus, user_id: userId })
            });
        } catch (error) {
            console.error('Error updating status:', error);
            this.tg.showAlert('Error updating status');
            throw error;
        }
    },
    
    showConfirm(message, callback) {
        this.tg.showConfirm(message, callback);
    },
    
    showAlert(message) {
        this.tg.showAlert(message);
    },
    
    haptic(type) {
        if (this.tg.HapticFeedback) {
            this.tg.HapticFeedback.impactOccurred(type);
        }
    },
    
    close() {
        this.tg.close();
    }
};
