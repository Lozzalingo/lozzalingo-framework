// News Editor functionality with Quill WYSIWYG and image upload
let allArticles = [];
let editingArticleId = null;
let quill = null;

document.addEventListener('DOMContentLoaded', function() {
    initQuill();
    loadCategories();
    loadArticles();
    setupForm();
    setupImagePreview();
    setupImageUpload();
    setupFilters();
    setupInlineImageUpload();
    setupGalleryFolderTabs();
    setupCoverBrowser();
});

// ===== Quill Initialization =====

// Register horizontal rule blot
var BlockEmbed = Quill.import('blots/block/embed');
class DividerBlot extends BlockEmbed {}
DividerBlot.blotName = 'divider';
DividerBlot.tagName = 'hr';
Quill.register(DividerBlot);

function initQuill() {
    quill = new Quill('#editor', {
        theme: 'snow',
        placeholder: 'Write your article content here...',
        modules: {
            toolbar: {
                container: [
                    [{ 'header': [1, 2, 3, 4, false] }],
                    ['bold', 'italic', 'underline', 'strike'],
                    [{ 'list': 'ordered' }, { 'list': 'bullet' }],
                    [{ 'indent': '-1' }, { 'indent': '+1' }],
                    [{ 'align': [] }],
                    [{ 'color': [] }, { 'background': [] }],
                    ['blockquote', 'code-block'],
                    ['link', 'image', 'video'],
                    ['divider'],
                    ['clean']
                ],
                handlers: {
                    'image': imageHandler,
                    'link': linkHandler,
                    'divider': function() {
                        var range = this.quill.getSelection(true);
                        this.quill.insertText(range.index, '\n', Quill.sources.USER);
                        this.quill.insertEmbed(range.index + 1, 'divider', true, Quill.sources.USER);
                        this.quill.setSelection(range.index + 2, Quill.sources.SILENT);
                    }
                }
            }
        }
    });
}

// ===== Custom Image Handler =====

function imageHandler() {
    galleryMode = 'inline';
    document.getElementById('imageModalTitle').textContent = 'Insert Image';
    document.getElementById('imageModal').style.display = 'flex';
    // Reset gallery state
    document.getElementById('imageGalleryGrid').style.display = 'none';
    document.getElementById('imageGalleryGrid').innerHTML = '';
    var tabs = document.getElementById('galleryFolderTabs');
    if (tabs) tabs.style.display = 'none';
}

function closeImageModal() {
    document.getElementById('imageModal').style.display = 'none';
    galleryMode = 'inline';
}

function setupGalleryFolderTabs() {
    const tabs = document.getElementById('galleryFolderTabs');
    if (!tabs) return;
    tabs.querySelectorAll('.ib-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            galleryCurrentFolder = this.dataset.folder;
            loadImageGallery(galleryCurrentFolder);
        });
    });
}

