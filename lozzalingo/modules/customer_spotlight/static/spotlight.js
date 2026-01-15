// Customer Spotlight Gallery - Infinite Scrolling Implementation
class CustomerSpotlightGallery {
    constructor() {
        this.allCustomers = [];
        this.currentIndex = 0;
        this.isLoading = false;
        this.visibleCustomers = [];
        this.scrollSpeed = 30; // pixels per second
        this.customerWidth = 200;
        this.customerGap = 20;
        this.containerHeight = 400;
        this.maxVisibleCustomers = 15;
        this.animationFrame = null;
        this.lastTimestamp = 0;
        this.scrollOffset = 0;

        this.init();
    }

    init() {
        this.setupElements();
        this.setupEventListeners();
        this.loadInitialCustomers();
    }

    setupElements() {
        this.container = document.getElementById('customer-container');
        this.scrollContainer = document.querySelector('.customer-gallery-scroll');
        this.loadingElement = document.getElementById('loading-customer');
    }

    setupEventListeners() {
        // Pause/resume scrolling on hover
        if (this.scrollContainer) {
            this.scrollContainer.addEventListener('mouseenter', () => this.pauseScrolling());
            this.scrollContainer.addEventListener('mouseleave', () => this.resumeScrolling());
        }

        // Handle window resize
        window.addEventListener('resize', () => {
            this.updateResponsiveDimensions();
        });
    }

    updateResponsiveDimensions() {
        // Update customer dimensions based on screen size
        if (window.innerWidth <= 480) {
            this.customerWidth = 140;
        } else if (window.innerWidth <= 768) {
            this.customerWidth = 160;
        } else {
            this.customerWidth = 200;
        }
    }

    async loadInitialCustomers() {
        if (this.isLoading) return;

        this.isLoading = true;
        this.showLoading();

        try {
            const response = await fetch('/api/customer-spotlight');
            const data = await response.json();

            if (data.success && data.spotlights && data.spotlights.length > 0) {
                this.allCustomers = data.spotlights;

                // Preload all images first
                await this.preloadAllImages();

                this.initializeInfiniteScroll();
                this.hideLoading();

                console.log(`Loaded ${this.allCustomers.length} customer spotlight images`);
            } else {
                console.log('No customers to display');
                this.hideLoading();
                // Hide the entire section if no spotlights
                const section = document.querySelector('.customer-spotlight');
                if (section) {
                    section.style.display = 'none';
                }
            }
        } catch (error) {
            console.error('Error loading customers:', error);
            this.showError('Connection error');
        } finally {
            this.isLoading = false;
        }
    }

    async preloadAllImages() {
        return new Promise((resolve) => {
            let loadedCount = 0;
            const totalImages = this.allCustomers.length;

            if (totalImages === 0) {
                resolve();
                return;
            }

            console.log(`Preloading ${totalImages} customer images...`);

            const checkComplete = () => {
                loadedCount++;

                if (loadedCount === totalImages) {
                    console.log('All customer images preloaded!');
                    setTimeout(resolve, 100);
                }
            };

            // Preload all images
            this.allCustomers.forEach((customer, index) => {
                const img = new Image();

                img.onload = () => {
                    customer._preloadedImage = img;
                    checkComplete();
                };

                img.onerror = (e) => {
                    console.error(`Failed to load: @${customer.instagram_handle}`, e);
                    customer._preloadedImage = null;
                    checkComplete();
                };

                img.crossOrigin = 'anonymous';
                img.loading = 'eager';
                img.decoding = 'sync';
                img.src = customer.image_url;
            });

            // Timeout
            setTimeout(() => {
                if (loadedCount < totalImages) {
                    console.warn(`Timeout: Only ${loadedCount}/${totalImages} images loaded`);
                    resolve();
                }
            }, 10000);
        });
    }

