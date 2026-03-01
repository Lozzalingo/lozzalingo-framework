// Merchandise Editor JavaScript
(function() {
    'use strict';

    let currentEditingProduct = null;
    let selectedImages = [];
    let imagesToDelete = [];
    let draggedElement = null;
    let allProducts = [];  // Store all products for filtering
    let storageBrowserCallback = null;  // Called when user picks a file from storage browser

    // Initialize when DOM is loaded
    document.addEventListener('DOMContentLoaded', function() {
        checkAuthAndInitialize();
    });

    function checkAuthAndInitialize() {
        fetch('/admin/status')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Not authenticated');
                }
                return response.json();
            })
            .then(data => {
                if (data.logged_in) {
                    initialize();
                } else {
                    throw new Error('Not authenticated');
                }
            })
            .catch(() => {
                window.location.href = '/admin/login?next=' + encodeURIComponent(window.location.pathname);
            });
    }

    function initialize() {
        console.log('Initializing Merchandise Editor...');

        initializeProductForm();
        initializeFulfilmentSection();
        initializeStorageBrowser();
        initializeFilters();
        loadProducts();
    }

    function initializeFilters() {
        const searchInput = document.getElementById('productSearch');
        const filterSelect = document.getElementById('productFilter');

        if (searchInput) {
            searchInput.addEventListener('input', filterProducts);
        }
        if (filterSelect) {
            filterSelect.addEventListener('change', filterProducts);
        }
    }

    function filterProducts() {
        const searchInput = document.getElementById('productSearch');
        const filterSelect = document.getElementById('productFilter');
        const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';
        const filterType = filterSelect ? filterSelect.value : 'all';

        let filtered = allProducts.filter(product => {
            // Text search
            const matchesSearch = !searchTerm ||
                product.name.toLowerCase().includes(searchTerm) ||
                (product.description && product.description.toLowerCase().includes(searchTerm));

            // Filter type
            let matchesFilter = true;
            switch (filterType) {
                case 'preorder':
                    matchesFilter = product.is_preorder;
                    break;
                case 'limited':
                    matchesFilter = product.limited_edition;
                    break;
                case 'pod':
                    matchesFilter = product.print_on_demand;
                    break;
                case 'active':
                    matchesFilter = product.is_active;
                    break;
            }

            return matchesSearch && matchesFilter;
        });

        renderProducts(filtered);
        updateProductCount(filtered.length, allProducts.length);
    }

    function updateProductCount(showing, total) {
        const countEl = document.getElementById('productCount');
        if (countEl) {
            if (showing === total) {
                countEl.textContent = `${total} products`;
            } else {
                countEl.textContent = `Showing ${showing} of ${total}`;
            }
        }
    }

    // Success message helper function
    function showSuccessMessage(message) {
        // Create success notification
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #28a745;
            color: white;
            padding: 12px 20px;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            z-index: 1000;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 500;
            transform: translateX(100%);
            transition: transform 0.3s ease;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);

        // Animate in
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 100);

        // Animate out and remove
        setTimeout(() => {
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (notification.parentNode) {
                    document.body.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }

    function initializeTabs() {
        const tabBtns = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');

        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetTab = btn.dataset.tab;

                // Update active states
                tabBtns.forEach(b => b.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));

                btn.classList.add('active');
                document.getElementById(targetTab + '-tab').classList.add('active');

                // Load data when switching to tabs
                if (targetTab === 'products') {
                    loadProducts();
                } else if (targetTab === 'news') {
                    loadArticles();
                }
            });
        });
    }

    function initializeProductForm() {
        const form = document.getElementById('productForm');
        const imageInput = document.getElementById('productImages');
        const dropZone = document.getElementById('imageDropZone');
        const previewsContainer = document.getElementById('imagePreviews');
        const uploadBtn = document.querySelector('.upload-btn');
        const cancelBtn = document.getElementById('cancelProductBtn');

        // Upload button click
        uploadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            imageInput.click();
        });

        // Drop zone click
        dropZone.addEventListener('click', (e) => {
            if (e.target === dropZone || e.target.classList.contains('upload-placeholder')) {
                imageInput.click();
            }
        });

        // File input change
        imageInput.addEventListener('change', handleFileSelection);

        // Drag and drop
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');

            const files = Array.from(e.dataTransfer.files);
            handleFiles(files);
        });

        // Form submission
        form.addEventListener('submit', handleProductSubmit);

        // Cancel button — use explicit event prevention to avoid form interference
        cancelBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            resetProductForm();
        });

        // Preorder and Print on Demand checkbox logic
        const preorderCheckbox = document.getElementById('productPreorder');
        const printOnDemandCheckbox = document.getElementById('productPrintOnDemand');
        const stockInput = document.getElementById('productStock');

        function updateStockInputState() {
            if (preorderCheckbox.checked || printOnDemandCheckbox.checked) {
                stockInput.value = '0';
                stockInput.disabled = true;
            } else {
                stockInput.disabled = false;
            }
            // Toggle fulfilment section and SKU field visibility
            const fulfilmentSection = document.getElementById('fulfilmentSection');
            if (fulfilmentSection) {
                fulfilmentSection.style.display = printOnDemandCheckbox.checked ? 'block' : 'none';
            }
            const skuGroup = document.getElementById('skuGroup');
            if (skuGroup) {
                skuGroup.style.display = printOnDemandCheckbox.checked ? 'block' : 'none';
            }
            const fulfilmentMetaGroup = document.getElementById('fulfilmentMetaGroup');
            if (fulfilmentMetaGroup) {
                fulfilmentMetaGroup.style.display = printOnDemandCheckbox.checked ? 'block' : 'none';
            }
            // Toggle sold out checkbox visibility (show when limited edition is checked)
            const soldOutGroup = document.getElementById('soldOutGroup');
            const limitedEditionCheckbox = document.getElementById('productLimitedEdition');
            if (soldOutGroup) {
                soldOutGroup.style.display = limitedEditionCheckbox.checked ? 'block' : 'none';
            }
        }

        const limitedEditionCheckbox = document.getElementById('productLimitedEdition');
        preorderCheckbox.addEventListener('change', updateStockInputState);
        printOnDemandCheckbox.addEventListener('change', updateStockInputState);
        limitedEditionCheckbox.addEventListener('change', updateStockInputState);
    }

    function initializeFulfilmentSection() {
        console.log('FULFILMENT_INIT: Setting up fulfilment file slots');
        const designSlots = document.querySelectorAll('.design-slot');

        designSlots.forEach(slot => {
            const field = slot.dataset.field;
            const preview = slot.querySelector('.design-preview');
            const fileInput = slot.querySelector('input[type="file"]');
            const removeBtn = slot.querySelector('.design-remove-btn');

            // Click preview to trigger file input
            preview.addEventListener('click', () => {
                if (!currentEditingProduct) {
                    showMessage('Save the product first, then edit it to upload fulfilment files.', 'info');
                    return;
                }
                fileInput.click();
            });

            // File selected — upload immediately
            fileInput.addEventListener('change', async () => {
                if (!fileInput.files[0] || !currentEditingProduct) return;

                const file = fileInput.files[0];
                console.log(`FULFILMENT_UPLOAD: Uploading ${field} for product ${currentEditingProduct.id}`);

                const formData = new FormData();
                formData.append('file', file);
                formData.append('product_id', currentEditingProduct.id);
                formData.append('field', field);

                try {
                    const response = await fetch('/admin/merchandise-editor/upload-design', {
                        method: 'POST',
                        body: formData
                    });
                    const result = await response.json();

                    if (result.success) {
                        console.log(`FULFILMENT_UPLOAD: Success — ${field}: ${result.url}`);
                        setDesignPreview(slot, result.url);
                        showSuccessMessage('Fulfilment file uploaded');
                    } else {
                        throw new Error(result.error || 'Upload failed');
                    }
                } catch (error) {
                    console.error('FULFILMENT_UPLOAD: Error:', error);
                    showMessage('Error uploading fulfilment file: ' + error.message, 'error');
                }

                // Reset file input
                fileInput.value = '';
            });

            // Remove button
            removeBtn.addEventListener('click', async () => {
                if (!currentEditingProduct) return;

                console.log(`FULFILMENT_REMOVE: Removing ${field} for product ${currentEditingProduct.id}`);

                const formData = new FormData();
                formData.append('product_id', currentEditingProduct.id);
                formData.append('field', field);

                try {
                    const response = await fetch('/admin/merchandise-editor/remove-design', {
                        method: 'POST',
                        body: formData
                    });
                    const result = await response.json();

                    if (result.success) {
                        console.log(`FULFILMENT_REMOVE: Success — cleared ${field}`);
                        clearDesignPreview(slot);
                        showSuccessMessage('Fulfilment file removed');
                    } else {
                        throw new Error(result.error || 'Remove failed');
                    }
                } catch (error) {
                    console.error('FULFILMENT_REMOVE: Error:', error);
                    showMessage('Error removing fulfilment file: ' + error.message, 'error');
                }
            });
        });
    }

    function setDesignPreview(slot, url) {
        const preview = slot.querySelector('.design-preview');
        const removeBtn = slot.querySelector('.design-remove-btn');

        preview.innerHTML = `<img src="${url}" alt="Design" style="width: 100%; height: 100%; object-fit: cover;">`;
        removeBtn.style.display = 'inline-block';
    }

    function clearDesignPreview(slot) {
        const preview = slot.querySelector('.design-preview');
        const removeBtn = slot.querySelector('.design-remove-btn');

        preview.innerHTML = '<span class="design-placeholder">Click to upload</span>';
        removeBtn.style.display = 'none';
    }

    function populateFulfilmentPreviews(product) {
        const fields = ['front_design_url', 'back_design_url', 'front_mockup_url', 'back_mockup_url'];

        fields.forEach(field => {
            const slot = document.querySelector(`.design-slot[data-field="${field}"]`);
            if (!slot) return;

            const url = product[field];
            if (url) {
                setDesignPreview(slot, url);
            } else {
                clearDesignPreview(slot);
            }
        });
    }

    function clearAllFulfilmentPreviews() {
        const slots = document.querySelectorAll('.design-slot');
        slots.forEach(slot => clearDesignPreview(slot));
    }

    function initializeStorageBrowser() {
        console.log('STORAGE_BROWSER: Initializing storage browser');

        const modal = document.getElementById('storageBrowserModal');
        const closeBtn = modal.querySelector('.modal-close');
        const refreshBtn = document.getElementById('storageBrowserRefresh');
        const subfolderSelect = document.getElementById('storageBrowserSubfolder');

        // Close modal
        closeBtn.addEventListener('click', () => { modal.style.display = 'none'; });
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.style.display = 'none';
        });

        // Refresh button
        refreshBtn.addEventListener('click', () => loadStorageBrowserFiles());

        // Subfolder change
        subfolderSelect.addEventListener('change', () => loadStorageBrowserFiles());

        // Browse Storage for product images button
        const browseStorageForImages = document.getElementById('browseStorageForImages');
        if (browseStorageForImages) {
            browseStorageForImages.addEventListener('click', () => {
                openStorageBrowser('Select Image for Product Listing', 'merchandise', (url) => {
                    // Add as a product listing image — URL already has /static/ or https://
                    const imageObj = {
                        existing: true,
                        url: url,
                        originalPath: url,
                        name: url.split('/').pop(),
                        type: url.includes('.mp4') ? 'video/mp4' : 'image/jpeg'
                    };
                    selectedImages.push(imageObj);
                    renderExistingImagePreview(imageObj);
                    updateDropZoneVisibility();
                    showSuccessMessage('Image added to product listing');
                });
            });
        }

        // Browse Storage buttons on design slots
        const designBrowseBtns = document.querySelectorAll('.design-browse-btn');
        designBrowseBtns.forEach(btn => {
            const slot = btn.closest('.design-slot');
            const field = slot.dataset.field;

            btn.addEventListener('click', () => {
                if (!currentEditingProduct) {
                    showMessage('Save the product first, then edit it to set fulfilment files.', 'info');
                    return;
                }

                // Designs browse "designs" folder, mockups browse "merchandise" folder
                const subfolder = field.includes('mockup') ? 'merchandise' : 'designs';
                openStorageBrowser(`Select file for ${field.replace(/_/g, ' ')}`, subfolder, async (url) => {
                    // Set the design URL via API
                    const formData = new FormData();
                    formData.append('product_id', currentEditingProduct.id);
                    formData.append('field', field);
                    formData.append('url', url);

                    try {
                        const response = await fetch('/admin/merchandise-editor/set-design-url', {
                            method: 'POST',
                            body: formData
                        });
                        const result = await response.json();

                        if (result.success) {
                            setDesignPreview(slot, result.url);
                            showSuccessMessage('Fulfilment file set from storage');
                        } else {
                            throw new Error(result.error || 'Failed to set URL');
                        }
                    } catch (error) {
                        console.error('STORAGE_BROWSER: Error setting design URL:', error);
                        showMessage('Error: ' + error.message, 'error');
                    }
                });
            });
        });
    }

    function openStorageBrowser(title, defaultSubfolder, callback) {
        const modal = document.getElementById('storageBrowserModal');
        const titleEl = document.getElementById('storageBrowserTitle');
        const subfolderSelect = document.getElementById('storageBrowserSubfolder');

        titleEl.textContent = title;
        storageBrowserCallback = callback;

        // Pre-select the appropriate folder
        if (defaultSubfolder && subfolderSelect) {
            subfolderSelect.value = defaultSubfolder;
        }

        modal.style.display = 'flex';
        loadStorageBrowserFiles();
    }

    async function loadStorageBrowserFiles() {
        const grid = document.getElementById('storageBrowserGrid');
        const loading = document.getElementById('storageBrowserLoading');
        const subfolder = document.getElementById('storageBrowserSubfolder').value;

        grid.innerHTML = '';
        loading.style.display = 'block';

        try {
            const response = await fetch(`/admin/merchandise-editor/browse-storage?subfolder=${encodeURIComponent(subfolder)}`);
            const data = await response.json();

            loading.style.display = 'none';

            if (!data.success || !data.files || data.files.length === 0) {
                grid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-secondary, #666);">No files found in this folder.</p>';
                return;
            }

            data.files.forEach(file => {
                const item = document.createElement('div');
                item.style.cssText = 'border: 2px solid var(--border-color, #ccc); border-radius: 8px; overflow: hidden; transition: border-color 0.2s; position: relative;';
                item.innerHTML = `
                    <div class="storage-item-select" style="cursor: pointer;">
                        <img src="${file.url}" alt="${file.filename}" style="width: 100%; height: 100px; object-fit: cover;">
                        <div style="padding: 4px 6px; font-size: 0.75rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${file.filename}">${file.filename}</div>
                    </div>
                    <button name="delete_storage_file" type="button" style="width: 100%; padding: 4px; font-size: 0.7rem; background: #dc3545; color: white; border: none; cursor: pointer; border-radius: 0 0 6px 6px;">Delete</button>
                `;

                const selectArea = item.querySelector('.storage-item-select');
                selectArea.addEventListener('mouseenter', () => { item.style.borderColor = 'var(--accent-color, #007bff)'; });
                selectArea.addEventListener('mouseleave', () => { item.style.borderColor = 'var(--border-color, #ccc)'; });

                // Click image/name to select file
                selectArea.addEventListener('click', () => {
                    if (storageBrowserCallback) {
                        storageBrowserCallback(file.url);
                        storageBrowserCallback = null;
                    }
                    document.getElementById('storageBrowserModal').style.display = 'none';
                });

                // Delete button
                const deleteBtn = item.querySelector('button');
                deleteBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    await handleStorageFileDelete(file.url, file.filename, item);
                });

                grid.appendChild(item);
            });

        } catch (error) {
            loading.style.display = 'none';
            grid.innerHTML = `<p style="grid-column: 1/-1; text-align: center; color: red;">Error loading files: ${error.message}</p>`;
            console.error('STORAGE_BROWSER: Error loading files:', error);
        }
    }

    async function handleStorageFileDelete(url, filename, itemElement) {
        // First check if the file is in use
        try {
            const checkForm = new FormData();
            checkForm.append('url', url);

            const checkResponse = await fetch('/admin/merchandise-editor/check-file-usage', {
                method: 'POST',
                body: checkForm
            });
            const checkResult = await checkResponse.json();

            if (checkResult.success && checkResult.in_use) {
                const usageList = checkResult.usage.map(u =>
                    `• ${u.product} (${u.reasons.join(', ')})`
                ).join('\n');

                if (!confirm(`⚠️ "${filename}" is in use:\n\n${usageList}\n\nDelete anyway? References will break.`)) {
                    return;
                }
            } else {
                if (!confirm(`Delete "${filename}"? This cannot be undone.`)) {
                    return;
                }
            }

            // Proceed with deletion
            const deleteForm = new FormData();
            deleteForm.append('url', url);

            const deleteResponse = await fetch('/admin/merchandise-editor/delete-storage-file', {
                method: 'POST',
                body: deleteForm
            });
            const deleteResult = await deleteResponse.json();

            if (deleteResult.success) {
                itemElement.remove();
                showSuccessMessage('File deleted');

                // Check if grid is now empty
                const grid = document.getElementById('storageBrowserGrid');
                if (grid.children.length === 0) {
                    grid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-secondary, #666);">No files found in this folder.</p>';
                }
            } else {
                throw new Error(deleteResult.error || 'Delete failed');
            }
        } catch (error) {
            console.error('STORAGE_DELETE: Error:', error);
            showMessage('Error deleting file: ' + error.message, 'error');
        }
    }

    function initializeNewsForm() {
        // Reuse existing news editor functionality
        const form = document.getElementById('articleForm');
        const cancelBtn = document.getElementById('cancelBtn');

        form.addEventListener('submit', handleArticleSubmit);
        cancelBtn.addEventListener('click', resetArticleForm);
    }

    function handleFileSelection(e) {
        const files = Array.from(e.target.files);
        handleFiles(files);
    }

    function handleFiles(files) {
        const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'video/mp4'];
        const maxSize = 50 * 1024 * 1024; // 50MB total

        let totalSize = selectedImages.reduce((sum, img) => sum + (img.file ? img.file.size : 0), 0);

        files.forEach(file => {
            if (!validTypes.includes(file.type)) {
                showMessage('Invalid file type: ' + file.name, 'error');
                return;
            }

            if (totalSize + file.size > maxSize) {
                showMessage('Total file size exceeds 50MB limit', 'error');
                return;
            }

            const imageObj = {
                file: file,
                url: URL.createObjectURL(file),
                name: file.name,
                type: file.type
            };

            selectedImages.push(imageObj);
            totalSize += file.size;
            renderImagePreview(imageObj);
        });

        updateDropZoneVisibility();
    }

    function renderImagePreview(imageObj) {
        const previewsContainer = document.getElementById('imagePreviews');
        const preview = document.createElement('div');
        preview.className = 'image-preview';
        preview.dataset.imageName = imageObj.name;
        preview.draggable = false;

        let mediaElement;
        if (imageObj.type.startsWith('video/')) {
            mediaElement = document.createElement('video');
            mediaElement.controls = false;
            mediaElement.muted = true;
        } else {
            mediaElement = document.createElement('img');
            mediaElement.alt = imageObj.name;
        }

        mediaElement.src = imageObj.url;

        const removeBtn = document.createElement('button');
        removeBtn.name = 'remove_product_image';
        removeBtn.className = 'remove-btn';
        removeBtn.innerHTML = '×';
        removeBtn.title = 'Remove image';
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            removeImage(imageObj, preview);
        });

        // Click to preview or select for reordering
        preview.addEventListener('click', (e) => {
            if (!e.target.classList.contains('remove-btn') && !e.target.classList.contains('reorder-btn')) {
                // If shift is held, show modal, otherwise handle reordering
                if (e.shiftKey) {
                    showImageModal(imageObj.url);
                } else {
                    handleImageClick(imageObj, preview);
                }
            }
        });

        // Add reorder buttons
        addReorderButtons(imageObj, preview);
        preview.appendChild(mediaElement);
        preview.appendChild(removeBtn);
        previewsContainer.appendChild(preview);
    }

    function removeImage(imageObj, previewElement) {
        // Remove from selected images
        const index = selectedImages.findIndex(img => img.name === imageObj.name);
        if (index > -1) {
            selectedImages.splice(index, 1);
            URL.revokeObjectURL(imageObj.url);
        }

        // If this is an existing image being edited, mark for deletion
        if (imageObj.existing) {
            imagesToDelete.push(imageObj.url);
        }

        // Remove preview element
        previewElement.remove();
        updateDropZoneVisibility();
    }

    function updateDropZoneVisibility() {
        const dropZone = document.getElementById('imageDropZone');
        const placeholder = dropZone.querySelector('.upload-placeholder');

        if (selectedImages.length === 0) {
            // Full size drop zone with icon and hints
            dropZone.style.display = 'block';
            dropZone.style.minHeight = '';
            dropZone.style.padding = '';
            if (placeholder) {
                placeholder.style.display = '';
                placeholder.innerHTML = '<div class="upload-icon">📷</div><p>Drag & drop images here</p><p class="upload-hint">Supports: JPG, PNG, WebP, MP4 (max 50MB total)</p>';
            }
        } else {
            // Compact drop zone for adding more
            dropZone.style.display = 'block';
            dropZone.style.minHeight = '48px';
            dropZone.style.padding = '8px';
            if (placeholder) {
                placeholder.style.display = '';
                placeholder.innerHTML = '<p style="margin:0; font-size: 0.85em; opacity: 0.7;">📷 Drag & drop more images here</p>';
            }
        }
    }

    function showImageModal(imageSrc) {
        const modal = document.getElementById('imageModal');
        const modalImage = document.getElementById('modalImage');

        modalImage.src = imageSrc;
        modal.style.display = 'flex';

        // Close modal events
        const closeBtn = modal.querySelector('.modal-close');
        closeBtn.onclick = () => modal.style.display = 'none';
        modal.onclick = (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        };
    }

    async function handleProductSubmit(e) {
        e.preventDefault();

        const form = e.target;
        const submitBtn = document.getElementById('saveProductBtn');
        const btnText = submitBtn.querySelector('.btn-text');
        const btnLoading = submitBtn.querySelector('.btn-loading');

        // Show loading state
        btnText.style.display = 'none';
        btnLoading.style.display = 'flex';
        submitBtn.disabled = true;

        try {
            const formData = new FormData();

            // Add form fields
            formData.append('name', form.productName.value);
            formData.append('description', form.productDescription.value);
            formData.append('price', parseFloat(form.productPrice.value)); // Convert to pence
            formData.append('stock_quantity', parseInt(form.productStock.value) || 0);
            formData.append('is_preorder', form.productPreorder.checked);
            formData.append('limited_edition', form.productLimitedEdition.checked);
            formData.append('print_on_demand', form.productPrintOnDemand.checked);
            formData.append('sold_out', document.getElementById('productSoldOut').checked);
            formData.append('sku', (document.getElementById('productSku').value || '').trim());
            formData.append('fulfilment_meta', (document.getElementById('productFulfilmentMeta').value || '').trim());

            // Add product ID if editing
            if (currentEditingProduct) {
                formData.append('product_id', currentEditingProduct.id);
                formData.append('images_to_delete', JSON.stringify(imagesToDelete));

                // Send the complete ordered list of existing images (for reordering)
                const existingImageOrder = selectedImages
                    .filter(img => img.existing)
                    .map(img => img.originalPath || img.url);
                formData.append('existing_image_order', JSON.stringify(existingImageOrder));
                console.log('MERCH_EDITOR: Saving existing image order:', existingImageOrder);
                console.log('MERCH_EDITOR: Images to delete:', imagesToDelete);
            }

            // Add new images
            let newImageCount = 0;
            selectedImages.forEach((img, index) => {
                if (img.file) {
                    formData.append('images', img.file);
                    newImageCount++;
                }
            });
            console.log('MERCH_EDITOR: New images to upload:', newImageCount);

            const url = currentEditingProduct ? '/admin/merchandise-editor/update' : '/admin/merchandise-editor/create';
            const response = await fetch(url, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            console.log('MERCH_EDITOR: Save response:', result);

            if (result.success) {
                showMessage(currentEditingProduct ? 'Product updated successfully!' : 'Product created successfully!', 'success');
                resetProductForm();
                loadProducts();
            } else {
                throw new Error(result.error || 'Unknown error');
            }

        } catch (error) {
            console.error('MERCH_EDITOR: Error saving product:', error);
            showMessage('Error saving product: ' + error.message, 'error');
        } finally {
            // Hide loading state
            btnText.style.display = 'inline';
            btnLoading.style.display = 'none';
            submitBtn.disabled = false;
        }
    }

    async function handleArticleSubmit(e) {
        e.preventDefault();

        const form = e.target;
        const submitBtn = document.getElementById('saveBtn');
        const btnText = submitBtn.querySelector('.btn-text');
        const btnLoading = submitBtn.querySelector('.btn-loading');

        // Show loading state
        btnText.style.display = 'none';
        btnLoading.style.display = 'flex';
        submitBtn.disabled = true;

        try {
            const formData = new FormData();
            formData.append('title', form.title.value);
            formData.append('content', form.content.value);

            if (form.imageFile.files[0]) {
                formData.append('image', form.imageFile.files[0]);
            }

            const response = await fetch('/news/create', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                showMessage('Article published successfully!', 'success');
                resetArticleForm();
                loadArticles();
            } else {
                throw new Error(result.error || 'Unknown error');
            }

        } catch (error) {
            console.error('Error saving article:', error);
            showMessage('Error saving article: ' + error.message, 'error');
        } finally {
            // Hide loading state
            btnText.style.display = 'inline';
            btnLoading.style.display = 'none';
            submitBtn.disabled = false;
        }
    }

    function resetProductForm() {
        const form = document.getElementById('productForm');
        const titleEl = document.getElementById('productFormTitle');
        const submitBtn = document.getElementById('saveProductBtn');

        form.reset();
        titleEl.textContent = 'Create New Product';
        submitBtn.querySelector('.btn-text').textContent = 'Create Product';

        // Clear images
        selectedImages.forEach(img => {
            if (img.url.startsWith('blob:')) {
                URL.revokeObjectURL(img.url);
            }
        });
        selectedImages = [];
        imagesToDelete = [];

        document.getElementById('imagePreviews').innerHTML = '';
        updateDropZoneVisibility();

        // Clear editing state
        currentEditingProduct = null;
        document.querySelectorAll('.product-card.editing').forEach(card => {
            card.classList.remove('editing');
        });

        // Re-enable stock input and reset checkboxes
        document.getElementById('productStock').disabled = false;
        document.getElementById('productPreorder').checked = false;
        document.getElementById('productLimitedEdition').checked = false;
        document.getElementById('productPrintOnDemand').checked = false;
        document.getElementById('productSoldOut').checked = false;
        document.getElementById('soldOutGroup').style.display = 'none';

        // Clear and hide SKU field
        const skuInput = document.getElementById('productSku');
        if (skuInput) skuInput.value = '';
        const skuGroup = document.getElementById('skuGroup');
        if (skuGroup) skuGroup.style.display = 'none';

        // Clear and hide fulfilment meta field
        const fulfilmentMetaInput = document.getElementById('productFulfilmentMeta');
        if (fulfilmentMetaInput) fulfilmentMetaInput.value = '';
        const fulfilmentMetaGroup = document.getElementById('fulfilmentMetaGroup');
        if (fulfilmentMetaGroup) fulfilmentMetaGroup.style.display = 'none';

        // Hide fulfilment section and clear previews
        const fulfilmentSection = document.getElementById('fulfilmentSection');
        if (fulfilmentSection) {
            fulfilmentSection.style.display = 'none';
            clearAllFulfilmentPreviews();
        }
    }

    function resetArticleForm() {
        const form = document.getElementById('articleForm');
        const titleEl = document.getElementById('formTitle');
        const submitBtn = document.getElementById('saveBtn');

        form.reset();
        titleEl.textContent = 'Create New Article';
        submitBtn.querySelector('.btn-text').textContent = 'Publish Article';
    }

    async function loadProducts() {
        try {
            const response = await fetch('/admin/merchandise-editor/products');
            const data = await response.json();

            if (data.products) {
                allProducts = data.products;  // Store for filtering
                renderProducts(data.products);
                updateProductCount(data.products.length, data.products.length);
            }
        } catch (error) {
            console.error('Error loading products:', error);
            showMessage('Error loading products', 'error');
        }
    }

    function renderProducts(products) {
        const container = document.getElementById('productsGrid');

        if (products.length === 0) {
            container.innerHTML = '<p>No products found. Create your first product above!</p>';
            return;
        }

        container.innerHTML = products.map((product, index) => `
            <div class="product-card" data-product-id="${product.id}" data-sort-order="${index}" draggable="true">
                <div class="product-drag-handle">⋮⋮</div>
                <div class="product-header">
                    <h3 class="product-title">${escapeHtml(product.name)}</h3>
                    <span class="product-price">${product.price_display}</span>
                </div>
                <div class="product-info">
                    ${escapeHtml(product.description || '')}
                    <br>
                    ${product.print_on_demand ? 'Print on Demand' : `Stock: ${product.stock_quantity}`} ${product.is_preorder ? '(Preorder)' : ''}
                    ${product.limited_edition ? '<br><span class="limited-edition-badge">Limited Edition</span>' : ''}
                    ${product.sold_out ? '<span class="limited-edition-badge" style="background: #ff002b;">Sold Out</span>' : ''}
                </div>
                <div class="product-images">
                    ${product.image_urls.slice(0, 3).map(url => {
                        if (url.includes('.mp4')) {
                            return `<video src="${url}" muted></video>`;
                        } else {
                            return `<img src="${url}" alt="${product.name}">`;
                        }
                    }).join('')}
                    ${product.image_urls.length > 3 ? `<span>+${product.image_urls.length - 3}</span>` : ''}
                </div>
                <div class="product-actions">
                    <button name="edit_product" class="btn btn-warning btn-small" onclick="editProduct(${product.id})">Edit</button>
                    <button name="duplicate_product" class="btn btn-secondary btn-small" onclick="duplicateProduct(${product.id})">Duplicate</button>
                    <button name="delete_product" class="btn btn-danger btn-small" onclick="deleteProduct(${product.id}, '${escapeHtml(product.name)}')">Delete</button>
                </div>
            </div>
        `).join('');

        // Add drag and drop event listeners to product cards
        const productCards = container.querySelectorAll('.product-card');
        productCards.forEach(card => {
            card.addEventListener('dragstart', handleProductDragStart);
            card.addEventListener('dragover', handleProductDragOver);
            card.addEventListener('dragleave', handleProductDragLeave);
            card.addEventListener('drop', handleProductDrop);
            card.addEventListener('dragend', handleProductDragEnd);
        });
    }

    async function loadArticles() {
        try {
            const response = await fetch('/news/articles');
            const data = await response.json();

            if (data.articles) {
                renderArticles(data.articles);
            }
        } catch (error) {
            console.error('Error loading articles:', error);
        }
    }

    function renderArticles(articles) {
        const container = document.getElementById('articlesContainer');

        if (articles.length === 0) {
            container.innerHTML = '<p>No articles found. Create your first article above!</p>';
            return;
        }

        container.innerHTML = articles.map(article => `
            <div class="article-card" style="border: 2px solid #e0e0e0; border-radius: 10px; padding: 15px; margin-bottom: 15px;">
                <h3 style="margin: 0 0 10px 0;">${escapeHtml(article.title)}</h3>
                <p style="color: #666; font-size: 0.9rem;">
                    Published: ${new Date(article.date_published).toLocaleDateString()}
                </p>
                <div style="display: flex; gap: 10px; justify-content: flex-end;">
                    <button class="btn btn-warning btn-small" onclick="editArticle(${article.id})">Edit</button>
                    <button class="btn btn-danger btn-small" onclick="deleteArticle(${article.id}, '${escapeHtml(article.title)}')">Delete</button>
                </div>
            </div>
        `).join('');
    }

    // Global functions for button clicks
    window.editProduct = async function(productId) {
        try {
            const response = await fetch(`/admin/merchandise-editor/product/${productId}`);
            const data = await response.json();

            if (data.success) {
                const product = data.product;
                populateProductForm(product);

                // Mark card as editing
                document.querySelectorAll('.product-card.editing').forEach(card => {
                    card.classList.remove('editing');
                });
                document.querySelector(`[data-product-id="${productId}"]`).classList.add('editing');

                // Scroll to form
                document.getElementById('productForm').scrollIntoView({ behavior: 'smooth' });
            }
        } catch (error) {
            showMessage('Error loading product: ' + error.message, 'error');
        }
    };

    window.duplicateProduct = async function(productId) {
        try {
            console.log('DUPLICATE_PRODUCT: Duplicating product', productId);
            const response = await fetch(`/admin/merchandise-editor/duplicate/${productId}`, {
                method: 'POST'
            });
            const result = await response.json();

            if (result.success) {
                showSuccessMessage('Product duplicated');
                loadProducts();
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            showMessage('Error duplicating product: ' + error.message, 'error');
        }
    };

    window.deleteProduct = async function(productId, productName) {
        if (!confirm(`Are you sure you want to delete "${productName}"?`)) return;

        try {
            const response = await fetch(`/admin/merchandise-editor/delete/${productId}`, {
                method: 'POST'
            });
            const result = await response.json();

            if (result.success) {
                showMessage('Product deleted successfully!', 'success');
                loadProducts();
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            showMessage('Error deleting product: ' + error.message, 'error');
        }
    };

    window.editArticle = function(articleId) {
        showMessage('Article editing not implemented yet', 'info');
    };

    window.deleteArticle = function(articleId, title) {
        showMessage('Article deletion not implemented yet', 'info');
    };

    function populateProductForm(product) {
        currentEditingProduct = product;

        // Update form title and button
        document.getElementById('productFormTitle').textContent = 'Edit Product';
        document.getElementById('saveProductBtn').querySelector('.btn-text').textContent = 'Update Product';

        // Populate form fields
        document.getElementById('productName').value = product.name || '';
        document.getElementById('productDescription').value = product.description || '';
        document.getElementById('productPrice').value = (product.price / 100).toFixed(2);
        document.getElementById('productStock').value = product.stock_quantity || 0;
        document.getElementById('productPreorder').checked = product.is_preorder;
        document.getElementById('productLimitedEdition').checked = product.limited_edition;
        document.getElementById('productPrintOnDemand').checked = product.print_on_demand;
        document.getElementById('productSoldOut').checked = product.sold_out || false;

        // Populate SKU field and show if print on demand
        const skuInput = document.getElementById('productSku');
        const skuGroup = document.getElementById('skuGroup');
        if (skuInput) skuInput.value = product.sku || '';
        if (skuGroup) skuGroup.style.display = product.print_on_demand ? 'block' : 'none';

        // Populate fulfilment meta and show if print on demand
        const fulfilmentMetaInput = document.getElementById('productFulfilmentMeta');
        const fulfilmentMetaGroup = document.getElementById('fulfilmentMetaGroup');
        if (fulfilmentMetaInput) {
            fulfilmentMetaInput.value = product.fulfilment_meta ? JSON.stringify(product.fulfilment_meta, null, 2) : '';
        }
        if (fulfilmentMetaGroup) fulfilmentMetaGroup.style.display = product.print_on_demand ? 'block' : 'none';

        // Show sold_out group if limited edition
        const soldOutGroup = document.getElementById('soldOutGroup');
        if (soldOutGroup) {
            soldOutGroup.style.display = product.limited_edition ? 'block' : 'none';
        }

        // Handle preorder or print_on_demand state - disable stock if either is checked
        const stockInput = document.getElementById('productStock');
        stockInput.disabled = product.is_preorder || product.print_on_demand;

        // Toggle fulfilment section — show if POD is checked OR if any design URLs exist
        const fulfilmentSection = document.getElementById('fulfilmentSection');
        const hasDesignUrls = product.front_design_url || product.back_design_url ||
                              product.front_mockup_url || product.back_mockup_url;
        if (fulfilmentSection) {
            fulfilmentSection.style.display = (product.print_on_demand || hasDesignUrls) ? 'block' : 'none';
            if (product.print_on_demand || hasDesignUrls) {
                populateFulfilmentPreviews(product);
            }
        }

        // Clear and load existing images
        selectedImages = [];
        imagesToDelete = [];
        document.getElementById('imagePreviews').innerHTML = '';

        if (product.image_urls && product.image_urls.length > 0) {
            product.image_urls.forEach(url => {
                const imageObj = {
                    existing: true,
                    url: url,
                    originalPath: url,
                    name: url.split('/').pop(),
                    type: url.includes('.mp4') ? 'video/mp4' : 'image/jpeg'
                };
                selectedImages.push(imageObj);
                renderExistingImagePreview(imageObj);
            });
        } else if (product.front_mockup_url || product.back_mockup_url) {
            // Default: populate listing images from mockup URLs if no images set
            console.log('MERCH_EDITOR: Auto-populating listing images from mockups');
            const mockupUrls = [product.front_mockup_url, product.back_mockup_url].filter(Boolean);
            mockupUrls.forEach(url => {
                const imageObj = {
                    existing: true,
                    url: url,
                    originalPath: url,
                    name: url.split('/').pop(),
                    type: 'image/jpeg'
                };
                selectedImages.push(imageObj);
                renderExistingImagePreview(imageObj);
            });
        }

        updateDropZoneVisibility();
    }

    function renderExistingImagePreview(imageObj) {
        const previewsContainer = document.getElementById('imagePreviews');
        const preview = document.createElement('div');
        preview.className = 'image-preview';
        preview.dataset.imageName = imageObj.name;
        preview.draggable = false;

        let mediaElement;
        if (imageObj.type.startsWith('video/')) {
            mediaElement = document.createElement('video');
            mediaElement.controls = false;
            mediaElement.muted = true;
        } else {
            mediaElement = document.createElement('img');
            mediaElement.alt = imageObj.name;
        }

        mediaElement.src = imageObj.url;

        const removeBtn = document.createElement('button');
        removeBtn.name = 'remove_product_image';
        removeBtn.className = 'remove-btn';
        removeBtn.innerHTML = '×';
        removeBtn.title = 'Remove image';
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            removeImage(imageObj, preview);
        });

        // Click to preview or select for reordering
        preview.addEventListener('click', (e) => {
            if (!e.target.classList.contains('remove-btn') && !e.target.classList.contains('reorder-btn')) {
                // If shift is held, show modal, otherwise handle reordering
                if (e.shiftKey) {
                    showImageModal(imageObj.url);
                } else {
                    handleImageClick(imageObj, preview);
                }
            }
        });

        // Add reorder buttons
        addReorderButtons(imageObj, preview);
        preview.appendChild(mediaElement);
        preview.appendChild(removeBtn);
        previewsContainer.appendChild(preview);
    }

    function showMessage(message, type = 'info') {
        // Remove existing messages
        const existingMessages = document.querySelectorAll('.message');
        existingMessages.forEach(msg => msg.remove());

        // Create new message
        const messageEl = document.createElement('div');
        messageEl.className = `message message-${type}`;
        messageEl.textContent = message;

        // Insert at top of container
        const container = document.querySelector('.editor-container');
        container.insertBefore(messageEl, container.firstChild);

        // Auto remove after 5 seconds
        setTimeout(() => {
            messageEl.remove();
        }, 5000);
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Simple click-based reordering instead of drag and drop
    let selectedImageForMove = null;

    function handleImageClick(imageObj, previewElement) {
        if (selectedImageForMove === null) {
            // First click - select image to move
            selectedImageForMove = { imageObj, previewElement };
            previewElement.classList.add('selected-for-move');
            showMessage('Image selected. Click another image to move it there.', 'info');
        } else if (selectedImageForMove.previewElement === previewElement) {
            // Clicking same image - deselect
            cancelImageMove();
        } else {
            // Second click - move the image
            moveImage(selectedImageForMove, { imageObj, previewElement });
            cancelImageMove();
        }
    }

    function cancelImageMove() {
        if (selectedImageForMove) {
            selectedImageForMove.previewElement.classList.remove('selected-for-move');
            selectedImageForMove = null;
            showMessage('Move cancelled', 'info');
        }
    }

    function moveImage(from, to) {
        const fromIndex = selectedImages.findIndex(img => img.name === from.imageObj.name);
        const toIndex = selectedImages.findIndex(img => img.name === to.imageObj.name);

        if (fromIndex !== -1 && toIndex !== -1) {
            // Move element in array
            const [movedItem] = selectedImages.splice(fromIndex, 1);
            selectedImages.splice(toIndex, 0, movedItem);

            // Re-render the preview area
            reRenderImagePreviews();
            showSuccessMessage('Images reordered successfully');
        }
    }

    // Add up/down arrow buttons for reordering
    function addReorderButtons(imageObj, previewElement) {
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'reorder-buttons';

        const upBtn = document.createElement('button');
        upBtn.name = 'move_image_up';
        upBtn.className = 'reorder-btn reorder-up';
        upBtn.innerHTML = '↑';
        upBtn.title = 'Move up';
        upBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            moveImageUp(imageObj);
        });

        const downBtn = document.createElement('button');
        downBtn.name = 'move_image_down';
        downBtn.className = 'reorder-btn reorder-down';
        downBtn.innerHTML = '↓';
        downBtn.title = 'Move down';
        downBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            moveImageDown(imageObj);
        });

        // Update button states based on position
        updateReorderButtonStates(imageObj, upBtn, downBtn);

        buttonContainer.appendChild(upBtn);
        buttonContainer.appendChild(downBtn);
        previewElement.appendChild(buttonContainer);
    }

    function updateReorderButtonStates(imageObj, upBtn, downBtn) {
        const index = selectedImages.findIndex(img => img.name === imageObj.name);

        // Disable up button if first item
        upBtn.disabled = index === 0;

        // Disable down button if last item
        downBtn.disabled = index === selectedImages.length - 1;
    }

    function moveImageUp(imageObj) {
        const index = selectedImages.findIndex(img => img.name === imageObj.name);
        if (index > 0) {
            // Swap with previous item
            [selectedImages[index - 1], selectedImages[index]] = [selectedImages[index], selectedImages[index - 1]];
            reRenderImagePreviews();
            showSuccessMessage('Image moved up');
        }
    }

    function moveImageDown(imageObj) {
        const index = selectedImages.findIndex(img => img.name === imageObj.name);
        if (index < selectedImages.length - 1) {
            // Swap with next item
            [selectedImages[index], selectedImages[index + 1]] = [selectedImages[index + 1], selectedImages[index]];
            reRenderImagePreviews();
            showSuccessMessage('Image moved down');
        }
    }

    function reRenderImagePreviews() {
        const previewsContainer = document.getElementById('imagePreviews');

        // Clear any move selection
        if (selectedImageForMove) {
            selectedImageForMove = null;
        }

        previewsContainer.innerHTML = '';

        selectedImages.forEach(imageObj => {
            if (imageObj.existing) {
                renderExistingImagePreview(imageObj);
            } else {
                renderImagePreview(imageObj);
            }
        });
    }

    // Product drag and drop handlers
    let draggedProductElement = null;

    function handleProductDragStart(e) {
        draggedProductElement = e.target;
        e.target.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';

        // Add visual feedback to all other product cards
        const allCards = document.querySelectorAll('.product-card');
        allCards.forEach(card => {
            if (card !== e.target) {
                card.style.transition = 'all 0.2s ease';
            }
        });
    }

    function handleProductDragOver(e) {
        if (e.preventDefault) {
            e.preventDefault();
        }
        e.dataTransfer.dropEffect = 'move';

        // Add visual feedback for valid drop targets
        if (e.target.classList.contains('product-card') && e.target !== draggedProductElement) {
            e.target.classList.add('drag-over');
        }

        return false;
    }

    function handleProductDragLeave(e) {
        if (e.target.classList.contains('product-card')) {
            e.target.classList.remove('drag-over');
        }
    }

    function handleProductDrop(e) {
        if (e.stopPropagation) {
            e.stopPropagation();
        }

        // Remove drag-over class from target
        if (e.target.classList.contains('product-card')) {
            e.target.classList.remove('drag-over');
        }

        if (draggedProductElement !== e.target && e.target.classList.contains('product-card')) {
            const container = document.getElementById('productsGrid');
            const allCards = Array.from(container.querySelectorAll('.product-card'));

            const draggedIndex = allCards.indexOf(draggedProductElement);
            const targetIndex = allCards.indexOf(e.target);

            if (draggedIndex !== -1 && targetIndex !== -1) {
                // Reorder DOM elements
                if (draggedIndex < targetIndex) {
                    container.insertBefore(draggedProductElement, e.target.nextSibling);
                } else {
                    container.insertBefore(draggedProductElement, e.target);
                }

                // Send reorder request to server
                updateProductOrder();

                // Show success feedback
                showSuccessMessage('Products reordered successfully');
            }
        }

        return false;
    }

    function handleProductDragEnd(e) {
        // Clean up all drag states
        e.target.classList.remove('dragging');
        const allCards = document.querySelectorAll('.product-card');
        allCards.forEach(card => {
            card.classList.remove('drag-over');
            card.style.transition = '';
        });
        draggedProductElement = null;
    }

    async function updateProductOrder() {
        try {
            const container = document.getElementById('productsGrid');
            const productCards = container.querySelectorAll('.product-card');

            const productOrders = Array.from(productCards).map((card, index) => ({
                id: parseInt(card.dataset.productId),
                sort_order: index
            }));

            const response = await fetch('/admin/merchandise-editor/reorder', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ product_orders: productOrders })
            });

            const result = await response.json();

            if (!result.success) {
                console.error('Failed to update product order:', result.error);
                showMessage('Failed to update product order', 'error');
                // Reload products to reset order
                loadProducts();
            }
        } catch (error) {
            console.error('Error updating product order:', error);
            showMessage('Error updating product order', 'error');
            // Reload products to reset order
            loadProducts();
        }
    }

})();