function setupCoverBrowser() {
    const btn = document.getElementById('browseCoverImagesBtn');
    if (!btn) return;

    // Cover browser uses the same inline modal but in 'cover' mode
    btn.addEventListener('click', function() {
        galleryMode = 'cover';
        document.getElementById('imageModalTitle').textContent = 'Browse Images';
        document.getElementById('imageModal').style.display = 'flex';
        // Auto-load gallery
        loadImageGallery('blog');
    });

    // Also set up the separate cover browser modal if it exists
    const coverModal = document.getElementById('coverBrowserModal');
    if (coverModal) {
        const coverGrid = document.getElementById('coverBrowserGrid');
        const closeBtn = document.getElementById('coverBrowserClose');
        let coverFolder = 'blog';

        closeBtn.addEventListener('click', () => { coverModal.style.display = 'none'; });
        coverModal.addEventListener('click', (e) => {
            if (e.target === coverModal) coverModal.style.display = 'none';
        });

        document.getElementById('coverBrowserTabs').querySelectorAll('.ib-tab').forEach(tab => {
            tab.addEventListener('click', function() {
                document.getElementById('coverBrowserTabs').querySelectorAll('.ib-tab').forEach(t => t.classList.remove('active'));
                this.classList.add('active');
                coverFolder = this.dataset.folder;
                loadCoverBrowserImages(coverFolder, coverGrid, coverModal);
            });
        });

        async function loadCoverBrowserImages(folder, grid, modal) {
            grid.innerHTML = '<p style="grid-column:1/-1; text-align:center; opacity:0.6;">Loading...</p>';
            try {
                const res = await fetch(`/admin/news-editor/list-images?folder=${folder}`);
                const images = await res.json();
                if (images.length === 0) {
                    grid.innerHTML = '<p style="grid-column:1/-1; text-align:center; opacity:0.6;">No images in this folder.</p>';
                    return;
                }
                grid.innerHTML = images.map(img => `
                    <div class="ib-item" data-url="${escapeHtml(img.url)}">
                        <img src="${escapeHtml(img.url)}" alt="${escapeHtml(img.filename)}" loading="lazy">
                        <span class="ib-filename">${escapeHtml(img.filename)}</span>
                        <div class="ib-actions">
                            <button type="button" class="ib-select-btn" data-url="${escapeHtml(img.url)}">Select</button>
                            <button type="button" class="ib-delete-btn" data-url="${escapeHtml(img.url)}" title="Delete">&#128465;</button>
                        </div>
                    </div>
                `).join('');

                grid.querySelectorAll('.ib-select-btn').forEach(b => {
                    b.addEventListener('click', function(e) {
                        e.stopPropagation();
                        document.getElementById('imageUrl').value = this.dataset.url;
                        const event = new Event('input');
                        document.getElementById('imageUrl').dispatchEvent(event);
                        modal.style.display = 'none';
                    });
                });

                grid.querySelectorAll('.ib-delete-btn').forEach(b => {
                    b.addEventListener('click', function(e) {
                        e.stopPropagation();
                        deleteGalleryImage(this.dataset.url, grid);
                    });
                });
            } catch (e) {
                grid.innerHTML = '<p style="grid-column:1/-1; text-align:center; color:#e74c3c;">Failed to load images.</p>';
            }
        }
    }
}

function triggerInlineUpload() {
    document.getElementById('inlineImageFile').click();
}

function setupInlineImageUpload() {
    const fileInput = document.getElementById('inlineImageFile');
    if (!fileInput) return;

    fileInput.addEventListener('change', async function(e) {
        const file = e.target.files[0];
        if (!file) return;

        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
        if (!allowedTypes.includes(file.type)) {
            showMessage('Invalid file type. Please use PNG, JPG, JPEG, GIF, or WEBP.', 'error');
            fileInput.value = '';
            return;
        }

        if (file.size > 50 * 1024 * 1024) {
            showMessage('File too large. Please use an image under 50MB.', 'error');
            fileInput.value = '';
            return;
        }

        try {
            const compressed = typeof compressImageFile === 'function' ? await compressImageFile(file) : file;

            const formData = new FormData();
            formData.append('image', compressed);

            const response = await fetch('/admin/news-editor/upload-image', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    insertImageIntoEditor(result.image_url);
                    closeImageModal();
                    showMessage('Image uploaded and inserted!', 'success');
                } else {
                    showMessage(result.error || 'Upload failed', 'error');
                }
            } else {
                showMessage('Upload failed. Please try again.', 'error');
            }
        } catch (error) {
            console.error('Inline upload error:', error);
            showMessage('Upload failed. Please try again.', 'error');
        }

        fileInput.value = '';
    });
}

let galleryCurrentFolder = 'blog';
let galleryMode = 'inline'; // 'inline' (for Quill) or 'cover' (for cover image)