    initializeInfiniteScroll() {
        if (!this.container || this.allCustomers.length === 0) return;

        // Update responsive dimensions
        this.updateResponsiveDimensions();

        // Clear any existing content
        this.container.innerHTML = '';

        // Reset state
        this.visibleCustomers = [];
        this.currentIndex = 0;
        this.scrollOffset = 0;

        // Create initial customers to fill the visible area
        this.populateInitialCustomers();

        // Start the scrolling animation
        this.startScrolling();
    }

    populateInitialCustomers() {
        // Calculate how many customers we need to fill the screen plus buffer
        const customersNeeded = Math.min(this.maxVisibleCustomers, this.allCustomers.length);

        for (let i = 0; i < customersNeeded; i++) {
            this.addCustomerToEnd();
        }
    }

    addCustomerToEnd() {
        if (this.allCustomers.length === 0) return null;

        // Get next customer (cycle through all customers)
        const customer = this.allCustomers[this.currentIndex % this.allCustomers.length];
        this.currentIndex++;

        // Create customer element
        const customerElement = this.createCustomerElement(customer, this.visibleCustomers.length);

        // Add to visible customers array
        this.visibleCustomers.push({
            element: customerElement,
            customer: customer,
            position: this.visibleCustomers.length * (this.customerWidth + this.customerGap)
        });

        // Add to container
        this.container.appendChild(customerElement);

        return customerElement;
    }

    createCustomerElement(customer, index) {
        const customerDiv = document.createElement('div');
        customerDiv.className = 'customer-item';
        customerDiv.dataset.index = index;
        customerDiv.dataset.handle = customer.instagram_handle;

        // Position the customer
        customerDiv.style.position = 'absolute';
        customerDiv.style.left = `${index * (this.customerWidth + this.customerGap)}px`;
        customerDiv.style.top = '50%';
        customerDiv.style.transform = 'translateY(-50%)';
        customerDiv.style.width = `${this.customerWidth}px`;

        // Analytics tracking for button click
        customerDiv.addEventListener('click', () => {
            // Track the Instagram click for analytics
            if (window.analyticsClient) {
                window.analyticsClient.logInteraction('customer_spotlight_click', {
                    instagram_handle: customer.instagram_handle,
                    customer_id: customer.id,
                    interaction_type: 'instagram_redirect',
                    button_type: 'customer_spotlight_image'
                });
            }

            this.openInstagram(customer.instagram_handle);
        });

        // Use preloaded image or create new one
        const img = customer._preloadedImage ? customer._preloadedImage.cloneNode(true) : new Image();
        if (!customer._preloadedImage) {
            img.src = customer.image_url;
            img.alt = `Customer @${customer.instagram_handle}`;
            img.loading = 'eager';
            img.decoding = 'sync';
        }

        img.onerror = function() {
            this.src = '/static/placeholder-customer.jpg';
        };

        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = 'customer-overlay';
        overlay.innerHTML = `
            <div class="customer-handle">
                ${customer.instagram_handle}
                <svg class="instagram-icon" viewBox="0 0 24 24">
                    <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                </svg>
            </div>
        `;

        customerDiv.appendChild(img);
        customerDiv.appendChild(overlay);

        return customerDiv;
    }

    startScrolling() {
        const animate = (timestamp) => {
            if (this.lastTimestamp === 0) {
                this.lastTimestamp = timestamp;
            }

            const deltaTime = timestamp - this.lastTimestamp;
            this.lastTimestamp = timestamp;

            // Move all customers to the left
            this.scrollOffset += (this.scrollSpeed * deltaTime) / 1000;

            this.updateCustomerPositions();
            this.recycleCustomers();

            this.animationFrame = requestAnimationFrame(animate);
        };

        this.animationFrame = requestAnimationFrame(animate);
    }

    updateCustomerPositions() {
        this.visibleCustomers.forEach((customerData, index) => {
            const newPosition = customerData.position - this.scrollOffset;
            customerData.element.style.left = `${newPosition}px`;
        });
    }

