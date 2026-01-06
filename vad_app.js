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
        
        // Processing timing metrics
        this.processingStartTime = null;
        this.processingTimer = null;
        this.maxProcessingTime = 3000; // 3 second limit
        this.targetMedianTime = 1000; // Target 1 second median
        
        // Settings (will be loaded from config)
        this.settings = {
            autoSendVoice: true,
            voiceThreshold: 0.5,
            selectedMicrophone: null,
            // VAD settings will be loaded from server config
            vadEnabled: true,
            vadSensitivity: 0.002,
            silenceTimeout: 800,
            speechStartDelay: 300,
            consecutiveSilenceThreshold: 3,
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
        
        // Browser and URL detection
        this.detectBrowserAndURL();
        
        // Initialize components
        this.initializeElements();
        this.initializeEventListeners();
        this.loadVADConfig();
        this.loadSettings();
        this.connectWebSocket();
        this.initializeAudio();
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
    
    generateClientId() {
        return 'client_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    }
    
    initializeElements() {
        // Get DOM elements
        this.elements = {
            connectionStatus: document.getElementById('connectionStatus'),
            chatMessages: document.getElementById('chatMessages'),
            messageInput: document.getElementById('messageInput'),
            sendButton: document.getElementById('sendButton'),
            voiceButton: document.getElementById('voiceButton'),
            recordingIndicator: document.getElementById('recordingIndicator'),
            processingIndicator: document.getElementById('processingIndicator'),
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
            screenshotModal: document.getElementById('screenshotModal'),
            modalBackdrop: document.getElementById('modalBackdrop'),
            modalClose: document.getElementById('modalClose'),
            modalTitle: document.getElementById('modalTitle'),
            modalImage: document.getElementById('modalImage'),
            downloadScreenshot: document.getElementById('downloadScreenshot'),
            deleteScreenshot: document.getElementById('deleteScreenshot')
        };
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
        
        // Take screenshot button
        this.elements.takeScreenshotButton.addEventListener('click', () => {
            this.takeScreenshot();
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

        // Test microphone button
        const testMicButton = document.getElementById('testMicButton');
        if (testMicButton) {
            testMicButton.addEventListener('click', () => {
                this.testMicrophoneAccess();
            });
        }
        
        // Close settings when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.elements.settingsPanel.contains(e.target) && 
                !this.elements.settingsToggle.contains(e.target)) {
                this.elements.settingsPanel.style.display = 'none';
            }
        });
        
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
                if (this.settings.autoSendVoice && data.text.trim()) {
                    // Auto-send the transcribed text
                    setTimeout(() => {
                        this.sendChatMessage(data.text);
                    }, 500);
                }
                break;
                
            case 'chat_response':
                this.hideProcessingIndicator();
                if (data.response && data.response.success) {
                    const response = data.response.response;
                    let messageText = response.message || 'I processed your request.';
                    
                    // Add timing information if available
                    if (data.response.actual_processing_time) {
                        const processingTime = data.response.actual_processing_time;
                        const processingId = data.response.processing_id || 'unknown';
                        console.log(`[TIMING-${processingId}] Server processing time: ${processingTime}`);
                    }
                    
                    // Format response based on action type
                    if (response.action === 'click') {
                        messageText = `I would ${response.action} on "${response.element_id}" at coordinates (${response.coordinates?.x}, ${response.coordinates?.y}). ${response.message || ''}`;
                    } else if (response.action === 'help') {
                        messageText = response.message || 'Here are the available commands...';
                    } else if (response.action === 'clarify') {
                        messageText = response.message || 'I need more information to help you.';
                    }
                    
                    this.addMessage('assistant', messageText);
                    
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
                break;
                
            case 'error':
                this.hideProcessingIndicator();
                this.addMessage('system', `Error: ${data.message}`);
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
            await this.startRecording();
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
                this.addMessage('system', `🎤 Recording started - speak naturally, auto-stop after ${this.settings.silenceTimeout/1000}s silence`);
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
            
            // Configure analyser for VAD
            this.vadAnalyser.fftSize = 512;
            this.vadAnalyser.smoothingTimeConstant = 0.8;
            source.connect(this.vadAnalyser);
            
            // Create data array for audio analysis
            this.vadDataArray = new Float32Array(this.vadAnalyser.frequencyBinCount);
            
            // Start VAD monitoring
            this.startVADMonitoring();
            
            console.log('VAD setup complete');
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
            
            // Grace period - don't apply VAD for the first second to allow user to start speaking
            if (recordingDuration < this.settings.speechStartDelay) {
                return;
            }
            
            // Get audio data
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
            
            // Debug logging (reduced frequency)
            if (Math.random() < 0.1) { // Only log 10% of the time
                console.log(`VAD: RMS=${rmsLevel.toFixed(6)}, Speech=${this.speechDetected}, Silence=${this.consecutiveSinceCount}, Duration=${Math.round(recordingDuration/1000)}s`);
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
    }
    
    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
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
    
    sendAudioData(base64Audio) {
        if (this.ws && this.isConnected) {
            this.ws.send(JSON.stringify({
                type: 'audio_data',
                audio: base64Audio,
                timestamp: new Date().toISOString()
            }));
        } else {
            this.hideProcessingIndicator();
            this.showError('Not connected to server');
        }
    }
    
    sendMessage() {
        const message = this.elements.messageInput.value.trim();
        if (message) {
            this.sendChatMessage(message);
            this.elements.messageInput.value = '';
        }
    }
    
    sendChatMessage(message) {
        if (this.ws && this.isConnected) {
            // Add user message to chat
            this.addMessage('user', message);
            
            // Show processing indicator
            this.showProcessingIndicator();
            
            // Send to server
            this.ws.send(JSON.stringify({
                type: 'chat_message',
                message: message,
                context: {
                    timestamp: new Date().toISOString(),
                    client_id: this.clientId
                }
            }));
        } else {
            this.showError('Not connected to server');
        }
    }
    
    addMessage(sender, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = text;
        
        messageDiv.appendChild(contentDiv);
        this.elements.chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
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
        this.processingStartTime = Date.now();
        this.elements.processingIndicator.style.display = 'flex';
        
        // Start real-time timer display
        this.startProcessingTimer();
        
        // Processing indicator without timeout - let successful commands complete
        
        // Update indicator text with timing info
        this.updateProcessingIndicatorText();
        
        console.log(`[TIMING] Processing started at: ${new Date().toISOString()}`);
    }
    
    hideProcessingIndicator() {
        if (this.processingStartTime) {
            const endTime = Date.now();
            const elapsedTime = endTime - this.processingStartTime;
            const startTimeStr = new Date(this.processingStartTime).toISOString();
            const endTimeStr = new Date(endTime).toISOString();
            
            // Clear timer
            this.stopProcessingTimer();
            
            // Log timing metrics
            console.log(`[TIMING] Processing completed:`);
            console.log(`[TIMING] - Start: ${startTimeStr}`);
            console.log(`[TIMING] - End: ${endTimeStr}`);
            console.log(`[TIMING] - Duration: ${elapsedTime}ms`);
            
            // Add timing message to chat
            this.addTimingMessage(this.processingStartTime, endTime, elapsedTime);
            
            // Performance warning if over target
            if (elapsedTime > this.targetMedianTime) {
                console.warn(`[PERFORMANCE] Processing took ${elapsedTime}ms (target: ${this.targetMedianTime}ms)`);
            }
            
            this.processingStartTime = null;
        }
        
        this.elements.processingIndicator.style.display = 'none';
    }
    
    startProcessingTimer() {
        this.processingTimer = setInterval(() => {
            if (this.processingStartTime) {
                this.updateProcessingIndicatorText();
            }
        }, 100); // Update every 100ms
    }
    
    stopProcessingTimer() {
        if (this.processingTimer) {
            clearInterval(this.processingTimer);
            this.processingTimer = null;
        }
    }
    
    
    updateProcessingIndicatorText() {
        if (!this.processingStartTime) return;
        
        const elapsed = Date.now() - this.processingStartTime;
        const elapsedSeconds = (elapsed / 1000).toFixed(1);
        const startTime = new Date(this.processingStartTime).toLocaleTimeString();
        
        const indicator = this.elements.processingIndicator.querySelector('span');
        if (indicator) {
            indicator.innerHTML = `
                Processing Input...<br>
                <small>Started: ${startTime} | Elapsed: ${elapsedSeconds}s</small>
            `;
        }
    }
    
    
    addTimingMessage(startTime, endTime, elapsedTime) {
        const startStr = new Date(startTime).toLocaleTimeString();
        const endStr = new Date(endTime).toLocaleTimeString();
        const duration = (elapsedTime / 1000).toFixed(2);
        
        // Determine performance level
        let performanceIcon = '🟢';
        let performanceText = 'Excellent';
        
        if (elapsedTime > this.targetMedianTime) {
            performanceIcon = '🟡';
            performanceText = 'Acceptable';
        }
        
        if (elapsedTime > 2000) {
            performanceIcon = '🔴';
            performanceText = 'Slow';
        }
        
        const timingMessage = `${performanceIcon} **Processing Complete** (${performanceText})\n` +
                             `📅 Start: ${startStr} | End: ${endStr}\n` +
                             `⏱️ Duration: ${duration}s`;
        
        this.addMessage('system', timingMessage);
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
    
    async takeScreenshot() {
        try {
            // Disable button during screenshot
            this.elements.takeScreenshotButton.disabled = true;
            this.elements.takeScreenshotButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Taking...</span>';
            
            // Call the MCP screenshot tool
            const response = await this.callMCPTool('screen_capture_take_screenshot', {});
            
            if (response.success && response.data.screenshot_path) {
                // Create screenshot object
                const screenshot = {
                    id: Date.now().toString(),
                    timestamp: new Date().toISOString(),
                    path: response.data.screenshot_path,
                    filename: response.data.filename || `screenshot_${Date.now()}.png`,
                    size: response.data.size || 'Unknown size'
                };
                
                // Add to screenshots array
                this.screenshots.push(screenshot);
                this.screenshotCount++;
                
                // Update UI
                this.updateScreenshotCount();
                this.addScreenshotToGallery(screenshot);
                
                console.log('Screenshot taken successfully:', screenshot);
                
            } else {
                throw new Error(response.error || 'Failed to take screenshot');
            }
            
        } catch (error) {
            console.error('Error taking screenshot:', error);
            this.showError('Failed to take screenshot: ' + error.message);
        } finally {
            // Re-enable button
            this.elements.takeScreenshotButton.disabled = false;
            this.elements.takeScreenshotButton.innerHTML = '<i class="fas fa-camera"></i><span>Take Screenshot</span>';
        }
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
    
    addScreenshotToGallery(screenshot) {
        // Remove empty state if this is the first screenshot
        if (this.screenshotCount === 1) {
            this.elements.screenshotGallery.innerHTML = '';
        }
        
        // Create thumbnail element
        const thumbnail = document.createElement('div');
        thumbnail.className = 'screenshot-thumbnail';
        thumbnail.dataset.screenshotId = screenshot.id;
        
        thumbnail.innerHTML = `
            <img src="/api/screenshot/${screenshot.filename}" alt="Screenshot ${screenshot.id}" loading="lazy">
            <div class="thumbnail-overlay">
                <span>View</span>
            </div>
        `;
        
        // Add click event to open modal
        thumbnail.addEventListener('click', () => {
            this.openScreenshotModal(screenshot);
        });
        
        // Add to gallery (newest first)
        this.elements.screenshotGallery.insertBefore(thumbnail, this.elements.screenshotGallery.firstChild);
    }
    
    openScreenshotModal(screenshot) {
        this.currentScreenshot = screenshot;
        this.elements.modalTitle.textContent = `Screenshot - ${new Date(screenshot.timestamp).toLocaleString()}`;
        this.elements.modalImage.src = `/api/screenshot/${screenshot.filename}`;
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
    
    downloadCurrentScreenshot() {
        if (!this.currentScreenshot) return;
        
        // Create download link
        const link = document.createElement('a');
        link.href = `/api/screenshot/${this.currentScreenshot.filename}`;
        link.download = this.currentScreenshot.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
    
    deleteCurrentScreenshot() {
        if (!this.currentScreenshot) return;
        
        if (confirm('Are you sure you want to delete this screenshot?')) {
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
            
            console.log('Screenshot deleted:', this.currentScreenshot.filename);
        }
    }
    
    saveSettings() {
        try {
            localStorage.setItem('kioskSpeechSettings', JSON.stringify(this.settings));
        } catch (error) {
            console.error('Error saving settings:', error);
        }
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.kioskChat = new KioskSpeechChat();
});

// Export for potential external use
window.KioskSpeechChat = KioskSpeechChat;
