/**
 * Kiosk Speech Chat Application
 * Handles WebSocket communication, Web Audio API, and chat interface
 */

class KioskSpeechChat {
    constructor() {
        // Initialize properties
        this.ws = null;
        this.clientId = this.generateClientId();
        this.isConnected = false;
        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioStream = null;
        this.audioChunks = [];
        
        // Voice Activity Detection
        this.vadAnalyser = null;
        this.vadDataArray = null;
        this.lastVoiceTime = 0;
        this.vadCheckInterval = null;
        this.recordingStartTime = 0;
        this.speechDetected = false;
        this.consecutiveSilenceCount = 0;
        
        // Dictation state (manual control)
        this.isDictationListening = false;
        
        
        // Screenshot management
        this.screenshots = [];
        this.screenshotCount = 0;
        this.currentScreenshot = null;
        
        // Vignette system for organizing screenshots with annotations
        this.vignettes = {
            current: {
                name: 'My Vignette',
                screenshots: [], // Array of screenshot IDs in order
                annotations: {}, // Map screenshot ID to annotation data
                created: new Date().toISOString(),
                modified: new Date().toISOString()
            }
        };
        this.currentVignetteName = 'My Vignette';
        this.currentScreenshotIndex = 0;
        
        // Drawing functionality
        this.drawingMode = 'none';
        this.isDrawing = false;
        this.rectangleStart = null;
        this.drawnShapes = [];
        this.drawingModeJustChanged = false;
        
        // Heuristic processing cache for performance optimization
        this.heuristicCache = {};
        this.heuristicCacheSize = 100; // Limit cache size
        
        // Settings (will be loaded from config)
        this.settings = {
            autoSendVoice: true,
            voiceThreshold: 0.5,
            selectedMicrophone: null,
            // VAD settings will be loaded from server config
            vadEnabled: true,
            vadSensitivity: 0.001,
            silenceTimeout: 800,
            speechStartDelay: 300,
            consecutiveSilenceThreshold: 2,
            checkInterval: 100,
            dynamicTimeout: {
                enabled: true,
                trigger_after_ms: 1500,
                reduction_factor: 0.6,
                minimum_timeout_ms: 600
            }
        };
        
        // Configuration loaded from server
        this.vadConfig = null;
        this.kioskData = null;
        this.pendingUpdates = {}; // Track coordinate updates before saving
        this.pendingNewScreens = {}; // Track new screens before saving
        this.lastRectangleCoords = null; // Store last drawn rectangle coordinates
        
        // Processing mode settings
        this.processingMode = 'llm'; // 'llm' or 'heuristic'
        this.commandHistory = null;
        
        // Element visibility settings
        this.elementsVisible = false; // Default to hidden
        this.currentElementOverlays = []; // Track current overlays
        this.currentSelectedScreen = null; // Track selected screen
        
        // Browser and URL detection
        this.detectBrowserAndURL();
        
        // Initialize components
        this.initializeElements();
        
        // Initialize annotation mode after elements are available
        this.annotationMode = new ScreenshotAnnotationMode(this);
        
        this.initializeEventListeners();
        this.initializeNavbar();
        this.loadVADConfig();
        this.loadKioskData();
        this.loadScreenshots();
        this.loadSettings();
        this.loadOptimizationState();
        this.loadCommandHistory();
        this.loadProcessingModePreference();
        this.loadElementsVisibilityPreference();
        this.connectWebSocket();
        this.initializeAudio();
        
        // Temporarily commented out to fix instantiation
        try {
            this.initializeTextReading();
        } catch (error) {
            console.error('initializeTextReading failed:', error);
            console.log('Continuing without text reading functionality');
        }
        
        // Debug: Verify method is available on this instance
        console.log('Constructor finished. Checking method availability:');
        console.log('handleUpdateCoordinatesScreen on this:', typeof this.handleUpdateCoordinatesScreen);
        console.log('handleUpdateCoordinates on this:', typeof this.handleUpdateCoordinates);
    }

    detectBrowserAndURL() {
        // Detect browser
        const userAgent = navigator.userAgent;
        this.browserInfo = {
            isChrome: /Chrome/.test(userAgent) && !/Edg/.test(userAgent),
            isFirefox: /Firefox/.test(userAgent),
            isEdge: /Edg/.test(userAgent),
            isSafari: /Safari/.test(userAgent) && !/Chrome/.test(userAgent),
            isLocalhost: location.hostname === 'localhost' || location.hostname === '127.0.0.1',
            isSecure: location.protocol === 'https:' || window.isSecureContext,
            currentURL: location.href
        };

        console.log('Browser info:', this.browserInfo);

        // Show URL guidance if not using localhost
        if (!this.browserInfo.isLocalhost && location.protocol === 'http:') {
            setTimeout(() => {
                this.addMessage('system', '⚠️ For best microphone support, use: http://localhost:8000');
                this.addMessage('system', '📍 Currently using: ' + location.href);
            }, 2000);
        }
    }
    
    async loadVADConfig() {
        try {
            const response = await fetch('/api/vad-config');
            const data = await response.json();
            
            if (data.success) {
                this.vadConfig = data.config;
                
                // Update default settings from config
                const defaults = data.config.client_defaults;
                Object.assign(this.settings, {
                    vadEnabled: defaults.vadEnabled,
                    vadSensitivity: defaults.vadSensitivity,
                    silenceTimeout: defaults.silenceTimeout,
                    speechStartDelay: defaults.speechStartDelay,
                    consecutiveSilenceThreshold: defaults.consecutiveSilenceThreshold,
                    checkInterval: defaults.checkInterval,
                    dynamicTimeout: defaults.dynamicTimeout
                });
                
                // Update UI ranges from config
                const uiSettings = data.config.ui_settings;
                if (uiSettings.timeoutRange) {
                    const range = uiSettings.timeoutRange;
                    const timeoutSlider = document.getElementById('silenceTimeout');
                    if (timeoutSlider) {
                        timeoutSlider.min = range.min;
                        timeoutSlider.max = range.max;
                        timeoutSlider.step = range.step;
                        timeoutSlider.value = range.default;
                    }
                }
                
                console.log('VAD configuration loaded from server:', this.vadConfig);
            } else {
                console.warn('Failed to load VAD config from server:', data.error);
                console.log('Using fallback configuration');
            }
        } catch (error) {
            console.error('Error loading VAD configuration:', error);
            console.log('Using default hardcoded configuration');
        }
    }
    
    async loadKioskData() {
        try {
            const response = await fetch('/api/kiosk-data');
            const data = await response.json();
            
            if (data.success) {
                this.kioskData = data.data;
                console.log('Kiosk data loaded from server:', this.kioskData);
                
                // Initialize the dropdowns
                this.initializeScreenDropdown();
            } else {
                console.warn('Failed to load kiosk data from server:', data.error);
            }
        } catch (error) {
            console.error('Error loading kiosk data:', error);
        }
    }
    
    async loadScreenshots() {
        try {
            const response = await fetch('/api/screenshots');
            const data = await response.json();
            
            if (data.success) {
                this.screenshots = data.screenshots;
                this.screenshotCount = data.total;
                console.log(`Loaded ${this.screenshotCount} screenshots from file system`);
                
                // Update UI
                this.updateScreenshotCount();
                this.populateGallery();
            } else {
                console.warn('Failed to load screenshots from server:', data.error);
            }
        } catch (error) {
            console.error('Error loading screenshots:', error);
        }
    }
    
