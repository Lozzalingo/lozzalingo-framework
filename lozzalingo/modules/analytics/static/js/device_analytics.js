// Device detection utility for analytics
class DeviceDetector {
    static detectDevice(userAgent, screenWidth, screenHeight, touchPoints, orientation = null) {
        const ua = userAgent.toLowerCase();
        
        // Mobile patterns
        const mobilePatterns = [
            /android.+mobile/, /iphone/, /ipod/, /blackberry/, /iemobile/, 
            /opera mini/, /mobile/, /palm/, /windows ce/, /symbian/,
            /webos/, /bada/, /tizen/, /kaios/
        ];
        
        // Tablet patterns  
        const tabletPatterns = [
            /ipad/, /android(?!.*mobile)/, /tablet/, /kindle/, /silk/,
            /playbook/, /rim tablet/
        ];
        
        // Smart TV patterns
        const tvPatterns = [
            /smart-tv/, /googletv/, /appletv/, /hbbtv/, /pov_tv/, /netcast/,
            /roku/, /dlnadoc/, /ce-html/, /xbox/, /playstation/
        ];
        
        // Gaming console patterns
        const consolePatterns = [
            /nintendo/, /xbox/, /playstation/, /vita/, /3ds/, /wii/
        ];
        
        // Check for specific device types
        const isMobileUA = mobilePatterns.some(pattern => pattern.test(ua));
        const isTabletUA = tabletPatterns.some(pattern => pattern.test(ua));
        const isTVUA = tvPatterns.some(pattern => pattern.test(ua));
        const isConsoleUA = consolePatterns.some(pattern => pattern.test(ua));
        
        // Screen size analysis
        const screenArea = screenWidth * screenHeight;
        const aspectRatio = Math.max(screenWidth, screenHeight) / Math.min(screenWidth, screenHeight);
        
        // Device categories based on screen size
        const isSmallScreen = screenWidth <= 768 || screenHeight <= 768;
        const isMediumScreen = screenWidth > 768 && screenWidth <= 1024;
        const isLargeScreen = screenWidth > 1024;
        const isUltraWideScreen = aspectRatio > 2.1;
        
        // Touch capability
        const hasTouch = touchPoints > 0;
        
        // Determine device type with confidence scoring
        const deviceScores = {
            mobile: 0,
            tablet: 0,
            desktop: 0,
            tv: 0,
            console: 0,
            wearable: 0
        };
        
        // User agent scoring
        if (isMobileUA) deviceScores.mobile += 40;
        if (isTabletUA) deviceScores.tablet += 40;
        if (isTVUA) deviceScores.tv += 50;
        if (isConsoleUA) deviceScores.console += 50;
        
        // Screen size scoring
        if (screenWidth <= 480) {
            deviceScores.mobile += 30;
            deviceScores.wearable += 20;
        } else if (screenWidth <= 768) {
            deviceScores.mobile += 25;
            deviceScores.tablet += 15;
        } else if (screenWidth <= 1024) {
            deviceScores.tablet += 25;
            deviceScores.desktop += 15;
        } else if (screenWidth <= 1920) {
            deviceScores.desktop += 30;
            deviceScores.tv += 10;
        } else {
            deviceScores.desktop += 25;
            deviceScores.tv += 20;
        }
        
        // Screen area considerations
        if (screenArea < 400000) { // ~640x600
            deviceScores.mobile += 20;
            deviceScores.wearable += 15;
        } else if (screenArea > 2000000) { // ~1920x1080
            deviceScores.desktop += 15;
            deviceScores.tv += 15;
        }
        
        // Touch scoring
        if (hasTouch) {
            deviceScores.mobile += 20;
            deviceScores.tablet += 20;
            deviceScores.desktop += 5; // Touch laptops exist
        } else {
            deviceScores.desktop += 15;
            deviceScores.tv += 10;
            deviceScores.console += 10;
        }
        
        // Aspect ratio considerations
        if (aspectRatio > 2.0) {
            deviceScores.tv += 15;
            deviceScores.desktop += 10; // Ultrawide monitors
        }
        
        // Special cases for iPad detection (often reports as desktop)
        if (ua.includes('mac') && hasTouch && screenWidth >= 768) {
            deviceScores.tablet += 30;
            deviceScores.mobile -= 10;
        }
        
        // Android tablet detection
        if (ua.includes('android') && !ua.includes('mobile') && screenWidth > 600) {
            deviceScores.tablet += 25;
            deviceScores.mobile -= 15;
        }
        
        // Find the highest scoring device type
        const topDevice = Object.entries(deviceScores)
            .sort(([,a], [,b]) => b - a)[0];
        
        const deviceType = topDevice[0];
        const confidence = Math.min(topDevice[1], 100);
        
        // Additional metadata
        const metadata = {
            screenSize: this.getScreenSizeCategory(screenWidth, screenHeight),
            screenClass: this.getScreenClass(screenWidth, screenHeight),
            touchCapable: hasTouch,
            aspectRatio: Math.round(aspectRatio * 100) / 100,
            screenArea: screenArea,
            pixelDensity: this.getPixelDensityClass(screenWidth, screenHeight)
        };
        
        return {
            deviceType,
            confidence,
            scores: deviceScores,
            metadata,
            raw: {
                userAgent: ua,
                screenWidth,
                screenHeight,
                touchPoints
            }
        };
    }
    