async function loadImageGallery(folder) {
    const grid = document.getElementById('imageGalleryGrid');
    const tabs = document.getElementById('galleryFolderTabs');
    grid.style.display = 'grid';
    tabs.style.display = 'flex';

    if (folder) galleryCurrentFolder = folder;

    // Update active tab
    tabs.querySelectorAll('.ib-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.folder === galleryCurrentFolder);
    });

    grid.innerHTML = '<p style="color: var(--noir-silver); grid-column: 1/-1; text-align: center;">Loading images...</p>';

    try {
        const response = await fetch(`/admin/news-editor/list-images?folder=${galleryCurrentFolder}`);
        if (!response.ok) throw new Error('Failed to load images');

        const images = await response.json();

        if (images.length === 0) {
            grid.innerHTML = '<p style="color: var(--noir-silver); grid-column: 1/-1; text-align: center;">No images in this folder.</p>';
            return;
        }

        grid.innerHTML = images.map(img => `
            <div class="gallery-item" data-url="${escapeHtml(img.url)}">
                <img src="${escapeHtml(img.url)}" alt="${escapeHtml(img.filename)}" loading="lazy">
                <span class="gallery-filename">${escapeHtml(img.filename)}</span>
                <div class="ib-actions">
                    <button type="button" class="ib-select-btn" data-url="${escapeHtml(img.url)}">Select</button>
                    <button type="button" class="ib-delete-btn" data-url="${escapeHtml(img.url)}" title="Delete">&#128465;</button>
                </div>
            </div>
        `).join('');

        grid.querySelectorAll('.ib-select-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                selectGalleryImage(this.dataset.url);
            });
        });

        grid.querySelectorAll('.ib-delete-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                deleteGalleryImage(this.dataset.url, grid);
            });
        });
    } catch (error) {
        console.error('Error loading gallery:', error);
        grid.innerHTML = '<p style="color: #e74c3c; grid-column: 1/-1; text-align: center;">Failed to load images.</p>';
    }
}

async function deleteGalleryImage(url, grid) {
    try {
        const res = await fetch('/admin/news-editor/delete-image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const data = await res.json();

        if (data.in_use) {
            const refs = data.references.map(r => `- ${r.type}: ${r.title}`).join('\n');
            if (!confirm(`This image is in use:\n${refs}\n\nDelete anyway?`)) return;
            const res2 = await fetch('/admin/news-editor/delete-image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, force: true })
            });
            const data2 = await res2.json();
            if (!data2.success) { alert('Delete failed: ' + (data2.error || 'Unknown error')); return; }
        } else if (!data.success) {
            alert('Delete failed: ' + (data.error || 'Unknown error'));
            return;
        }

        // Reload grid
        loadImageGallery(galleryCurrentFolder);
    } catch (e) {
        alert('Delete error: ' + e.message);
    }
}

function selectGalleryImage(url) {
    if (galleryMode === 'cover') {
        document.getElementById('imageUrl').value = url;
        const event = new Event('input');
        document.getElementById('imageUrl').dispatchEvent(event);
        closeImageModal();
    } else {
        insertImageIntoEditor(url);
        closeImageModal();
    }
}

function promptImageUrl() {
    const url = prompt('Enter image URL:');
    if (url && url.trim()) {
        insertImageIntoEditor(url.trim());
        closeImageModal();
    }
}

function insertImageIntoEditor(url) {
    const range = quill.getSelection(true);
    quill.insertEmbed(range.index, 'image', url);
    quill.setSelection(range.index + 1);
}

// ===== Custom Link Handler =====