    recycleCustomers() {
        const containerWidth = this.scrollContainer ? this.scrollContainer.offsetWidth : window.innerWidth;

        // Remove customers that have scrolled completely off-screen to the left
        while (this.visibleCustomers.length > 0) {
            const firstCustomer = this.visibleCustomers[0];
            const customerRight = firstCustomer.position - this.scrollOffset + this.customerWidth;

            if (customerRight < -50) { // 50px buffer
                // Remove the customer from DOM and array
                firstCustomer.element.remove();
                this.visibleCustomers.shift();

                // Add a new customer to the end
                if (this.visibleCustomers.length > 0) {
                    const lastCustomer = this.visibleCustomers[this.visibleCustomers.length - 1];
                    const newCustomerPosition = lastCustomer.position + (this.customerWidth + this.customerGap);

                    const newCustomerElement = this.addCustomerToEnd();
                    if (newCustomerElement) {
                        const newCustomerData = this.visibleCustomers[this.visibleCustomers.length - 1];
                        newCustomerData.position = newCustomerPosition;
                        newCustomerElement.style.left = `${newCustomerPosition - this.scrollOffset}px`;
                        newCustomerElement.style.width = `${this.customerWidth}px`;
                    }
                }
            } else {
                break; // First customer is still visible, so stop checking
            }
        }

        // Add customers to the right if needed
        while (this.visibleCustomers.length > 0 && this.visibleCustomers.length < this.maxVisibleCustomers) {
            const lastCustomer = this.visibleCustomers[this.visibleCustomers.length - 1];
            const lastCustomerRight = lastCustomer.position - this.scrollOffset + this.customerWidth;

            if (lastCustomerRight < containerWidth + 500) { // Add when within 500px of viewport
                const newCustomerPosition = lastCustomer.position + (this.customerWidth + this.customerGap);

                const newCustomerElement = this.addCustomerToEnd();
                if (newCustomerElement) {
                    const newCustomerData = this.visibleCustomers[this.visibleCustomers.length - 1];
                    newCustomerData.position = newCustomerPosition;
                    newCustomerElement.style.left = `${newCustomerPosition - this.scrollOffset}px`;
                    newCustomerElement.style.width = `${this.customerWidth}px`;
                }
            } else {
                break;
            }
        }
    }

    pauseScrolling() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
            this.animationFrame = null;
        }
    }

    resumeScrolling() {
        if (!this.animationFrame) {
            this.lastTimestamp = 0; // Reset timestamp to avoid jump
            this.startScrolling();
        }
    }

    openInstagram(handle) {
        const cleanHandle = handle.replace('@', '');
        const url = `https://www.instagram.com/${cleanHandle}`;
        window.open(url, '_blank', 'noopener,noreferrer');
    }

    showLoading() {
        if (this.loadingElement) {
            this.loadingElement.style.display = 'flex';
        }
    }

    hideLoading() {
        if (this.loadingElement) {
            this.loadingElement.style.display = 'none';
        }
    }

    showError(message) {
        if (!this.container) return;

        this.hideLoading();

        // Create error element
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-customer';
        errorDiv.innerHTML = `
            <div class="error-icon">⚠️</div>
            <div class="error-message">${message}</div>
            <button name="retry_customer_gallery" class="retry-button" onclick="window.customerGallery?.refresh()">
                Try Again
            </button>
        `;

        this.container.innerHTML = '';
        this.container.appendChild(errorDiv);
    }

    // Public methods for external control
    refresh() {
        this.destroy();
        this.currentIndex = 0;
        this.scrollOffset = 0;
        this.visibleCustomers = [];
        this.loadInitialCustomers();
    }

    destroy() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
            this.animationFrame = null;
        }

        // Clear all customers
        this.visibleCustomers = [];
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.customerGallery = new CustomerSpotlightGallery();
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (window.customerGallery) {
        window.customerGallery.destroy();
    }
});
