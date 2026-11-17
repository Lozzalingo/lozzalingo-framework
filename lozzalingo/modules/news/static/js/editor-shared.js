/**
 * Shared Quill editor blots and utilities.
 *
 * Loaded by BOTH the news editor (newseditor.js) and the projects editor
 * (projects_editor.html). Any rich-content feature that should work in both
 * editors lives here so the implementation stays in sync.
 *
 * Requires: Quill must be loaded before this script.
 */

(function () {
    'use strict';

    if (typeof Quill === 'undefined') {
        console.error('[EditorShared] Quill is not loaded');
        return;
    }

    var BlockEmbed = Quill.import('blots/block/embed');

    // =========================================================================
    // Horizontal Rule / Divider
    // =========================================================================

    class DividerBlot extends BlockEmbed {}
    DividerBlot.blotName = 'divider';
    DividerBlot.tagName = 'hr';
    Quill.register(DividerBlot, true);

    // =========================================================================
    // YouTube Embed
    // =========================================================================

    /**
     * Extract a YouTube video ID from common URL formats.
     * Returns the 11-char ID or null.
     */
    function extractYouTubeId(url) {
        if (!url) return null;
        url = url.trim();
        var patterns = [
            /[?&]v=([a-zA-Z0-9_-]{11})/,        // youtube.com/watch?v=
            /youtu\.be\/([a-zA-Z0-9_-]{11})/,    // youtu.be/
            /\/embed\/([a-zA-Z0-9_-]{11})/,       // youtube.com/embed/
            /\/shorts\/([a-zA-Z0-9_-]{11})/       // youtube.com/shorts/
        ];
        for (var i = 0; i < patterns.length; i++) {
            var m = url.match(patterns[i]);
            if (m) return m[1];
        }
        return null;
    }

    class YouTubeBlot extends BlockEmbed {
        static create(videoId) {
            var node = super.create();
            node.setAttribute('contenteditable', 'false');
            var iframe = document.createElement('iframe');
            iframe.setAttribute('src', 'https://www.youtube.com/embed/' + videoId);
            iframe.setAttribute('frameborder', '0');
            iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
            iframe.setAttribute('allowfullscreen', 'true');
            node.appendChild(iframe);
            return node;
        }

        static value(node) {
            var iframe = node.querySelector('iframe');
            if (!iframe) return '';
            var src = iframe.getAttribute('src') || '';
            var m = src.match(/\/embed\/([a-zA-Z0-9_-]{11})/);
            return m ? m[1] : src;
        }
    }
    YouTubeBlot.blotName = 'youtube';
    YouTubeBlot.tagName = 'div';
    YouTubeBlot.className = 'ql-youtube-embed';
    Quill.register(YouTubeBlot, true);

    /**
     * Standard YouTube toolbar handler.
     * Prompts for a URL, extracts the video ID, and inserts the embed.
     * Bind to the Quill toolbar: handlers: { 'youtube': youtubeHandler }
     */
    function youtubeHandler() {
        var url = prompt('YouTube URL:');
        if (!url) return;
        var videoId = extractYouTubeId(url);
        if (!videoId) {
            alert('Could not parse YouTube URL. Try a youtube.com/watch, youtu.be, or youtube.com/shorts link.');
            return;
        }
        var range = this.quill.getSelection(true);
        this.quill.insertText(range.index, '\n', Quill.sources.USER);
        this.quill.insertEmbed(range.index + 1, 'youtube', videoId, Quill.sources.USER);
        this.quill.setSelection(range.index + 2, Quill.sources.SILENT);
    }

    // =========================================================================
    // Self-hosted Video Embed
    // =========================================================================

    class VideoBlot extends BlockEmbed {
        static create(value) {
            var node = super.create();
            var wrapper = document.createElement('div');
            wrapper.style.cssText = 'max-width:720px;margin:1em 0;position:relative;';
            wrapper.setAttribute('contenteditable', 'false');

            var video = document.createElement('video');
            video.setAttribute('controls', '');
            video.setAttribute('playsinline', '');
            video.setAttribute('preload', 'metadata');
            video.style.cssText = 'width:100%;border-radius:8px;';
            if (value.poster) video.setAttribute('poster', value.poster);

            var source = document.createElement('source');
            source.setAttribute('src', value.src);
            source.setAttribute('type', value.type || 'video/mp4');
            video.appendChild(source);
            wrapper.appendChild(video);

            if (value.caption) {
                var cap = document.createElement('p');
                cap.style.cssText = 'text-align:center;font-size:0.85em;color:rgba(255,255,255,0.5);margin-top:0.5em;';
                cap.textContent = value.caption;
                wrapper.appendChild(cap);
            }

            node.appendChild(wrapper);
            return node;
        }

        static value(node) {
            var video = node.querySelector('video');
            var source = node.querySelector('source');
            var cap = node.querySelector('p');
            return {
                src: source ? source.getAttribute('src') : '',
                type: source ? source.getAttribute('type') : 'video/mp4',
                poster: video ? video.getAttribute('poster') : '',
                caption: cap ? cap.textContent : ''
            };
        }
    }
    VideoBlot.blotName = 'video-embed';
    VideoBlot.tagName = 'div';
    VideoBlot.className = 'ql-video-embed';
    Quill.register(VideoBlot, true);

    // =========================================================================
    // Self-hosted video upload (file picker -> host upload endpoint -> blot)
    // =========================================================================

    /**
     * Create a Quill toolbar handler that uploads a video file to the host
     * app's upload endpoint and inserts a video-embed blot with the returned
     * URL. Client-side video compression is not practical in the browser, so
     * the handler enforces a size cap instead; transcode server-side if
     * smaller files are needed.
     *
     * options:
     *   uploadUrl - POST endpoint accepting multipart/form-data. Falls back
     *               to window.BLOG_EDITOR_CONFIG.videoUploadUrl. The endpoint
     *               must return JSON {url: '...'} (or {src: '...'}), plus an
     *               optional {poster: '...'} thumbnail URL.
     *   fieldName - form field name for the file (default 'video').
     *   maxBytes  - size cap in bytes (default 200MB).
     *   accept    - file picker accept string (default 'video/mp4,video/webm').
     *   headers   - optional extra request headers (e.g. auth).
     *   onStatus  - optional function(message|null) for progress UI; called
     *               with a message when the upload starts and null when done.
     *
     * Bind to the Quill toolbar:
     *   handlers: { 'video-upload': EditorShared.createVideoUploadHandler({uploadUrl: '/admin/projects/upload-video'}) }
     */
    function createVideoUploadHandler(options) {
        options = options || {};
        return function () {
            var quill = this.quill;
            var cfg = (typeof window !== 'undefined' && window.BLOG_EDITOR_CONFIG) || {};
            var uploadUrl = options.uploadUrl || cfg.videoUploadUrl;
            if (!uploadUrl) {
                alert('Video uploads are not configured for this editor.');
                return;
            }
            var maxBytes = options.maxBytes || 200 * 1024 * 1024;
            var notify = options.onStatus || function (msg) {
                if (msg) console.log('[EditorShared] ' + msg);
            };
            var input = document.createElement('input');
            input.type = 'file';
            input.accept = options.accept || 'video/mp4,video/webm';
            input.onchange = function () {
                var file = input.files && input.files[0];
                if (!file) return;
                if (file.size > maxBytes) {
                    alert('Video is too large (' + Math.round(file.size / (1024 * 1024)) + 'MB). Maximum is ' + Math.round(maxBytes / (1024 * 1024)) + 'MB.');
                    return;
                }
                notify('Uploading video (' + Math.round(file.size / (1024 * 1024)) + 'MB)...');
                var fd = new FormData();
                fd.append(options.fieldName || 'video', file);
                fetch(uploadUrl, {
                    method: 'POST',
                    body: fd,
                    headers: options.headers || {},
                    credentials: 'same-origin'
                })
                    .then(function (res) {
                        if (!res.ok) throw new Error('Upload failed with status ' + res.status);
                        return res.json();
                    })
                    .then(function (data) {
                        var src = data.url || data.src;
                        if (!src) throw new Error('Upload response missing url');
                        var range = quill.getSelection(true);
                        quill.insertText(range.index, '\n', Quill.sources.USER);
                        quill.insertEmbed(range.index + 1, 'video-embed', {
                            src: src,
                            type: file.type || 'video/mp4',
                            poster: data.poster || '',
                            caption: ''
                        }, Quill.sources.USER);
                        quill.setSelection(range.index + 2, Quill.sources.SILENT);
                        notify(null);
                    })
                    .catch(function (err) {
                        console.error('[EditorShared] Video upload failed:', err);
                        notify(null);
                        alert('Video upload failed: ' + err.message);
                    });
            };
            input.click();
        };
    }

    /**
     * Give the custom video-upload toolbar button an icon (call after Quill init).
     */
    function addVideoUploadIcon() {
        var btn = document.querySelector('.ql-toolbar .ql-video-upload');
        if (btn) {
            btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" style="vertical-align:middle;"><path fill="currentColor" d="M17 10.5V7a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3.5l4 4v-11l-4 4zM10 9l4 3-4 3V9z"/></svg>';
            btn.title = 'Upload Video';
        }
    }

    // =========================================================================
    // Divider toolbar handler (shared)
    // =========================================================================

    function dividerHandler() {
        var range = this.quill.getSelection(true);
        this.quill.insertText(range.index, '\n', Quill.sources.USER);
        this.quill.insertEmbed(range.index + 1, 'divider', true, Quill.sources.USER);
        this.quill.setSelection(range.index + 2, Quill.sources.SILENT);
    }

    // =========================================================================
    // YouTube toolbar icon (call after Quill init)
    // =========================================================================

    function addYouTubeIcon() {
        var btn = document.querySelector('.ql-toolbar .ql-youtube');
        if (btn) {
            btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" style="vertical-align:middle;"><path fill="currentColor" d="M21.8 8.001a2.75 2.75 0 0 0-1.94-1.93C18.12 5.5 12 5.5 12 5.5s-6.12 0-7.86.57A2.75 2.75 0 0 0 2.2 8.001 28.7 28.7 0 0 0 1.75 12a28.7 28.7 0 0 0 .45 3.999 2.75 2.75 0 0 0 1.94 1.93c1.74.57 7.86.57 7.86.57s6.12 0 7.86-.57a2.75 2.75 0 0 0 1.94-1.93A28.7 28.7 0 0 0 22.25 12a28.7 28.7 0 0 0-.45-3.999zM9.75 15.02V8.98L15.5 12l-5.75 3.02z"/></svg>';
            btn.title = 'YouTube Embed';
        }
    }

    // =========================================================================
    // Clipboard paste interceptor for images
    // =========================================================================
    //
    // Without this, Quill embeds pasted images (screenshots, copies from the
    // browser) as base64 data URIs inline in the content. Large articles end
    // up with tens of MB of base64, killing page loads and causing 413s on
    // save. This interceptor uploads pasted images to the host app's upload
    // endpoint (the same one the image toolbar button uses) and inserts the
    // returned URL instead.

    var pasteUploadCounter = 0;

    function dataUrlToBlob(dataUrl) {
        try {
            var parts = dataUrl.split(',');
            var mime = (parts[0].match(/data:([^;]+)/) || [])[1] || 'image/png';
            var bin = atob(parts[1]);
            var arr = new Uint8Array(bin.length);
            for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
            return new Blob([arr], { type: mime });
        } catch (e) {
            return null;
        }
    }

    /**
     * Intercept pasted images, upload them, and insert URLs instead of
     * base64. Call once AFTER Quill init:
     *
     *   EditorShared.createPasteImageHandler(quill, { uploadUrl: '/admin/news-editor/upload-image' });
     *
     * Covers both paste paths:
     *   - image FILES on the clipboard (screenshots): paste event listener
     *   - data: URI <img> tags inside pasted HTML: clipboard matcher
     *
     * While an upload is in flight a small grey placeholder token is shown
     * at the paste position; it is replaced by the image on success or
     * removed on failure.
     *
     * options:
     *   uploadUrl - POST endpoint accepting multipart/form-data. Falls back
     *               to window.BLOG_EDITOR_CONFIG.imageUploadUrl. Must return
     *               JSON {image_url: '...'} (or {url: ...} / {src: ...}).
     *   fieldName - form field name for the file (default 'image').
     *   maxBytes  - per-image size cap (default 25MB); oversize pastes are
     *               dropped with an alert rather than embedded as base64.
     *   headers   - optional extra request headers (e.g. auth).
     *   onStatus  - optional function(message|null) for progress UI.
     */
    function createPasteImageHandler(quill, options) {
        options = options || {};
        var cfg = (typeof window !== 'undefined' && window.BLOG_EDITOR_CONFIG) || {};
        var uploadUrl = options.uploadUrl || cfg.imageUploadUrl;
        if (!uploadUrl) {
            console.warn('[EditorShared] createPasteImageHandler: no uploadUrl configured, pasted images will stay base64');
            return;
        }
        var fieldName = options.fieldName || 'image';
        var maxBytes = options.maxBytes || 25 * 1024 * 1024;
        var notify = options.onStatus || function (msg) {
            if (msg) console.log('[EditorShared] ' + msg);
        };
        var Delta = Quill.import('delta');

        function uploadBlob(blob, filename) {
            var fd = new FormData();
            fd.append(fieldName, blob, filename);
            return fetch(uploadUrl, {
                method: 'POST',
                body: fd,
                headers: options.headers || {},
                credentials: 'same-origin'
            }).then(function (res) {
                if (!res.ok) throw new Error('Upload failed with status ' + res.status);
                return res.json();
            }).then(function (data) {
                var url = data.image_url || data.url || data.src;
                if (!url) throw new Error('Upload response missing image URL');
                return url;
            });
        }

        function replaceToken(token, url) {
            var idx = quill.getText().indexOf(token);
            if (idx < 0) return;
            quill.deleteText(idx, token.length, Quill.sources.SILENT);
            if (url) {
                quill.insertEmbed(idx, 'image', url, Quill.sources.USER);
            }
        }

        function startUpload(blob, filename, insertIndex) {
            if (blob.size > maxBytes) {
                alert('Pasted image is too large (' + Math.round(blob.size / (1024 * 1024)) + 'MB). Maximum is ' + Math.round(maxBytes / (1024 * 1024)) + 'MB.');
                return;
            }
            var token = '[[uploading-image-' + (++pasteUploadCounter) + ']]';
            if (typeof insertIndex === 'number') {
                quill.insertText(insertIndex, token, { italic: true, color: '#888888' }, Quill.sources.SILENT);
                quill.setSelection(insertIndex + token.length, Quill.sources.SILENT);
            }
            notify('Uploading pasted image (' + Math.max(1, Math.round(blob.size / 1024)) + 'KB)...');
            uploadBlob(blob, filename).then(function (url) {
                replaceToken(token, url);
                notify(null);
            }).catch(function (err) {
                console.error('[EditorShared] Pasted image upload failed:', err);
                replaceToken(token, null);
                notify(null);
                alert('Pasted image upload failed: ' + err.message);
            });
            return token;
        }

        // Path 1: image files on the clipboard (screenshots, copied files).
        // Capture phase so we beat Quill's own clipboard/uploader handling.
        quill.root.addEventListener('paste', function (e) {
            var cd = e.clipboardData;
            if (!cd || !cd.files || !cd.files.length) return;
            var images = Array.prototype.filter.call(cd.files, function (f) {
                return f.type.indexOf('image/') === 0;
            });
            if (!images.length) return;
            e.preventDefault();
            e.stopPropagation();
            var range = quill.getSelection(true);
            var index = range ? range.index : quill.getLength();
            images.forEach(function (file) {
                startUpload(file, file.name || ('pasted.' + (file.type.split('/')[1] || 'png')), index);
            });
        }, true);

        // Path 2: data: URI <img> tags inside pasted HTML.
        quill.clipboard.addMatcher('IMG', function (node, delta) {
            var src = node.getAttribute('src') || '';
            if (src.indexOf('data:image/') !== 0) return delta;
            var blob = dataUrlToBlob(src);
            if (!blob) return new Delta();
            if (blob.size > maxBytes) {
                alert('Pasted image is too large (' + Math.round(blob.size / (1024 * 1024)) + 'MB). Maximum is ' + Math.round(maxBytes / (1024 * 1024)) + 'MB.');
                return new Delta();
            }
            var token = '[[uploading-image-' + (++pasteUploadCounter) + ']]';
            notify('Uploading pasted image (' + Math.max(1, Math.round(blob.size / 1024)) + 'KB)...');
            uploadBlob(blob, 'pasted.' + (blob.type.split('/')[1] || 'png')).then(function (url) {
                replaceToken(token, url);
                notify(null);
            }).catch(function (err) {
                console.error('[EditorShared] Pasted image upload failed:', err);
                replaceToken(token, null);
                notify(null);
                alert('Pasted image upload failed: ' + err.message);
            });
            return new Delta().insert(token, { italic: true, color: '#888888' });
        });
    }

    // =========================================================================
    // Slug helpers
    // =========================================================================

    // Convert free text to a URL-friendly slug. Mirrors the server-side
    // generate_slug() in the Blog Service so previews match what is stored.
    function slugify(text) {
        return String(text || '')
            .toLowerCase()
            .trim()
            .replace(/[^\w\s-]/g, '')
            .replace(/[\s_]+/g, '-')
            .replace(/-+/g, '-')
            .replace(/^-+|-+$/g, '');
    }

    // Keep a slug input in sync with a title input until the user edits the
    // slug by hand. Clearing the slug field re-enables auto-generation.
    //
    //   var binding = EditorShared.bindSlugField(titleEl, slugEl);
    //   binding.setSlug('existing-slug');  // when loading an article, marks manual
    //   binding.reset();                   // back to auto mode (e.g. on form reset)
    //   binding.getSlug();                 // cleaned current value or '' (= server decides)
    function bindSlugField(titleInput, slugInput, options) {
        options = options || {};
        var manual = false;

        function syncFromTitle() {
            if (manual) return;
            slugInput.value = slugify(titleInput.value);
        }

        titleInput.addEventListener('input', syncFromTitle);

        slugInput.addEventListener('input', function () {
            manual = slugInput.value.trim() !== '';
            if (!manual) syncFromTitle();
        });

        // Clean the slug on blur so the user sees exactly what will be saved
        slugInput.addEventListener('blur', function () {
            if (slugInput.value.trim()) {
                slugInput.value = slugify(slugInput.value);
            }
        });

        return {
            setSlug: function (value) {
                slugInput.value = value || '';
                manual = !!(value && String(value).trim());
                if (!manual) syncFromTitle();
            },
            reset: function () {
                manual = false;
                slugInput.value = '';
            },
            getSlug: function () {
                return slugify(slugInput.value);
            },
            isManual: function () { return manual; }
        };
    }

    // =========================================================================
    // Expose to global scope so editors can use them
    // =========================================================================

    window.EditorShared = {
        extractYouTubeId: extractYouTubeId,
        youtubeHandler: youtubeHandler,
        dividerHandler: dividerHandler,
        addYouTubeIcon: addYouTubeIcon,
        createVideoUploadHandler: createVideoUploadHandler,
        addVideoUploadIcon: addVideoUploadIcon,
        createPasteImageHandler: createPasteImageHandler,
        slugify: slugify,
        bindSlugField: bindSlugField
    };

    console.log('[EditorShared] Blots registered: divider, youtube, video-embed');
})();