function linkHandler() {
    const range = quill.getSelection();
    if (!range) return;

    const currentFormat = quill.getFormat(range);
    if (currentFormat.link) {
        // Remove link if already linked
        quill.format('link', false);
        return;
    }

    let url = prompt('Enter URL:');
    if (!url || !url.trim()) return;
    url = url.trim();

    // Smart URL normalization
    if (url.match(/^mailto:/i) || url.match(/^tel:/i)) {
        // Already proper protocol
    } else if (url.match(/^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/)) {
        // Bare domain like example.com - add https://
        url = 'https://' + url;
    } else if (!url.match(/^https?:\/\//i)) {
        url = 'https://' + url;
    }

    quill.format('link', url);
}

// ===== Search and filter setup =====

function setupFilters() {
    const searchInput = document.getElementById('articleSearch');
    const filterSelect = document.getElementById('articleFilter');
    if (searchInput) searchInput.addEventListener('input', applyFilters);
    if (filterSelect) filterSelect.addEventListener('change', applyFilters);
}

function applyFilters() {
    const search = (document.getElementById('articleSearch').value || '').toLowerCase().trim();
    const filter = (document.getElementById('articleFilter').value || 'all');

    let filtered = allArticles;
    if (filter !== 'all') {
        filtered = filtered.filter(a => (a.status || 'published') === filter);
    }
    if (search) {
        filtered = filtered.filter(a =>
            a.title.toLowerCase().includes(search) ||
            (a.slug || '').toLowerCase().includes(search)
        );
    }
    displayArticles(filtered, true);
}

function updateArticleCount(count) {
    const el = document.getElementById('articleCount');
    if (el) el.textContent = count + ' article' + (count !== 1 ? 's' : '');
}

// ===== Populate category dropdown =====

async function loadCategories() {
    const select = document.getElementById('categoryName');
    if (!select) return;
    try {
        const res = await fetch('/news/api/categories');
        if (!res.ok) return;
        const data = await res.json();
        const categories = data.categories || [];
        if (categories.length === 0) return;
        categories.forEach(function(cat) {
            const opt = document.createElement('option');
            opt.value = cat.name;
            opt.textContent = cat.name;
            select.appendChild(opt);
        });
    } catch (e) {
        console.log('[Editor] Could not load categories');
    }
}

// ===== Form setup =====

function setupForm() {
    const form = document.getElementById('articleForm');
    const cancelBtn = document.getElementById('cancelBtn');
    const publishBtn = document.getElementById('publishBtn');
    const draftBtn = document.getElementById('draftBtn');

    form.addEventListener('submit', (e) => e.preventDefault());

    publishBtn.addEventListener('click', () => handleSubmit('published'));
    draftBtn.addEventListener('click', () => handleSubmit('draft'));
    cancelBtn.addEventListener('click', cancelEdit);
}

// ===== Image upload setup (cover image) =====

function setupImageUpload() {
    const imageFile = document.getElementById('imageFile');
    const uploadProgress = document.getElementById('uploadProgress');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');

    imageFile.addEventListener('change', async function(e) {
        const file = e.target.files[0];
        if (!file) return;

        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
        if (!allowedTypes.includes(file.type)) {
            showMessage('Invalid file type. Please use PNG, JPG, JPEG, GIF, or WEBP.', 'error');
            imageFile.value = '';
            return;
        }

        if (file.size > 50 * 1024 * 1024) {
            showMessage('File too large. Please use an image under 50MB.', 'error');
            imageFile.value = '';
            return;
        }

        uploadProgress.style.display = 'block';
        progressFill.style.width = '0%';
        progressText.textContent = 'Compressing...';

        try {
            const compressed = typeof compressImageFile === 'function' ? await compressImageFile(file) : file;
            progressText.textContent = 'Uploading...';

            const formData = new FormData();
            formData.append('image', compressed);

            const xhr = new XMLHttpRequest();

            xhr.upload.addEventListener('progress', function(e) {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    progressFill.style.width = percentComplete + '%';
                    progressText.textContent = `Uploading... ${Math.round(percentComplete)}%`;
                }
            });

            xhr.addEventListener('load', function() {
                uploadProgress.style.display = 'none';

                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    if (response.success) {
                        document.getElementById('imageUrl').value = response.image_url;
                        const event = new Event('input');
                        document.getElementById('imageUrl').dispatchEvent(event);
                        showMessage('Image uploaded successfully!', 'success');
                    } else {
                        showMessage(response.error || 'Upload failed', 'error');
                    }
                } else {
                    try {
                        const error = JSON.parse(xhr.responseText);
                        showMessage(error.error || 'Upload failed', 'error');
                    } catch (e) {
                        showMessage('Upload failed. Please try again.', 'error');
                    }
                }

                imageFile.value = '';
            });

            xhr.addEventListener('error', function() {
                uploadProgress.style.display = 'none';
                showMessage('Upload failed. Please check your connection.', 'error');
                imageFile.value = '';
            });

            xhr.open('POST', '/admin/news-editor/upload-image');
            xhr.send(formData);

        } catch (error) {
            console.error('Upload error:', error);
            uploadProgress.style.display = 'none';
            showMessage('Upload failed. Please try again.', 'error');
            imageFile.value = '';
        }
    });
}

