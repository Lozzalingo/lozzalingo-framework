/**
 * Product Detail Modal — Lozzalingo Framework
 * Self-contained IIFE with inline CSS, hash detection, image gallery, and pulsating CTA.
 * Host apps configure via ProductDetail.init(config).
 */
(function() {
    'use strict';

    var state = {
        config: null,
        overlay: null,
        product: null,
        images: [],
        currentImage: 0,
        touchStartX: 0,
        styleInjected: false
    };

    // === CSS (inline, all classes prefixed lz-pd-) ===
    var CSS = '\
/* Product Detail Overlay */\
.lz-pd-overlay {\
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;\
    background: rgba(0,0,0,0.85); z-index: 9999;\
    display: flex; align-items: center; justify-content: center;\
    opacity: 0; visibility: hidden;\
    transition: opacity 0.3s ease, visibility 0.3s ease;\
    padding: 20px; box-sizing: border-box;\
}\
.lz-pd-overlay.lz-pd-active {\
    opacity: 1; visibility: visible;\
}\
.lz-pd-container {\
    background: #fff; border-radius: 12px; max-width: 900px; width: 100%;\
    max-height: 90vh; overflow-y: auto; position: relative;\
    display: grid; grid-template-columns: 1fr 1fr;\
    box-shadow: 0 25px 60px rgba(0,0,0,0.4);\
    animation: lz-pd-slideUp 0.3s ease;\
}\
@keyframes lz-pd-slideUp {\
    from { transform: translateY(30px); opacity: 0; }\
    to { transform: translateY(0); opacity: 1; }\
}\
.lz-pd-close {\
    position: absolute; top: 12px; right: 12px; z-index: 10;\
    background: rgba(0,0,0,0.6); border: none; color: #fff;\
    width: 36px; height: 36px; border-radius: 50%; cursor: pointer;\
    font-size: 20px; line-height: 36px; text-align: center;\
    transition: background 0.2s;\
}\
.lz-pd-close:hover { background: rgba(0,0,0,0.8); }\
\
/* Gallery */\
.lz-pd-gallery {\
    background: #f5f5f5; border-radius: 12px 0 0 12px; overflow: hidden;\
    display: flex; flex-direction: column;\
}\
.lz-pd-main-image-wrap {\
    position: relative; width: 100%; aspect-ratio: 1/1;\
    overflow: hidden; background: #eee;\
}\
.lz-pd-main-image-wrap img {\
    width: 100%; height: 100%; object-fit: cover;\
    transition: opacity 0.3s ease;\
}\
.lz-pd-nav-arrow {\
    position: absolute; top: 50%; transform: translateY(-50%);\
    background: rgba(0,0,0,0.5); border: none; color: #fff;\
    width: 40px; height: 40px; border-radius: 50%; cursor: pointer;\
    font-size: 18px; display: flex; align-items: center; justify-content: center;\
    transition: background 0.2s; z-index: 2;\
}\
.lz-pd-nav-arrow:hover { background: rgba(0,0,0,0.8); }\
.lz-pd-nav-prev { left: 10px; }\
.lz-pd-nav-next { right: 10px; }\
.lz-pd-counter {\
    position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%);\
    background: rgba(0,0,0,0.6); color: #fff; padding: 4px 12px;\
    border-radius: 12px; font-size: 13px;\
}\
.lz-pd-thumbnails {\
    display: flex; gap: 6px; padding: 8px;\
    overflow-x: auto; flex-shrink: 0;\
}\
.lz-pd-thumb {\
    width: 60px; height: 60px; border-radius: 6px; overflow: hidden;\
    cursor: pointer; border: 2px solid transparent; flex-shrink: 0;\
    transition: border-color 0.2s;\
}\
.lz-pd-thumb.lz-pd-thumb-active { border-color: #4ade80; }\
.lz-pd-thumb img {\
    width: 100%; height: 100%; object-fit: cover;\
}\
\
/* Info Panel */\
.lz-pd-info {\
    padding: 28px; display: flex; flex-direction: column;\
    overflow-y: auto;\
}\
.lz-pd-name {\
    font-size: 24px; font-weight: 700; margin: 0 0 8px; color: #111;\
}\
.lz-pd-price {\
    font-size: 22px; font-weight: 700; color: #16a34a; margin: 0 0 12px;\
}\
.lz-pd-badges {\
    display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap;\
}\
.lz-pd-badge {\
    display: inline-block; padding: 4px 12px; border-radius: 4px;\
    font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;\
}\
.lz-pd-badge-limited {\
    background: #fef3c7; color: #92400e; border: 1px solid #f59e0b;\
}\
.lz-pd-badge-preorder {\
    background: #dbeafe; color: #1e40af; border: 1px solid #3b82f6;\
}\
.lz-pd-description {\
    font-size: 15px; line-height: 1.6; color: #444; margin-bottom: 24px;\
    flex: 1; overflow-y: auto; max-height: 200px;\
}\
.lz-pd-actions {\
    display: flex; gap: 10px; margin-bottom: 16px;\
}\
.lz-pd-buy-now {\
    flex: 1; padding: 14px 20px; border: none; border-radius: 8px;\
    font-size: 15px; font-weight: 700; cursor: pointer;\
    background: #111; color: #fff; transition: background 0.2s;\
    text-transform: uppercase; letter-spacing: 1px;\
}\
.lz-pd-buy-now:hover { background: #333; }\
.lz-pd-buy-now:disabled {\
    background: #9ca3af; cursor: not-allowed;\
}\
.lz-pd-add-to-cart {\
    flex: 1; padding: 14px 20px; border: 2px solid #111; border-radius: 8px;\
    font-size: 15px; font-weight: 700; cursor: pointer;\
    background: #fff; color: #111; transition: all 0.2s;\
    text-transform: uppercase; letter-spacing: 1px;\
}\
.lz-pd-add-to-cart:hover { background: #f3f4f6; }\
.lz-pd-add-to-cart:disabled {\
    border-color: #9ca3af; color: #9ca3af; cursor: not-allowed;\
}\
\
/* Pulsating See All Products link */\
.lz-pd-see-all {\
    display: block; text-align: center; padding: 12px;\
    color: #4ade80; font-weight: 700; font-size: 16px;\
    text-decoration: none; cursor: pointer;\
    animation: lz-pd-pulse 2s ease-in-out infinite;\
    border: none; background: none; width: 100%;\
}\
.lz-pd-see-all:hover { color: #22c55e; }\
@keyframes lz-pd-pulse {\
    0%, 100% { opacity: 1; transform: scale(1); text-shadow: 0 0 10px rgba(74,222,128,0.3); }\
    50% { opacity: 0.8; transform: scale(1.03); text-shadow: 0 0 20px rgba(74,222,128,0.6); }\
}\
\
/* Loading state */\
.lz-pd-loading {\
    grid-column: 1 / -1; display: flex; align-items: center;\
    justify-content: center; min-height: 300px;\
}\
.lz-pd-spinner {\
    width: 40px; height: 40px; border: 4px solid #e5e7eb;\
    border-top-color: #4ade80; border-radius: 50%;\
    animation: lz-pd-spin 0.8s linear infinite;\
}\
@keyframes lz-pd-spin {\
    to { transform: rotate(360deg); }\
}\
\
/* Not found state */\
.lz-pd-not-found {\
    grid-column: 1 / -1; text-align: center;\
    padding: 60px 20px; color: #666;\
}\
.lz-pd-not-found h3 { margin: 0 0 8px; color: #333; font-size: 20px; }\
.lz-pd-not-found p { margin: 0 0 20px; }\
\
/* Mobile responsive */\
@media (max-width: 700px) {\
    .lz-pd-container {\
        grid-template-columns: 1fr; max-height: 95vh;\
        border-radius: 12px;\
    }\
    .lz-pd-gallery { border-radius: 12px 12px 0 0; }\
    .lz-pd-main-image-wrap { aspect-ratio: 4/3; }\
    .lz-pd-info { padding: 20px; }\
    .lz-pd-name { font-size: 20px; }\
    .lz-pd-price { font-size: 20px; }\
    .lz-pd-description { max-height: 120px; }\
    .lz-pd-actions { flex-direction: column; }\
    .lz-pd-overlay { padding: 10px; }\
}\
';

    function injectStyles() {
        if (state.styleInjected) return;
        var style = document.createElement('style');
        style.id = 'lz-pd-styles';
        style.textContent = CSS;
        document.head.appendChild(style);
        state.styleInjected = true;
    }

    // === Hash Detection ===
    function getProductIdFromHash() {
        var hash = window.location.hash;
        var match = hash.match(/^#product-(\d+)$/);
        return match ? parseInt(match[1], 10) : null;
    }

    function removeHash() {
        if (window.location.hash) {
            history.replaceState(null, '', window.location.pathname + window.location.search);
        }
    }

    // === Overlay Creation ===
    function createOverlay() {
        if (state.overlay) {
            state.overlay.remove();
        }

        var overlay = document.createElement('div');
        overlay.className = 'lz-pd-overlay';
        overlay.innerHTML =
            '<div class="lz-pd-container">' +
                '<button class="lz-pd-close">&times;</button>' +
                '<div class="lz-pd-gallery">' +
                    '<div class="lz-pd-main-image-wrap">' +
                        '<img src="" alt="">' +
                        '<button class="lz-pd-nav-arrow lz-pd-nav-prev">&#8249;</button>' +
                        '<button class="lz-pd-nav-arrow lz-pd-nav-next">&#8250;</button>' +
                        '<div class="lz-pd-counter"></div>' +
                    '</div>' +
                    '<div class="lz-pd-thumbnails"></div>' +
                '</div>' +
                '<div class="lz-pd-info">' +
                    '<h2 class="lz-pd-name"></h2>' +
                    '<div class="lz-pd-price"></div>' +
                    '<div class="lz-pd-badges"></div>' +
                    '<div class="lz-pd-description"></div>' +
                    '<div class="lz-pd-actions">' +
                        '<button class="lz-pd-buy-now">BUY NOW</button>' +
                        '<button class="lz-pd-add-to-cart">ADD TO BAG</button>' +
                    '</div>' +
                    '<button class="lz-pd-see-all">See All Products &rarr;</button>' +
                '</div>' +
            '</div>';

        document.body.appendChild(overlay);
        state.overlay = overlay;
        bindOverlayEvents(overlay);
        return overlay;
    }

    function showLoading() {
        if (state.overlay) state.overlay.remove();

        var overlay = document.createElement('div');
        overlay.className = 'lz-pd-overlay lz-pd-active';
        overlay.innerHTML =
            '<div class="lz-pd-container">' +
                '<button class="lz-pd-close">&times;</button>' +
                '<div class="lz-pd-loading"><div class="lz-pd-spinner"></div></div>' +
            '</div>';

        document.body.appendChild(overlay);
        state.overlay = overlay;
        document.body.style.overflow = 'hidden';

        overlay.querySelector('.lz-pd-close').addEventListener('click', close);
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) close();
        });
    }

    function showNotFound() {
        if (state.overlay) state.overlay.remove();

        var overlay = document.createElement('div');
        overlay.className = 'lz-pd-overlay lz-pd-active';
        overlay.innerHTML =
            '<div class="lz-pd-container">' +
                '<button class="lz-pd-close">&times;</button>' +
                '<div class="lz-pd-not-found">' +
                    '<h3>Product Not Found</h3>' +
                    '<p>This product may no longer be available.</p>' +
                    '<button class="lz-pd-see-all">See All Products &rarr;</button>' +
                '</div>' +
            '</div>';

        document.body.appendChild(overlay);
        state.overlay = overlay;
        document.body.style.overflow = 'hidden';

        overlay.querySelector('.lz-pd-close').addEventListener('click', close);
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) close();
        });
        overlay.querySelector('.lz-pd-see-all').addEventListener('click', function() {
            close();
            if (state.config && state.config.productsUrl) {
                window.location.href = state.config.productsUrl;
            }
        });
    }

    // === Render Product ===
    function renderProduct(product) {
        state.product = product;
        var cfg = state.config;

        var images = cfg.getImageUrls ? cfg.getImageUrls(product) : [];
        state.images = images;
        state.currentImage = 0;

        var overlay = createOverlay();

        // Name
        overlay.querySelector('.lz-pd-name').textContent = product.name || '';

        // Price
        var priceText = cfg.formatPrice ? cfg.formatPrice(product.price) : '';
        overlay.querySelector('.lz-pd-price').textContent = priceText;

        // Badges
        var badgesEl = overlay.querySelector('.lz-pd-badges');
        badgesEl.innerHTML = '';
        if (product.limited_edition) {
            badgesEl.innerHTML += '<span class="lz-pd-badge lz-pd-badge-limited">LIMITED EDITION</span>';
        }
        if (cfg.isPreorder && cfg.isPreorder(product)) {
            badgesEl.innerHTML += '<span class="lz-pd-badge lz-pd-badge-preorder">PRE ORDER</span>';
        }

        // Description
        var descEl = overlay.querySelector('.lz-pd-description');
        descEl.textContent = product.description || '';

        // Gallery
        updateGalleryImage(overlay);
        renderThumbnails(overlay);

        // Show/hide nav
        var showNav = images.length > 1;
        overlay.querySelector('.lz-pd-nav-prev').style.display = showNav ? 'flex' : 'none';
        overlay.querySelector('.lz-pd-nav-next').style.display = showNav ? 'flex' : 'none';
        overlay.querySelector('.lz-pd-counter').style.display = showNav ? 'block' : 'none';

        // Button states
        var soldOut = cfg.isSoldOut ? cfg.isSoldOut(product) : false;
        var preorder = cfg.isPreorder ? cfg.isPreorder(product) : false;

        var buyBtn = overlay.querySelector('.lz-pd-buy-now');
        var cartBtn = overlay.querySelector('.lz-pd-add-to-cart');

        if (soldOut) {
            buyBtn.textContent = 'SOLD OUT';
            buyBtn.disabled = true;
            cartBtn.disabled = true;
        } else if (preorder) {
            buyBtn.textContent = 'PRE ORDER';
        }

        // Show overlay
        document.body.style.overflow = 'hidden';
        requestAnimationFrame(function() {
            overlay.classList.add('lz-pd-active');
        });
    }

    function updateGalleryImage(overlay) {
        var img = overlay.querySelector('.lz-pd-main-image-wrap img');
        var counter = overlay.querySelector('.lz-pd-counter');

        if (state.images.length > 0) {
            img.src = state.images[state.currentImage];
            img.alt = state.product ? state.product.name : '';
        }

        if (state.images.length > 1) {
            counter.textContent = (state.currentImage + 1) + ' / ' + state.images.length;
        }

        // Update thumbnail active state
        var thumbs = overlay.querySelectorAll('.lz-pd-thumb');
        thumbs.forEach(function(t, i) {
            t.classList.toggle('lz-pd-thumb-active', i === state.currentImage);
        });
    }

    function renderThumbnails(overlay) {
        var container = overlay.querySelector('.lz-pd-thumbnails');
        container.innerHTML = '';

        if (state.images.length <= 1) {
            container.style.display = 'none';
            return;
        }

        container.style.display = 'flex';
        state.images.forEach(function(url, i) {
            var thumb = document.createElement('div');
            thumb.className = 'lz-pd-thumb' + (i === 0 ? ' lz-pd-thumb-active' : '');
            thumb.innerHTML = '<img src="' + url + '" alt="">';
            thumb.addEventListener('click', function() {
                state.currentImage = i;
                updateGalleryImage(overlay);
            });
            container.appendChild(thumb);
        });
    }

    function nextImage() {
        if (state.images.length <= 1 || !state.overlay) return;
        state.currentImage = (state.currentImage + 1) % state.images.length;
        updateGalleryImage(state.overlay);
    }

    function prevImage() {
        if (state.images.length <= 1 || !state.overlay) return;
        state.currentImage = (state.currentImage - 1 + state.images.length) % state.images.length;
        updateGalleryImage(state.overlay);
    }

    // === Events ===
    function bindOverlayEvents(overlay) {
        // Close
        overlay.querySelector('.lz-pd-close').addEventListener('click', close);
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) close();
        });

        // Gallery nav
        overlay.querySelector('.lz-pd-nav-prev').addEventListener('click', prevImage);
        overlay.querySelector('.lz-pd-nav-next').addEventListener('click', nextImage);

        // Buy Now
        overlay.querySelector('.lz-pd-buy-now').addEventListener('click', function() {
            if (!state.product || !state.config.onBuyNow) return;
            state.config.onBuyNow(state.product);
        });

        // Add to Cart
        overlay.querySelector('.lz-pd-add-to-cart').addEventListener('click', function() {
            if (!state.product || !state.config.onAddToCart) return;
            var result = state.config.onAddToCart(state.product);
            if (result && typeof result.then === 'function') {
                result.then(function() { close(); });
            }
        });

        // See All Products
        overlay.querySelector('.lz-pd-see-all').addEventListener('click', function() {
            close();
            if (state.config && state.config.productsUrl) {
                window.location.href = state.config.productsUrl;
            }
        });

        // Touch swipe on gallery
        var imageWrap = overlay.querySelector('.lz-pd-main-image-wrap');
        imageWrap.addEventListener('touchstart', function(e) {
            state.touchStartX = e.touches[0].clientX;
        }, { passive: true });

        imageWrap.addEventListener('touchend', function(e) {
            if (!state.touchStartX) return;
            var diff = e.changedTouches[0].clientX - state.touchStartX;
            if (Math.abs(diff) > 50) {
                if (diff < 0) nextImage();
                else prevImage();
            }
            state.touchStartX = 0;
        }, { passive: true });
    }

    function onKeydown(e) {
        if (!state.overlay || !state.overlay.classList.contains('lz-pd-active')) return;

        // Don't capture keys if a sub-modal (size/color/country) is open on top
        var subModals = document.querySelectorAll(
            '.size-modal-overlay.show, .color-modal-overlay.show, ' +
            '.country-modal-overlay.show, .pinto-size-modal-overlay.show, ' +
            '.pinto-country-modal-overlay.show'
        );
        if (subModals.length > 0) return;

        if (e.key === 'Escape') {
            close();
        } else if (e.key === 'ArrowLeft') {
            prevImage();
        } else if (e.key === 'ArrowRight') {
            nextImage();
        }
    }

    // === Close ===
    function close() {
        if (!state.overlay) return;
        state.overlay.classList.remove('lz-pd-active');
        document.body.style.overflow = '';
        removeHash();

        setTimeout(function() {
            if (state.overlay && state.overlay.parentNode) {
                state.overlay.remove();
            }
            state.overlay = null;
            state.product = null;
        }, 300);
    }

    // === Open by ID ===
    function openProduct(id) {
        var cfg = state.config;
        if (!cfg) return;

        // Try local data first
        var product = cfg.getProduct ? cfg.getProduct(id) : null;
        if (product) {
            renderProduct(product);
            return;
        }

        // Fallback to fetch
        if (cfg.fetchProduct) {
            showLoading();
            cfg.fetchProduct(id).then(function(p) {
                if (p) {
                    renderProduct(p);
                } else {
                    showNotFound();
                }
            }).catch(function() {
                showNotFound();
            });
        } else {
            showNotFound();
        }
    }

    // === Hash Change Handler ===
    function onHashChange() {
        var id = getProductIdFromHash();
        if (id) {
            openProduct(id);
        }
    }

    // === Public API ===
    function init(config) {
        state.config = config;
        injectStyles();

        // Listen for keyboard
        document.removeEventListener('keydown', onKeydown);
        document.addEventListener('keydown', onKeydown);

        // Listen for hash changes
        window.removeEventListener('hashchange', onHashChange);
        window.addEventListener('hashchange', onHashChange);

        // Check current hash
        var id = getProductIdFromHash();
        if (id) {
            openProduct(id);
        }
    }

    window.ProductDetail = {
        init: init,
        open: openProduct,
        close: close
    };

})();
