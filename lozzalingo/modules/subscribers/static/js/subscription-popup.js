// Subscription Pop-up Manager (Framework version — config-driven)
class SubscriptionPopup {
    constructor() {
        this.overlay = null;
        this.form = null;
        this.emailInput = null;
        this.submitBtn = null;
        this.messageElement = null;
        this.closeBtn = null;
        this.skipBtn = null;
        this.feedContainer = null;

        // Default config — overridden by server response
        this.config = {
            title: 'Stay Updated',
            subtitle: 'Get the latest news and exclusive content delivered straight to your inbox.',
            button_text: 'Subscribe Now',
            skip_text: 'No thanks, maybe later',
            placeholder: 'Enter your email address',
            time_delay: 30,
            exit_intent: true,
            scroll_trigger: '#news',
            dismissal_days: 7,
            button_bg: '',
            button_color: '',
            button_hover_bg: '',
            show_feeds: true,
        };

        this.storageKey = 'subscription_popup_dismissed';
        this.subscriberKey = 'subscriber_email';

        // Feed data
        this.feeds = [];
        this.defaultFeed = '';

        // State
        this.hasShown = false;
        this.timeoutId = null;
        this.exitIntentBound = false;
        this.scrollObserver = null;

        this.init();
    }

    init() {
        // Permanently skip for known subscribers
        if (this.isSubscriber()) return;

        // Skip if recently dismissed (uses default dismissal_days initially)
        if (this.isDismissed()) return;

        // Load feeds + config then create modal
        this.loadFeeds().then(() => {
            this.createModal();
            this.attachEventListeners();
            this.startTimers();
        });
    }

    async loadFeeds() {
        try {
            const response = await fetch('/api/subscribers/feeds');
            if (!response.ok) return;
            const data = await response.json();
            this.feeds = data.feeds || [];
            this.defaultFeed = data.default || '';

            // Merge server popup config into local config
            if (data.popup) {
                Object.assign(this.config, data.popup);
            }
        } catch (err) {
            // No feeds/config — popup will work with defaults
        }
    }