// ===== Image preview setup (cover image) =====

function setupImagePreview() {
    const imageUrlInput = document.getElementById('imageUrl');
    const imagePreview = document.getElementById('imagePreview');
    const previewImg = document.getElementById('previewImg');

    imageUrlInput.addEventListener('input', function() {
        const url = this.value.trim();
        if (url) {
            imagePreview.style.display = 'block';
            previewImg.src = url;

            previewImg.onload = function() {
                imagePreview.style.display = 'block';
            };

            previewImg.onerror = function() {
                if (url.startsWith('/') || url.startsWith('./') || url.startsWith('../')) {
                    return;
                }
                imagePreview.style.display = 'none';
            };
        } else {
            imagePreview.style.display = 'none';
        }
    });
}

// ===== Load articles =====

async function loadArticles() {
    try {
        const response = await fetch('/admin/news-editor/api/articles');

        if (!response.ok) {
            if (response.status === 401) {
                window.location.href = '/admin/login';
                return;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const articles = await response.json();
        allArticles = articles;
        updateArticleCount(articles.length);
        displayArticles(articles);
    } catch (error) {
        console.error('Error loading articles:', error);
        const container = document.getElementById('articlesList');
        if (error.message.includes('401')) {
            container.innerHTML = '<p class="articles-error">Authentication required. Please log in.</p>';
        } else {
            container.innerHTML = '<p class="articles-error">Error loading articles. Please try again.</p>';
        }
    }
}

// ===== Display articles =====

function displayArticles(articles, isFiltered) {
    const container = document.getElementById('articlesList');
    updateArticleCount(articles.length);

    if (articles.length === 0) {
        container.innerHTML = isFiltered
            ? '<p class="articles-empty">No articles match your search.</p>'
            : '<p class="articles-empty">No articles yet. Create your first article!</p>';
        return;
    }

    const articlesHTML = articles.map(article => {
        const status = article.status || 'published';
        const isDraft = status === 'draft';
        const statusBadge = isDraft
            ? '<span class="status-badge status-draft">Draft</span>'
            : '<span class="status-badge status-published">Published</span>';
        const toggleBtn = isDraft
            ? '<button class="publish-btn" onclick="toggleArticleStatus(' + article.id + ')" title="Publish this article">Publish</button>'
            : '<button class="draft-btn-small" onclick="toggleArticleStatus(' + article.id + ')" title="Move to draft">Unpublish</button>';

        return `
            <div class="article-item">
                ${article.image_url ? `
                    <div class="article-item-image">
                        <img src="${escapeHtml(article.image_url)}" alt="${escapeHtml(article.title)}" loading="lazy">
                    </div>
                ` : ''}
                <div class="article-item-content">
                    <div class="article-item-title">
                        ${escapeHtml(article.title)}
                        ${statusBadge}
                    </div>
                    <div class="article-item-slug">/${escapeHtml(article.slug)}</div>
                    <div class="article-item-date">${formatDate(article.created_at)}</div>
                    <div class="article-actions">
                        ${isDraft ? '' : '<a href="/news/' + escapeHtml(article.slug) + '" target="_blank" class="view-btn">View</a>'}
                        <button class="edit-btn" onclick="editArticle(${article.id})">Edit</button>
                        ${toggleBtn}
                        <button class="email-btn" onclick="sendArticleEmail(${article.id})" title="Send/Resend email to subscribers">Send Email</button>
                        <div class="crosspost-dropdown">
                            <button class="crosspost-btn" onclick="this.nextElementSibling.classList.toggle('show')">Cross-Post ▾</button>
                            <div class="crosspost-menu">
                                <div class="crosspost-item" onclick="crosspostArticle(${article.id},'linkedin')">${article.crossposted_linkedin ? '✓ ' : ''}LinkedIn</div>
                                <div class="crosspost-item" onclick="crosspostArticle(${article.id},'medium')">${article.crossposted_medium ? '✓ ' : ''}Medium</div>
                                <div class="crosspost-item" onclick="crosspostArticle(${article.id},'substack')">${article.crossposted_substack ? '✓ ' : ''}Substack</div>
                            </div>
                        </div>
                        <button class="delete-btn" onclick="deleteArticle(${article.id})">Delete</button>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = articlesHTML;
}

// ===== Handle form submission =====

async function handleSubmit(status) {
    const title = document.getElementById('title').value.trim();
    const content = quill.root.innerHTML.trim();
    const imageUrl = document.getElementById('imageUrl').value.trim();

    // Check if Quill is empty (only has the default empty paragraph)
    const isEmpty = !quill.getText().trim();

    if (!title || isEmpty) {
        alert('Please fill in both title and content fields.');
        return;
    }

    const categoryName = document.getElementById('categoryName').value.trim();

    // Collect SEO & author fields
    const excerpt = (document.getElementById('excerpt').value || '').trim() || null;
    const metaTitle = (document.getElementById('metaTitle').value || '').trim() || null;
    const metaDescription = (document.getElementById('metaDescription').value || '').trim() || null;
    const authorName = (document.getElementById('authorName').value || '').trim() || null;
    const authorEmail = (document.getElementById('authorEmail').value || '').trim() || null;
    const sourceId = (document.getElementById('sourceId').value || '').trim() || null;
    const sourceUrl = (document.getElementById('sourceUrl').value || '').trim() || null;

    const data = {
        title,
        content,
        image_url: imageUrl || null,
        category_name: categoryName || null,
        status: status,
        excerpt: excerpt,
        meta_title: metaTitle,
        meta_description: metaDescription,
        author_name: authorName,
        author_email: authorEmail,
        source_id: sourceId,
        source_url: sourceUrl
    };

    console.log('Submitting data:', data);

    const publishBtn = document.getElementById('publishBtn');
    const draftBtn = document.getElementById('draftBtn');
    const activeBtn = status === 'published' ? publishBtn : draftBtn;
    const originalText = activeBtn.textContent;

    publishBtn.disabled = true;
    draftBtn.disabled = true;
    activeBtn.textContent = 'Saving...';

    try {
        let response;
        if (editingArticleId) {
            console.log(`Updating article ${editingArticleId} with status:`, status);
            response = await fetch(`/admin/news-editor/api/articles/${editingArticleId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        } else {
            console.log('Creating new article with status:', status);
            response = await fetch('/admin/news-editor/api/articles', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }

        if (response.ok) {
            const result = await response.json();
            console.log('Server response:', result);
            resetForm();
            loadArticles();

            showMessage(result.message || 'Article saved successfully!', 'success');

            if (!editingArticleId && result.slug && status === 'published') {
                setTimeout(() => {
                    if (confirm('Article published! Would you like to view it?')) {
                        window.open(`/news/${result.slug}`, '_blank');
                    }
                }, 1000);
            }
        } else {
            const error = await response.json();
            console.error('Server error response:', error);
            throw new Error(error.error || 'Failed to save article');
        }
    } catch (error) {
        console.error('Error saving article:', error);
        showMessage(error.message || 'Error saving article. Please try again.', 'error');
    } finally {
        activeBtn.textContent = originalText;
        publishBtn.disabled = false;
        draftBtn.disabled = false;
    }
}

// ===== Edit article =====

async function editArticle(id) {
    try {
        const response = await fetch(`/admin/news-editor/api/articles/${id}`);

        if (!response.ok) {
            throw new Error('Failed to load article');
        }

        const article = await response.json();

        document.getElementById('articleId').value = article.id;
        document.getElementById('title').value = article.title;
        document.getElementById('imageUrl').value = article.image_url || '';
        document.getElementById('categoryName').value = article.category_name || '';

        // Set Quill content
        quill.root.innerHTML = article.content || '';

        // Populate SEO & author fields
        document.getElementById('excerpt').value = article.excerpt || '';
        document.getElementById('metaTitle').value = article.meta_title || '';
        document.getElementById('metaDescription').value = article.meta_description || '';
        document.getElementById('authorName').value = article.author_name || '';
        document.getElementById('authorEmail').value = article.author_email || '';
        document.getElementById('sourceId').value = article.source_id || '';
        document.getElementById('sourceUrl').value = article.source_url || '';

        // Trigger image preview
        if (article.image_url) {
            const event = new Event('input');
            document.getElementById('imageUrl').dispatchEvent(event);
        }

        // Show status indicator
        const status = article.status || 'published';
        document.getElementById('statusIndicator').style.display = 'block';
        document.getElementById('currentStatus').textContent = status === 'draft' ? 'Draft' : 'Published';
        document.getElementById('currentStatus').className = status === 'draft' ? 'status-draft' : 'status-published';

        // Update button labels
        document.getElementById('formTitle').textContent = 'Edit Article';
        document.getElementById('publishBtn').textContent = status === 'draft' ? 'Publish Article' : 'Update & Publish';
        document.getElementById('draftBtn').textContent = 'Update as Draft';
        document.getElementById('cancelBtn').style.display = 'inline-block';
        editingArticleId = id;

        // Scroll to form
        document.querySelector('.editor-form').scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });

    } catch (error) {
        console.error('Error loading article:', error);
        showMessage('Error loading article for editing.', 'error');
    }
}

// ===== Toggle article status =====

async function toggleArticleStatus(id) {
    const article = await fetch(`/admin/news-editor/api/articles/${id}`).then(r => r.json());
    const currentStatus = article.status || 'published';
    const newStatus = currentStatus === 'draft' ? 'published' : 'draft';
    const confirmMsg = currentStatus === 'draft'
        ? 'Publish this article? It will be visible to the public.'
        : 'Move this article to draft? It will no longer be visible to the public.';

    if (!confirm(confirmMsg)) {
        return;
    }

    try {
        const response = await fetch(`/admin/news-editor/api/articles/${id}/toggle-status`, {
            method: 'POST'
        });

        if (response.ok) {
            const result = await response.json();
            showMessage(result.message, 'success');
            loadArticles();

            if (editingArticleId === id) {
                document.getElementById('currentStatus').textContent = result.status === 'draft' ? 'Draft' : 'Published';
                document.getElementById('currentStatus').className = result.status === 'draft' ? 'status-draft' : 'status-published';
                document.getElementById('publishBtn').textContent = result.status === 'draft' ? 'Publish Article' : 'Update & Publish';
            }
        } else {
            const error = await response.json();
            throw new Error(error.error || 'Failed to toggle status');
        }
    } catch (error) {
        console.error('Error toggling article status:', error);
        showMessage('Error changing article status. Please try again.', 'error');
    }
}

// ===== Send article email =====

async function sendArticleEmail(id) {
    const emailBtn = document.querySelector(`button[onclick="sendArticleEmail(${id})"]`);

    let article = null;
    try {
        const articleRes = await fetch(`/admin/news-editor/api/articles/${id}`);
        if (articleRes.ok) article = await articleRes.json();
    } catch (e) {}

    let autoFeed = null;
    let autoFeedLabel = null;
    try {
        const catRes = await fetch('/news/api/categories');
        if (catRes.ok) {
            const catData = await catRes.json();
            const match = (catData.categories || []).find(
                c => article && c.name === article.category_name && c.feed
            );
            if (match) {
                autoFeed = match.feed;
                const feedsRes = await fetch('/api/subscribers/feeds');
                if (feedsRes.ok) {
                    const feedsData = await feedsRes.json();
                    const feedMatch = (feedsData.feeds || []).find(f => f.id === autoFeed);
                    autoFeedLabel = feedMatch ? feedMatch.label : autoFeed;
                }
            }
        }
    } catch (e) {}

    let feedChoice = null;
    if (autoFeed) {
        const label = autoFeedLabel || autoFeed;
        if (!confirm(`Send this article to ${label} subscribers and All Updates subscribers?`)) return;
        feedChoice = autoFeed;
    } else {
        if (!confirm('Send this article to all subscribers via email?')) return;
        feedChoice = '__all__';
    }

    const originalText = emailBtn.textContent;
    emailBtn.disabled = true;
    emailBtn.textContent = 'Sending...';

    try {
        const body = { feed: feedChoice };
        const response = await fetch(`/admin/news-editor/api/articles/${id}/send-email`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        const result = await response.json();

        if (response.ok) {
            if (result.success) {
                const label = (feedChoice && feedChoice !== '__all__')
                    ? (autoFeedLabel || feedChoice)
                    : 'all';
                showMessage(`Email sent to ${result.subscriber_count} subscribers (${label})!`, 'success');
            } else {
                showMessage(result.message || 'No subscribers found', 'info');
            }
        } else {
            throw new Error(result.error || 'Failed to send email');
        }
    } catch (error) {
        console.error('Error sending article email:', error);
        showMessage('Failed to send email: ' + error.message, 'error');
    } finally {
        emailBtn.disabled = false;
        emailBtn.textContent = originalText;
    }
}

// ===== Cross-post article =====

async function crosspostArticle(id, platform) {
    // Close any open dropdown
    document.querySelectorAll('.crosspost-menu.show').forEach(m => m.classList.remove('show'));

    const platformName = platform.charAt(0).toUpperCase() + platform.slice(1);
    if (!confirm(`Cross-post this article to ${platformName}?`)) return;

    try {
        const response = await fetch(`/admin/news-editor/api/articles/${id}/crosspost/${platform}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await response.json();

        if (response.ok && result.success) {
            let msg = `Posted to ${platformName}!`;
            if (result.url) msg += `\n\nURL: ${result.url}`;
            showMessage(msg, 'success');
            loadArticles();
        } else {
            showMessage(result.error || `Failed to post to ${platformName}`, 'error');
        }
    } catch (error) {
        console.error('Error cross-posting article:', error);
        showMessage('Failed to cross-post: ' + error.message, 'error');
    }
}

// Close crosspost dropdown when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.crosspost-dropdown')) {
        document.querySelectorAll('.crosspost-menu.show').forEach(m => m.classList.remove('show'));
    }
});

// ===== Delete article =====

async function deleteArticle(id) {
    if (!confirm('Are you sure you want to delete this article? This action cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch(`/admin/news-editor/api/articles/${id}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            loadArticles();
            showMessage('Article deleted successfully.', 'success');

            if (editingArticleId === id) {
                resetForm();
            }
        } else {
            const error = await response.json();
            throw new Error(error.error || 'Failed to delete article');
        }
    } catch (error) {
        console.error('Error deleting article:', error);
        showMessage('Error deleting article. Please try again.', 'error');
    }
}

// ===== Cancel edit =====

function cancelEdit() {
    resetForm();
}

// ===== Reset form =====

function resetForm() {
    document.getElementById('articleForm').reset();
    document.getElementById('articleId').value = '';
    document.getElementById('formTitle').textContent = 'Create New Article';
    document.getElementById('publishBtn').textContent = 'Publish Article';
    document.getElementById('draftBtn').textContent = 'Save as Draft';
    document.getElementById('cancelBtn').style.display = 'none';
    document.getElementById('statusIndicator').style.display = 'none';
    document.getElementById('imagePreview').style.display = 'none';
    document.getElementById('uploadProgress').style.display = 'none';

    // Clear Quill
    quill.setContents([]);

    // Clear SEO & author fields
    document.getElementById('excerpt').value = '';
    document.getElementById('metaTitle').value = '';
    document.getElementById('metaDescription').value = '';
    document.getElementById('authorName').value = '';
    document.getElementById('authorEmail').value = '';
    document.getElementById('sourceId').value = '';
    document.getElementById('sourceUrl').value = '';

    editingArticleId = null;
}

// ===== Show message =====

function showMessage(message, type = 'info') {
    const existingMessage = document.querySelector('.message');
    if (existingMessage) {
        existingMessage.remove();
    }

    const messageEl = document.createElement('div');
    messageEl.className = `message message-${type}`;
    messageEl.textContent = message;

    const container = document.querySelector('.editor-container');
    container.insertBefore(messageEl, container.firstChild);

    setTimeout(() => {
        if (messageEl.parentNode) {
            messageEl.remove();
        }
    }, 5000);

    messageEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ===== Utility functions =====

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