    static getScreenSizeCategory(width, height) {
        const maxDimension = Math.max(width, height);
        if (maxDimension <= 480) return 'extra_small';
        if (maxDimension <= 768) return 'small';
        if (maxDimension <= 1024) return 'medium';
        if (maxDimension <= 1440) return 'large';
        if (maxDimension <= 1920) return 'extra_large';
        return 'ultra_large';
    }
    
    static getScreenClass(width, height) {
        const area = width * height;
        if (area < 300000) return 'compact';
        if (area < 800000) return 'standard';
        if (area < 2000000) return 'large';
        return 'ultra_large';
    }
    
    static getPixelDensityClass(width, height) {
        const area = width * height;
        if (area < 500000) return 'low_res';
        if (area < 1000000) return 'standard_res';
        if (area < 2500000) return 'high_res';
        if (area < 8000000) return 'very_high_res';
        return 'ultra_high_res';
    }
}

// Integration example for your analytics class
class EnhancedAnalyticsClient extends AnalyticsClient {
    constructor() {
        super();
        // Add device detection to session data
        this.deviceInfo = this.detectDeviceInfo();
    }
    
    detectDeviceInfo() {
        const detection = DeviceDetector.detectDevice(
            navigator.userAgent,
            screen.width,
            screen.height,
            navigator.maxTouchPoints || 0,
            screen.orientation ? screen.orientation.type : null
        );
        
        return {
            device_type: detection.deviceType,
            device_confidence: detection.confidence,
            device_scores: detection.scores,
            screen_size_category: detection.metadata.screenSize,
            screen_class: detection.metadata.screenClass,
            touch_capable: detection.metadata.touchCapable,
            aspect_ratio: detection.metadata.aspectRatio,
            pixel_density_class: detection.metadata.pixelDensity,
            is_portrait: screen.height > screen.width,
            // Additional device characteristics
            is_retina: window.devicePixelRatio > 1.5,
            supports_orientation: 'orientation' in screen,
            supports_vibration: 'vibrate' in navigator,
            supports_geolocation: 'geolocation' in navigator,
            supports_notifications: 'Notification' in window,
            supports_service_worker: 'serviceWorker' in navigator,
            supports_web_share: 'share' in navigator
        };
    }
    
    collectSessionData() {
        const baseData = super.collectSessionData();
        return {
            ...baseData,
            ...this.deviceInfo
        };
    }
    
    // Enhanced interaction logging with device context
    async logInteraction(type, additionalData = {}) {
        const enhancedData = {
            ...additionalData,
            device_type: this.deviceInfo.device_type,
            is_touch_interaction: 'ontouchstart' in window,
            current_orientation: screen.orientation ? screen.orientation.type : 'unknown'
        };
        
        await super.logInteraction(type, enhancedData);
    }
}

// Usage example
document.addEventListener('DOMContentLoaded', function() {
    // Test device detection
    const deviceInfo = DeviceDetector.detectDevice(
        navigator.userAgent,
        screen.width,
        screen.height,
        navigator.maxTouchPoints || 0
    );
    
    // Initialize enhanced analytics
    if (!window.analyticsClient) {
        window.analyticsClient = new EnhancedAnalyticsClient();
        console.log('Enhanced analytics with device detection initialized');
    }
});