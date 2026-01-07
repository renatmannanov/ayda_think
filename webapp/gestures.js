// gestures.js - Touch gesture handling for mobile

export const gestures = {
    config: {
        swipeThreshold: 50,      // Minimum swipe distance (px)
        swipeTimeout: 300,       // Maximum swipe duration (ms)
        doubleTapTimeout: 300,   // Maximum interval for double tap (ms)
        highlightDuration: 200   // Button highlight duration (ms)
    },

    state: {
        startX: 0,
        startY: 0,
        startTime: 0,
        lastTap: 0,
        element: null,
        callbacks: null
    },

    // Initialize gesture handling on element
    init(element, callbacks) {
        this.state.element = element;
        this.state.callbacks = callbacks;

        // Bind handlers
        this._onTouchStart = this.handleTouchStart.bind(this);
        this._onTouchEnd = this.handleTouchEnd.bind(this);

        element.addEventListener('touchstart', this._onTouchStart, { passive: true });
        element.addEventListener('touchend', this._onTouchEnd, { passive: true });
    },

    handleTouchStart(e) {
        const touch = e.touches[0];
        this.state.startX = touch.clientX;
        this.state.startY = touch.clientY;
        this.state.startTime = Date.now();
    },

    handleTouchEnd(e) {
        const touch = e.changedTouches[0];
        const deltaX = touch.clientX - this.state.startX;
        const deltaY = touch.clientY - this.state.startY;
        const deltaTime = Date.now() - this.state.startTime;

        const absX = Math.abs(deltaX);
        const absY = Math.abs(deltaY);

        // Check for swipe (horizontal, fast enough, significant distance)
        if (deltaTime < this.config.swipeTimeout && absX > this.config.swipeThreshold && absX > absY) {
            if (deltaX < 0) {
                // Swipe left → Next
                this.state.callbacks?.onSwipeLeft?.();
            } else {
                // Swipe right → Prev
                this.state.callbacks?.onSwipeRight?.();
            }
            return;
        }

        // Check for double tap (minimal movement)
        if (absX < 10 && absY < 10) {
            const now = Date.now();
            if (now - this.state.lastTap < this.config.doubleTapTimeout) {
                // Double tap detected
                this.state.callbacks?.onDoubleTap?.();
                this.state.lastTap = 0; // Reset to prevent triple-tap
            } else {
                this.state.lastTap = now;
            }
        }
    },

    // Highlight button with animation
    highlightButton(selector) {
        const btn = document.querySelector(selector);
        if (!btn) return;

        btn.classList.add('gesture-highlight');
        setTimeout(() => {
            btn.classList.remove('gesture-highlight');
        }, this.config.highlightDuration);
    },

    // Cleanup event listeners
    destroy() {
        if (this.state.element) {
            this.state.element.removeEventListener('touchstart', this._onTouchStart);
            this.state.element.removeEventListener('touchend', this._onTouchEnd);
        }
    }
};
