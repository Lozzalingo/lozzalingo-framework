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
    // Expose to global scope so editors can use them
    // =========================================================================

    window.EditorShared = {
        extractYouTubeId: extractYouTubeId,
        youtubeHandler: youtubeHandler,
        dividerHandler: dividerHandler,
        addYouTubeIcon: addYouTubeIcon
    };

    console.log('[EditorShared] Blots registered: divider, youtube, video-embed');
})();
