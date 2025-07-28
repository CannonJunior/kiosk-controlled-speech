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
        
        // Settings
        this.settings = {
            autoSendVoice: true,
            voiceThreshold: 0.5,
            selectedMicrophone: null
        };
        
        // Browser and URL detection
        this.detectBrowserAndURL();
        
        // Initialize components
        this.initializeElements();
        this.initializeEventListeners();
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
            microphoneSelect: document.getElementById('microphoneSelect'),
            autoSendVoice: document.getElementById('autoSendVoice'),
            voiceThreshold: document.getElementById('voiceThreshold'),
            errorModal: document.getElementById('errorModal'),
            errorMessage: document.getElementById('errorMessage'),
            errorClose: document.getElementById('errorClose')
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
    
    async startRecording() {
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
                this.processRecordedAudio();
            };
            
            // Start recording
            this.mediaRecorder.start();
            this.isRecording = true;
            this.updateRecordingUI(true);
            
            console.log('Recording started');
            
            // Auto-stop after 30 seconds
            setTimeout(() => {
                if (this.isRecording) {
                    this.stopRecording();
                }
            }, 30000);
            
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
        this.elements.processingIndicator.style.display = 'flex';
    }
    
    hideProcessingIndicator() {
        this.elements.processingIndicator.style.display = 'none';
    }
    
    toggleSettings() {
        const panel = this.elements.settingsPanel;
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
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
            const savedSettings = localStorage.getItem('kioskSpeechSettings');
            if (savedSettings) {
                const settings = JSON.parse(savedSettings);
                this.settings = { ...this.settings, ...settings };
                
                // Apply settings to UI
                this.elements.autoSendVoice.checked = this.settings.autoSendVoice;
                this.elements.voiceThreshold.value = this.settings.voiceThreshold;
            }
        } catch (error) {
            console.error('Error loading settings:', error);
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