    generateClientId() {
        return 'client_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    }
    
    initializeElements() {
        // Get DOM elements
        this.elements = {
            // Navbar elements
            topNavbar: document.getElementById('topNavbar'),
            mouseX: document.getElementById('mouseX'),
            mouseY: document.getElementById('mouseY'),
            currentTime: document.getElementById('currentTime'),
            drawingMode: document.getElementById('drawingMode'),
            drawingRectangle: document.getElementById('drawingRectangle'),
            saveButton: document.getElementById('saveButton'),
            screenDropdown: document.getElementById('screen'),
            elementDropdown: document.getElementById('element'),
            
            connectionStatus: document.getElementById('connectionStatus'),
            chatMessages: document.getElementById('chatMessages'),
            messageInput: document.getElementById('messageInput'),
            sendButton: document.getElementById('sendButton'),
            voiceButton: document.getElementById('voiceButton'),
            recordingIndicator: document.getElementById('recordingIndicator'),
            processingIndicator: document.getElementById('processingIndicator'),
            processingModeToggle: document.getElementById('processingModeToggle'),
            processingModeCheckbox: document.getElementById('processingModeCheckbox'),
            processingModeText: document.getElementById('processingModeText'),
            elementsVisibilityToggle: document.getElementById('elementsVisibilityToggle'),
            elementsVisibilityCheckbox: document.getElementById('elementsVisibilityCheckbox'),
            elementsVisibilityText: document.getElementById('elementsVisibilityText'),
            annotationElementsVisibilityToggle: document.getElementById('annotationElementsVisibilityToggle'),
            annotationElementsVisibilityCheckbox: document.getElementById('annotationElementsVisibilityCheckbox'),
            annotationElementsVisibilityText: document.getElementById('annotationElementsVisibilityText'),
            settingsToggle: document.getElementById('settingsToggle'),
            settingsPanel: document.getElementById('settingsPanel'),
            vadSidebar: document.getElementById('vadSidebar'),
            sidebarToggle: document.getElementById('sidebarToggle'),
            dictationButton: document.getElementById('dictationButton'),
            microphoneSelect: document.getElementById('microphoneSelect'),
            autoSendVoice: document.getElementById('autoSendVoice'),
            voiceThreshold: document.getElementById('voiceThreshold'),
            vadEnabled: document.getElementById('vadEnabled'),
            silenceTimeout: document.getElementById('silenceTimeout'),
            silenceTimeoutValue: document.getElementById('silenceTimeoutValue'),
            vadSensitivity: document.getElementById('vadSensitivity'),
            vadSensitivityValue: document.getElementById('vadSensitivityValue'),
            speechStartDelay: document.getElementById('speechStartDelay'),
            speechStartDelayValue: document.getElementById('speechStartDelayValue'),
            consecutiveSilenceThreshold: document.getElementById('consecutiveSilenceThreshold'),
            consecutiveSilenceThresholdValue: document.getElementById('consecutiveSilenceThresholdValue'),
            checkInterval: document.getElementById('checkInterval'),
            checkIntervalValue: document.getElementById('checkIntervalValue'),
            dynamicTimeoutEnabled: document.getElementById('dynamicTimeoutEnabled'),
            dynamicTimeoutTrigger: document.getElementById('dynamicTimeoutTrigger'),
            dynamicTimeoutTriggerValue: document.getElementById('dynamicTimeoutTriggerValue'),
            dynamicTimeoutReduction: document.getElementById('dynamicTimeoutReduction'),
            dynamicTimeoutReductionValue: document.getElementById('dynamicTimeoutReductionValue'),
            dynamicTimeoutMinimum: document.getElementById('dynamicTimeoutMinimum'),
            dynamicTimeoutMinimumValue: document.getElementById('dynamicTimeoutMinimumValue'),
            errorModal: document.getElementById('errorModal'),
            errorMessage: document.getElementById('errorMessage'),
            errorClose: document.getElementById('errorClose'),
            // Screenshot elements
            screenshotSidebar: document.getElementById('screenshotSidebar'),
            screenshotToggle: document.getElementById('screenshotToggle'),
            takeScreenshotButton: document.getElementById('takeScreenshotButton'),
            screenshotCount: document.getElementById('screenshotCount'),
            screenshotGallery: document.getElementById('screenshotGallery'),
            galleryControls: document.getElementById('galleryControls'),
            selectAllScreenshots: document.getElementById('selectAllScreenshots'),
            deleteSelectedButton: document.getElementById('deleteSelectedButton'),
            screenshotModal: document.getElementById('screenshotModal'),
            modalBackdrop: document.getElementById('modalBackdrop'),
            modalClose: document.getElementById('modalClose'),
            modalTitle: document.getElementById('modalTitle'),
            modalImage: document.getElementById('modalImage'),
            downloadScreenshot: document.getElementById('downloadScreenshot'),
            deleteScreenshot: document.getElementById('deleteScreenshot'),
            // Add new screen modal elements
            addScreenModal: document.getElementById('addScreenModal'),
            addScreenModalBackdrop: document.getElementById('addScreenModalBackdrop'),
            addScreenModalClose: document.getElementById('addScreenModalClose'),
            screenId: document.getElementById('screenId'),
            screenName: document.getElementById('screenName'),
            screenDescription: document.getElementById('screenDescription'),
            titleText: document.getElementById('titleText'),
            cancelAddScreen: document.getElementById('cancelAddScreen'),
            confirmAddScreen: document.getElementById('confirmAddScreen'),
            // Add new element modal elements
            addElementModal: document.getElementById('addElementModal'),
            addElementModalBackdrop: document.getElementById('addElementModalBackdrop'),
            addElementModalClose: document.getElementById('addElementModalClose'),
            elementId: document.getElementById('elementId'),
            elementName: document.getElementById('elementName'),
            elementDescription: document.getElementById('elementDescription'),
            elementAction: document.getElementById('elementAction'),
            elementVoiceCommands: document.getElementById('elementVoiceCommands'),
            elementX: document.getElementById('elementX'),
            elementY: document.getElementById('elementY'),
            elementWidth: document.getElementById('elementWidth'),
            elementHeight: document.getElementById('elementHeight'),
            cancelAddElement: document.getElementById('cancelAddElement'),
            confirmAddElement: document.getElementById('confirmAddElement'),
            // Screenshot annotation modal elements
            screenshotAnnotationModal: document.getElementById('screenshotAnnotationModal'),
            annotationBackground: document.getElementById('annotationBackground'),
            annotationNavbar: document.getElementById('annotationNavbar'),
            annotationDrawingMode: document.getElementById('annotationDrawingMode'),
            annotationSaveButton: document.getElementById('annotationSaveButton'),
            annotationUpdateButton: document.getElementById('annotationUpdateButton'),
            annotationScreen: document.getElementById('annotationScreen'),
            annotationElement: document.getElementById('annotationElement'),
            annotationMouseX: document.getElementById('annotationMouseX'),
            annotationMouseY: document.getElementById('annotationMouseY'),
            annotationDrawingOverlay: document.getElementById('annotationDrawingOverlay'),
            annotationDrawingRectangle: document.getElementById('annotationDrawingRectangle'),
            annotationExit: document.getElementById('annotationExit'),
            // New annotation elements
            prevScreenshotBtn: document.getElementById('prevScreenshotBtn'),
            nextScreenshotBtn: document.getElementById('nextScreenshotBtn'),
            screenshotOrder: document.getElementById('screenshotOrder'),
            vignetteLabel: document.getElementById('vignetteLabel'),
            vignetteSaveButton: document.getElementById('vignetteSaveButton'),
            screenshotAnnotation: document.getElementById('screenshotAnnotation')
        };
    }
    
    initializeNavbar() {
        // Initialize mouse position tracking
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        this.lastClientX = 0;
        this.lastClientY = 0;
        this.mouseUpdateThrottle = null;
        
        // Track mouse movement globally
        document.addEventListener('mousemove', (e) => {
            this.lastMouseMoveTime = Date.now();
            
            // Throttle updates to avoid excessive DOM manipulation
            if (this.mouseUpdateThrottle) {
                clearTimeout(this.mouseUpdateThrottle);
            }
            
            this.mouseUpdateThrottle = setTimeout(() => {
                // Use screen coordinates for display to match MCP tool coordinate system
                this.updateMousePosition(e.screenX, e.screenY);
                // Store client coordinates for drawing
                this.lastClientX = e.clientX;
                this.lastClientY = e.clientY;
            }, 16); // ~60fps
        });
        
        // Initialize time display
        this.updateTime();
        this.timeInterval = setInterval(() => {
            this.updateTime();
        }, 1000);
        
        // Also track mouse position from MCP server periodically
        this.startMousePositionPolling();
        
        // Initialize drawing functionality
        this.initializeDrawing();
        
        // Initialize keyboard shortcuts
        this.initializeKeyboardShortcuts();
    }
    
    updateMousePosition(x, y) {
        if (this.elements.mouseX && this.elements.mouseY) {
            this.elements.mouseX.textContent = x;
            this.elements.mouseY.textContent = y;
            this.lastMouseX = x;
            this.lastMouseY = y;
        }
    }
    
    updateTime() {
        if (this.elements.currentTime) {
            const now = new Date();
            const timeString = now.toLocaleTimeString('en-US', { 
                hour12: false, 
                hour: '2-digit', 
                minute: '2-digit' 
            });
            this.elements.currentTime.textContent = timeString;
        }
    }
    
    async startMousePositionPolling() {
        // Poll the actual mouse position from the MCP server every 2 seconds
        const pollMousePosition = async () => {
            try {
                const response = await this.callMCPTool('mouse_control_get_position', {});
                if (response.success && response.data) {
                    const { x, y } = response.data;
                    // Only update if we haven't received a recent local mouse move
                    const timeSinceLastMove = Date.now() - (this.lastMouseMoveTime || 0);
                    if (timeSinceLastMove > 1000) { // 1 second
                        this.updateMousePosition(x, y);
                    }
                }
            } catch (error) {
                // Silently fail - mouse position polling is not critical
                console.debug('Mouse position polling failed:', error);
            }
        };
        
        // Start polling
        setInterval(pollMousePosition, 2000);
    }
    
    initializeDrawing() {
        // Handle drawing mode changes
        if (this.elements.drawingMode) {
            this.elements.drawingMode.addEventListener('change', (e) => {
                this.setDrawingMode(e.target.value);
            });
        }
        
        // Handle mouse events for drawing
        document.addEventListener('click', (e) => {
            if (this.drawingMode !== 'none') {
                this.handleDrawingClick(e);
            }
        });
        
        document.addEventListener('mousemove', (e) => {
            if (this.drawingMode === 'rectangle' && this.isDrawing) {
                this.updateRectangleDrawing(e);
            }
        });
    }
    
    setDrawingMode(mode) {
        this.drawingMode = mode;
        this.drawingModeJustChanged = true;
        
        if (mode === 'none') {
            document.body.classList.remove('drawing-mode');
            this.cancelCurrentDrawing();
        } else {
            document.body.classList.add('drawing-mode');
        }
        
        // Add brief delay to prevent immediate click registration
        setTimeout(() => {
            this.drawingModeJustChanged = false;
        }, 200); // 200ms delay
        
        console.log(`Drawing mode set to: ${mode}`);
    }
    
    handleDrawingClick(e) {
        // Prevent default behavior
        e.preventDefault();
        e.stopPropagation();
        
        // Ignore clicks if drawing mode was just changed
        if (this.drawingModeJustChanged) {
            console.log('Ignoring click - drawing mode just changed');
            return;
        }
        
        if (this.drawingMode === 'rectangle') {
            if (!this.isDrawing) {
                // Start drawing rectangle
                this.startRectangleDrawing(e.clientX, e.clientY);
            } else {
                // Finish drawing rectangle
                this.finishRectangleDrawing(e.clientX, e.clientY);
            }
        }
    }
    
    startRectangleDrawing(x, y) {
        this.isDrawing = true;
        this.rectangleStart = { x, y };
        
        // Show and position the rectangle
        if (this.elements.drawingRectangle) {
            this.elements.drawingRectangle.classList.add('active');
            this.elements.drawingRectangle.style.left = x + 'px';
            this.elements.drawingRectangle.style.top = y + 'px';
            this.elements.drawingRectangle.style.width = '0px';
            this.elements.drawingRectangle.style.height = '0px';
        }
        
        console.log(`Started rectangle at (${x}, ${y})`);
    }
    
    updateRectangleDrawing(e) {
        if (!this.isDrawing || !this.rectangleStart || !this.elements.drawingRectangle) {
            return;
        }
        
        const currentX = e.clientX;
        const currentY = e.clientY;
        const startX = this.rectangleStart.x;
        const startY = this.rectangleStart.y;
        
        const width = Math.abs(currentX - startX);
        const height = Math.abs(currentY - startY);
        const left = Math.min(startX, currentX);
        const top = Math.min(startY, currentY);
        
        this.elements.drawingRectangle.style.left = left + 'px';
        this.elements.drawingRectangle.style.top = top + 'px';
        this.elements.drawingRectangle.style.width = width + 'px';
        this.elements.drawingRectangle.style.height = height + 'px';
    }
    
    finishRectangleDrawing(x, y) {
        if (!this.isDrawing || !this.rectangleStart) {
            return;
        }
        
        const startX = this.rectangleStart.x;
        const startY = this.rectangleStart.y;
        const endX = x;
        const endY = y;
        
        // Calculate rectangle bounds
        const left = Math.min(startX, endX);
        const top = Math.min(startY, endY);
        const right = Math.max(startX, endX);
        const bottom = Math.max(startY, endY);
        const width = right - left;
        const height = bottom - top;
        
        // Calculate center point (client coordinates)
        const centerX = Math.round(left + width / 2);
        const centerY = Math.round(top + height / 2);
        
        // Convert to screen coordinates by calculating offset
        // Use current mouse position to estimate screen offset
        const screenOffsetX = this.lastMouseX - this.lastClientX;
        const screenOffsetY = this.lastMouseY - this.lastClientY;
        
        // Calculate screen coordinates  
        const screenCenterX = Math.round(centerX + screenOffsetX);
        const screenCenterY = Math.round(centerY + screenOffsetY);
        const screenX = Math.round(left + screenOffsetX);
        const screenY = Math.round(top + screenOffsetY);
        
        // Record the shape
        const rectangle = {
            type: 'rectangle',
            coordinates: {
                x1: startX,
                y1: startY,
                x2: endX,
                y2: endY,
                left: left,
                top: top,
                right: right,
                bottom: bottom,
                width: width,
                height: height,
                centerX: centerX,
                centerY: centerY,
                screenCenterX: screenCenterX,
                screenCenterY: screenCenterY
            },
            timestamp: new Date().toISOString()
        };
        
        this.drawnShapes.push(rectangle);
        
        // Store the last rectangle coordinates for potential updates
        this.lastRectangleCoords = {
            // Use drawn rectangle bounds coordinates instead of center
            x: left,
            y: top,
            screenX: screenX,
            screenY: screenY,
            centerX: centerX,
            centerY: centerY,
            screenCenterX: screenCenterX,
            screenCenterY: screenCenterY,
            width: width,
            height: height
        };
        
        // Hide the drawing rectangle
        if (this.elements.drawingRectangle) {
            this.elements.drawingRectangle.classList.remove('active');
        }
        
        // Reset drawing state
        this.isDrawing = false;
        this.rectangleStart = null;
        
        // Log the completed rectangle
        console.log('Rectangle completed:', rectangle);
        
        // Create message with Update buttons
        const messageId = 'rect_' + Date.now();
        this.addMessage('system', 
            `📐 Rectangle Drawn\n` +
            `Rectangle: (${startX}, ${startY}) to (${endX}, ${endY}) [Client]\n` +
            `Bounds: ${width}×${height} at (${left}, ${top})\n` +
            `Center (Client): (${centerX}, ${centerY})\n` +
            `Center (Screen): (${screenCenterX}, ${screenCenterY})\n` +
            `Total shapes drawn: ${this.drawnShapes.length}\n` +
            `<button class="update-button" data-message-id="${messageId}" onclick="window.handleUpdateCoordinates('${messageId}')" style="margin-right: 8px;">📍 Update with Client Coords</button>` +
            `<button class="update-button" data-message-id="${messageId}" onclick="window.handleUpdateCoordinatesScreen('${messageId}')">📍 Update with Screen Coords</button>`
        );
    }
    
    cancelCurrentDrawing() {
        if (this.isDrawing) {
            this.isDrawing = false;
            this.rectangleStart = null;
            
            if (this.elements.drawingRectangle) {
                this.elements.drawingRectangle.classList.remove('active');
            }
        }
    }
    
    getDrawnShapes() {
        return this.drawnShapes;
    }
    
    clearDrawnShapes() {
        this.drawnShapes = [];
        this.addMessage('system', '🗑️ Shapes Cleared\nAll drawn shapes have been cleared.');
    }
    
    exportDrawnShapes() {
        if (this.drawnShapes.length === 0) {
            this.addMessage('system', '📄 Export Results\nNo shapes to export. Draw some rectangles first!');
            return null;
        }
        
        const exportData = {
            timestamp: new Date().toISOString(),
            totalShapes: this.drawnShapes.length,
            shapes: this.drawnShapes
        };
        
        // Display export summary
        const summary = this.drawnShapes.map((shape, index) => {
            const coords = shape.coordinates;
            return `${index + 1}. Rectangle: (${coords.x1}, ${coords.y1}) to (${coords.x2}, ${coords.y2}) - ${coords.width}×${coords.height} - Client: (${coords.centerX}, ${coords.centerY}) - Screen: (${coords.screenCenterX}, ${coords.screenCenterY})`;
        }).join('\n');
        
        this.addMessage('system', 
            `📄 Exported Shape Data\n` +
            `Total shapes: ${this.drawnShapes.length}\n\n${summary}\n\nShape data available in console (window.kioskChat.getDrawnShapes())`
        );
        
        console.log('Exported shape data:', exportData);
        return exportData;
    }
    
    initializeScreenDropdown() {
        if (!this.kioskData || !this.kioskData.screens) {
            console.warn('No kiosk data available for screen dropdown');
            return;
        }
        
        // Clear existing options except the first one
        this.elements.screenDropdown.innerHTML = '<option value="">Screen</option>';
        
        // Add screen options
        Object.keys(this.kioskData.screens).forEach(screenKey => {
            const screen = this.kioskData.screens[screenKey];
            const option = document.createElement('option');
            option.value = screenKey;
            option.textContent = screen.name || screenKey;
            this.elements.screenDropdown.appendChild(option);
        });
        
        // Add "Add New Screen..." option at the end
        const addNewOption = document.createElement('option');
        addNewOption.value = '__add_new_screen__';
        addNewOption.textContent = '+ Add New Screen...';
        addNewOption.style.fontStyle = 'italic';
        addNewOption.style.color = '#667eea';
        this.elements.screenDropdown.appendChild(addNewOption);
        
        console.log('Screen dropdown initialized with screens:', Object.keys(this.kioskData.screens));
    }
    
    updateElementDropdown(selectedScreen) {
        if (!this.kioskData || !this.kioskData.screens || !selectedScreen) {
            // Reset to default
            this.elements.elementDropdown.innerHTML = '<option value="">Element</option>';
            return;
        }
        
        const screenData = this.kioskData.screens[selectedScreen];
        if (!screenData || !screenData.elements) {
            this.elements.elementDropdown.innerHTML = '<option value="">Element</option>';
            // Add "Add New Element..." option even if no elements exist
            const addNewOption = document.createElement('option');
            addNewOption.value = '__add_new_element__';
            addNewOption.textContent = '+ Add New Element...';
            addNewOption.style.fontStyle = 'italic';
            addNewOption.style.color = '#667eea';
            this.elements.elementDropdown.appendChild(addNewOption);
            return;
        }
        
        // Clear existing options
        this.elements.elementDropdown.innerHTML = '<option value="">Element</option>';
        
        // Add element options
        screenData.elements.forEach(element => {
            const option = document.createElement('option');
            option.value = element.id;
            option.textContent = element.name || element.id;
            this.elements.elementDropdown.appendChild(option);
        });
        
        // Add "Add New Element..." option at the end
        const addNewOption = document.createElement('option');
        addNewOption.value = '__add_new_element__';
        addNewOption.textContent = '+ Add New Element...';
        addNewOption.style.fontStyle = 'italic';
        addNewOption.style.color = '#667eea';
        this.elements.elementDropdown.appendChild(addNewOption);
        
        console.log(`Element dropdown updated for screen "${selectedScreen}" with elements:`, 
                   screenData.elements.map(e => e.id));
    }
    
    handleScreenChange() {
        const selectedScreen = this.elements.screenDropdown.value;
        console.log('Screen changed to:', selectedScreen);
        
        // Clear previous element overlays if screen changed
        if (this.currentSelectedScreen !== selectedScreen) {
            this.clearElementOverlays();
            this.currentSelectedScreen = selectedScreen;
        }
        
        // Check if "Add New Screen..." option was selected
        if (selectedScreen === '__add_new_screen__') {
            console.log('Add New Screen option selected');
            this.showAddScreenModal();
            // Reset dropdown to empty selection
            this.elements.screenDropdown.value = '';
            this.updateElementDropdown('');
            this.currentSelectedScreen = null;
            return;
        }
        
        // Update element dropdown based on selected screen
        this.updateElementDropdown(selectedScreen);
        
        // If elements are currently visible, redraw them for the new screen
        if (this.elementsVisible && selectedScreen) {
            this.showElementOverlays(selectedScreen);
        }
        
        if (selectedScreen) {
            const screenData = this.kioskData.screens[selectedScreen];
            this.addMessage('system', 
                `🖥️ Screen Selected: ${screenData.name || selectedScreen}\n` +
                `Description: ${screenData.description || 'No description'}\n` +
                `Elements: ${screenData.elements ? screenData.elements.length : 0}`
            );
        }
    }
    
    handleElementChange() {
        const selectedScreen = this.elements.screenDropdown.value;
        const selectedElement = this.elements.elementDropdown.value;
        
        console.log('Element changed to:', selectedElement, 'for screen:', selectedScreen);
        
        // Check if "Add New Element..." option was selected
        if (selectedElement === '__add_new_element__') {
            console.log('Add New Element option selected');
            this.showAddElementModal();
            // Reset dropdown to empty selection
            this.elements.elementDropdown.value = '';
            return;
        }
        
        if (selectedElement && selectedScreen) {
            const screenData = this.kioskData.screens[selectedScreen];
            const elementData = screenData.elements.find(e => e.id === selectedElement);
            
            if (elementData) {
                this.addMessage('system', 
                    `🧩 Element Selected: ${elementData.name || selectedElement}\n` +
                    `Screen: ${screenData.name || selectedScreen}\n` +
                    `Coordinates: (${elementData.coordinates?.x || 'N/A'}, ${elementData.coordinates?.y || 'N/A'})\n` +
                    `Description: ${elementData.description || 'No description'}`
                );
            }
        }
    }
    
    handleUpdateCoordinates(messageId) {
        const selectedScreen = this.elements.screenDropdown.value;
        const selectedElement = this.elements.elementDropdown.value;
        
        if (!selectedScreen || !selectedElement) {
            this.addMessage('system', '⚠️ Update Failed\nPlease select both a Screen and Element before updating coordinates.');
            return;
        }
        
        if (!this.lastRectangleCoords) {
            this.addMessage('system', '⚠️ Update Failed\nNo rectangle coordinates available. Draw a rectangle first.');
            return;
        }
        
        // Store the pending update
        const updateKey = `${selectedScreen}.${selectedElement}`;
        this.pendingUpdates[updateKey] = {
            screen: selectedScreen,
            elementId: selectedElement,
            newCoordinates: {
                x: this.lastRectangleCoords.x,
                y: this.lastRectangleCoords.y
            },
            newSize: {
                width: this.lastRectangleCoords.width,
                height: this.lastRectangleCoords.height
            },
            timestamp: new Date().toISOString()
        };
        
        // Enable the save button
        this.elements.saveButton.disabled = false;
        
        // Show confirmation message
        const screenData = this.kioskData.screens[selectedScreen];
        const elementData = screenData.elements.find(e => e.id === selectedElement);
        const elementName = elementData?.name || selectedElement;
        
        this.addMessage('system', 
            `✅ Client Coordinate Update Queued\n` +
            `Element: ${elementName}\n` +
            `Screen: ${screenData.name || selectedScreen}\n` +
            `New Coordinates: (${this.lastRectangleCoords.x}, ${this.lastRectangleCoords.y}) [Client] New bounds: width ${this.lastRectangleCoords.width} height ${this.lastRectangleCoords.height}\n` +
            `Click Save to apply changes to config file.`
        );
        
        console.log('Pending update queued:', updateKey, this.pendingUpdates[updateKey]);
    }
    
    handleUpdateCoordinatesScreen(messageId) {
        console.log('handleUpdateCoordinatesScreen method is being defined');
        console.log('handleUpdateCoordinatesScreen called with messageId:', messageId);
        console.log('Save button element:', this.elements.saveButton);
        console.log('Save button current disabled state:', this.elements.saveButton?.disabled);
        
        const selectedScreen = this.elements.screenDropdown.value;
        const selectedElement = this.elements.elementDropdown.value;
        
        console.log('Selected screen:', selectedScreen);
        console.log('Selected element:', selectedElement);
        console.log('lastRectangleCoords:', this.lastRectangleCoords);
        
        if (!selectedScreen || !selectedElement) {
            console.log('Missing screen or element selection, showing error');
            this.addMessage('system', '⚠️ Update Failed\nPlease select both a Screen and Element before updating coordinates.');
            return;
        }
        
        if (!this.lastRectangleCoords) {
            this.addMessage('system', '⚠️ Update Failed\nNo rectangle coordinates available. Draw a rectangle first.');
            return;
        }
        
        // Store the pending update with screen coordinates
        const updateKey = `${selectedScreen}.${selectedElement}`;
        this.pendingUpdates[updateKey] = {
            screen: selectedScreen,
            elementId: selectedElement,
            newCoordinates: {
                x: this.lastRectangleCoords.screenX,
                y: this.lastRectangleCoords.screenY
            },
            newSize: {
                width: this.lastRectangleCoords.width,
                height: this.lastRectangleCoords.height
            },
            timestamp: new Date().toISOString()
        };
        
        // Enable the save button
        this.elements.saveButton.disabled = false;
        console.log('Main interface: Save button enabled after Update with Screen Coords');
        console.log('Save button disabled state after enabling:', this.elements.saveButton.disabled);
        
        // Show confirmation message
        const screenData = this.kioskData.screens[selectedScreen];
        const elementData = screenData.elements.find(e => e.id === selectedElement);
        const elementName = elementData?.name || selectedElement;
        
        this.addMessage('system', 
            `✅ Screen Coordinate Update Queued\n` +
            `Element: ${elementName}\n` +
            `Screen: ${screenData.name || selectedScreen}\n` +
            `New Coordinates: (${this.lastRectangleCoords.screenX}, ${this.lastRectangleCoords.screenY}) [Screen] New bounds: width ${this.lastRectangleCoords.width} height ${this.lastRectangleCoords.height}\n` +
            `Click Save to apply changes to config file.`
        );
        
        console.log('Pending screen coordinate update queued:', updateKey, this.pendingUpdates[updateKey]);
    }
    
    async handleSaveCoordinates() {
        const hasUpdates = Object.keys(this.pendingUpdates).length > 0;
        const hasNewScreens = this.pendingNewScreens && Object.keys(this.pendingNewScreens).length > 0;
        const hasNewElements = this.pendingNewElements && Object.keys(this.pendingNewElements).length > 0;
        
        if (!hasUpdates && !hasNewScreens && !hasNewElements) {
            this.addMessage('system', '⚠️ No Changes to Save\nNo coordinate updates, new screens, or new elements are pending.');
            return;
        }
        
        try {
            // Disable save button during save operation
            this.elements.saveButton.disabled = true;
            this.addMessage('system', '💾 Saving Changes\nUpdating kiosk_data.json...');
            
            // Send updates to backend
            const requestBody = {
                updates: this.pendingUpdates
            };
            
            // Add new screens if any
            if (hasNewScreens) {
                requestBody.newScreens = this.pendingNewScreens;
            }
            
            // Add new elements if any
            if (hasNewElements) {
                requestBody.newElements = this.pendingNewElements;
            }
            
            console.log('Sending save request:', {
                hasUpdates,
                hasNewScreens,
                hasNewElements,
                requestBody: JSON.stringify(requestBody, null, 2)
            });
            
            const response = await fetch('/api/kiosk-data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Clear pending updates on successful save
                const updateCount = Object.keys(this.pendingUpdates).length;
                const newScreenCount = hasNewScreens ? Object.keys(this.pendingNewScreens).length : 0;
                let newElementCount = 0;
                if (hasNewElements) {
                    newElementCount = Object.values(this.pendingNewElements).reduce((total, elements) => total + elements.length, 0);
                }
                
                this.pendingUpdates = {};
                if (this.pendingNewScreens) {
                    this.pendingNewScreens = {};
                }
                if (this.pendingNewElements) {
                    this.pendingNewElements = {};
                }
                
                // Reload kiosk data to reflect changes
                await this.loadKioskData();
                
                let successMessage = `✅ Changes Saved Successfully\n`;
                if (updateCount > 0) {
                    successMessage += `Updated ${updateCount} element coordinate(s)\n`;
                }
                if (newScreenCount > 0) {
                    successMessage += `Added ${newScreenCount} new screen(s)\n`;
                }
                if (newElementCount > 0) {
                    successMessage += `Added ${newElementCount} new element(s)\n`;
                }
                successMessage += `Configuration reloaded.`;
                
                this.addMessage('system', successMessage);
                
                console.log('Coordinate updates saved successfully');
            } else {
                // Re-enable save button on failure
                this.elements.saveButton.disabled = false;
                
                this.addMessage('system', 
                    `❌ Save Failed\n` +
                    `Error: ${result.error || 'Unknown error occurred'}\n` +
                    `Changes not saved. Please try again.`
                );
                
                console.error('Save failed:', result.error);
            }
        } catch (error) {
            // Re-enable save button on error
            this.elements.saveButton.disabled = false;
            
            this.addMessage('system', 
                `❌ Save Error\n` +
                `Network or server error: ${error.message}\n` +
                `Changes not saved. Please check connection and try again.`
            );
            
            console.error('Save error:', error);
        }
    }
    
    initializeKeyboardShortcuts() {
        // Handle keyboard shortcuts for drawing functionality
        document.addEventListener('keydown', (e) => {
            // ESC key - exit drawing mode
            if (e.key === 'Escape' || e.keyCode === 27) {
                if (this.drawingMode !== 'none') {
                    // Cancel any current drawing
                    this.cancelCurrentDrawing();
                    
                    // Set drawing mode back to none
                    this.elements.drawingMode.value = 'none';
                    this.setDrawingMode('none');
                    
                    // Show feedback message
                    this.addMessage('system', '⌨️ Drawing Mode Exited\nESC pressed - drawing mode set back to None');
                    
                    console.log('ESC pressed - exiting drawing mode');
                }
            }
        });
    }
    
    initializeEventListeners() {
        // Send message on button click
        this.elements.sendButton.addEventListener('click', () => {
            this.sendMessage();
        });
        
        // Send message on Enter key
        this.elements.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendMessage();
            }
        });
        
        // Voice recording toggle
        this.elements.voiceButton.addEventListener('click', () => {
            this.toggleVoiceRecording();
        });
        
        // Processing Mode Toggle
        this.elements.processingModeCheckbox.addEventListener('change', () => {
            this.toggleProcessingMode();
        });
        
        // Elements Visibility Toggle
        this.elements.elementsVisibilityCheckbox.addEventListener('change', () => {
            this.toggleElementsVisibility(this.elements.elementsVisibilityCheckbox);
        });
        
        // Annotation Elements Visibility Toggle (sync with main toggle)
        if (this.elements.annotationElementsVisibilityCheckbox) {
            this.elements.annotationElementsVisibilityCheckbox.addEventListener('change', () => {
                this.toggleElementsVisibility(this.elements.annotationElementsVisibilityCheckbox);
            });
        }
        
        // Screen dropdown
        this.elements.screenDropdown.addEventListener('change', () => {
            this.handleScreenChange();
        });
        
        // Element dropdown
        this.elements.elementDropdown.addEventListener('change', () => {
            this.handleElementChange();
        });
        
        // Save button
        this.elements.saveButton.addEventListener('click', () => {
            this.handleSaveCoordinates();
        });
        
        // Settings toggle
        this.elements.settingsToggle.addEventListener('click', () => {
            this.toggleSettings();
        });
        
        // Sidebar toggle
        this.elements.sidebarToggle.addEventListener('click', () => {
            this.toggleSidebar();
        });
        
        // Dictation button (manual start/stop listening)
        this.elements.dictationButton.addEventListener('click', () => {
            this.toggleDictationListening();
        });
        
        // Screenshot panel toggle
        this.elements.screenshotToggle.addEventListener('click', () => {
            this.toggleScreenshotSidebar();
        });
        
        // Add new screen modal event listeners
        this.elements.addScreenModalClose.addEventListener('click', () => {
            this.closeAddScreenModal();
        });
        
        this.elements.addScreenModalBackdrop.addEventListener('click', () => {
            this.closeAddScreenModal();
        });
        
        this.elements.cancelAddScreen.addEventListener('click', () => {
            this.closeAddScreenModal();
        });
        
        this.elements.confirmAddScreen.addEventListener('click', () => {
            this.handleAddNewScreen();
        });
        
        // Form validation for add screen modal
        [this.elements.screenId, this.elements.screenName].forEach(input => {
            input.addEventListener('input', () => {
                this.validateAddScreenForm();
            });
        });
        
        // Add new element modal event listeners
        this.elements.addElementModalClose.addEventListener('click', () => {
            this.closeAddElementModal();
        });
        
        this.elements.addElementModalBackdrop.addEventListener('click', () => {
            this.closeAddElementModal();
        });
        
        this.elements.cancelAddElement.addEventListener('click', () => {
            this.closeAddElementModal();
        });
        
        this.elements.confirmAddElement.addEventListener('click', () => {
            this.handleAddNewElement();
        });
        
        // Form validation for add element modal
        [this.elements.elementId, this.elements.elementName, this.elements.elementAction].forEach(input => {
            input.addEventListener('input', () => {
                this.validateAddElementForm();
            });
        });
        
        // Take screenshot button
        this.elements.takeScreenshotButton.addEventListener('click', () => {
            this.takeScreenshot();
        });
        
        // Gallery controls event listeners
        this.elements.selectAllScreenshots.addEventListener('change', () => {
            this.toggleAllScreenshots();
        });
        
        this.elements.deleteSelectedButton.addEventListener('click', () => {
            this.deleteSelectedScreenshots();
        });
        
        // Screenshot modal event listeners
        this.elements.modalClose.addEventListener('click', () => {
            this.closeScreenshotModal();
        });
        
        this.elements.modalBackdrop.addEventListener('click', () => {
            this.closeScreenshotModal();
        });
        
        this.elements.downloadScreenshot.addEventListener('click', () => {
            this.downloadCurrentScreenshot();
        });
        
        this.elements.deleteScreenshot.addEventListener('click', () => {
            this.deleteCurrentScreenshot();
        });
        
        // Settings changes
        this.elements.autoSendVoice.addEventListener('change', () => {
            this.settings.autoSendVoice = this.elements.autoSendVoice.checked;
            this.saveSettings();
        });
        
        this.elements.voiceThreshold.addEventListener('change', () => {
            this.settings.voiceThreshold = parseFloat(this.elements.voiceThreshold.value);
            this.saveSettings();
        });
        
        this.elements.microphoneSelect.addEventListener('change', () => {
            this.settings.selectedMicrophone = this.elements.microphoneSelect.value;
            this.saveSettings();
            this.initializeAudio();
        });
        
        // VAD settings
        this.elements.vadEnabled.addEventListener('change', () => {
            this.settings.vadEnabled = this.elements.vadEnabled.checked;
            this.saveSettings();
        });
        
        this.elements.silenceTimeout.addEventListener('input', () => {
            this.settings.silenceTimeout = parseFloat(this.elements.silenceTimeout.value) * 1000; // Convert to ms
            this.elements.silenceTimeoutValue.textContent = this.elements.silenceTimeout.value + 's';
            this.saveSettings();
        });
        
        // VAD Settings Event Listeners
        this.elements.vadSensitivity.addEventListener('input', () => {
            this.settings.vadSensitivity = parseFloat(this.elements.vadSensitivity.value);
            this.elements.vadSensitivityValue.textContent = this.settings.vadSensitivity.toFixed(3);
            this.saveSettings();
        });
        
        this.elements.speechStartDelay.addEventListener('input', () => {
            this.settings.speechStartDelay = parseInt(this.elements.speechStartDelay.value);
            this.elements.speechStartDelayValue.textContent = this.settings.speechStartDelay + 'ms';
            this.saveSettings();
        });
        
        this.elements.consecutiveSilenceThreshold.addEventListener('input', () => {
            this.settings.consecutiveSilenceThreshold = parseInt(this.elements.consecutiveSilenceThreshold.value);
            this.elements.consecutiveSilenceThresholdValue.textContent = this.settings.consecutiveSilenceThreshold;
            this.saveSettings();
        });
        
        this.elements.checkInterval.addEventListener('input', () => {
            this.settings.checkInterval = parseInt(this.elements.checkInterval.value);
            this.elements.checkIntervalValue.textContent = this.settings.checkInterval + 'ms';
            this.saveSettings();
        });
        
        // Dynamic Timeout Settings Event Listeners
        this.elements.dynamicTimeoutEnabled.addEventListener('change', () => {
            this.settings.dynamicTimeout.enabled = this.elements.dynamicTimeoutEnabled.checked;
            this.saveSettings();
        });
        
        this.elements.dynamicTimeoutTrigger.addEventListener('input', () => {
            this.settings.dynamicTimeout.trigger_after_ms = parseInt(this.elements.dynamicTimeoutTrigger.value);
            this.elements.dynamicTimeoutTriggerValue.textContent = this.settings.dynamicTimeout.trigger_after_ms + 'ms';
            this.saveSettings();
        });
        
        this.elements.dynamicTimeoutReduction.addEventListener('input', () => {
            this.settings.dynamicTimeout.reduction_factor = parseFloat(this.elements.dynamicTimeoutReduction.value);
            this.elements.dynamicTimeoutReductionValue.textContent = this.settings.dynamicTimeout.reduction_factor.toFixed(1);
            this.saveSettings();
        });
        
        this.elements.dynamicTimeoutMinimum.addEventListener('input', () => {
            this.settings.dynamicTimeout.minimum_timeout_ms = parseInt(this.elements.dynamicTimeoutMinimum.value);
            this.elements.dynamicTimeoutMinimumValue.textContent = this.settings.dynamicTimeout.minimum_timeout_ms + 'ms';
            this.saveSettings();
        });
        
        // Error modal close
        this.elements.errorClose.addEventListener('click', () => {
            this.hideError();
        });

        
        // Close settings when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.elements.settingsPanel.contains(e.target) && 
                !this.elements.settingsToggle.contains(e.target)) {
                this.elements.settingsPanel.style.display = 'none';
            }
            
            // Close optimization panel when clicking outside
            const optimizationPanel = document.getElementById('optimizationPanel');
            const optimizationToggle = document.getElementById('optimizationToggle');
            if (optimizationPanel && optimizationToggle && 
                !optimizationPanel.contains(e.target) && 
                !optimizationToggle.contains(e.target)) {
                optimizationPanel.style.display = 'none';
            }
        });
        
        // Optimization panel toggle
        const optimizationToggle = document.getElementById('optimizationToggle');
        if (optimizationToggle) {
            optimizationToggle.addEventListener('click', () => {
                this.toggleOptimizationPanel();
            });
        }
        
        // Optimization preset buttons
        const presetButtons = document.querySelectorAll('.preset-button');
        presetButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const preset = e.currentTarget.dataset.preset;
                this.setOptimizationPreset(preset);
            });
        });
        
        // Clear caches button
        const clearCachesButton = document.getElementById('clearCachesButton');
        if (clearCachesButton) {
            clearCachesButton.addEventListener('click', () => {
                this.clearOptimizationCaches();
            });
        }
        
        // Refresh stats button
        const refreshStatsButton = document.getElementById('refreshStatsButton');
        if (refreshStatsButton) {
            refreshStatsButton.addEventListener('click', () => {
                this.refreshOptimizationStats();
            });
        }
        
        
        // Handle page visibility changes
        document.addEventListener('visibilitychange', () => {
            if (document.hidden && this.isRecording) {
                this.stopRecording();
            }
        });
        
        // Handle window unload
        window.addEventListener('beforeunload', () => {
            if (this.ws) {
                this.ws.close();
            }
            if (this.audioStream) {
                this.audioStream.getTracks().forEach(track => track.stop());
            }
        });
    }
    
    connectWebSocket() {
        try {
            // Determine WebSocket URL (works for both localhost and WSL)
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            const wsUrl = `${protocol}//${host}/ws/${this.clientId}`;
            
            console.log('Connecting to WebSocket:', wsUrl);
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.isConnected = true;
                this.updateConnectionStatus('connected', 'Connected');
                this.startHeartbeat();
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };
            
            this.ws.onclose = (event) => {
                console.log('WebSocket disconnected:', event.code, event.reason);
                this.isConnected = false;
                this.updateConnectionStatus('disconnected', 'Disconnected');
                this.stopHeartbeat();
                
                // Attempt to reconnect after 3 seconds
                setTimeout(() => {
                    if (!this.isConnected) {
                        this.connectWebSocket();
                    }
                }, 3000);
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.showError('Connection error. Please check if the server is running.');
            };
            
        } catch (error) {
            console.error('Error creating WebSocket:', error);
            this.showError('Failed to connect to server. Please try again.');
        }
    }
    
    handleWebSocketMessage(data) {
        console.log('Received message:', data);
        
        switch (data.type) {
            case 'connection':
                this.addMessage('system', data.message);
                break;
                
            case 'transcription':
                this.showTranscription(data.text, data.confidence);
                
                
                // Only process transcription on client-side in heuristic mode
                // In LLM mode, server handles transcription processing automatically
                if (this.settings.autoSendVoice && data.text.trim() && this.processingMode === 'heuristic') {
                    // Reduced delay for faster heuristic processing
                    setTimeout(() => {
                        this.sendChatMessage(data.text);
                    }, 200);
                }
                break;
                
            case 'chat_response':
                this.hideProcessingIndicator();
                if (data.response && data.response.success) {
                    const response = data.response.response;
                    const actionResult = data.response.action_result;
                    
                    let messageText = response.message || 'I processed your request.';
                    
                    // Format response based on action type and execution result
                    if (response.action === 'click') {
                        if (actionResult && actionResult.action_executed) {
                            // Check if this was a real click or mock
                            const method = actionResult.method || 'unknown';
                            const isMock = method.includes('mock');
                            const methodIcon = isMock ? '🎭' : '🖱️';
                            
                            messageText = `${methodIcon} Successfully clicked "${response.element_id}" at coordinates (${actionResult.coordinates?.x}, ${actionResult.coordinates?.y}) using ${method}`;
                        } else if (actionResult && !actionResult.action_executed) {
                            messageText = `❌ Failed to click "${response.element_id}": ${actionResult.error || 'Unknown error'}`;
                        } else {
                            messageText = `I would ${response.action} on "${response.element_id}" at coordinates (${response.coordinates?.x}, ${response.coordinates?.y}). ${response.message || ''}`;
                        }
                    } else if (response.action === 'help') {
                        messageText = response.message || 'Here are the available commands...';
                    } else if (response.action === 'clarify') {
                        messageText = response.message || 'I need more information to help you.';
                    }
                    
                    this.addMessage('assistant', messageText);
                    
                    // If action was executed, also show action feedback
                    if (actionResult && actionResult.action_executed) {
                        this.addMessage('system', `🖱️ Action Executed\n${actionResult.message || 'Action completed successfully'}`);
                    }
                    
                    // Show confidence if available
                    if (response.confidence !== undefined) {
                        this.addMessage('system', `Confidence: ${Math.round(response.confidence * 100)}%`);
                    }
                } else {
                    this.addMessage('assistant', 'I apologize, but I encountered an error processing your request.');
                    if (data.response && data.response.error) {
                        console.error('Chat response error:', data.response.error);
                    }
                }
                
                // Resume wake word listening if in wake word mode
                this.resumeWakeWordListeningIfActive();
                break;
                
            case 'error':
                this.hideProcessingIndicator();
                this.addMessage('system', `Error: ${data.message}`);
                
                // Resume wake word listening if in wake word mode
                this.resumeWakeWordListeningIfActive();
                break;
                
            case 'pong':
                // Heartbeat response
                break;
                
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    async initializeAudio() {
        try {
            // Check microphone permissions first
            await this.checkMicrophonePermissions();
            
            // Get available microphones
            const devices = await navigator.mediaDevices.enumerateDevices();
            const microphones = devices.filter(device => device.kind === 'audioinput');
            
            // Update microphone select
            this.elements.microphoneSelect.innerHTML = '<option value="">Default microphone</option>';
            microphones.forEach(mic => {
                const option = document.createElement('option');
                option.value = mic.deviceId;
                option.textContent = mic.label || `Microphone ${mic.deviceId.substr(0, 5)}...`;
                if (mic.deviceId === this.settings.selectedMicrophone) {
                    option.selected = true;
                }
                this.elements.microphoneSelect.appendChild(option);
            });
            
            console.log('Audio initialized, microphones found:', microphones.length);
            
        } catch (error) {
            console.error('Error initializing audio:', error);
            this.addMessage('system', '⚠️ Microphone access may be restricted. Click the microphone button to test permissions.');
        }
    }
    
    async checkMicrophonePermissions() {
        try {
            // First, check basic browser support
            if (!navigator.mediaDevices) {
                this.addMessage('system', '❌ Your browser does not support microphone access.');
                this.addMessage('system', '💡 Try using Chrome, Firefox, or Edge with HTTPS.');
                return;
            }

            if (!navigator.mediaDevices.getUserMedia) {
                this.addMessage('system', '❌ getUserMedia not supported.');
                this.addMessage('system', '💡 Make sure you\'re using HTTPS or localhost.');
                return;
            }

            // Check if we're in a secure context
            if (!window.isSecureContext) {
                this.addMessage('system', '⚠️ Not in secure context - microphone may be blocked.');
                this.addMessage('system', '💡 Use https:// or localhost for microphone access.');
            }

            // Check permissions API if available
            if (navigator.permissions) {
                try {
                    const result = await navigator.permissions.query({ name: 'microphone' });
                    console.log('Microphone permission status:', result.state);
                    
                    if (result.state === 'denied') {
                        this.addMessage('system', '🚫 Microphone blocked. Click the 🔒 icon in your address bar to allow.');
                        this.showMicrophoneInstructions();
                    } else if (result.state === 'prompt') {
                        this.addMessage('system', '🎤 Click the microphone button to request permissions.');
                    } else if (result.state === 'granted') {
                        this.addMessage('system', '✅ Microphone access already granted!');
                    }
                    
                    // Listen for permission changes
                    result.addEventListener('change', () => {
                        console.log('Microphone permission changed to:', result.state);
                        if (result.state === 'granted') {
                            this.addMessage('system', '✅ Microphone access granted!');
                            this.initializeAudio();
                        } else if (result.state === 'denied') {
                            this.addMessage('system', '🚫 Microphone access denied.');
                            this.showMicrophoneInstructions();
                        }
                    });
                } catch (permError) {
                    console.log('Permissions query failed:', permError);
                    this.addMessage('system', '🎤 Click the microphone button to test permissions.');
                }
            } else {
                this.addMessage('system', '🎤 Click the microphone button to request permissions.');
            }
        } catch (error) {
            console.error('Permission check failed:', error);
            this.addMessage('system', '⚠️ Unable to check microphone permissions.');
        }
    }

    showMicrophoneInstructions() {
        this.addMessage('system', '🔧 To enable microphone:');
        this.addMessage('system', '1. Click the 🔒 or 🎤 icon in your address bar');
        this.addMessage('system', '2. Select "Allow" for microphone permissions');
        this.addMessage('system', '3. Refresh this page if needed');
    }

    async testMicrophoneAccess() {
        this.addMessage('system', '🧪 Testing microphone access...');
        
        // Show current context info
        this.addMessage('system', `📍 URL: ${location.href}`);
        this.addMessage('system', `🔒 Secure context: ${window.isSecureContext ? 'Yes' : 'No'}`);
        this.addMessage('system', `🌐 Browser: ${navigator.userAgent.split(' ')[0]}`);
        
        try {
            // Test basic API availability
            if (!navigator.mediaDevices) {
                this.addMessage('system', '❌ navigator.mediaDevices not available');
                this.addMessage('system', '💡 This browser may not support modern audio APIs');
                return;
            }

            if (!navigator.mediaDevices.getUserMedia) {
                this.addMessage('system', '❌ getUserMedia not available');
                this.addMessage('system', '💡 Use a modern browser with HTTPS or localhost');
                return;
            }

            this.addMessage('system', '✅ Basic audio APIs available');

            // Test permissions
            if (navigator.permissions) {
                try {
                    const result = await navigator.permissions.query({ name: 'microphone' });
                    this.addMessage('system', `🎤 Permission status: ${result.state}`);
                    
                    if (result.state === 'denied') {
                        this.addMessage('system', '🚫 Microphone permission is DENIED');
                        this.showMicrophoneInstructions();
                        return;
                    }
                } catch (permError) {
                    this.addMessage('system', '⚠️ Cannot check permissions: ' + permError.message);
                }
            }

            // Attempt actual microphone access
            this.addMessage('system', '🎤 Requesting microphone access...');
            
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            this.addMessage('system', '🎉 SUCCESS! Microphone access granted');
            
            // Get device info
            const tracks = stream.getAudioTracks();
            if (tracks.length > 0) {
                const track = tracks[0];
                this.addMessage('system', `🎙️ Device: ${track.label || 'Default microphone'}`);
                this.addMessage('system', `⚙️ Settings: ${JSON.stringify(track.getSettings())}`);
            }

            // Show available devices
            const devices = await navigator.mediaDevices.enumerateDevices();
            const audioInputs = devices.filter(device => device.kind === 'audioinput');
            this.addMessage('system', `🔍 Found ${audioInputs.length} audio input device(s)`);

            // Clean up
            stream.getTracks().forEach(track => track.stop());
            this.addMessage('system', '✅ Test completed successfully! Microphone should work now.');

        } catch (error) {
            this.addMessage('system', `❌ Microphone test FAILED: ${error.name}`);
            this.addMessage('system', `📝 Error details: ${error.message}`);
            
            // Provide specific guidance based on error
            if (error.name === 'NotAllowedError') {
                this.addMessage('system', '🔧 FIX: Click the microphone/lock icon in your address bar and allow access');
            } else if (error.name === 'NotFoundError') {
                this.addMessage('system', '🔧 FIX: Check that a microphone is connected and working');
            } else if (error.name === 'NotSupportedError') {
                this.addMessage('system', '🔧 FIX: Use HTTPS or localhost URL for microphone access');
            } else if (error.name === 'SecurityError') {
                this.addMessage('system', '🔧 FIX: Use a secure context (HTTPS or localhost)');
            }
            
            this.showMicrophoneInstructions();
        }
    }
    
    async toggleVoiceRecording() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            // Toggle wake word mode: if not in wake word mode, start it; if in wake word mode, stop it
            if (this.wakeWordActive) {
                this.stopWakeWordMode();
            } else {
                this.startWakeWordMode();
            }
        }
    }
    
    startWakeWordMode() {
        this.wakeWordActive = true;
        this.elements.voiceButton.classList.add('wake-word-active');
        this.elements.voiceButton.title = 'Wake Word Mode Active - Click to stop';
        this.startWakeWordListening();
        console.log('Wake word mode activated');
    }
    
    stopWakeWordMode() {
        this.wakeWordActive = false;
        this.isListeningForWakeWord = false;
        this.elements.voiceButton.classList.remove('wake-word-active');
        this.elements.voiceButton.title = 'Voice Input';
        if (this.isRecording) {
            this.stopRecording();
        }
        console.log('Wake word mode deactivated');
    }
    
    async startWakeWordListening() {
        if (!this.wakeWordActive || this.isListeningForWakeWord) {
            return;
        }
        
        this.isListeningForWakeWord = true;
        console.log('Starting wake word listening...');
        
        try {
            await this.startRecording();
        } catch (error) {
            console.error('Failed to start wake word listening:', error);
            this.isListeningForWakeWord = false;
        }
    }
    
    resumeWakeWordListeningIfActive() {
        if (this.wakeWordActive && !this.isListeningForWakeWord && !this.isRecording) {
            console.log('Resuming wake word listening after command processing...');
            setTimeout(() => {
                this.startWakeWordListening();
            }, 1000); // Small delay to ensure cleanup is complete
        }
    }
    
    async startRecording(disableVAD = null) {
        try {
            // Check WebSocket connection
            if (!this.isConnected) {
                this.showError('Not connected to server. Please wait for connection.');
                return;
            }
            
            // Check if getUserMedia is available
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                this.showError('Microphone access not supported. Please use HTTPS or localhost.');
                return;
            }
            
            // Get audio stream with more basic constraints first
            let constraints = {
                audio: true
            };
            
            // Try with advanced constraints if basic ones work
            try {
                this.audioStream = await navigator.mediaDevices.getUserMedia(constraints);
                
                // If basic constraints work, stop and try with advanced
                this.audioStream.getTracks().forEach(track => track.stop());
                
                constraints = {
                    audio: {
                        deviceId: this.settings.selectedMicrophone || undefined,
                        sampleRate: 16000,
                        channelCount: 1,
                        echoCancellation: true,
                        noiseSuppression: true
                    }
                };
                
                this.audioStream = await navigator.mediaDevices.getUserMedia(constraints);
            } catch (advancedError) {
                console.warn('Advanced audio constraints failed, using basic:', advancedError);
                // Fall back to basic constraints
                constraints = { audio: true };
                this.audioStream = await navigator.mediaDevices.getUserMedia(constraints);
            }
            
            // Set up Voice Activity Detection (only if enabled and not explicitly disabled)
            if (this.settings.vadEnabled && disableVAD !== false) {
                this.setupVAD();
            }
            
            // Create MediaRecorder
            this.mediaRecorder = new MediaRecorder(this.audioStream, {
                mimeType: 'audio/webm;codecs=opus'
            });
            
            this.audioChunks = [];
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = () => {
                this.cleanupVAD();
                this.processRecordedAudio();
            };
            
            // Start recording
            this.mediaRecorder.start();
            this.isRecording = true;
            this.recordingStartTime = Date.now();
            this.lastVoiceTime = Date.now();
            this.speechDetected = false;
            this.consecutiveSilenceCount = 0;
            this.updateRecordingUI(true);
            
            console.log('Recording started with VAD enabled:', this.settings.vadEnabled, 'Grace period:', this.settings.speechStartDelay + 'ms');
            
            // Show appropriate message based on VAD status
            if (this.settings.vadEnabled && disableVAD !== false) {
                const silenceTimeoutSeconds = (this.settings.silenceTimeout || 800) / 1000;
                this.addMessage('system', `🎤 Recording started - speak naturally, auto-stop after ${silenceTimeoutSeconds}s silence`);
            } else if (disableVAD === false) {
                this.addMessage('system', '🎤 Dictation mode - click the dictation button again to stop and process');
            }
            
            // Fallback timeout (longer for dictation mode, shorter for VAD mode)
            const fallbackTimeout = (disableVAD === false) ? 60000 : 30000; // 60s for dictation, 30s for VAD
            setTimeout(() => {
                if (this.isRecording) {
                    console.log('Fallback timeout reached');
                    this.stopRecording();
                }
            }, fallbackTimeout);
            
        } catch (error) {
            console.error('Error starting recording:', error);
            
            let errorMessage = 'Failed to access microphone. ';
            
            if (error.name === 'NotAllowedError') {
                errorMessage += 'Please allow microphone access in your browser settings.';
            } else if (error.name === 'NotFoundError') {
                errorMessage += 'No microphone found. Please connect a microphone.';
            } else if (error.name === 'NotSupportedError') {
                errorMessage += 'Microphone not supported. Try using HTTPS or localhost.';
            } else if (error.name === 'SecurityError') {
                errorMessage += 'Security error. Please use HTTPS or localhost.';
            } else {
                errorMessage += `Error: ${error.message}`;
            }
            
            this.showError(errorMessage);
        }
    }
    
    setupVAD() {
        try {
            // Create audio context and analyser for VAD
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioContext.createMediaStreamSource(this.audioStream);
            this.vadAnalyser = audioContext.createAnalyser();
            
            console.log('Audio context state:', audioContext.state);
            
            // Configure analyser for VAD
            this.vadAnalyser.fftSize = 512;
            this.vadAnalyser.smoothingTimeConstant = 0.8;
            source.connect(this.vadAnalyser);
            
            // Create data array for audio analysis
            this.vadDataArray = new Float32Array(this.vadAnalyser.frequencyBinCount);
            
            // Start VAD monitoring
            this.startVADMonitoring();
            
            console.log('VAD setup complete with settings:', {
                vadEnabled: this.settings.vadEnabled,
                vadSensitivity: this.settings.vadSensitivity,
                silenceTimeout: this.settings.silenceTimeout,
                speechStartDelay: this.settings.speechStartDelay,
                consecutiveSilenceThreshold: this.settings.consecutiveSilenceThreshold,
                checkInterval: this.settings.checkInterval
            });
        } catch (error) {
            console.error('VAD setup failed:', error);
            this.settings.vadEnabled = false;
        }
    }
    
    startVADMonitoring() {
        this.vadCheckInterval = setInterval(() => {
            if (!this.isRecording || !this.vadAnalyser) return;
            
            const now = Date.now();
            const recordingDuration = now - this.recordingStartTime;
            
            // Grace period - don't apply VAD for the first period to allow user to start speaking
            if (recordingDuration < this.settings.speechStartDelay) {
                if (Math.random() < 0.01) { // Occasional debug log during grace period
                    console.log(`VAD: Grace period active, ${recordingDuration}ms < ${this.settings.speechStartDelay}ms`);
                }
                return;
            }
            
            // Get frequency domain audio data (working approach from vad_app.js)
            this.vadAnalyser.getFloatFrequencyData(this.vadDataArray);
            
            // Calculate RMS energy for more accurate voice detection
            let sum = 0;
            let validSamples = 0;
            for (let i = 0; i < this.vadDataArray.length; i++) {
                if (this.vadDataArray[i] > -Infinity) {
                    const linear = Math.pow(10, this.vadDataArray[i] / 20);
                    sum += linear * linear;
                    validSamples++;
                }
            }
            
            const rmsLevel = validSamples > 0 ? Math.sqrt(sum / validSamples) : 0;
            
            // Update real-time debug info in UI
            const rmsLevelSpan = document.getElementById('rmsLevel');
            const vadThresholdSpan = document.getElementById('vadThreshold');
            if (rmsLevelSpan) rmsLevelSpan.textContent = rmsLevel.toFixed(4);
            if (vadThresholdSpan) vadThresholdSpan.textContent = this.settings.vadSensitivity.toFixed(4);
            
            // Voice detection with hysteresis (different thresholds for start/stop)
            const isVoiceDetected = rmsLevel > this.settings.vadSensitivity;
            
            if (isVoiceDetected) {
                this.lastVoiceTime = now;
                this.consecutiveSilenceCount = 0;
                
                if (!this.speechDetected) {
                    this.speechDetected = true;
                    console.log('🗣️ Speech started! RMS level:', rmsLevel.toFixed(6));
                }
            } else {
                this.consecutiveSilenceCount++;
                
                // Only stop if we've detected speech before AND we have some consistent silence
                if (this.speechDetected && this.consecutiveSilenceCount >= this.settings.consecutiveSilenceThreshold) {
                    const silenceDuration = now - this.lastVoiceTime;
                    
                    // Dynamic timeout - shorter if we've been recording for a while
                    const recordingTime = now - this.recordingStartTime;
                    let effectiveTimeout = this.settings.silenceTimeout;
                    
                    // Apply dynamic timeout if enabled
                    const dynamicConfig = this.settings.dynamicTimeout;
                    if (dynamicConfig.enabled && recordingTime > dynamicConfig.trigger_after_ms) {
                        effectiveTimeout = Math.max(
                            dynamicConfig.minimum_timeout_ms,
                            this.settings.silenceTimeout * dynamicConfig.reduction_factor
                        );
                    }
                    
                    if (silenceDuration > effectiveTimeout) {
                        console.log(`🔇 VAD: Silence for ${silenceDuration}ms after speech (timeout: ${effectiveTimeout}ms), stopping recording`);
                        this.stopRecording();
                    }
                }
            }
            
            // Debug logging (reduced frequency like working version)
            if (Math.random() < 0.1) { // Only log 10% of the time
                console.log(`VAD: RMS=${rmsLevel.toFixed(6)}, Speech=${this.speechDetected}, Silence=${this.consecutiveSilenceCount}, Duration=${Math.round(recordingDuration/1000)}s`);
            }
        }, this.settings.checkInterval); // Use configured check interval
    }
    
    cleanupVAD() {
        if (this.vadCheckInterval) {
            clearInterval(this.vadCheckInterval);
            this.vadCheckInterval = null;
        }
        this.vadAnalyser = null;
        this.vadDataArray = null;
        this.speechDetected = false;
        this.consecutiveSilenceCount = 0;
        this.recordingStartTime = 0;
        
        // Reset visual indicator
        const recordingIndicator = document.getElementById('recordingIndicator');
        if (recordingIndicator) {
            recordingIndicator.style.border = '';
        }
    }
    
    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            this.isListeningForWakeWord = false;
            this.updateRecordingUI(false);
            
            // Stop audio stream
            if (this.audioStream) {
                this.audioStream.getTracks().forEach(track => track.stop());
                this.audioStream = null;
            }
            
            console.log('Recording stopped');
        }
    }
    
    async processRecordedAudio() {
        try {
            if (this.audioChunks.length === 0) {
                console.warn('No audio data recorded');
                return;
            }
            
            this.showProcessingIndicator();
            
            // Create audio blob
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
            
            // Convert to WAV format for better compatibility
            const audioBuffer = await this.convertToWAV(audioBlob);
            
            // Convert to base64
            const base64Audio = await this.blobToBase64(audioBuffer);
            
            // Send to server
            this.sendAudioData(base64Audio);
            
        } catch (error) {
            console.error('Error processing audio:', error);
            this.hideProcessingIndicator();
            this.showError('Failed to process audio. Please try again.');
        }
    }
    
    async convertToWAV(webmBlob) {
        // For now, return the original blob
        // In production, you might want to convert to WAV format
        return webmBlob;
    }
    
    blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const base64 = reader.result.split(',')[1]; // Remove data URL prefix
                resolve(base64);
            };
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }
    
    async sendAudioData(base64Audio) {
        if (!this.ws || !this.isConnected) {
            this.hideProcessingIndicator();
            this.showError('Not connected to server');
            return;
        }

        // Determine if we should only do transcription or full processing
        const transcriptionOnly = this.processingMode === 'heuristic';
        
        this.ws.send(JSON.stringify({
            type: 'audio_data',
            audio: base64Audio,
            processing_mode: this.processingMode,
            transcription_only: transcriptionOnly,
            timestamp: new Date().toISOString()
        }));
    }
    
    sendMessage() {
        const message = this.elements.messageInput.value.trim();
        if (message) {
            this.sendChatMessage(message);
            this.elements.messageInput.value = '';
        }
    }
    
    async sendChatMessage(message) {
        if (this.ws && this.isConnected) {
            // Add user message to chat
            this.addMessage('user', message);
            
            // Show processing indicator
            this.showProcessingIndicator();
            
            // Check processing mode
            if (this.processingMode === 'heuristic') {
                // Process with heuristic locally
                try {
                    const result = await this.processHeuristicCommand(message);
                    this.handleHeuristicResponse(message, result);
                } catch (error) {
                    console.error('Heuristic processing error:', error);
                    this.hideProcessingIndicator();
                    this.addMessage('system', `❌ Heuristic processing error: ${error.message}`);
                }
            } else {
                // Send to server for LLM processing
                this.ws.send(JSON.stringify({
                    type: 'chat_message',
                    message: message,
                    processing_mode: this.processingMode,
                    context: {
                        timestamp: new Date().toISOString(),
                        client_id: this.clientId
                    }
                }));
            }
        } else {
            this.showError('Not connected to server');
        }
    }

    handleHeuristicResponse(originalMessage, result) {
        this.hideProcessingIndicator();
        
        if (result.success) {
            const action = result.action;
            const similarity = (result.similarity * 100).toFixed(1);
            
            let responseMessage = `🎯 **Heuristic Match Found** (${similarity}% similarity)\n\n`;
            responseMessage += `**Matched Command:** "${action.user_command}"\n`;
            responseMessage += `**Action Taken:** ${action.action.description}\n\n`;
            
            if (result.result && result.result.success) {
                responseMessage += `✅ **Action executed successfully**`;
            } else if (result.result) {
                responseMessage += `⚠️  **Action completed with issues**`;
            }
            
            // Add feedback buttons
            const messageElement = this.addMessage('assistant', responseMessage);
            this.addFeedbackButtons(messageElement, originalMessage, action);
            
        } else {
            let errorMessage = `❌ **Heuristic Processing Failed**\n\n`;
            errorMessage += `**Reason:** ${result.error}\n`;
            
            if (result.similarity !== undefined) {
                const similarity = (result.similarity * 100).toFixed(1);
                errorMessage += `**Best match similarity:** ${similarity}%\n`;
            }
            
            errorMessage += `\n💡 **Suggestion:** Try rephrasing your command or switch to LLM mode for better understanding.`;
            
            this.addMessage('system', errorMessage);
        }
    }

    addFeedbackButtons(messageElement, originalCommand, matchedAction) {
        const feedbackContainer = document.createElement('div');
        feedbackContainer.className = 'feedback-buttons';
        feedbackContainer.innerHTML = `
            <div class="feedback-question">Was this action correct?</div>
            <div class="feedback-options">
                <button class="feedback-btn feedback-yes" data-feedback="yes">
                    <i class="fas fa-thumbs-up"></i>
                    Yes, correct
                </button>
                <button class="feedback-btn feedback-no" data-feedback="no">
                    <i class="fas fa-thumbs-down"></i>
                    No, incorrect
                </button>
            </div>
        `;
        
        // Add event listeners
        feedbackContainer.querySelector('.feedback-yes').addEventListener('click', () => {
            this.handleFeedback('yes', originalCommand, matchedAction, feedbackContainer);
        });
        
        feedbackContainer.querySelector('.feedback-no').addEventListener('click', () => {
            this.handleFeedback('no', originalCommand, matchedAction, feedbackContainer);
        });
        
        messageElement.appendChild(feedbackContainer);
    }

    handleFeedback(feedback, originalCommand, matchedAction, buttonContainer) {
        console.log('handleFeedback called with:', { feedback, originalCommand, matchedAction });
        
        if (feedback === 'yes') {
            // Replace buttons with success message
            buttonContainer.innerHTML = `
                <div class="feedback-result">
                    <i class="fas fa-check-circle"></i>
                    Feedback recorded: Correct action - Added to learning database
                </div>
            `;
            
            // Send positive feedback to server to add command-action pair
            this.sendFeedbackToServer('add_pair', originalCommand, matchedAction);
            
        } else if (feedback === 'no') {
            console.log('Processing "no" feedback, calling showCorrectionInterface');
            // Show correction interface
            this.showCorrectionInterface(buttonContainer, originalCommand, matchedAction);
        }
        
        // Log feedback for debugging
        console.log('User feedback processed:', {
            feedback,
            originalCommand,
            matchedAction,
            timestamp: new Date().toISOString()
        });
    }

    async sendFeedbackToServer(action, originalCommand, matchedAction, correctionData = null) {
        try {
            const payload = {
                action: action, // 'add_pair' or 'update_correction'
                user_command: originalCommand,
                matched_action: matchedAction
            };
            
            if (correctionData) {
                payload.correct_screen = correctionData.screen;
                payload.correct_element = correctionData.element;
            }
            
            const response = await fetch('/api/feedback/command-history', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('Feedback sent successfully:', result);
                
                // Reload command history to get updated data
                await this.loadCommandHistory();
            } else {
                console.error('Failed to send feedback:', response.statusText);
            }
        } catch (error) {
            console.error('Error sending feedback to server:', error);
        }
    }

    showCorrectionInterface(buttonContainer, originalCommand, matchedAction) {
        console.log('showCorrectionInterface called with:', { originalCommand, matchedAction });
        
        // Show loading state first
        buttonContainer.innerHTML = `
            <div class="feedback-correction">
                <div class="correction-header">
                    <i class="fas fa-spinner fa-spin"></i>
                    Loading correction interface...
                </div>
            </div>
        `;
        
        // Load kiosk data to get available screens and elements
        this.loadKioskDataForFeedback().then(kioskData => {
            console.log('Kiosk data loaded:', kioskData);
            
            if (!kioskData || !kioskData.screens) {
                buttonContainer.innerHTML = `
                    <div class="feedback-correction">
                        <div class="correction-header">
                            <i class="fas fa-exclamation-triangle"></i>
                            Error: Could not load screen data. Please try again.
                        </div>
                        <div class="correction-actions">
                            <button class="correction-cancel-btn">
                                <i class="fas fa-times"></i>
                                Close
                            </button>
                        </div>
                    </div>
                `;
                return;
            }
            
            const screens = Object.keys(kioskData.screens);
            console.log('Available screens:', screens);
            
            buttonContainer.innerHTML = `
                <div class="feedback-correction">
                    <div class="correction-header">
                        <i class="fas fa-exclamation-triangle"></i>
                        Help us learn: Which screen and element should have been used?
                    </div>
                    <div class="correction-controls">
                        <div class="correction-step">
                            <label>Select Screen:</label>
                            <select class="screen-selector">
                                <option value="">Choose screen...</option>
                                ${screens.map(screen => 
                                    `<option value="${screen}">${kioskData.screens[screen].name}</option>`
                                ).join('')}
                            </select>
                        </div>
                        <div class="correction-step" style="display: none;">
                            <label>Select Element:</label>
                            <select class="element-selector">
                                <option value="">Choose element...</option>
                            </select>
                        </div>
                        <div class="correction-actions" style="display: none;">
                            <button class="correction-submit-btn">
                                <i class="fas fa-check"></i>
                                Submit Correction
                            </button>
                            <button class="correction-cancel-btn">
                                <i class="fas fa-times"></i>
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            // Add event listeners for the correction interface
            this.setupCorrectionListeners(buttonContainer, originalCommand, matchedAction, kioskData);
        }).catch(error => {
            console.error('Error in showCorrectionInterface:', error);
            buttonContainer.innerHTML = `
                <div class="feedback-correction">
                    <div class="correction-header">
                        <i class="fas fa-exclamation-triangle"></i>
                        Error loading correction interface: ${error.message}
                    </div>
                    <div class="correction-actions">
                        <button class="correction-cancel-btn">
                            <i class="fas fa-times"></i>
                            Close
                        </button>
                    </div>
                </div>
            `;
        });
    }

    async loadKioskDataForFeedback() {
        try {
            const response = await fetch('/api/kiosk-data');
            if (response.ok) {
                const result = await response.json();
                console.log('Raw API response:', result);
                // The API returns data wrapped in { success: true, data: { ... } }
                if (result.success && result.data) {
                    return result.data;
                } else {
                    console.error('API returned success=false or no data');
                    return { screens: {} };
                }
            } else {
                console.error('Failed to load kiosk data, status:', response.status);
                return { screens: {} };
            }
        } catch (error) {
            console.error('Error loading kiosk data:', error);
            return { screens: {} };
        }
    }

    setupCorrectionListeners(container, originalCommand, matchedAction, kioskData) {
        const screenSelector = container.querySelector('.screen-selector');
        const elementSelector = container.querySelector('.element-selector');
        const elementStep = container.querySelector('.correction-step:nth-child(2)');
        const actionsStep = container.querySelector('.correction-actions');
        const submitBtn = container.querySelector('.correction-submit-btn');
        const cancelBtn = container.querySelector('.correction-cancel-btn');
        
        screenSelector.addEventListener('change', (e) => {
            const selectedScreen = e.target.value;
            if (selectedScreen) {
                // Populate element dropdown
                const screenData = kioskData.screens[selectedScreen];
                const elements = screenData.elements || [];
                
                elementSelector.innerHTML = '<option value="">Choose element...</option>' +
                    elements.map(element => 
                        `<option value="${element.id}">${element.name}</option>`
                    ).join('');
                
                elementStep.style.display = 'block';
            } else {
                elementStep.style.display = 'none';
                actionsStep.style.display = 'none';
            }
        });
        
        elementSelector.addEventListener('change', (e) => {
            if (e.target.value) {
                actionsStep.style.display = 'block';
            } else {
                actionsStep.style.display = 'none';
            }
        });
        
        submitBtn.addEventListener('click', () => {
            const selectedScreen = screenSelector.value;
            const selectedElement = elementSelector.value;
            
            if (selectedScreen && selectedElement) {
                // Send correction to server
                this.sendFeedbackToServer('update_correction', originalCommand, matchedAction, {
                    screen: selectedScreen,
                    element: selectedElement
                });
                
                // Update UI
                container.innerHTML = `
                    <div class="feedback-result">
                        <i class="fas fa-check-circle"></i>
                        Correction recorded - Thank you for helping us learn!
                    </div>
                `;
            }
        });
        
        cancelBtn.addEventListener('click', () => {
            container.innerHTML = `
                <div class="feedback-result">
                    <i class="fas fa-times-circle"></i>
                    feedback cancelled
                </div>
            `;
        });
    }

    loadProcessingModePreference() {
        const savedMode = localStorage.getItem('processingMode');
        if (savedMode) {
            this.processingMode = savedMode;
            this.elements.processingModeCheckbox.checked = (savedMode === 'heuristic');
        }
        
        // Update the label to match the current mode
        const isHeuristic = (this.processingMode === 'heuristic');
        const modeText = isHeuristic ? 'Heuristic Mode' : 'LLM Mode';
        const modeIcon = isHeuristic ? 'fas fa-cogs' : 'fas fa-brain';
        
        this.elements.processingModeText.textContent = modeText;
        this.elements.processingModeToggle.querySelector('i').className = modeIcon;
        
        // Update toggle container color class
        if (isHeuristic) {
            this.elements.processingModeToggle.classList.add('heuristic-mode');
        } else {
            this.elements.processingModeToggle.classList.remove('heuristic-mode');
        }
        
        console.log('Loaded processing mode preference:', this.processingMode);
    }

    
    addMessage(sender, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Handle line breaks by converting \n to <br> tags
        const formattedText = text.replace(/\n/g, '<br>');
        contentDiv.innerHTML = formattedText;
        
        messageDiv.appendChild(contentDiv);
        this.elements.chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
        
        // Return the message element for further modification (e.g., adding feedback buttons)
        return messageDiv;
    }
    
    showTranscription(text, confidence) {
        const transcriptionDiv = document.createElement('div');
        transcriptionDiv.className = 'transcription';
        transcriptionDiv.textContent = `"${text}" (${Math.round(confidence * 100)}% confidence)`;
        
        this.elements.chatMessages.appendChild(transcriptionDiv);
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }
    
    updateRecordingUI(recording) {
        if (recording) {
            this.elements.voiceButton.classList.add('recording');
            this.elements.recordingIndicator.style.display = 'flex';
        } else {
            this.elements.voiceButton.classList.remove('recording');
            this.elements.recordingIndicator.style.display = 'none';
        }
    }
    
    updateConnectionStatus(status, text) {
        this.elements.connectionStatus.className = `connection-status ${status}`;
        this.elements.connectionStatus.querySelector('span').textContent = text;
    }
    
    showProcessingIndicator() {
        this.elements.processingIndicator.style.display = 'flex';
    }
    
    hideProcessingIndicator() {
        this.elements.processingIndicator.style.display = 'none';
    }
    
    toggleSettings() {
        const panel = this.elements.settingsPanel;
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    }
    
    toggleSidebar() {
        this.elements.vadSidebar.classList.toggle('collapsed');
        
        // Save sidebar state to localStorage
        const isCollapsed = this.elements.vadSidebar.classList.contains('collapsed');
        localStorage.setItem('vadSidebarCollapsed', isCollapsed.toString());
    }
    
    async toggleDictationListening() {
        if (this.isDictationListening) {
            this.stopDictationListening();
        } else {
            await this.startDictationListening();
        }
    }
    
    async startDictationListening() {
        try {
            // Use the same recording logic as voice button but disable VAD for manual control
            await this.startRecording(false); // false = disable VAD for manual control
            
            this.isDictationListening = true;
            this.elements.dictationButton.classList.add('active');
            this.elements.dictationButton.title = 'Stop listening';
            
            console.log('Dictation listening started - manual control mode');
            
        } catch (error) {
            console.error('Error starting dictation listening:', error);
            this.showError('Failed to start dictation. Please try again.');
        }
    }
    
    stopDictationListening() {
        if (this.isRecording) {
            this.stopRecording();
        }
        
        this.isDictationListening = false;
        this.elements.dictationButton.classList.remove('active');
        this.elements.dictationButton.title = 'Dictation - Click to start/stop listening';
        
        console.log('Dictation listening stopped');
    }
    
    showError(message) {
        this.elements.errorMessage.textContent = message;
        this.elements.errorModal.style.display = 'flex';
    }
    
    hideError() {
        this.elements.errorModal.style.display = 'none';
    }
    
    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (this.ws && this.isConnected) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000); // Ping every 30 seconds
    }
    
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }
    
    loadSettings() {
        try {
            // Load sidebar states
            const vadSidebarCollapsed = localStorage.getItem('vadSidebarCollapsed');
            if (vadSidebarCollapsed === 'true') {
                this.elements.vadSidebar.classList.add('collapsed');
            }
            
            const screenshotSidebarCollapsed = localStorage.getItem('screenshotSidebarCollapsed');
            if (screenshotSidebarCollapsed === 'true') {
                this.elements.screenshotSidebar.classList.add('collapsed');
            }
            
            const savedSettings = localStorage.getItem('kioskSpeechSettings');
            if (savedSettings) {
                const settings = JSON.parse(savedSettings);
                this.settings = { ...this.settings, ...settings };
                
                // Apply settings to UI
                this.elements.autoSendVoice.checked = this.settings.autoSendVoice;
                this.elements.voiceThreshold.value = this.settings.voiceThreshold;
                this.elements.vadEnabled.checked = this.settings.vadEnabled;
                this.elements.silenceTimeout.value = this.settings.silenceTimeout / 1000; // Convert from ms
                this.elements.silenceTimeoutValue.textContent = (this.settings.silenceTimeout / 1000) + 's';
                
                // VAD Settings
                this.elements.vadSensitivity.value = this.settings.vadSensitivity;
                this.elements.vadSensitivityValue.textContent = this.settings.vadSensitivity.toFixed(3);
                this.elements.speechStartDelay.value = this.settings.speechStartDelay;
                this.elements.speechStartDelayValue.textContent = this.settings.speechStartDelay + 'ms';
                this.elements.consecutiveSilenceThreshold.value = this.settings.consecutiveSilenceThreshold;
                this.elements.consecutiveSilenceThresholdValue.textContent = this.settings.consecutiveSilenceThreshold;
                this.elements.checkInterval.value = this.settings.checkInterval;
                this.elements.checkIntervalValue.textContent = this.settings.checkInterval + 'ms';
                
                // Dynamic Timeout Settings
                this.elements.dynamicTimeoutEnabled.checked = this.settings.dynamicTimeout.enabled;
                this.elements.dynamicTimeoutTrigger.value = this.settings.dynamicTimeout.trigger_after_ms;
                this.elements.dynamicTimeoutTriggerValue.textContent = this.settings.dynamicTimeout.trigger_after_ms + 'ms';
                this.elements.dynamicTimeoutReduction.value = this.settings.dynamicTimeout.reduction_factor;
                this.elements.dynamicTimeoutReductionValue.textContent = this.settings.dynamicTimeout.reduction_factor.toFixed(1);
                this.elements.dynamicTimeoutMinimum.value = this.settings.dynamicTimeout.minimum_timeout_ms;
                this.elements.dynamicTimeoutMinimumValue.textContent = this.settings.dynamicTimeout.minimum_timeout_ms + 'ms';
            }
        } catch (error) {
            console.error('Error loading settings:', error);
        }
    }
    
    // Screenshot functionality
    toggleScreenshotSidebar() {
        this.elements.screenshotSidebar.classList.toggle('collapsed');
        
        // Save sidebar state to localStorage
        const isCollapsed = this.elements.screenshotSidebar.classList.contains('collapsed');
        localStorage.setItem('screenshotSidebarCollapsed', isCollapsed.toString());
    }
    
    async loadCommandHistory() {
        try {
            const response = await fetch('/config/command_history.json');
            if (response.ok) {
                this.commandHistory = await response.json();
                console.log('Command history loaded:', this.commandHistory);
            } else {
                console.warn('Could not load command history');
                this.commandHistory = { command_pairs: [] };
            }
        } catch (error) {
            console.error('Error loading command history:', error);
            this.commandHistory = { command_pairs: [] };
        }
    }

    toggleProcessingMode() {
        const isHeuristic = this.elements.processingModeCheckbox.checked;
        this.processingMode = isHeuristic ? 'heuristic' : 'llm';
        
        console.log('Processing mode changed to:', this.processingMode);
        
        // Update the label text and styling
        const modeText = isHeuristic ? 'Heuristic Mode' : 'LLM Mode';
        const modeIcon = isHeuristic ? 'fas fa-cogs' : 'fas fa-brain';
        
        this.elements.processingModeText.textContent = modeText;
        this.elements.processingModeToggle.querySelector('i').className = modeIcon;
        
        // Update toggle container color class
        if (isHeuristic) {
            this.elements.processingModeToggle.classList.add('heuristic-mode');
        } else {
            this.elements.processingModeToggle.classList.remove('heuristic-mode');
        }
        
        // Add a status message to chat
        const shortModeText = isHeuristic ? 'Heuristic' : 'LLM';
        this.addMessage('system', `🔄 Processing mode switched to: ${shortModeText}`);
        
        // Save preference to localStorage
        localStorage.setItem('processingMode', this.processingMode);
    }

    toggleElementsVisibility(sourceCheckbox = null) {
        // Determine visibility state from the checkbox that triggered the change
        const mainCheckbox = this.elements.elementsVisibilityCheckbox;
        const annotationCheckbox = this.elements.annotationElementsVisibilityCheckbox;
        
        // If sourceCheckbox is provided, use its state; otherwise use main checkbox
        if (sourceCheckbox) {
            this.elementsVisible = sourceCheckbox.checked;
        } else {
            this.elementsVisible = mainCheckbox.checked;
        }
        
        console.log('Elements visibility changed to:', this.elementsVisible);
        
        // Sync both checkboxes to the same state
        mainCheckbox.checked = this.elementsVisible;
        if (annotationCheckbox) {
            annotationCheckbox.checked = this.elementsVisible;
        }
        
        // Update the label text and styling for both toggles
        const visibilityText = this.elementsVisible ? 'Elements Visible' : 'Elements Hidden';
        const visibilityIcon = this.elementsVisible ? 'fas fa-eye' : 'fas fa-eye-slash';
        
        // Update main toggle
        this.elements.elementsVisibilityText.textContent = visibilityText;
        this.elements.elementsVisibilityToggle.querySelector('i').className = visibilityIcon;
        
        // Update annotation toggle
        if (this.elements.annotationElementsVisibilityText) {
            this.elements.annotationElementsVisibilityText.textContent = visibilityText;
            this.elements.annotationElementsVisibilityToggle.querySelector('i').className = visibilityIcon;
        }
        
        // Update toggle container color classes for both toggles
        if (this.elementsVisible) {
            this.elements.elementsVisibilityToggle.classList.add('elements-visible');
            if (this.elements.annotationElementsVisibilityToggle) {
                this.elements.annotationElementsVisibilityToggle.classList.add('elements-visible');
            }
        } else {
            this.elements.elementsVisibilityToggle.classList.remove('elements-visible');
            if (this.elements.annotationElementsVisibilityToggle) {
                this.elements.annotationElementsVisibilityToggle.classList.remove('elements-visible');
            }
        }
        
        // Show or hide element overlays based on current state
        // Use annotation screen dropdown if in annotation mode, otherwise use main screen dropdown
        const selectedScreen = (this.annotationMode && this.annotationMode.isActive) 
            ? this.elements.annotationScreen.value 
            : this.elements.screenDropdown.value;
            
        if (this.elementsVisible && selectedScreen) {
            this.showElementOverlays(selectedScreen);
        } else {
            this.clearElementOverlays();
        }
        
        // Add a status message to chat
        const statusText = this.elementsVisible ? 'shown' : 'hidden';
        this.addMessage('system', `👁️ Element outlines ${statusText} for current screen`);
        
        // Save preference to localStorage
        localStorage.setItem('elementsVisible', this.elementsVisible);
    }

    showElementOverlays(screenId) {
        // Clear existing overlays first
        this.clearElementOverlays();
        
        if (!this.kioskData || !this.kioskData.screens || !screenId) {
            return;
        }
        
        const screenData = this.kioskData.screens[screenId];
        if (!screenData || !screenData.elements) {
            console.log('No elements found for screen:', screenId);
            return;
        }
        
        console.log(`Showing ${screenData.elements.length} element overlays for screen: ${screenId}`);
        
        screenData.elements.forEach(element => {
            this.createElementOverlay(element);
        });
    }

    calculateLayoutOffset() {
        // The key insight: overlay elements are positioned using screen coordinates from config/kiosk_data.json,
        // but they need to be positioned relative to the browser's client coordinate system.
        // We need to convert from screen coordinates to client coordinates.
        
        // Calculate the offset between screen coordinates and client coordinates
        // This is the same approach used in rectangle drawing for coordinate conversion
        const screenOffsetX = this.lastMouseX - this.lastClientX;
        const screenOffsetY = this.lastMouseY - this.lastClientY;
        
        // To position overlays correctly, we need the inverse offset:
        // screenCoord + offset = clientCoord, so offset = clientCoord - screenCoord
        const offsetX = -screenOffsetX;  // Negative because we're converting FROM screen TO client
        const offsetY = -screenOffsetY;
        
        return { x: offsetX, y: offsetY };
    }

    createElementOverlay(element) {
        const overlay = document.createElement('div');
        overlay.className = 'element-overlay';
        overlay.setAttribute('data-element-id', element.id);
        
        // Calculate proper positioning offset for layout
        const layoutOffset = this.calculateLayoutOffset();
        
        // Position and size the overlay with layout offset applied
        overlay.style.left = (element.coordinates.x + layoutOffset.x) + 'px';
        overlay.style.top = (element.coordinates.y + layoutOffset.y) + 'px';
        overlay.style.width = element.size.width + 'px';
        overlay.style.height = element.size.height + 'px';
        
        // Debug: Log overlay creation and check if in annotation mode
        const isInAnnotationMode = document.body.classList.contains('annotation-mode-active');
        console.log(`Creating element overlay for ${element.id}, annotation mode: ${isInAnnotationMode}`);
        
        // Create and add label
        const label = document.createElement('div');
        label.className = 'element-label';
        label.textContent = element.name || element.id;
        overlay.appendChild(label);
        
        // Add to page and track overlay
        document.body.appendChild(overlay);
        this.currentElementOverlays.push(overlay);
        
        // Debug: Check computed z-index after adding to DOM
        const computedStyle = window.getComputedStyle(overlay);
        console.log(`Created overlay for element: ${element.id} at (${element.coordinates.x}, ${element.coordinates.y}), z-index: ${computedStyle.zIndex}`);
    }

    clearElementOverlays() {
        this.currentElementOverlays.forEach(overlay => {
            if (overlay.parentNode) {
                overlay.parentNode.removeChild(overlay);
            }
        });
        this.currentElementOverlays = [];
        console.log('Cleared all element overlays');
    }

    loadElementsVisibilityPreference() {
        const savedVisibility = localStorage.getItem('elementsVisible');
        if (savedVisibility !== null) {
            this.elementsVisible = savedVisibility === 'true';
            this.elements.elementsVisibilityCheckbox.checked = this.elementsVisible;
            if (this.elements.annotationElementsVisibilityCheckbox) {
                this.elements.annotationElementsVisibilityCheckbox.checked = this.elementsVisible;
            }
        }
        
        // Update the label to match the current state
        const visibilityText = this.elementsVisible ? 'Elements Visible' : 'Elements Hidden';
        const visibilityIcon = this.elementsVisible ? 'fas fa-eye' : 'fas fa-eye-slash';
        
        // Update main toggle
        this.elements.elementsVisibilityText.textContent = visibilityText;
        this.elements.elementsVisibilityToggle.querySelector('i').className = visibilityIcon;
        
        // Update annotation toggle
        if (this.elements.annotationElementsVisibilityText) {
            this.elements.annotationElementsVisibilityText.textContent = visibilityText;
            this.elements.annotationElementsVisibilityToggle.querySelector('i').className = visibilityIcon;
        }
        
        // Update toggle container color classes for both toggles
        if (this.elementsVisible) {
            this.elements.elementsVisibilityToggle.classList.add('elements-visible');
            if (this.elements.annotationElementsVisibilityToggle) {
                this.elements.annotationElementsVisibilityToggle.classList.add('elements-visible');
            }
        } else {
            this.elements.elementsVisibilityToggle.classList.remove('elements-visible');
            if (this.elements.annotationElementsVisibilityToggle) {
                this.elements.annotationElementsVisibilityToggle.classList.remove('elements-visible');
            }
        }
        
        console.log('Loaded elements visibility preference:', this.elementsVisible);
    }


    calculateTextSimilarity(text1, text2) {
        const normalize = (str) => str.toLowerCase().trim().replace(/[^\w\s]/g, '');
        const a = normalize(text1);
        const b = normalize(text2);
        
        if (a === b) return 1.0;
        
        // Fast length difference check - early exit if too different
        const maxLength = Math.max(a.length, b.length);
        const minLength = Math.min(a.length, b.length);
        if (maxLength === 0) return 1.0;
        if (minLength / maxLength < 0.3) return 0; // Early exit for very different lengths
        
        // Use two-row optimization for Levenshtein distance
        let previousRow = Array(b.length + 1).fill(0).map((_, i) => i);
        let currentRow = Array(b.length + 1);
        
        for (let i = 0; i < a.length; i++) {
            currentRow[0] = i + 1;
            for (let j = 0; j < b.length; j++) {
                const cost = a[i] === b[j] ? 0 : 1;
                currentRow[j + 1] = Math.min(
                    currentRow[j] + 1,      // insertion
                    previousRow[j + 1] + 1, // deletion
                    previousRow[j] + cost   // substitution
                );
            }
            [previousRow, currentRow] = [currentRow, previousRow];
        }
        
        return 1 - (previousRow[b.length] / maxLength);
    }

    async processHeuristicCommand(message) {
        if (!this.commandHistory || !this.commandHistory.command_pairs) {
            return {
                success: false,
                error: 'Command history not loaded'
            };
        }

        // Check cache first for exact matches
        const normalizedMessage = message.toLowerCase().trim().replace(/[^\w\s]/g, '');
        if (this.heuristicCache && this.heuristicCache[normalizedMessage]) {
            const cached = this.heuristicCache[normalizedMessage];
            console.log(`Using cached match for: "${message}"`);
            return cached;
        }

        // Find the most similar command with early exit optimization
        let bestMatch = null;
        let bestSimilarity = 0;
        const threshold = 0.3;
        
        for (const pair of this.commandHistory.command_pairs) {
            // Early exit if we find a very high similarity match
            if (bestSimilarity > 0.95) break;
            
            const similarity = this.calculateTextSimilarity(message, pair.user_command);
            if (similarity > bestSimilarity) {
                bestSimilarity = similarity;
                bestMatch = pair;
                
                // Early exit for exact or near-exact matches
                if (similarity >= 0.98) break;
            }
        }
        
        if (!bestMatch || bestSimilarity < threshold) {
            return {
                success: false,
                error: 'No similar command found',
                similarity: bestSimilarity
            };
        }
        
        console.log(`Best match: "${bestMatch.user_command}" (similarity: ${bestSimilarity.toFixed(2)})`);
        
        // Execute the action
        try {
            const action = bestMatch.action;
            let result = null;
            
            if (action.type === 'click' && action.coordinates) {
                result = await this.callMCPTool('mouse_control_click', {
                    x: action.coordinates.x,
                    y: action.coordinates.y,
                    button: 'left'
                });
            } else if (action.type === 'help') {
                result = { success: true, data: { message: 'Help information displayed' } };
            }
            
            const response = {
                success: true,
                action: bestMatch,
                similarity: bestSimilarity,
                result: result
            };
            
            // Cache successful responses for high-similarity matches
            if (bestSimilarity > 0.7) {
                this.cacheHeuristicResult(normalizedMessage, response);
            }
            
            return response;
        } catch (error) {
            return {
                success: false,
                error: error.message,
                action: bestMatch,
                similarity: bestSimilarity
            };
        }
    }
    
    cacheHeuristicResult(key, result) {
        // Maintain cache size limit
        const cacheKeys = Object.keys(this.heuristicCache);
        if (cacheKeys.length >= this.heuristicCacheSize) {
            // Remove oldest entry (simple FIFO)
            delete this.heuristicCache[cacheKeys[0]];
        }
        
        this.heuristicCache[key] = result;
    }
    
    async takeScreenshot() {
        try {
            // Disable button during screenshot
            this.elements.takeScreenshotButton.disabled = true;
            this.elements.takeScreenshotButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Taking...</span>';
            
            console.log('Calling MCP screenshot tool...');
            
            // Call the MCP screenshot tool via the web app backend
            const response = await this.callMCPTool('screen_capture_take_screenshot', {});
            
            if (response.success && response.data) {
                const data = response.data;
                
                // Create screenshot object from MCP response
                // Extract ID from filename (remove .png extension)
                const filename = data.filename || `screenshot_${Date.now()}.png`;
                const screenshotId = filename.replace(/\.(png|jpg|jpeg)$/i, '');
                
                const screenshot = {
                    id: screenshotId,
                    timestamp: new Date().toISOString(),
                    path: data.screenshot_path,
                    filename: filename,
                    size: data.size || 'Unknown size',
                    method: data.method || 'MCP Tool',
                    width: data.width,
                    height: data.height
                };
                
                // Add to screenshots array
                this.screenshots.push(screenshot);
                this.screenshotCount++;
                
                // Update UI
                this.updateScreenshotCount();
                this.addScreenshotToGallery(screenshot);
                
                console.log('Screenshot taken successfully:', screenshot);
                
                // Show success message with method used
                if (data.method === 'PowerShell Script') {
                    this.addMessage('system', '📸 Real desktop screenshot captured via PowerShell!');
                } else if (data.method && data.method.includes('simulated')) {
                    this.addMessage('system', '🎭 Mock screenshot generated (real capture unavailable)');
                } else {
                    this.addMessage('system', `📸 Screenshot captured using ${data.method}`);
                }
                
                // Show any errors encountered but still succeeded
                if (data.errors && data.errors.length > 0) {
                    console.log('Screenshot warnings:', data.errors);
                }
                
            } else {
                // MCP call failed, show error
                const errorMsg = response.error || 'Unknown error from screenshot service';
                console.error('MCP screenshot failed:', errorMsg);
                this.showError('Failed to take screenshot: ' + errorMsg);
            }
            
        } catch (error) {
            console.error('Error calling screenshot service:', error);
            this.showError('Failed to take screenshot: ' + error.message);
        } finally {
            // Re-enable button
            this.elements.takeScreenshotButton.disabled = false;
            this.elements.takeScreenshotButton.innerHTML = '<i class="fas fa-camera"></i><span>Take Screenshot</span>';
        }
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    async callMCPTool(toolName, parameters) {
        try {
            const response = await fetch('/api/mcp-tool', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    tool: toolName,
                    parameters: parameters
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('MCP tool call failed:', error);
            throw error;
        }
    }
    
    updateScreenshotCount() {
        this.elements.screenshotCount.textContent = this.screenshotCount;
    }
    
    populateGallery() {
        // Clear gallery first
        this.elements.screenshotGallery.innerHTML = '';
        
        if (this.screenshots.length === 0) {
            // Show empty state and hide gallery controls
            this.elements.screenshotGallery.innerHTML = `
                <div class="gallery-empty">
                    <i class="fas fa-camera"></i>
                    <p>No screenshots yet</p>
                    <p>Click "Take Screenshot" to start</p>
                </div>
            `;
            this.elements.galleryControls.style.display = 'none';
            return;
        }
        
        // Show gallery controls
        this.elements.galleryControls.style.display = 'block';
        
        // Add all screenshots to gallery (they're already sorted by timestamp in the API)
        this.screenshots.forEach(screenshot => {
            this.addScreenshotToGallery(screenshot);
        });
        
        // Initialize button state
        this.updateDeleteButtonState();
        
        console.log(`Populated gallery with ${this.screenshots.length} screenshots`);
    }

    addScreenshotToGallery(screenshot) {
        // Create thumbnail element
        const thumbnail = document.createElement('div');
        thumbnail.className = 'screenshot-thumbnail';
        thumbnail.dataset.screenshotId = screenshot.id;
        
        thumbnail.innerHTML = `
            <div class="thumbnail-checkbox">
                <input type="checkbox" class="screenshot-checkbox" data-screenshot-id="${screenshot.id}">
            </div>
            <img src="${screenshot.path}" alt="Screenshot ${screenshot.id}" loading="lazy">
            <div class="thumbnail-overlay">
                <div class="thumbnail-actions">
                    <button class="thumbnail-action view-action" title="View Screenshot">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="thumbnail-action annotate-action" title="Annotate Screenshot">
                        <i class="fas fa-draw-polygon"></i>
                    </button>
                </div>
            </div>
        `;
        
        // Add click events for actions
        const viewButton = thumbnail.querySelector('.view-action');
        const annotateButton = thumbnail.querySelector('.annotate-action');
        const checkbox = thumbnail.querySelector('.screenshot-checkbox');
        
        viewButton.addEventListener('click', (e) => {
            e.stopPropagation();
            this.openScreenshotModal(screenshot);
        });
        
        annotateButton.addEventListener('click', (e) => {
            e.stopPropagation();
            this.annotationMode.enterMode(screenshot.path, screenshot);
        });
        
        // Add checkbox event listener
        checkbox.addEventListener('change', () => {
            this.updateDeleteButtonState();
        });
        
        // Add to gallery 
        this.elements.screenshotGallery.appendChild(thumbnail);
    }
    
    updateDeleteButtonState() {
        const checkboxes = this.elements.screenshotGallery.querySelectorAll('.screenshot-checkbox');
        const checkedBoxes = this.elements.screenshotGallery.querySelectorAll('.screenshot-checkbox:checked');
        
        // Update delete button state
        this.elements.deleteSelectedButton.disabled = checkedBoxes.length === 0;
        
        // Update button text
        const deleteButtonText = this.elements.deleteSelectedButton.querySelector('span');
        if (checkedBoxes.length === 0) {
            deleteButtonText.textContent = 'Delete Selected';
        } else {
            deleteButtonText.textContent = `Delete Selected (${checkedBoxes.length})`;
        }
        
        // Update select all checkbox state
        if (checkboxes.length === 0) {
            this.elements.selectAllScreenshots.checked = false;
            this.elements.selectAllScreenshots.indeterminate = false;
        } else if (checkedBoxes.length === checkboxes.length) {
            this.elements.selectAllScreenshots.checked = true;
            this.elements.selectAllScreenshots.indeterminate = false;
        } else if (checkedBoxes.length > 0) {
            this.elements.selectAllScreenshots.checked = false;
            this.elements.selectAllScreenshots.indeterminate = true;
        } else {
            this.elements.selectAllScreenshots.checked = false;
            this.elements.selectAllScreenshots.indeterminate = false;
        }
    }
    
    toggleAllScreenshots() {
        const checkboxes = this.elements.screenshotGallery.querySelectorAll('.screenshot-checkbox');
        const shouldCheck = this.elements.selectAllScreenshots.checked;
        
        checkboxes.forEach(checkbox => {
            checkbox.checked = shouldCheck;
        });
        
        this.updateDeleteButtonState();
    }
    
    async deleteSelectedScreenshots() {
        const checkedBoxes = this.elements.screenshotGallery.querySelectorAll('.screenshot-checkbox:checked');
        
        if (checkedBoxes.length === 0) {
            return;
        }
        
        // Confirm deletion
        const screenshotIds = Array.from(checkedBoxes).map(cb => cb.dataset.screenshotId);
        const confirmMessage = `Are you sure you want to delete ${screenshotIds.length} screenshot(s)?\n\nThis action cannot be undone.`;
        
        if (!confirm(confirmMessage)) {
            return;
        }
        
        try {
            // Disable button during operation
            this.elements.deleteSelectedButton.disabled = true;
            this.elements.deleteSelectedButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Deleting...</span>';
            
            let deletedCount = 0;
            let errorCount = 0;
            
            // Delete each screenshot individually using existing API pattern
            for (const screenshotId of screenshotIds) {
                try {
                    const response = await fetch(`/api/screenshots/${screenshotId}`, {
                        method: 'DELETE'
                    });
                    
                    if (response.ok) {
                        // Remove from frontend array (similar to existing deleteCurrentScreenshot)
                        this.screenshots = this.screenshots.filter(s => s.id !== screenshotId);
                        this.screenshotCount--;
                        
                        // Remove from gallery DOM
                        const thumbnail = this.elements.screenshotGallery.querySelector(`[data-screenshot-id="${screenshotId}"]`);
                        if (thumbnail) {
                            thumbnail.remove();
                        }
                        
                        deletedCount++;
                    } else {
                        console.error(`Failed to delete screenshot ${screenshotId}: ${response.status}`);
                        errorCount++;
                    }
                } catch (error) {
                    console.error(`Error deleting screenshot ${screenshotId}:`, error);
                    errorCount++;
                }
            }
            
            // Update count and show empty state if needed
            this.updateScreenshotCount();
            
            if (this.screenshotCount === 0) {
                this.elements.screenshotGallery.innerHTML = `
                    <div class="gallery-empty">
                        <i class="fas fa-camera"></i>
                        <p>No screenshots yet</p>
                        <p>Click "Take Screenshot" to start</p>
                    </div>
                `;
            }
            
            // Show result message
            if (deletedCount > 0) {
                this.addMessage('system', `🗑️ Successfully deleted ${deletedCount} screenshot(s)${errorCount > 0 ? ` (${errorCount} failed)` : ''}`);
            } else {
                this.addMessage('system', `❌ Failed to delete screenshots`);
            }
            
        } catch (error) {
            console.error('Error in bulk delete:', error);
            this.addMessage('system', `❌ Error deleting screenshots: ${error.message || 'Unknown error'}`);
        } finally {
            // Restore button state
            this.elements.deleteSelectedButton.innerHTML = '<i class="fas fa-trash"></i><span>Delete Selected</span>';
            this.updateDeleteButtonState();
        }
    }
    
    openScreenshotModal(screenshot) {
        this.currentScreenshot = screenshot;
        this.elements.modalTitle.textContent = `Screenshot - ${new Date(screenshot.timestamp).toLocaleString()}`;
        this.elements.modalImage.src = screenshot.path;
        this.elements.screenshotModal.style.display = 'flex';
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
    }
    
    closeScreenshotModal() {
        this.elements.screenshotModal.style.display = 'none';
        this.currentScreenshot = null;
        
        // Restore body scroll
        document.body.style.overflow = '';
    }
    
    // Add new screen modal methods
    showAddScreenModal() {
        console.log('showAddScreenModal called');
        
        // Check if modal elements exist
        if (!this.elements.addScreenModal) {
            console.error('Add screen modal element not found');
            this.addMessage('system', '❌ Error: Add screen modal not available');
            return;
        }
        
        // Clear form fields
        this.elements.screenId.value = '';
        this.elements.screenName.value = '';
        this.elements.screenDescription.value = '';
        this.elements.titleText.value = '';
        
        // Reset validation
        this.validateAddScreenForm();
        
        // Show modal
        this.elements.addScreenModal.style.display = 'flex';
        
        // Focus on first input
        this.elements.screenId.focus();
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
        
        console.log('Add screen modal opened');
    }
    
    closeAddScreenModal() {
        this.elements.addScreenModal.style.display = 'none';
        
        // Restore body scroll
        document.body.style.overflow = '';
        
        console.log('Add screen modal closed');
    }
    
    validateAddScreenForm() {
        const screenId = this.elements.screenId.value.trim();
        const screenName = this.elements.screenName.value.trim();
        
        // Check if required fields are filled and screenId is valid
        const isValid = screenId && screenName && /^[a-zA-Z0-9_]+$/.test(screenId);
        
        // Check if screen ID already exists
        const alreadyExists = this.kioskData && this.kioskData.screens && this.kioskData.screens[screenId];
        
        this.elements.confirmAddScreen.disabled = !isValid || alreadyExists;
        
        // Update screen ID input border color for validation feedback
        if (!screenId) {
            this.elements.screenId.style.borderColor = '';
        } else if (!/^[a-zA-Z0-9_]+$/.test(screenId)) {
            this.elements.screenId.style.borderColor = '#ff6b6b';
        } else if (alreadyExists) {
            this.elements.screenId.style.borderColor = '#ff6b6b';
        } else {
            this.elements.screenId.style.borderColor = '#4ecdc4';
        }
    }
    
    handleAddNewScreen() {
        const screenId = this.elements.screenId.value.trim();
        const screenName = this.elements.screenName.value.trim();
        const screenDescription = this.elements.screenDescription.value.trim();
        const titleText = this.elements.titleText.value.trim();
        
        if (!screenId || !screenName) {
            console.error('Screen ID and Name are required');
            return;
        }
        
        // Create new screen object
        const newScreen = {
            name: screenName,
            description: screenDescription || `Screen configuration for ${screenName}`,
            detection_criteria: {
                title_text: titleText || screenName,
                elements: []
            },
            elements: []
        };
        
        // Add to pending updates (this will be saved when Save button is clicked)
        if (!this.pendingNewScreens) {
            this.pendingNewScreens = {};
        }
        this.pendingNewScreens[screenId] = newScreen;
        
        // Enable save button
        this.elements.saveButton.disabled = false;
        
        // Close modal
        this.closeAddScreenModal();
        
        // Add success message
        this.addMessage('system', 
            `✅ New Screen Queued for Addition\n` +
            `Screen ID: ${screenId}\n` +
            `Name: ${screenName}\n` +
            `Description: ${newScreen.description}\n` +
            `Click Save to add this screen to the configuration.`
        );
        
        console.log('New screen queued:', screenId, newScreen);
    }
    
    showAddElementModal() {
        console.log('showAddElementModal called');
        
        // Check if modal elements exist
        if (!this.elements.addElementModal) {
            console.error('Add element modal element not found');
            this.addMessage('system', '❌ Error: Add element modal not available');
            return;
        }
        
        // Check if a screen is selected
        const selectedScreen = this.elements.screenDropdown.value;
        if (!selectedScreen) {
            this.addMessage('system', '⚠️ Please select a screen first before adding an element.');
            return;
        }
        
        // Clear form fields
        this.elements.elementId.value = '';
        this.elements.elementName.value = '';
        this.elements.elementDescription.value = '';
        this.elements.elementAction.value = '';
        this.elements.elementVoiceCommands.value = '';
        this.elements.elementX.value = '';
        this.elements.elementY.value = '';
        this.elements.elementWidth.value = '';
        this.elements.elementHeight.value = '';
        
        // Reset validation
        this.validateAddElementForm();
        
        // Show modal
        this.elements.addElementModal.style.display = 'flex';
        
        // Focus on first input
        this.elements.elementId.focus();
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
        
        console.log('Add element modal opened for screen:', selectedScreen);
    }
    
    closeAddElementModal() {
        this.elements.addElementModal.style.display = 'none';
        
        // Restore body scroll
        document.body.style.overflow = '';
        
        console.log('Add element modal closed');
    }
    
    validateAddElementForm() {
        const elementId = this.elements.elementId.value.trim();
        const elementName = this.elements.elementName.value.trim();
        const elementAction = this.elements.elementAction.value.trim();
        
        // Check if required fields are filled and elementId is valid
        const isValid = elementId && elementName && elementAction && /^[a-zA-Z0-9_]+$/.test(elementId);
        
        this.elements.confirmAddElement.disabled = !isValid;
    }
    
    handleAddNewElement() {
        const selectedScreen = this.elements.screenDropdown.value;
        if (!selectedScreen) {
            console.error('No screen selected');
            return;
        }
        
        const elementId = this.elements.elementId.value.trim();
        const elementName = this.elements.elementName.value.trim();
        const elementDescription = this.elements.elementDescription.value.trim();
        const elementAction = this.elements.elementAction.value.trim();
        const elementVoiceCommands = this.elements.elementVoiceCommands.value.trim();
        const elementX = parseInt(this.elements.elementX.value) || 0;
        const elementY = parseInt(this.elements.elementY.value) || 0;
        const elementWidth = parseInt(this.elements.elementWidth.value) || 50;
        const elementHeight = parseInt(this.elements.elementHeight.value) || 50;
        
        if (!elementId || !elementName || !elementAction) {
            console.error('Element ID, Name, and Action are required');
            return;
        }
        
        // Parse voice commands
        const voiceCommands = elementVoiceCommands 
            ? elementVoiceCommands.split(',').map(cmd => cmd.trim()).filter(cmd => cmd)
            : [elementName.toLowerCase()];
        
        // Create new element object
        const newElement = {
            id: elementId,
            name: elementName,
            coordinates: {
                x: elementX,
                y: elementY
            },
            size: {
                width: elementWidth,
                height: elementHeight
            },
            voice_commands: voiceCommands,
            conditions: ["always_visible"],
            action: elementAction,
            description: elementDescription || `${elementName} element`
        };
        
        // Add to pending updates (this will be saved when Save button is clicked)
        if (!this.pendingNewElements) {
            this.pendingNewElements = {};
        }
        if (!this.pendingNewElements[selectedScreen]) {
            this.pendingNewElements[selectedScreen] = [];
        }
        this.pendingNewElements[selectedScreen].push(newElement);
        
        // Enable save button
        this.elements.saveButton.disabled = false;
        
        // Close modal
        this.closeAddElementModal();
        
        // Add success message
        this.addMessage('system', 
            `✅ New Element Queued for Addition\n` +
            `Screen: ${selectedScreen}\n` +
            `Element ID: ${elementId}\n` +
            `Name: ${elementName}\n` +
            `Action: ${elementAction}\n` +
            `Coordinates: (${elementX}, ${elementY})\n` +
            `Voice Commands: ${voiceCommands.join(', ')}\n` +
            `Click Save to add this element to the configuration.`
        );
        
        console.log('New element queued for screen:', selectedScreen, newElement);
    }
    
    downloadCurrentScreenshot() {
        if (!this.currentScreenshot) return;
        
        // Create download link
        const link = document.createElement('a');
        link.href = this.currentScreenshot.path;
        link.download = this.currentScreenshot.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
    
    async deleteCurrentScreenshot() {
        if (!this.currentScreenshot) return;
        
        if (confirm('Are you sure you want to delete this screenshot?')) {
            try {
                // Call API to delete the file
                const response = await fetch(`/api/screenshots/${this.currentScreenshot.id}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    // Remove from array
                    this.screenshots = this.screenshots.filter(s => s.id !== this.currentScreenshot.id);
                    this.screenshotCount--;
                    
                    // Remove from gallery
                    const thumbnail = this.elements.screenshotGallery.querySelector(`[data-screenshot-id="${this.currentScreenshot.id}"]`);
                    if (thumbnail) {
                        thumbnail.remove();
                    }
                    
                    // Update count
                    this.updateScreenshotCount();
                    
                    // Show empty state if no screenshots left
                    if (this.screenshotCount === 0) {
                        this.elements.screenshotGallery.innerHTML = `
                            <div class="gallery-empty">
                                <i class="fas fa-camera"></i>
                                <p>No screenshots yet</p>
                                <p>Click "Take Screenshot" to start</p>
                            </div>
                        `;
                    }
                    
                    // Close modal
                    this.closeScreenshotModal();
                    
                    this.addMessage('system', '🗑️ Screenshot deleted successfully');
                } else {
                    throw new Error(`Failed to delete screenshot: ${response.status}`);
                }
            } catch (error) {
                console.error('Error deleting screenshot:', error);
                this.addMessage('system', `❌ Error deleting screenshot: ${error.message}`);
            }
        }
    }
    
    saveSettings() {
        try {
            localStorage.setItem('kioskSpeechSettings', JSON.stringify(this.settings));
        } catch (error) {
            console.error('Error saving settings:', error);
        }
    }
    
    // Optimization Panel Methods
    toggleOptimizationPanel() {
        const panel = document.getElementById('optimizationPanel');
        if (!panel) return;
        
        if (panel.style.display === 'none' || !panel.style.display) {
            panel.style.display = 'block';
            this.refreshOptimizationStats();
        } else {
            panel.style.display = 'none';
        }
    }
    
    async setOptimizationPreset(preset) {
        try {
            const response = await fetch(`/api/optimization/preset/${preset}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                this.addMessage('system', `🚀 Performance preset set to "${preset}"\nModel: ${result.model.name}\nDescription: ${result.model.description}`);
                
                // Update current model display with preset-specific information
                if (this.optimizationPresets && this.optimizationPresets[preset]) {
                    const presetConfig = this.optimizationPresets[preset];
                    const modelInfo = {
                        name: `${presetConfig.name} Mode`,
                        description: `Model: ${presetConfig.model}`,
                        parameters: `Temperature: ${presetConfig.temperature}, Max Tokens: ${presetConfig.max_tokens}`,
                        estimated_latency: preset === 'speed' ? '< 1s' : preset === 'balanced' ? '< 2s' : '< 3s'
                    };
                    this.updateCurrentModel(modelInfo);
                } else {
                    this.updateCurrentModel(result.model);
                }
                
                this.updateActivePreset(preset);
            } else {
                throw new Error(`Failed to set preset: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Error setting optimization preset:', error);
            this.addMessage('system', `❌ Failed to set optimization preset: ${error.message}`);
        }
    }
    
    async clearOptimizationCaches() {
        try {
            const response = await fetch('/api/optimization/cache/clear', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                this.addMessage('system', '🗑️ All optimization caches cleared\nNext queries will rebuild cache for improved performance');
                this.refreshOptimizationStats();
            } else {
                throw new Error(`Failed to clear caches: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Error clearing caches:', error);
            this.addMessage('system', `❌ Failed to clear caches: ${error.message}`);
        }
    }
    
    async refreshOptimizationStats() {
        try {
            const response = await fetch('/api/optimization/stats');
            if (response.ok) {
                const stats = await response.json();
                this.updateOptimizationStats(stats);
            }
        } catch (error) {
            console.error('Error refreshing optimization stats:', error);
        }
    }
    
    updateOptimizationStats(stats) {
        const screenHitRate = document.getElementById('screenCacheHitRate');
        const responseHitRate = document.getElementById('responseCacheHitRate');
        const totalQueries = document.getElementById('totalQueries');
        
        if (screenHitRate && stats.cache_stats?.screen_cache) {
            screenHitRate.textContent = `${stats.cache_stats.screen_cache.hit_rate.toFixed(1)}%`;
        }
        
        if (responseHitRate && stats.cache_stats?.response_cache) {
            responseHitRate.textContent = `${stats.cache_stats.response_cache.hit_rate.toFixed(1)}%`;
        }
        
        if (totalQueries && stats.metrics) {
            totalQueries.textContent = stats.metrics.total_queries || 0;
        }
        
        // Update current model info
        if (stats.model_config?.current_model) {
            this.updateCurrentModel(stats.model_config.current_model);
        }
    }
    
    async loadOptimizationState() {
        try {
            // Load both current state and preset configurations
            const [currentResponse, presetsResponse] = await Promise.all([
                fetch('/api/optimization/current'),
                fetch('/api/optimization/presets')
            ]);
            
            if (currentResponse.ok && presetsResponse.ok) {
                const currentResult = await currentResponse.json();
                const presetsResult = await presetsResponse.json();
                
                if (currentResult.success && presetsResult.success) {
                    // Store presets for later use
                    this.optimizationPresets = presetsResult.presets;
                    
                    // Update active preset
                    this.updateActivePreset(currentResult.current_preset);
                    
                    // Update model info display with preset-specific information
                    const currentPreset = presetsResult.presets[currentResult.current_preset];
                    if (currentPreset) {
                        const modelInfo = {
                            name: `${currentPreset.name} Mode`,
                            description: `Model: ${currentPreset.model}`,
                            parameters: `Temperature: ${currentPreset.temperature}, Max Tokens: ${currentPreset.max_tokens}`,
                            estimated_latency: currentResult.current_preset === 'speed' ? '< 1s' :
                                             currentResult.current_preset === 'balanced' ? '< 2s' : '< 3s'
                        };
                        this.updateCurrentModel(modelInfo);
                    }
                    
                    // Update preset buttons with model information
                    this.updatePresetButtons(presetsResult.presets);
                }
            }
        } catch (error) {
            console.error('Error loading optimization state:', error);
            // Set default state
            this.updateActivePreset('balanced');
            this.updateCurrentModel({
                name: 'Balanced Mode',
                description: 'Model: qwen2.5:1.5b',
                parameters: 'Temperature: 0.1, Max Tokens: 512',
                estimated_latency: '< 2s'
            });
        }
    }
    
    updateCurrentModel(modelInfo) {
        const currentModelDiv = document.getElementById('currentModel');
        if (currentModelDiv && modelInfo) {
            currentModelDiv.innerHTML = `
                <div><strong>${modelInfo.name}</strong></div>
                <div style="font-size: 11px; color: #666; margin-top: 4px;">
                    ${modelInfo.description}<br>
                    ${modelInfo.parameters ? modelInfo.parameters + '<br>' : ''}
                    Latency: ${modelInfo.estimated_latency}
                </div>
            `;
        }
    }
    
    updatePresetButtons(presets) {
        const presetButtons = document.querySelectorAll('.preset-button');
        presetButtons.forEach(button => {
            const presetKey = button.dataset.preset;
            const preset = presets[presetKey];
            if (preset) {
                // Update button title with model information
                button.title = `${preset.name}: ${preset.description}\nModel: ${preset.model}\nTemperature: ${preset.temperature}, Max Tokens: ${preset.max_tokens}`;
            }
        });
    }
    
    updateActivePreset(activePreset) {
        const presetButtons = document.querySelectorAll('.preset-button');
        presetButtons.forEach(button => {
            if (button.dataset.preset === activePreset) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }
    
}

// Screenshot Annotation Mode Class
class ScreenshotAnnotationMode {
    constructor(kioskChat) {
        this.kioskChat = kioskChat;
        this.isActive = false;
        this.currentScreenshot = null;
        this.navbarPosition = { x: 50, y: 50 };
        this.screenshotDimensions = null;
        this.isDragging = false;
        this.dragOffset = { x: 0, y: 0 };
        this.isDrawing = false;
        this.drawStart = { x: 0, y: 0 };
        
        this.initializeEventListeners();
    }
    
    initializeEventListeners() {
        // Exit annotation mode
        this.kioskChat.elements.annotationExit.addEventListener('click', () => {
            this.exitMode();
        });
        
        // ESC key to exit
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isActive) {
                // Check if we're in drawing mode first
                const currentDrawingMode = this.kioskChat.elements.annotationDrawingMode.value;
                if (currentDrawingMode !== 'none') {
                    // Exit drawing mode first
                    this.kioskChat.elements.annotationDrawingMode.value = 'none';
                    this.handleAnnotationDrawingModeChange();
                    console.log('Escaped from drawing mode in annotation mode');
                } else {
                    // Only exit annotation mode if we're not in drawing mode
                    this.exitMode();
                    console.log('Escaped from annotation mode');
                }
            }
        });
        
        // Drawing mode change
        this.kioskChat.elements.annotationDrawingMode.addEventListener('change', () => {
            this.handleAnnotationDrawingModeChange();
        });
        
        // Save button
        this.kioskChat.elements.annotationSaveButton.addEventListener('click', () => {
            this.handleSave();
        });
        
        // Update with Screen Coords button
        this.kioskChat.elements.annotationUpdateButton.addEventListener('click', () => {
            this.handleUpdateClientCoords();
        });
        
        // Screen/Element dropdowns
        this.kioskChat.elements.annotationScreen.addEventListener('change', () => {
            this.handleScreenChange();
        });
        
        this.kioskChat.elements.annotationElement.addEventListener('change', () => {
            this.handleElementChange();
        });
        
        // Screenshot navigation
        this.kioskChat.elements.prevScreenshotBtn.addEventListener('click', () => {
            this.navigateScreenshot(-1);
        });
        
        this.kioskChat.elements.nextScreenshotBtn.addEventListener('click', () => {
            this.navigateScreenshot(1);
        });
        
        // Vignette controls
        this.kioskChat.elements.vignetteLabel.addEventListener('blur', () => {
            this.updateVignetteName();
        });
        
        this.kioskChat.elements.vignetteLabel.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.kioskChat.elements.vignetteLabel.blur();
            }
        });
        
        this.kioskChat.elements.vignetteSaveButton.addEventListener('click', () => {
            this.saveVignette();
        });
        
        // Screenshot annotation dropdown
        this.kioskChat.elements.screenshotAnnotation.addEventListener('change', () => {
            this.handleScreenshotAnnotationChange();
        });
        
        // Mouse position tracking
        this.kioskChat.elements.annotationDrawingOverlay.addEventListener('mousemove', (e) => {
            this.updateMousePosition(e);
        });
        
        // Drawing events
        this.kioskChat.elements.annotationDrawingOverlay.addEventListener('mousedown', (e) => {
            this.startDrawing(e);
        });
        
        this.kioskChat.elements.annotationDrawingOverlay.addEventListener('mousemove', (e) => {
            this.updateDrawing(e);
        });
        
        this.kioskChat.elements.annotationDrawingOverlay.addEventListener('mouseup', (e) => {
            this.endDrawing(e);
        });
        
        // Draggable navbar
        this.initializeDraggableNavbar();
    }
    
    initializeDraggableNavbar() {
        const navbar = this.kioskChat.elements.annotationNavbar;
        const dragHandle = navbar.querySelector('.drag-handle');
        
        const startDrag = (e) => {
            this.isDragging = true;
            const rect = navbar.getBoundingClientRect();
            this.dragOffset.x = e.clientX - rect.left;
            this.dragOffset.y = e.clientY - rect.top;
            
            document.addEventListener('mousemove', drag);
            document.addEventListener('mouseup', endDrag);
            
            navbar.style.cursor = 'grabbing';
            dragHandle.style.cursor = 'grabbing';
        };
        
        const drag = (e) => {
            if (!this.isDragging) return;
            
            const newX = e.clientX - this.dragOffset.x;
            const newY = e.clientY - this.dragOffset.y;
            
            // Constrain to viewport
            const maxX = window.innerWidth - navbar.offsetWidth;
            const maxY = window.innerHeight - navbar.offsetHeight;
            
            const constrainedX = Math.max(0, Math.min(newX, maxX));
            const constrainedY = Math.max(0, Math.min(newY, maxY));
            
            navbar.style.left = constrainedX + 'px';
            navbar.style.top = constrainedY + 'px';
            
            this.navbarPosition.x = constrainedX;
            this.navbarPosition.y = constrainedY;
        };
        
        const endDrag = () => {
            this.isDragging = false;
            document.removeEventListener('mousemove', drag);
            document.removeEventListener('mouseup', endDrag);
            
            navbar.style.cursor = 'move';
            dragHandle.style.cursor = 'grab';
        };
        
        dragHandle.addEventListener('mousedown', startDrag);
        navbar.addEventListener('mousedown', (e) => {
            if (e.target === navbar || e.target.closest('.annotation-navbar-content')) {
                startDrag(e);
            }
        });
    }
    
    enterMode(screenshotSrc, screenshotData = null) {
        if (this.isActive) return;
        
        this.isActive = true;
        this.currentScreenshot = { src: screenshotSrc, data: screenshotData };
        
        // Add annotation mode class to body for CSS styling
        document.body.classList.add('annotation-mode-active');
        
        // Set screenshot as background
        this.kioskChat.elements.annotationBackground.style.backgroundImage = `url(${screenshotSrc})`;
        
        // Reset position
        this.kioskChat.elements.annotationNavbar.style.left = this.navbarPosition.x + 'px';
        this.kioskChat.elements.annotationNavbar.style.top = this.navbarPosition.y + 'px';
        
        // Initialize dropdowns with current data
        this.populateDropdowns();
        
        // Initialize vignette system
        this.initializeVignetteSystem();
        
        // Show modal
        this.kioskChat.elements.screenshotAnnotationModal.style.display = 'block';
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
        
        console.log('Entered screenshot annotation mode:', screenshotSrc);
    }
    
    exitMode() {
        if (!this.isActive) return;
        
        this.isActive = false;
        this.currentScreenshot = null;
        
        // Remove annotation mode class from body
        document.body.classList.remove('annotation-mode-active');
        
        // Clean up drawing mode
        document.body.classList.remove('drawing-mode');
        this.kioskChat.elements.annotationDrawingOverlay.classList.remove('drawing-mode');
        this.kioskChat.elements.annotationDrawingMode.value = 'none';
        
        // Hide modal
        this.kioskChat.elements.screenshotAnnotationModal.style.display = 'none';
        
        // Restore body scroll
        document.body.style.overflow = '';
        
        // Clean up annotation-specific state
        this.currentRectangle = null;
        this.kioskChat.elements.annotationUpdateButton.style.display = 'none';
        this.kioskChat.elements.annotationSaveButton.disabled = true;
        
        // Reset drawing state
        this.resetDrawing();
        
        console.log('Exited screenshot annotation mode');
    }
    
    populateDropdowns() {
        // Clear existing options
        this.kioskChat.elements.annotationScreen.innerHTML = '<option value="">Screen</option>';
        this.kioskChat.elements.annotationElement.innerHTML = '<option value="">Element</option>';
        
        // Populate screen dropdown
        if (this.kioskChat.kioskData && this.kioskChat.kioskData.screens) {
            Object.entries(this.kioskChat.kioskData.screens).forEach(([screenKey, screen]) => {
                const option = document.createElement('option');
                option.value = screenKey;
                option.textContent = screen.name || screenKey;
                this.kioskChat.elements.annotationScreen.appendChild(option);
            });
            
            // Add "Add New Screen..." option
            const addNewOption = document.createElement('option');
            addNewOption.value = '__add_new_screen__';
            addNewOption.textContent = '+ Add New Screen...';
            addNewOption.style.fontStyle = 'italic';
            addNewOption.style.color = '#667eea';
            this.kioskChat.elements.annotationScreen.appendChild(addNewOption);
        }
    }
    
    handleScreenChange() {
        const selectedScreen = this.kioskChat.elements.annotationScreen.value;
        
        if (selectedScreen === '__add_new_screen__') {
            // Show add screen modal
            this.kioskChat.showAddScreenModal();
            this.kioskChat.elements.annotationScreen.value = '';
            return;
        }
        
        // Update element dropdown
        this.updateElementDropdown(selectedScreen);
        
        // Update element overlays if elements are currently visible
        if (this.kioskChat.elementsVisible && selectedScreen) {
            this.kioskChat.showElementOverlays(selectedScreen);
        } else if (!selectedScreen) {
            this.kioskChat.clearElementOverlays();
        }
    }
    
    updateElementDropdown(selectedScreen) {
        this.kioskChat.elements.annotationElement.innerHTML = '<option value="">Element</option>';
        
        if (!selectedScreen || !this.kioskChat.kioskData?.screens?.[selectedScreen]) {
            return;
        }
        
        const screenData = this.kioskChat.kioskData.screens[selectedScreen];
        if (screenData.elements) {
            screenData.elements.forEach(element => {
                const option = document.createElement('option');
                option.value = element.id;
                option.textContent = element.name || element.id;
                this.kioskChat.elements.annotationElement.appendChild(option);
            });
        }
        
        // Add "Add New Element..." option
        const addNewOption = document.createElement('option');
        addNewOption.value = '__add_new_element__';
        addNewOption.textContent = '+ Add New Element...';
        addNewOption.style.fontStyle = 'italic';
        addNewOption.style.color = '#667eea';
        this.kioskChat.elements.annotationElement.appendChild(addNewOption);
    }
    
    handleElementChange() {
        const selectedElement = this.kioskChat.elements.annotationElement.value;
        
        if (selectedElement === '__add_new_element__') {
            // Show add element modal
            this.kioskChat.showAddElementModal();
            this.kioskChat.elements.annotationElement.value = '';
            return;
        }
    }
    
    updateMousePosition(e) {
        const imageCoords = this.screenToImageCoordinates(e.clientX, e.clientY);
        this.kioskChat.elements.annotationMouseX.textContent = Math.round(imageCoords.x);
        this.kioskChat.elements.annotationMouseY.textContent = Math.round(imageCoords.y);
    }
    
    startDrawing(e) {
        if (this.kioskChat.elements.annotationDrawingMode.value !== 'rectangle') return;
        
        this.isDrawing = true;
        const coords = this.screenToImageCoordinates(e.clientX, e.clientY);
        this.drawStart = coords;
        
        const rect = this.kioskChat.elements.annotationDrawingRectangle;
        const screenCoords = this.imageToScreenCoordinates(coords.x, coords.y);
        
        rect.style.left = screenCoords.x + 'px';
        rect.style.top = screenCoords.y + 'px';
        rect.style.width = '0px';
        rect.style.height = '0px';
        rect.style.display = 'block';
    }
    
    updateDrawing(e) {
        if (!this.isDrawing) return;
        
        const coords = this.screenToImageCoordinates(e.clientX, e.clientY);
        const rect = this.kioskChat.elements.annotationDrawingRectangle;
        
        const left = Math.min(this.drawStart.x, coords.x);
        const top = Math.min(this.drawStart.y, coords.y);
        const width = Math.abs(coords.x - this.drawStart.x);
        const height = Math.abs(coords.y - this.drawStart.y);
        
        const screenCoords = this.imageToScreenCoordinates(left, top);
        const screenSize = this.imageToScreenSize(width, height);
        
        rect.style.left = screenCoords.x + 'px';
        rect.style.top = screenCoords.y + 'px';
        rect.style.width = screenSize.width + 'px';
        rect.style.height = screenSize.height + 'px';
    }
    
    endDrawing(e) {
        if (!this.isDrawing) return;
        
        this.isDrawing = false;
        const coords = this.screenToImageCoordinates(e.clientX, e.clientY);
        
        const left = Math.min(this.drawStart.x, coords.x);
        const top = Math.min(this.drawStart.y, coords.y);
        const width = Math.abs(coords.x - this.drawStart.x);
        const height = Math.abs(coords.y - this.drawStart.y);
        
        // Only create rectangle if it has meaningful size
        if (width > 10 && height > 10) {
            // Store rectangle data but don't enable save button yet
            this.currentRectangle = {
                x: Math.round(left),
                y: Math.round(top),
                width: Math.round(width),
                height: Math.round(height)
            };
            
            console.log('Rectangle drawn:', this.currentRectangle);
            
            // Show the update button in navbar when rectangle is drawn
            this.showUpdateButton();
        } else {
            this.resetDrawing();
        }
    }
    
    resetDrawing() {
        this.isDrawing = false;
        this.kioskChat.elements.annotationDrawingRectangle.style.display = 'none';
        
        // Only disable save button if there are no pending updates
        const hasPendingUpdates = Object.keys(this.kioskChat.pendingUpdates || {}).length > 0;
        console.log('resetDrawing called, pendingUpdates:', this.kioskChat.pendingUpdates, 'hasPendingUpdates:', hasPendingUpdates);
        if (!hasPendingUpdates) {
            this.kioskChat.elements.annotationSaveButton.disabled = true;
            console.log('Annotation mode: Save button disabled by resetDrawing (no pending updates)');
        } else {
            console.log('Annotation mode: Save button kept enabled by resetDrawing (has pending updates)');
        }
        
        // Don't hide the update button in resetDrawing - it should only be hidden
        // when annotation mode is exited or when Save is clicked
        // The currentRectangle is kept so the update button can still be used
        console.log('resetDrawing: keeping currentRectangle and update button visible');
    }
    
    showUpdateButton() {
        this.kioskChat.elements.annotationUpdateButton.style.display = 'inline-flex';
    }
    
    handleUpdateClientCoords() {
        if (!this.currentRectangle) {
            alert('No rectangle data available');
            return;
        }
        
        const selectedScreen = this.kioskChat.elements.annotationScreen.value;
        const selectedElement = this.kioskChat.elements.annotationElement.value;
        
        if (!selectedScreen || !selectedElement) {
            alert('Please select both a screen and element from the dropdowns before updating coordinates.');
            return;
        }
        
        // Use client bounds coordinates same as main interface
        // Main interface uses this.lastRectangleCoords.x/y which are bounds coordinates
        
        // Use the existing coordinate update system (use dot separator to match main interface)
        const updateKey = `${selectedScreen}.${selectedElement}`;
        this.kioskChat.pendingUpdates[updateKey] = {
            screen: selectedScreen,
            elementId: selectedElement,
            newCoordinates: {
                x: this.currentRectangle.x,
                y: this.currentRectangle.y
            },
            newSize: {
                width: this.currentRectangle.width,
                height: this.currentRectangle.height
            }
        };
        
        // Enable the save button
        this.kioskChat.elements.annotationSaveButton.disabled = false;
        console.log('Annotation mode: Save button enabled after Update with Client Coords');
        
        // Show feedback message in chat
        this.kioskChat.addMessage('system', 
            `✅ Client Coordinate Update Queued\n` +
            `Screen: ${selectedScreen}\n` +
            `Element: ${selectedElement}\n` +
            `Bounds: ${this.currentRectangle.width}×${this.currentRectangle.height} at (${this.currentRectangle.x}, ${this.currentRectangle.y})\n` +
            `New Coordinates: (${this.currentRectangle.x}, ${this.currentRectangle.y}) [Client] New bounds: width ${this.currentRectangle.width} height ${this.currentRectangle.height}\n` +
            `Use the Save button in annotation mode to apply changes.`
        );
        
        console.log('Coordinates queued from navbar button:', updateKey, this.kioskChat.pendingUpdates[updateKey]);
        
        // Don't hide the update button here - it should only disappear when Save is clicked
    }
    
    handleAnnotationDrawingModeChange() {
        const mode = this.kioskChat.elements.annotationDrawingMode.value;
        const overlay = this.kioskChat.elements.annotationDrawingOverlay;
        
        console.log('Annotation drawing mode changed to:', mode);
        
        if (mode === 'rectangle') {
            // Enable drawing mode
            overlay.classList.add('drawing-mode');
            document.body.classList.add('drawing-mode');
            console.log('Annotation drawing mode enabled');
        } else {
            // Disable drawing mode
            overlay.classList.remove('drawing-mode');
            document.body.classList.remove('drawing-mode');
            this.resetDrawing();
            console.log('Annotation drawing mode disabled');
        }
    }
    
    screenToImageCoordinates(screenX, screenY) {
        const background = this.kioskChat.elements.annotationBackground;
        const rect = background.getBoundingClientRect();
        
        // Calculate the actual image dimensions and position within the container
        const containerAspect = rect.width / rect.height;
        let imageWidth, imageHeight, imageLeft, imageTop;
        
        // Assume 16:9 aspect ratio for screenshots (can be made dynamic)
        const imageAspect = 16 / 9;
        
        if (containerAspect > imageAspect) {
            // Container is wider than image - letterbox on sides
            imageHeight = rect.height;
            imageWidth = imageHeight * imageAspect;
            imageLeft = rect.left + (rect.width - imageWidth) / 2;
            imageTop = rect.top;
        } else {
            // Container is taller than image - letterbox on top/bottom
            imageWidth = rect.width;
            imageHeight = imageWidth / imageAspect;
            imageLeft = rect.left;
            imageTop = rect.top + (rect.height - imageHeight) / 2;
        }
        
        // Convert screen coordinates to image coordinates
        const relativeX = (screenX - imageLeft) / imageWidth;
        const relativeY = (screenY - imageTop) / imageHeight;
        
        // Assume image resolution (can be made dynamic)
        const imageResolutionX = 1920;
        const imageResolutionY = 1080;
        
        return {
            x: relativeX * imageResolutionX,
            y: relativeY * imageResolutionY
        };
    }
    
    imageToScreenCoordinates(imageX, imageY) {
        const background = this.kioskChat.elements.annotationBackground;
        const rect = background.getBoundingClientRect();
        
        // Calculate the actual image dimensions and position within the container
        const containerAspect = rect.width / rect.height;
        let imageWidth, imageHeight, imageLeft, imageTop;
        
        const imageAspect = 16 / 9;
        
        if (containerAspect > imageAspect) {
            imageHeight = rect.height;
            imageWidth = imageHeight * imageAspect;
            imageLeft = rect.left + (rect.width - imageWidth) / 2;
            imageTop = rect.top;
        } else {
            imageWidth = rect.width;
            imageHeight = imageWidth / imageAspect;
            imageLeft = rect.left;
            imageTop = rect.top + (rect.height - imageHeight) / 2;
        }
        
        const imageResolutionX = 1920;
        const imageResolutionY = 1080;
        
        const relativeX = imageX / imageResolutionX;
        const relativeY = imageY / imageResolutionY;
        
        return {
            x: imageLeft + relativeX * imageWidth,
            y: imageTop + relativeY * imageHeight
        };
    }
    
    imageToScreenSize(imageWidth, imageHeight) {
        const background = this.kioskChat.elements.annotationBackground;
        const rect = background.getBoundingClientRect();
        
        const containerAspect = rect.width / rect.height;
        const imageAspect = 16 / 9;
        
        let displayImageWidth, displayImageHeight;
        
        if (containerAspect > imageAspect) {
            displayImageHeight = rect.height;
            displayImageWidth = displayImageHeight * imageAspect;
        } else {
            displayImageWidth = rect.width;
            displayImageHeight = displayImageWidth / imageAspect;
        }
        
        const imageResolutionX = 1920;
        const imageResolutionY = 1080;
        
        return {
            width: (imageWidth / imageResolutionX) * displayImageWidth,
            height: (imageHeight / imageResolutionY) * displayImageHeight
        };
    }
    
    handleSave() {
        // Check if there are pending updates to save
        const hasPendingUpdates = Object.keys(this.kioskChat.pendingUpdates || {}).length > 0;
        
        if (!hasPendingUpdates) {
            alert('No pending updates to save. Please click "Update with Screen Coords" first.');
            return;
        }
        
        // Call the main save handler to process pending updates
        this.kioskChat.handleSaveCoordinates();
        
        // Hide the update button and disable save button after successful save
        this.kioskChat.elements.annotationUpdateButton.style.display = 'none';
        this.kioskChat.elements.annotationSaveButton.disabled = true;
        
        // Show success message
        this.kioskChat.addMessage('system', 
            `✅ Pending coordinate updates saved to config file\n` +
            `All queued changes have been applied.`
        );
    }
    
    // Vignette and Screenshot Navigation Methods
    navigateScreenshot(direction) {
        const screenshots = this.kioskChat.vignettes.current.screenshots;
        if (screenshots.length === 0) return;
        
        const newIndex = this.kioskChat.currentScreenshotIndex + direction;
        
        if (newIndex >= 0 && newIndex < screenshots.length) {
            this.kioskChat.currentScreenshotIndex = newIndex;
            this.updateScreenshotDisplay();
            this.updateNavigationButtons();
            this.updateScreenshotOrder();
        }
    }
    
    updateScreenshotDisplay() {
        const screenshots = this.kioskChat.vignettes.current.screenshots;
        if (screenshots.length === 0) return;
        
        const currentScreenshotId = screenshots[this.kioskChat.currentScreenshotIndex];
        const screenshot = this.kioskChat.screenshots.find(s => s.id === currentScreenshotId);
        
        if (screenshot) {
            // Update the annotation background with current screenshot
            const annotationBackground = this.kioskChat.elements.annotationBackground;
            annotationBackground.style.backgroundImage = `url('${screenshot.path}')`;
            annotationBackground.style.backgroundSize = 'contain';
            annotationBackground.style.backgroundRepeat = 'no-repeat';
            annotationBackground.style.backgroundPosition = 'center';
            
            // Load annotation data for this screenshot if it exists
            this.loadScreenshotAnnotation(currentScreenshotId);
        }
    }
    
    updateNavigationButtons() {
        const screenshots = this.kioskChat.vignettes.current.screenshots;
        this.kioskChat.elements.prevScreenshotBtn.disabled = this.kioskChat.currentScreenshotIndex <= 0;
        this.kioskChat.elements.nextScreenshotBtn.disabled = this.kioskChat.currentScreenshotIndex >= screenshots.length - 1;
    }
    
    updateScreenshotOrder() {
        const screenshots = this.kioskChat.vignettes.current.screenshots;
        const orderText = screenshots.length === 0 ? '0 of 0' : `${this.kioskChat.currentScreenshotIndex + 1} of ${screenshots.length}`;
        this.kioskChat.elements.screenshotOrder.textContent = orderText;
    }
    
    updateVignetteName() {
        const newName = this.kioskChat.elements.vignetteLabel.textContent.trim();
        if (newName && newName !== this.kioskChat.currentVignetteName) {
            this.kioskChat.currentVignetteName = newName;
            this.kioskChat.vignettes.current.name = newName;
            this.kioskChat.vignettes.current.modified = new Date().toISOString();
            this.updateVignetteSaveButton();
        }
    }
    
    handleScreenshotAnnotationChange() {
        const selectedScreen = this.kioskChat.elements.screenshotAnnotation.value;
        if (!selectedScreen) return;
        
        const screenshots = this.kioskChat.vignettes.current.screenshots;
        if (screenshots.length === 0) return;
        
        const currentScreenshotId = screenshots[this.kioskChat.currentScreenshotIndex];
        
        // Store the annotation for this screenshot
        if (!this.kioskChat.vignettes.current.annotations[currentScreenshotId]) {
            this.kioskChat.vignettes.current.annotations[currentScreenshotId] = {};
        }
        
        this.kioskChat.vignettes.current.annotations[currentScreenshotId].screenAnnotation = selectedScreen;
        this.kioskChat.vignettes.current.modified = new Date().toISOString();
        this.updateVignetteSaveButton();
    }
    
    loadScreenshotAnnotation(screenshotId) {
        const annotation = this.kioskChat.vignettes.current.annotations[screenshotId];
        if (annotation && annotation.screenAnnotation) {
            this.kioskChat.elements.screenshotAnnotation.value = annotation.screenAnnotation;
        } else {
            this.kioskChat.elements.screenshotAnnotation.value = '';
        }
    }
    
    updateVignetteSaveButton() {
        // Enable vignette save button if there are any screenshots or changes
        const hasScreenshots = this.kioskChat.vignettes.current.screenshots.length > 0;
        const hasAnnotations = Object.keys(this.kioskChat.vignettes.current.annotations).length > 0;
        this.kioskChat.elements.vignetteSaveButton.disabled = !(hasScreenshots || hasAnnotations);
    }
    
    async saveVignette() {
        try {
            const vignetteData = {
                name: this.kioskChat.vignettes.current.name,
                screenshots: this.kioskChat.vignettes.current.screenshots,
                annotations: this.kioskChat.vignettes.current.annotations,
                created: this.kioskChat.vignettes.current.created,
                modified: new Date().toISOString(),
                screenshotData: []
            };
            
            // Include actual screenshot data
            for (const screenshotId of this.kioskChat.vignettes.current.screenshots) {
                const screenshot = this.kioskChat.screenshots.find(s => s.id === screenshotId);
                if (screenshot) {
                    vignetteData.screenshotData.push({
                        id: screenshot.id,
                        filename: screenshot.filename,
                        path: screenshot.path,
                        timestamp: screenshot.timestamp,
                        size: screenshot.size
                    });
                }
            }
            
            // Save to server/local storage
            await this.saveVignetteToStorage(vignetteData);
            
            this.kioskChat.addMessage('system', 
                `📁 Vignette "${vignetteData.name}" saved successfully\n` +
                `Screenshots: ${vignetteData.screenshots.length}\n` +
                `Annotations: ${Object.keys(vignetteData.annotations).length}`
            );
            
        } catch (error) {
            console.error('Error saving vignette:', error);
            this.kioskChat.addMessage('system', `❌ Error saving vignette: ${error.message}`);
        }
    }
    
    async saveVignetteToStorage(vignetteData) {
        // For now, save to localStorage. In production, this could save to server
        const vignetteKey = `vignette_${vignetteData.name.replace(/[^a-zA-Z0-9]/g, '_')}`;
        localStorage.setItem(vignetteKey, JSON.stringify(vignetteData));
        
        // Also update a list of all vignettes
        const vignettesListKey = 'saved_vignettes';
        const existingVignettes = JSON.parse(localStorage.getItem(vignettesListKey) || '[]');
        
        const existingIndex = existingVignettes.findIndex(v => v.name === vignetteData.name);
        const vignetteInfo = {
            name: vignetteData.name,
            created: vignetteData.created,
            modified: vignetteData.modified,
            screenshotCount: vignetteData.screenshots.length,
            annotationCount: Object.keys(vignetteData.annotations).length
        };
        
        if (existingIndex >= 0) {
            existingVignettes[existingIndex] = vignetteInfo;
        } else {
            existingVignettes.push(vignetteInfo);
        }
        
        localStorage.setItem(vignettesListKey, JSON.stringify(existingVignettes));
    }
    
    // Initialize vignette system when annotation mode opens
    initializeVignetteSystem() {
        // Add all current screenshots to the vignette if not already present
        for (const screenshot of this.kioskChat.screenshots) {
            if (!this.kioskChat.vignettes.current.screenshots.includes(screenshot.id)) {
                this.kioskChat.vignettes.current.screenshots.push(screenshot.id);
            }
        }
        
        // Populate screenshot annotation dropdown with available screens
        this.populateScreenshotAnnotationDropdown();
        
        // Update initial display
        if (this.kioskChat.vignettes.current.screenshots.length > 0) {
            this.kioskChat.currentScreenshotIndex = 0;
            this.updateScreenshotDisplay();
        }
        this.updateNavigationButtons();
        this.updateScreenshotOrder();
        this.updateVignetteSaveButton();
        
        // Set initial vignette name
        this.kioskChat.elements.vignetteLabel.textContent = this.kioskChat.vignettes.current.name;
    }
    
    populateScreenshotAnnotationDropdown() {
        const dropdown = this.kioskChat.elements.screenshotAnnotation;
        
        // Clear existing options except the default
        while (dropdown.children.length > 1) {
            dropdown.removeChild(dropdown.lastChild);
        }
        
        // Add screen options from kiosk data
        if (this.kioskChat.kioskData && this.kioskChat.kioskData.screens) {
            for (const [screenId, screenData] of Object.entries(this.kioskChat.kioskData.screens)) {
                const option = document.createElement('option');
                option.value = screenId;
                option.textContent = screenData.name || screenId;
                dropdown.appendChild(option);
            }
        }
    }

    // Text Reading Functionality
    initializeTextReading() {
        // Get elements
        this.elements.readTextButton = document.getElementById('readTextButton');
        this.elements.regionSelectionCanvas = document.getElementById('regionSelectionCanvas');
        this.elements.regionSelectionInfo = document.getElementById('regionSelectionInfo');
        this.elements.regionCoordinates = document.getElementById('regionCoordinates');
        
        // Text reading modal elements
        this.elements.textReadingModal = document.getElementById('textReadingModal');
        this.elements.textReadingBackdrop = document.getElementById('textReadingBackdrop');
        this.elements.textReadingClose = document.getElementById('textReadingClose');
        this.elements.extractionStatus = document.getElementById('extractionStatus');
        this.elements.extractedTextContainer = document.getElementById('extractedTextContainer');
        this.elements.extractedText = document.getElementById('extractedText');
        this.elements.textConfidence = document.getElementById('textConfidence');
        this.elements.wordCount = document.getElementById('wordCount');
        this.elements.audioControls = document.getElementById('audioControls');
        this.elements.textAudio = document.getElementById('textAudio');
        this.elements.speechRate = document.getElementById('speechRate');
        this.elements.speechVolume = document.getElementById('speechVolume');
        this.elements.extractionError = document.getElementById('extractionError');
        this.elements.errorMessage = document.getElementById('errorMessage');
        this.elements.regenerateAudioButton = document.getElementById('regenerateAudioButton');
        this.elements.copyTextButton = document.getElementById('copyTextButton');
        this.elements.retryExtractionButton = document.getElementById('retryExtractionButton');

        // Initialize text reading state
        this.textReading = {
            isSelecting: false,
            selectionStart: null,
            selectionEnd: null,
            selectedRegion: null,
            currentScreenshot: null,
            extractedText: null,
            audioPath: null
        };

        // Bind events
        this.bindTextReadingEvents();
    }

    bindTextReadingEvents() {
        // Read text button
        this.elements.readTextButton?.addEventListener('click', () => {
            this.startRegionSelection();
        });

        // Canvas events for region selection
        this.elements.regionSelectionCanvas?.addEventListener('mousedown', (e) => {
            if (this.textReading.isSelecting) {
                this.startSelection(e);
            }
        });

        this.elements.regionSelectionCanvas?.addEventListener('mousemove', (e) => {
            if (this.textReading.isSelecting) {
                this.updateSelection(e);
            }
        });

        this.elements.regionSelectionCanvas?.addEventListener('mouseup', (e) => {
            if (this.textReading.isSelecting) {
                this.endSelection(e);
            }
        });

        // Text reading modal events
        this.elements.textReadingClose?.addEventListener('click', () => {
            this.closeTextReadingModal();
        });

        this.elements.textReadingBackdrop?.addEventListener('click', () => {
            this.closeTextReadingModal();
        });

        // Button events
        this.elements.regenerateAudioButton?.addEventListener('click', () => {
            this.regenerateAudio();
        });

        this.elements.copyTextButton?.addEventListener('click', () => {
            this.copyExtractedText();
        });

        this.elements.retryExtractionButton?.addEventListener('click', () => {
            this.retryTextExtraction();
        });

        // Audio settings events
        this.elements.speechRate?.addEventListener('change', () => {
            if (this.textReading.extractedText) {
                this.regenerateAudio();
            }
        });

        this.elements.speechVolume?.addEventListener('change', (e) => {
            const audio = this.elements.textAudio;
            if (audio) {
                audio.volume = e.target.value / 100;
            }
        });
    }

    startRegionSelection() {
        const modalImage = this.elements.modalImage;
        const canvas = this.elements.regionSelectionCanvas;
        const infoDiv = this.elements.regionSelectionInfo;

        if (!modalImage || !canvas) return;

        // Set canvas size to match image
        canvas.width = modalImage.offsetWidth;
        canvas.height = modalImage.offsetHeight;
        canvas.style.width = modalImage.offsetWidth + 'px';
        canvas.style.height = modalImage.offsetHeight + 'px';

        // Show canvas and info
        canvas.style.display = 'block';
        canvas.classList.add('active');
        infoDiv.style.display = 'block';

        // Update button state
        this.elements.readTextButton.innerHTML = '<i class="fas fa-times"></i> Cancel Selection';
        this.elements.readTextButton.onclick = () => this.cancelRegionSelection();

        // Set selection state
        this.textReading.isSelecting = true;
        this.textReading.currentScreenshot = this.currentScreenshot;

        // Update info text
        this.elements.regionCoordinates.textContent = 'Click and drag to select text region';
    }

    cancelRegionSelection() {
        const canvas = this.elements.regionSelectionCanvas;
        const infoDiv = this.elements.regionSelectionInfo;

        // Hide canvas and info
        canvas.style.display = 'none';
        canvas.classList.remove('active');
        infoDiv.style.display = 'none';

        // Clear canvas
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Reset button
        this.elements.readTextButton.innerHTML = '<i class="fas fa-font"></i> Read Text';
        this.elements.readTextButton.onclick = () => this.startRegionSelection();

        // Reset state
        this.textReading.isSelecting = false;
        this.textReading.selectionStart = null;
        this.textReading.selectionEnd = null;
        this.textReading.selectedRegion = null;
    }

    startSelection(e) {
        const rect = this.elements.regionSelectionCanvas.getBoundingClientRect();
        this.textReading.selectionStart = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
    }

    updateSelection(e) {
        if (!this.textReading.selectionStart) return;

        const rect = this.elements.regionSelectionCanvas.getBoundingClientRect();
        const currentPos = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };

        this.drawSelectionRectangle(this.textReading.selectionStart, currentPos);
        this.updateSelectionInfo(this.textReading.selectionStart, currentPos);
    }

    endSelection(e) {
        if (!this.textReading.selectionStart) return;

        const rect = this.elements.regionSelectionCanvas.getBoundingClientRect();
        this.textReading.selectionEnd = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };

        // Calculate region
        const region = this.calculateRegion(this.textReading.selectionStart, this.textReading.selectionEnd);
        
        if (region.width > 10 && region.height > 10) { // Minimum size
            this.textReading.selectedRegion = region;
            this.processTextExtraction(region);
        } else {
            alert('Selected region is too small. Please select a larger area.');
        }
    }

    drawSelectionRectangle(start, end) {
        const canvas = this.elements.regionSelectionCanvas;
        const ctx = canvas.getContext('2d');

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw selection rectangle
        ctx.strokeStyle = '#4CAF50';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.fillStyle = 'rgba(76, 175, 80, 0.1)';

        const x = Math.min(start.x, end.x);
        const y = Math.min(start.y, end.y);
        const width = Math.abs(end.x - start.x);
        const height = Math.abs(end.y - start.y);

        ctx.fillRect(x, y, width, height);
        ctx.strokeRect(x, y, width, height);
    }

    calculateRegion(start, end) {
        const modalImage = this.elements.modalImage;
        
        // Convert canvas coordinates to image coordinates
        const scaleX = modalImage.naturalWidth / modalImage.offsetWidth;
        const scaleY = modalImage.naturalHeight / modalImage.offsetHeight;

        const x = Math.min(start.x, end.x) * scaleX;
        const y = Math.min(start.y, end.y) * scaleY;
        const width = Math.abs(end.x - start.x) * scaleX;
        const height = Math.abs(end.y - start.y) * scaleY;

        return {
            x: Math.round(x),
            y: Math.round(y),
            width: Math.round(width),
            height: Math.round(height)
        };
    }

    updateSelectionInfo(start, current) {
        const region = this.calculateRegion(start, current);
        this.elements.regionCoordinates.textContent = 
            `Region: ${region.x}, ${region.y} (${region.width} × ${region.height})`;
    }

    async processTextExtraction(region) {
        // Hide selection UI
        this.cancelRegionSelection();

        // Show text reading modal
        this.showTextReadingModal();
        this.showExtractionStatus('Extracting text from selected region...');

        try {
            // Extract text using OCR MCP service
            const ocrResult = await this.callMCPTool('extract_text_from_region', {
                image_path: this.textReading.currentScreenshot.path,
                region: region,
                language: 'eng',
                preprocess: true
            });

            if (!ocrResult.success) {
                throw new Error(ocrResult.error || 'OCR extraction failed');
            }

            const textData = ocrResult.data;
            if (!textData.text || textData.text.trim().length === 0) {
                throw new Error('No text found in selected region');
            }

            this.textReading.extractedText = textData.text;

            // Show extracted text
            this.showExtractedText(textData);

            // Generate audio
            await this.generateTextAudio(textData.text);

        } catch (error) {
            console.error('Text extraction failed:', error);
            this.showExtractionError(error.message);
        }
    }

    async generateTextAudio(text) {
        this.updateExtractionStatus('Generating audio...');

        try {
            const rate = parseInt(this.elements.speechRate.value) || 200;
            const volume = parseFloat(this.elements.speechVolume.value) / 100 || 0.8;

            const ttsResult = await this.callMCPTool('text_to_speech', {
                text: text,
                rate: rate,
                volume: volume
            });

            if (!ttsResult.success) {
                throw new Error(ttsResult.error || 'Audio generation failed');
            }

            this.textReading.audioPath = ttsResult.data.audio_path;
            
            // Load audio
            const audioUrl = `/temp_audio/${ttsResult.data.audio_path.split('/').pop()}`;
            this.elements.textAudio.src = audioUrl;
            this.elements.textAudio.volume = volume;

            // Show audio controls
            this.elements.audioControls.style.display = 'block';
            this.elements.regenerateAudioButton.style.display = 'inline-block';

            this.hideExtractionStatus();

        } catch (error) {
            console.error('Audio generation failed:', error);
            this.showExtractionError(`Audio generation failed: ${error.message}`);
        }
    }

    showTextReadingModal() {
        this.elements.textReadingModal.style.display = 'flex';
    }

    closeTextReadingModal() {
        this.elements.textReadingModal.style.display = 'none';
        this.resetTextReadingState();
    }

    showExtractionStatus(message) {
        this.elements.extractionStatus.querySelector('span').textContent = message;
        this.elements.extractionStatus.style.display = 'block';
        this.elements.extractedTextContainer.style.display = 'none';
        this.elements.extractionError.style.display = 'none';
    }

    updateExtractionStatus(message) {
        this.elements.extractionStatus.querySelector('span').textContent = message;
    }

    hideExtractionStatus() {
        this.elements.extractionStatus.style.display = 'none';
    }

    showExtractedText(textData) {
        this.elements.extractedText.textContent = textData.text;
        this.elements.textConfidence.textContent = `${Math.round(textData.confidence * 100)}%`;
        this.elements.wordCount.textContent = textData.word_count || textData.text.split(' ').length;

        this.elements.extractedTextContainer.style.display = 'block';
        this.elements.copyTextButton.style.display = 'inline-block';
        this.hideExtractionStatus();
    }

    showExtractionError(message) {
        this.elements.errorMessage.textContent = message;
        this.elements.extractionError.style.display = 'block';
        this.elements.retryExtractionButton.style.display = 'inline-block';
        this.elements.extractedTextContainer.style.display = 'none';
        this.hideExtractionStatus();
    }

    async regenerateAudio() {
        if (!this.textReading.extractedText) return;
        await this.generateTextAudio(this.textReading.extractedText);
    }

    copyExtractedText() {
        if (!this.textReading.extractedText) return;
        
        navigator.clipboard.writeText(this.textReading.extractedText).then(() => {
            // Show temporary success message
            const originalText = this.elements.copyTextButton.innerHTML;
            this.elements.copyTextButton.innerHTML = '<i class="fas fa-check"></i> Copied!';
            setTimeout(() => {
                this.elements.copyTextButton.innerHTML = originalText;
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy text:', err);
            alert('Failed to copy text to clipboard');
        });
    }

    retryTextExtraction() {
        if (this.textReading.selectedRegion) {
            this.processTextExtraction(this.textReading.selectedRegion);
        }
    }

    resetTextReadingState() {
        this.textReading.isSelecting = false;
        this.textReading.selectionStart = null;
        this.textReading.selectionEnd = null;
        this.textReading.selectedRegion = null;
        this.textReading.currentScreenshot = null;
        this.textReading.extractedText = null;
        this.textReading.audioPath = null;

        // Reset UI
        if (this.elements.textAudio) {
            this.elements.textAudio.src = '';
        }
        this.elements.audioControls.style.display = 'none';
        this.elements.regenerateAudioButton.style.display = 'none';
        this.elements.copyTextButton.style.display = 'none';
        this.elements.retryExtractionButton.style.display = 'none';
    }
}

// Debug: Check if script is loading
console.log('JavaScript file loading...');
console.log('Document ready state:', document.readyState);
console.log('DOMContentLoaded listener about to be added');

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded event fired!');
    console.log('DOM loaded, creating KioskSpeechChat instance...');
    
    // Clear any existing instance
    if (window.kioskChat) {
        console.log('Existing kioskChat found, clearing it');
        window.kioskChat = null;
    }
    
    try {
        const instance = new KioskSpeechChat();
        window.kioskChat = instance;
        console.log('KioskSpeechChat instantiated successfully');
        console.log('window.kioskChat assigned:', window.kioskChat);
        
        // Make it even more persistent
        Object.defineProperty(window, 'kioskChatBackup', {
            value: instance,
            writable: false,
            configurable: false
        });
        console.log('Backup reference created');
        
        // Test the object periodically
        setInterval(() => {
            if (!window.kioskChat) {
                console.error('window.kioskChat has been lost! Timestamp:', new Date().toISOString());
                console.log('Attempting to restore from backup...');
                if (window.kioskChatBackup) {
                    window.kioskChat = window.kioskChatBackup;
                    console.log('Restored from backup');
                } else {
                    console.error('Backup is also missing!');
                }
            }
        }, 5000); // Check every 5 seconds
        
    } catch (error) {
        console.error('Error creating KioskSpeechChat instance:', error);
        console.error('Error stack:', error.stack);
        return;
    }
    
    // Debug: Check if methods are accessible
    console.log('window.kioskChat created:', window.kioskChat);
    console.log('handleUpdateCoordinatesScreen available:', typeof window.kioskChat.handleUpdateCoordinatesScreen);
    console.log('handleUpdateCoordinates available:', typeof window.kioskChat.handleUpdateCoordinates);
    
    // Try to access method directly
    try {
        console.log('Direct method access:', window.kioskChat.handleUpdateCoordinatesScreen);
    } catch (e) {
        console.error('Error accessing method:', e);
    }
    
    // List all methods available on kioskChat
    console.log('Available methods on kioskChat:');
    for (let method in window.kioskChat) {
        if (typeof window.kioskChat[method] === 'function') {
            console.log('- ' + method);
        }
    }
    
    // Also check prototype
    console.log('Prototype methods:');
    const proto = Object.getPrototypeOf(window.kioskChat);
    const props = Object.getOwnPropertyNames(proto);
    props.forEach(prop => {
        if (typeof window.kioskChat[prop] === 'function') {
            console.log('- ' + prop + ' (from prototype)');
        }
    });
});

// Alternative initialization - run immediately if DOM is already loaded
if (document.readyState === 'loading') {
    console.log('Document still loading, DOMContentLoaded listener should work');
} else {
    console.log('Document already loaded, running initialization immediately');
    try {
        if (!window.kioskChat) {
            const instance = new KioskSpeechChat();
            window.kioskChat = instance;
            Object.defineProperty(window, 'kioskChatBackup', {
                value: instance,
                writable: false,
                configurable: false
            });
            console.log('KioskSpeechChat created immediately (DOM already loaded)');
        } else {
            console.log('KioskSpeechChat already exists');
        }
    } catch (error) {
        console.error('Error creating KioskSpeechChat immediately:', error);
    }
}

// Export for potential external use
window.KioskSpeechChat = KioskSpeechChat;

// Global wrapper functions for onclick handlers
window.handleUpdateCoordinatesScreen = function(messageId) {
    console.log('Global wrapper called for handleUpdateCoordinatesScreen with messageId:', messageId);
    
    // Try to get kioskChat instance, with backup fallback
    let kioskChatInstance = window.kioskChat;
    if (!kioskChatInstance && window.kioskChatBackup) {
        console.log('Main kioskChat not available, using backup');
        kioskChatInstance = window.kioskChatBackup;
        window.kioskChat = kioskChatInstance; // Restore the main reference
    }
    
    if (!kioskChatInstance) {
        console.error('No kioskChat instance available (neither main nor backup)');
        console.log('window.kioskChat:', window.kioskChat);
        console.log('window.kioskChatBackup:', window.kioskChatBackup);
        console.log('Available window properties:', Object.keys(window).filter(k => k.includes('kiosk')));
        
        // Last resort: try to create the instance now
        console.log('Attempting emergency instance creation...');
        try {
            if (window.KioskSpeechChat) {
                const emergencyInstance = new window.KioskSpeechChat();
                window.kioskChat = emergencyInstance;
                kioskChatInstance = emergencyInstance;
                console.log('Emergency instance created successfully');
            } else {
                console.error('KioskSpeechChat class not available for emergency creation');
                return;
            }
        } catch (error) {
            console.error('Emergency instance creation failed:', error);
            return;
        }
    }
    
    // Try to find the method on the instance
    if (typeof kioskChatInstance.handleUpdateCoordinatesScreen === 'function') {
        return kioskChatInstance.handleUpdateCoordinatesScreen(messageId);
    }
    
    // Try to find it on the prototype
    const proto = Object.getPrototypeOf(kioskChatInstance);
    if (proto && typeof proto.handleUpdateCoordinatesScreen === 'function') {
        console.log('Found method on prototype, calling it');
        return proto.handleUpdateCoordinatesScreen.call(kioskChatInstance, messageId);
    }
    
    // Manual fallback - call the method logic directly
    console.log('Method not found, implementing fallback logic');
    
    const selectedScreen = kioskChatInstance.elements.screenDropdown.value;
    const selectedElement = kioskChatInstance.elements.elementDropdown.value;
    
    console.log('Selected screen:', selectedScreen);
    console.log('Selected element:', selectedElement);
    console.log('lastRectangleCoords:', kioskChatInstance.lastRectangleCoords);
    
    if (!selectedScreen || !selectedElement) {
        console.log('Missing screen or element selection, showing error');
        kioskChatInstance.addMessage('system', '⚠️ Update Failed\nPlease select both a Screen and Element before updating coordinates.');
        return;
    }
    
    if (!kioskChatInstance.lastRectangleCoords) {
        kioskChatInstance.addMessage('system', '⚠️ Update Failed\nNo rectangle coordinates available. Draw a rectangle first.');
        return;
    }
    
    // Store the pending update with screen coordinates
    const updateKey = `${selectedScreen}.${selectedElement}`;
    kioskChatInstance.pendingUpdates[updateKey] = {
        screen: selectedScreen,
        elementId: selectedElement,
        newCoordinates: {
            x: kioskChatInstance.lastRectangleCoords.screenX,
            y: kioskChatInstance.lastRectangleCoords.screenY
        },
        newSize: {
            width: kioskChatInstance.lastRectangleCoords.width,
            height: kioskChatInstance.lastRectangleCoords.height
        },
        timestamp: new Date().toISOString()
    };
    
    // Enable the save button
    kioskChatInstance.elements.saveButton.disabled = false;
    console.log('Main interface: Save button enabled after Update with Screen Coords (fallback)');
    console.log('Save button disabled state after enabling:', kioskChatInstance.elements.saveButton.disabled);
    
    // Show confirmation message
    const screenData = kioskChatInstance.kioskData.screens[selectedScreen];
    const elementData = screenData.elements.find(e => e.id === selectedElement);
    const elementName = elementData?.name || selectedElement;
    
    kioskChatInstance.addMessage('system', 
        `✅ Screen Coordinate Update Queued (Fallback)\n` +
        `Element: ${elementName}\n` +
        `Screen: ${screenData.name || selectedScreen}\n` +
        `New Coordinates: (${kioskChatInstance.lastRectangleCoords.screenX}, ${kioskChatInstance.lastRectangleCoords.screenY}) [Screen] New bounds: width ${kioskChatInstance.lastRectangleCoords.width} height ${kioskChatInstance.lastRectangleCoords.height}\n` +
        `Click Save to apply changes to config file.`
    );
    
    console.log('Pending screen coordinate update queued (fallback):', updateKey, kioskChatInstance.pendingUpdates[updateKey]);
};

window.handleUpdateCoordinates = function(messageId) {
    console.log('Global wrapper called for handleUpdateCoordinates with messageId:', messageId);
    if (window.kioskChat && typeof window.kioskChat.handleUpdateCoordinates === 'function') {
        return window.kioskChat.handleUpdateCoordinates(messageId);
    } else {
        console.error('window.kioskChat.handleUpdateCoordinates not available');
    }
};
