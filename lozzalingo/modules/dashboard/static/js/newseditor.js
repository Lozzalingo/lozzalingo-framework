// News Editor functionality with image upload
document.addEventListener('DOMContentLoaded', function() {
    loadArticles();
    setupForm();
    setupImagePreview();
    setupImageUpload();
    initializeFilters();
});

let editingArticleId = null;
let allArticles = [];  // Store all articles for filtering

// Form setup
function setupForm() {
    const form = document.getElementById('articleForm');
    const cancelBtn = document.getElementById('cancelBtn');
    const publishBtn = document.getElementById('publishBtn');
    const draftBtn = document.getElementById('draftBtn');

    // Remove form submit handler, use button handlers instead
    form.addEventListener('submit', (e) => e.preventDefault());

    publishBtn.addEventListener('click', () => handleSubmit('published'));
    draftBtn.addEventListener('click', () => handleSubmit('draft'));
    cancelBtn.addEventListener('click', cancelEdit);
}

// Image upload setup
function setupImageUpload() {
    const imageFile = document.getElementById('imageFile');
    const uploadProgress = document.getElementById('uploadProgress');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    
    imageFile.addEventListener('change', async function(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        // Validate file type
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
        if (!allowedTypes.includes(file.type)) {
            showMessage('Invalid file type. Please use PNG, JPG, JPEG, GIF, or WEBP.', 'error');
            imageFile.value = '';
            return;
        }
        
        // Validate file size (10MB limit)
        if (file.size > 10 * 1024 * 1024) {
            showMessage('File too large. Please use an image under 10MB.', 'error');
            imageFile.value = '';
            return;
        }
        
        // Show upload progress
        uploadProgress.style.display = 'block';
        progressFill.style.width = '0%';
        progressText.textContent = 'Uploading...';
        
        try {
            const formData = new FormData();
            formData.append('image', file);
            
            const xhr = new XMLHttpRequest();
            
            // Track upload progress
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
                        // Set the image URL and trigger preview
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
                
                // Clear file input
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

// Filter initialization
function initializeFilters() {
    const searchInput = document.getElementById('articleSearch');
    const filterSelect = document.getElementById('articleFilter');

    if (searchInput) {
        searchInput.addEventListener('input', filterArticles);
    }
    if (filterSelect) {
        filterSelect.addEventListener('change', filterArticles);
    }
}

// Filter articles based on search and filter criteria
function filterArticles() {
    const searchInput = document.getElementById('articleSearch');
    const filterSelect = document.getElementById('articleFilter');

    const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';
    const filterType = filterSelect ? filterSelect.value : 'all';

    let filtered = allArticles.filter(article => {
        // Search filter - check title and content
        const matchesSearch = !searchTerm ||
            article.title.toLowerCase().includes(searchTerm) ||
            (article.content && article.content.toLowerCase().includes(searchTerm)) ||
            (article.slug && article.slug.toLowerCase().includes(searchTerm));

        // Status filter
        let matchesFilter = true;
        const status = article.status || 'published';
        switch (filterType) {
            case 'published':
                matchesFilter = status === 'published';
                break;
            case 'draft':
                matchesFilter = status === 'draft';
                break;
            case 'all':
            default:
                matchesFilter = true;
        }

        return matchesSearch && matchesFilter;
    });

    renderArticles(filtered);
    updateArticleCount(filtered.length, allArticles.length);
}

// Update article count display
function updateArticleCount(shown, total) {
    const countEl = document.getElementById('articleCount');
    if (countEl) {
        if (shown === total) {
            countEl.textContent = `${total} article${total !== 1 ? 's' : ''}`;
        } else {
            countEl.textContent = `${shown} of ${total} article${total !== 1 ? 's' : ''}`;
        }
    }
}

// Image preview setup
function setupImagePreview() {
    const imageUrlInput = document.getElementById('imageUrl');
    const imagePreview = document.getElementById('imagePreview');
    const previewImg = document.getElementById('previewImg');
    
    imageUrlInput.addEventListener('input', function() {
        const url = this.value.trim();
        if (url) {
            // Show preview for any URL (relative or absolute)
            imagePreview.style.display = 'block';
            previewImg.src = url;
            
            // Handle load success
            previewImg.onload = function() {
                imagePreview.style.display = 'block';
            };
            
            // Handle load errors - only hide for clearly invalid URLs
            previewImg.onerror = function() {
                // Keep preview visible for relative URLs (they should work on the server)
                if (url.startsWith('/') || url.startsWith('./') || url.startsWith('../')) {
                    console.log('Relative URL - keeping preview visible:', url);
                    return;
                }
                
                // Hide only for absolute URLs that fail to load
                console.log('Image failed to load:', url);
                imagePreview.style.display = 'none';
            };
        } else {
            imagePreview.style.display = 'none';
        }
    });
}

// Load articles for management
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
        allArticles = articles;  // Store for filtering
        renderArticles(articles);
        updateArticleCount(articles.length, articles.length);
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

// Render articles in management list
function renderArticles(articles) {
    const container = document.getElementById('articlesList');

    if (articles.length === 0) {
        // Check if this is due to filtering or no articles at all
        const hasFilters = (document.getElementById('articleSearch')?.value || document.getElementById('articleFilter')?.value !== 'all');
        if (hasFilters && allArticles.length > 0) {
            container.innerHTML = '<p class="articles-empty">No articles match your search/filter criteria.</p>';
        } else {
            container.innerHTML = '<p class="articles-empty">No articles yet. Create your first article!</p>';
        }
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
                        <button class="delete-btn" onclick="deleteArticle(${article.id})">Delete</button>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = articlesHTML;
}

// Handle form submission
async function handleSubmit(status) {
    const title = document.getElementById('title').value.trim();
    const content = document.getElementById('content').value.trim();
    const imageUrl = document.getElementById('imageUrl').value.trim();

    if (!title || !content) {
        alert('Please fill in both title and content fields.');
        return;
    }

    // Ensure image URL is not empty string when sending
    const data = {
        title,
        content,
        image_url: imageUrl || null,
        status: status
    };

    console.log('Submitting data:', data);

    const publishBtn = document.getElementById('publishBtn');
    const draftBtn = document.getElementById('draftBtn');
    const activeBtn = status === 'published' ? publishBtn : draftBtn;
    const originalText = activeBtn.textContent;

    // Disable both buttons during submission
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

            // Show success message
            showMessage(result.message || 'Article saved successfully!', 'success');

            // If creating new published article, optionally redirect to view it
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

// Edit article
async function editArticle(id) {
    try {
        const response = await fetch(`/admin/news-editor/api/articles/${id}`);

        if (!response.ok) {
            throw new Error('Failed to load article');
        }

        const article = await response.json();

        document.getElementById('articleId').value = article.id;
        document.getElementById('title').value = article.title;
        document.getElementById('content').value = article.content;
        document.getElementById('imageUrl').value = article.image_url || '';

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

// Toggle article status
async function toggleArticleStatus(id) {
    const article = await fetch(`/admin/news-editor/api/articles/${id}`).then(r => r.json());
    const currentStatus = article.status || 'published';
    const newStatus = currentStatus === 'draft' ? 'published' : 'draft';
    const confirmMsg = currentStatus === 'draft'
        ? 'Publish this article? Subscribers will be notified via email.'
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

            // If we're currently editing this article, update the status indicator
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

// Send article email to subscribers
async function sendArticleEmail(id) {
    if (!confirm('Send this article to all subscribers via email?')) {
        return;
    }

    const emailBtn = document.querySelector(`button[onclick="sendArticleEmail(${id})"]`);
    const originalText = emailBtn.textContent;

    // Show loading state
    emailBtn.disabled = true;
    emailBtn.textContent = 'Sending...';

    try {
        const response = await fetch(`/admin/news-editor/api/articles/${id}/send-email`, {
            method: 'POST'
        });

        const result = await response.json();

        if (response.ok) {
            if (result.success) {
                showMessage(`Email sent successfully to ${result.subscriber_count} subscribers!`, 'success');
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
        // Restore button state
        emailBtn.disabled = false;
        emailBtn.textContent = originalText;
    }
}

// Delete article
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
            
            // If we're currently editing this article, reset the form
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

// Cancel edit
function cancelEdit() {
    resetForm();
}

// Reset form
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
    editingArticleId = null;
}

// Show message to user
function showMessage(message, type = 'info') {
    // Remove any existing messages
    const existingMessage = document.querySelector('.message');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    // Create message element
    const messageEl = document.createElement('div');
    messageEl.className = `message message-${type}`;
    messageEl.textContent = message;
    
    // Insert at top of editor container
    const container = document.querySelector('.editor-container');
    container.insertBefore(messageEl, container.firstChild);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (messageEl.parentNode) {
            messageEl.remove();
        }
    }, 5000);
    
    // Scroll to message
    messageEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Utility functions
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