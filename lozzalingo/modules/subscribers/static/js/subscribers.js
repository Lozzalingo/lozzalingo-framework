// Subscribers functionality
class SubscribersManager {
    constructor() {
        this.form = document.getElementById('subscriberForm');
        this.emailInput = document.getElementById('email');
        this.submitBtn = this.form.querySelector('.newsletter-btn');
        this.btnText = this.form.querySelector('.btn-text');
        this.btnLoading = this.form.querySelector('.btn-loading');
        this.messageElement = document.getElementById('formMessage');
        this.subscriberCountElement = document.getElementById('subscriberCount');
        this.lastUpdatedElement = document.getElementById('lastUpdated');
        this.feedOptionsContainer = document.getElementById('feedOptions');

        this.feeds = [];
        this.defaultFeed = '';

        this.init();
    }

    init() {
        this.attachEventListeners();
        this.loadSubscriberStats();
        this.setupValidation();
        this.loadFeeds();
        // Set timestamp for bot detection
        var tsInput = this.form ? this.form.querySelector('input[name="_ts"]') : null;
        if (tsInput) tsInput.value = Math.floor(Date.now() / 1000);
    }

    async loadFeeds() {
        if (!this.feedOptionsContainer) return;

        try {
            const response = await fetch('/api/subscribers/feeds');
            if (!response.ok) return;

            const data = await response.json();
            this.feeds = data.feeds || [];
            this.defaultFeed = data.default || '';

            if (this.feeds.length > 0) {
                this.renderFeedOptions();
            }
        } catch (err) {
            // No feeds configured or endpoint unavailable — hide feed options
        }
    }

    renderFeedOptions() {
        if (!this.feedOptionsContainer || !this.feeds.length) return;

        let html = '<div class="feed-options-label">I\'m interested in:</div>';
        html += '<div class="feed-radio-group">';

        this.feeds.forEach(feed => {
            const checked = feed.id === this.defaultFeed ? 'checked' : '';
            html += `
                <label class="feed-radio-option">
                    <input type="radio" name="subscriber_feed" value="${feed.id}" ${checked}>
                    <span class="feed-radio-mark"></span>
                    <span class="feed-radio-content">
                        <span class="feed-radio-label">${feed.label}</span>
                        ${feed.description ? `<span class="feed-radio-desc">${feed.description}</span>` : ''}
                    </span>
                </label>
            `;
        });

        // "All updates" option
        const allChecked = !this.defaultFeed ? 'checked' : '';
        html += `
            <label class="feed-radio-option">
                <input type="radio" name="subscriber_feed" value="__all__" ${allChecked}>
                <span class="feed-radio-mark"></span>
                <span class="feed-radio-content">
                    <span class="feed-radio-label">All updates</span>
                    <span class="feed-radio-desc">Receive everything</span>
                </span>
            </label>
        `;

        html += '</div>';
        this.feedOptionsContainer.innerHTML = html;
    }

    getSelectedFeeds() {
        if (!this.feeds.length) return [];

        const selected = this.feedOptionsContainer?.querySelector('input[name="subscriber_feed"]:checked');
        if (!selected) return [];

        if (selected.value === '__all__') {
            return this.feeds.map(f => f.id);
        }
        return [selected.value];
    }

    attachEventListeners() {
        if (this.form) {
            this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        }

        if (this.emailInput) {
            this.emailInput.addEventListener('input', () => this.clearMessages());
            this.emailInput.addEventListener('blur', () => this.validateEmail());
        }
    }

    setupValidation() {
        if (this.emailInput) {
            this.emailInput.addEventListener('input', () => {
                const email = this.emailInput.value.trim();
                if (email && !this.isValidEmail(email)) {
                    this.emailInput.setCustomValidity('Please enter a valid email address');
                } else {
                    this.emailInput.setCustomValidity('');
                }
            });
        }
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
            // Anti-bot fields
            var hp = this.form.querySelector('input[name="website"]');
            if (hp && hp.value) body.website = hp.value;
            var ts = this.form.querySelector('input[name="_ts"]');
            if (ts) body._ts = ts.value;

            const response = await fetch('/api/subscribers', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(body)
            });

            const data = await response.json();

            if (response.ok) {
                this.showMessage(data.message || 'Successfully subscribed!', 'success');
                this.form.reset();
                this.form.classList.add('success');

                // Re-select default feed after form reset
                if (this.feeds.length > 0) {
                    this.renderFeedOptions();
                }

                // Store email in localStorage so popup knows they're subscribed
                try {
                    localStorage.setItem('subscriber_email', email);
                } catch (e) {}

                setTimeout(() => this.loadSubscriberStats(), 1000);

                setTimeout(() => {
                    this.form.classList.remove('success');
                    this.clearMessages();
                }, 5000);

            } else {
                this.showMessage(data.error || 'Something went wrong. Please try again.', 'error');
                this.form.classList.add('error');

                setTimeout(() => {
                    this.form.classList.remove('error');
                }, 3000);
            }

        } catch (error) {
            console.error('Subscription error:', error);
            this.showMessage('Connection error. Please check your internet and try again.', 'error');
            this.form.classList.add('error');

            setTimeout(() => {
                this.form.classList.remove('error');
            }, 3000);
        } finally {
            this.setSubmitting(false);
        }
    }

    async loadSubscriberStats() {
        try {
            const response = await fetch('/api/subscribers/stats');

            if (response.ok) {
                const data = await response.json();
                this.updateStats(data);
            } else {
                console.warn('Could not load subscriber stats');
                this.updateStats({ count: 0, last_updated: null });
            }
        } catch (error) {
            console.error('Error loading subscriber stats:', error);
            this.updateStats({ count: 0, last_updated: null });
        }
    }

    updateStats(data) {
        if (this.subscriberCountElement) {
            const targetCount = data.count || 0;
            this.animateNumber(this.subscriberCountElement, targetCount);
        }
    }

    animateNumber(element, target) {
        const current = parseInt(element.textContent) || 0;
        const increment = target > current ? 1 : -1;
        const step = Math.abs(target - current) / 20;

        let currentValue = current;
        const timer = setInterval(() => {
            currentValue += increment * Math.max(1, Math.floor(step));

            if ((increment > 0 && currentValue >= target) ||
                (increment < 0 && currentValue <= target)) {
                currentValue = target;
                clearInterval(timer);
            }

            element.textContent = currentValue.toLocaleString();
        }, 50);
    }

    setSubmitting(isSubmitting) {
        if (isSubmitting) {
            this.submitBtn.disabled = true;
            this.btnText.style.display = 'none';
            this.btnLoading.style.display = 'flex';
            this.form.classList.add('submitting');
        } else {
            this.submitBtn.disabled = false;
            this.btnText.style.display = 'flex';
            this.btnLoading.style.display = 'none';
            this.form.classList.remove('submitting');
        }
    }

    showMessage(message, type) {
        if (!this.messageElement) return;

        this.messageElement.textContent = message;
        this.messageElement.className = `form-message ${type}`;
        this.messageElement.style.display = 'block';

        if (type === 'success') {
            setTimeout(() => {
                this.clearMessages();
            }, 5000);
        }
    }

    clearMessages() {
        if (this.messageElement) {
            this.messageElement.style.display = 'none';
            this.messageElement.className = 'form-message';
        }
    }

    validateEmail() {
        const email = this.emailInput.value.trim();

        if (email && !this.isValidEmail(email)) {
            this.showMessage('Please enter a valid email address.', 'error');
            return false;
        }

        this.clearMessages();
        return true;
    }

    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new SubscribersManager();
});

// Export for testing or external use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SubscribersManager;
}
