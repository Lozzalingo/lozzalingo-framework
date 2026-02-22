/**
 * Client-side image compression utility
 * Resizes large images in the browser before upload to avoid nginx 413 errors
 * and reduce upload time. Server-side compression (WebP) still runs as a safety net.
 */
async function compressImageFile(file, opts) {
    const defaults = { maxWidth: 2048, maxHeight: 2048, quality: 0.85 };
    const o = Object.assign({}, defaults, opts || {});

    // Only compress raster images
    if (!file.type.match(/^image\/(jpeg|jpg|png|webp)$/i)) {
        return file;
    }

    // Skip if already small (under 500KB)
    if (file.size < 500 * 1024) {
        return file;
    }

    try {
        const bitmap = await createImageBitmap(file);

        // Skip if dimensions are already within limits
        if (bitmap.width <= o.maxWidth && bitmap.height <= o.maxHeight) {
            bitmap.close();
            return file;
        }

        // Calculate new dimensions maintaining aspect ratio
        let w = bitmap.width;
        let h = bitmap.height;
        if (w > o.maxWidth) {
            h = Math.round(h * (o.maxWidth / w));
            w = o.maxWidth;
        }
        if (h > o.maxHeight) {
            w = Math.round(w * (o.maxHeight / h));
            h = o.maxHeight;
        }

        // Draw to canvas at new size
        const canvas = new OffscreenCanvas(w, h);
        const ctx = canvas.getContext('2d');
        ctx.drawImage(bitmap, 0, 0, w, h);
        bitmap.close();

        // Export as JPEG
        const blob = await canvas.convertToBlob({ type: 'image/jpeg', quality: o.quality });

        // Only use compressed version if it's actually smaller
        if (blob.size >= file.size) {
            return file;
        }

        // Preserve original name but change extension
        const name = file.name.replace(/\.[^.]+$/, '.jpg');
        const compressed = new File([blob], name, { type: 'image/jpeg', lastModified: Date.now() });

        console.log(`[IMG] Compressed ${file.name}: ${(file.size/1024).toFixed(0)}KB → ${(compressed.size/1024).toFixed(0)}KB (${w}x${h})`);
        return compressed;
    } catch (e) {
        console.warn('[IMG] Client compression failed, using original:', e.message);
        return file;
    }
}