    createModal() {
        let feedsHTML = '';
        if (this.config.show_feeds && this.feeds.length > 0) {
            feedsHTML = '<div class="popup-feed-options">';
            feedsHTML += '<div class="popup-feed-label">I\'m interested in:</div>';
            feedsHTML += '<div class="popup-feed-group">';

            this.feeds.forEach(feed => {
                const checked = feed.id === this.defaultFeed ? 'checked' : '';
                feedsHTML += `
                    <label class="popup-feed-option">
                        <input type="radio" name="popup_feed" value="${feed.id}" ${checked}>
                        <span class="popup-feed-radio"></span>
                        <span class="popup-feed-text">
                            <span class="popup-feed-name">${feed.label}</span>
                            ${feed.description ? `<span class="popup-feed-desc">${feed.description}</span>` : ''}
                        </span>
                    </label>
                `;
            });

            const allChecked = !this.defaultFeed ? 'checked' : '';
            feedsHTML += `
                <label class="popup-feed-option">
                    <input type="radio" name="popup_feed" value="__all__" ${allChecked}>
                    <span class="popup-feed-radio"></span>
                    <span class="popup-feed-text">
                        <span class="popup-feed-name">All updates</span>
                        <span class="popup-feed-desc">Receive everything</span>
                    </span>
                </label>
            `;
            feedsHTML += '</div></div>';
        }

        const c = this.config;
        const modalHTML = `
            <div class="subscription-popup-overlay" id="subscriptionPopup">
                <div class="subscription-popup">
                    <button class="subscription-popup-close" id="popupClose" name="subscribe_popup_close" aria-label="Close popup">&times;</button>

                    <h2 class="subscription-popup-title">${this._esc(c.title)}</h2>
                    <p class="subscription-popup-subtitle">${this._esc(c.subtitle)}</p>

                    <form class="subscription-popup-form" id="popupSubscribeForm">
                        <div class="subscription-popup-input-group">
                            <input
                                type="email"
                                id="popupEmail"
                                name="email"
                                class="subscription-popup-input"
                                placeholder="${this._esc(c.placeholder)}"
                                required
                                autocomplete="email"
                            >
                        </div>

                        ${feedsHTML}

                        <button type="submit" class="subscription-popup-submit" id="popupSubmit" name="subscribe_popup_submit">
                            <span class="popup-btn-text">${this._esc(c.button_text)}</span>
                            <span class="popup-btn-loading" style="display: none;">
                                <span class="popup-loading-spinner"></span>
                            </span>
                        </button>

                        <div class="subscription-popup-message" id="popupMessage"></div>
                    </form>

                    <button class="subscription-popup-skip" id="popupSkip" name="subscribe_popup_skip">
                        ${this._esc(c.skip_text)}
                    </button>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);

        this.overlay = document.getElementById('subscriptionPopup');
        this.form = document.getElementById('popupSubscribeForm');
        this.emailInput = document.getElementById('popupEmail');
        this.submitBtn = document.getElementById('popupSubmit');
        this.messageElement = document.getElementById('popupMessage');
        this.closeBtn = document.getElementById('popupClose');
        this.skipBtn = document.getElementById('popupSkip');

        // Apply button colors via CSS custom properties
        if (this.submitBtn) {
            if (c.button_bg) this.submitBtn.style.setProperty('--popup-btn-bg', c.button_bg);
            if (c.button_color) this.submitBtn.style.setProperty('--popup-btn-color', c.button_color);
            if (c.button_hover_bg) this.submitBtn.style.setProperty('--popup-btn-hover-bg', c.button_hover_bg);
        }
    }

    _esc(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    }

    attachEventListeners() {
        if (this.form) {
            this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        }

        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.dismiss());
        }

        if (this.skipBtn) {
            this.skipBtn.addEventListener('click', () => this.dismiss());
        }

        if (this.overlay) {
            this.overlay.addEventListener('click', (e) => {
                if (e.target === this.overlay) this.dismiss();
            });
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.overlay && this.overlay.classList.contains('active')) {
                this.dismiss();
            }
        });
    }

    startTimers() {
        const delay = (this.config.time_delay || 30) * 1000;
        this.timeoutId = setTimeout(() => this.show(), delay);

        if (this.config.exit_intent && !this.exitIntentBound) {
            document.addEventListener('mouseout', (e) => this.handleExitIntent(e));
            this.exitIntentBound = true;
        }

        this.setupScrollTrigger();
    }

    setupScrollTrigger() {
        const selector = this.config.scroll_trigger;
        if (!selector) return;

        const section = document.querySelector(selector);
        if (!section) return;

        this.scrollObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !this.hasShown && !this.isDismissed()) {
                    this.show();
                    this.scrollObserver.disconnect();
                }
            });
        }, { threshold: 0.2 });

        this.scrollObserver.observe(section);
    }

    handleExitIntent(e) {
        if (e.clientY <= 0 && !this.hasShown && !this.isDismissed()) {
            this.show();
        }
    }

    show() {
        if (this.hasShown || this.isDismissed() || this.isSubscriber()) return;

        if (this.overlay) {
            this.overlay.classList.add('active');
            this.hasShown = true;

            setTimeout(() => {
                if (this.emailInput) this.emailInput.focus();
            }, 1000);

            if (this.timeoutId) clearTimeout(this.timeoutId);
        }
    }

    hide() {
        if (this.overlay) this.overlay.classList.remove('active');
    }

    dismiss() {
        this.hide();
        this.saveDismissal();
    }

    getSelectedFeeds() {
        if (!this.config.show_feeds || !this.feeds.length) return [];

        const selected = this.overlay?.querySelector('input[name="popup_feed"]:checked');
        if (!selected) return [];

        if (selected.value === '__all__') {
            return this.feeds.map(f => f.id);
        }
        return [selected.value];
    }

    async handleSubmit(e) {
        e.preventDefault();

        const email = this.emailInput.value.trim();

        if (!this.isValidEmail(email)) {
            this.showMessage('Please enter a valid email address.', 'error');
            return;
        }

        this.setSubmitting(true);

        try {
            const body = { email: email };
            const selectedFeeds = this.getSelectedFeeds();
            if (selectedFeeds.length > 0) {
                body.feeds = selectedFeeds;
            }

            const response = await fetch('/api/subscribers', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            const data = await response.json();

            if (response.ok) {
                this.showMessage(
                    data.message || 'Successfully subscribed!',
                    'success'
                );
                this.form.reset();

                // Store subscriber email — popup will never show again
                try {
                    localStorage.setItem(this.subscriberKey, email);
                } catch (e) {}

                setTimeout(() => this.dismiss(), 3000);

            } else {
                this.showMessage(
                    data.error || 'Something went wrong. Please try again.',
                    'error'
                );
            }

        } catch (error) {
            console.error('Subscription error:', error);
            this.showMessage(
                'Connection error. Please check your internet and try again.',
                'error'
            );
        } finally {
            this.setSubmitting(false);
        }
    }

    setSubmitting(isSubmitting) {
        const btnText = this.submitBtn.querySelector('.popup-btn-text');
        const btnLoading = this.submitBtn.querySelector('.popup-btn-loading');

        if (isSubmitting) {
            this.submitBtn.disabled = true;
            btnText.style.display = 'none';
            btnLoading.style.display = 'flex';
        } else {
            this.submitBtn.disabled = false;
            btnText.style.display = 'flex';
            btnLoading.style.display = 'none';
        }
    }

    showMessage(message, type) {
        if (!this.messageElement) return;

        this.messageElement.textContent = message;
        this.messageElement.className = `subscription-popup-message ${type}`;
        this.messageElement.style.display = 'block';

        if (type === 'error') {
            setTimeout(() => {
                this.messageElement.style.display = 'none';
            }, 5000);
        }
    }

    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    isSubscriber() {
        try {
            return !!localStorage.getItem(this.subscriberKey);
        } catch (e) {
            return false;
        }
    }

    isDismissed() {
        try {
            const dismissData = localStorage.getItem(this.storageKey);
            if (!dismissData) return false;

            const data = JSON.parse(dismissData);
            const expiryMs = (this.config.dismissal_days || 7) * 24 * 60 * 60 * 1000;
            if (Date.now() - data.timestamp > expiryMs) {
                localStorage.removeItem(this.storageKey);
                return false;
            }
            return true;
        } catch (e) {
            localStorage.removeItem(this.storageKey);
            return false;
        }
    }

    saveDismissal() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify({ timestamp: Date.now() }));
        } catch (e) {}
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        new SubscriptionPopup();
    }, 1000);
});

// Export for testing or external use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SubscriptionPopup;
}
