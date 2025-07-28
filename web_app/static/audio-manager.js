/**
 * Optimized Audio Manager
 * Handles high-performance audio capture and processing
 */

class OptimizedAudioManager {
    constructor(config = {}) {
        this.config = {
            sampleRate: 16000,
            channels: 1,
            bufferSize: 4096,
            maxRecordingTime: 30000, // 30 seconds
            chunkDuration: 100, // ms
            useWebWorker: true,
            enableCompression: true,
            adaptiveQuality: true,
            lowLatencyMode: true,
            ...config
        };

        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioContext = null;
        this.analyser = null;
        this.processor = null;
        this.worker = null;
        this.audioChunks = [];
        this.recordingStartTime = null;
        
        // Performance monitoring
        this.metrics = {
            recordingCount: 0,
            totalRecordingTime: 0,
            averageProcessingTime: 0,
            compressionRatio: 0,
            errorCount: 0
        };

        // Audio quality detection
        this.audioQuality = 'balanced';
        this.noiseLevel = 0;
        this.signalLevel = 0;

        this.initializeWebWorker();
    }

    /**
     * Initialize Web Worker for audio processing
     */
    initializeWebWorker() {
        if (!this.config.useWebWorker || typeof Worker === 'undefined') {
            console.warn('Web Worker not available or disabled');
            return;
        }

        try {
            this.worker = new Worker('/static/audio-worker.js');
            
            this.worker.onmessage = (e) => {
                this.handleWorkerMessage(e.data);
            };

            this.worker.onerror = (error) => {
                console.error('Audio worker error:', error);
                this.worker = null;
            };

            console.log('Audio worker initialized');
        } catch (error) {
            console.error('Failed to initialize audio worker:', error);
            this.worker = null;
        }
    }

    /**
     * Handle messages from Web Worker
     */
    handleWorkerMessage(message) {
        const { id, type, success, data, error } = message;

        if (!success) {
            console.error(`Worker ${type} failed:`, error);
            this.metrics.errorCount++;
            return;
        }

        if (type === 'processAudio') {
            this.onAudioProcessed(data);
        } else if (type === 'processBatch') {
            this.onBatchProcessed(data);
        }
    }

    /**
     * Start optimized audio recording
     */
    async startRecording() {
        if (this.isRecording) {
            throw new Error('Already recording');
        }

        try {
            // Get optimized audio constraints
            const constraints = this.getOptimizedConstraints();
            
            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            
            // Initialize audio context for analysis
            await this.initializeAudioContext(stream);
            
            // Set up MediaRecorder with optimized settings
            this.setupMediaRecorder(stream);
            
            // Start recording
            this.mediaRecorder.start(this.config.chunkDuration);
            this.isRecording = true;
            this.recordingStartTime = Date.now();
            
            // Start audio analysis
            this.startAudioAnalysis();
            
            console.log('Optimized recording started');
            
            // Auto-stop after max time
            setTimeout(() => {
                if (this.isRecording) {
                    this.stopRecording();
                }
            }, this.config.maxRecordingTime);
            
        } catch (error) {
            this.metrics.errorCount++;
            throw new Error(`Failed to start recording: ${error.message}`);
        }
    }

    /**
     * Get optimized audio constraints based on current conditions
     */
    getOptimizedConstraints() {
        const baseConstraints = {
            audio: {
                sampleRate: this.config.sampleRate,
                channelCount: this.config.channels,
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                googEchoCancellation: true,
                googAutoGainControl: true,
                googNoiseSuppression: true,
                googHighpassFilter: true,
                googTypingNoiseDetection: true
            }
        };

        // Adaptive quality adjustments
        if (this.config.adaptiveQuality) {
            if (this.audioQuality === 'high') {
                baseConstraints.audio.sampleRate = 22050;
            } else if (this.audioQuality === 'low') {
                baseConstraints.audio.sampleRate = 8000;
                baseConstraints.audio.echoCancellation = false;
                baseConstraints.audio.noiseSuppression = false;
            }
        }

        // Low latency mode adjustments
        if (this.config.lowLatencyMode) {
            baseConstraints.audio.latency = 0.01; // 10ms
            baseConstraints.audio.googAudioMirroring = false;
        }

        return baseConstraints;
    }

    /**
     * Initialize audio context for real-time analysis
     */
    async initializeAudioContext(stream) {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.config.sampleRate
            });

            const source = this.audioContext.createMediaStreamSource(stream);
            
            // Create analyser for audio quality detection
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.analyser.smoothingTimeConstant = 0.8;
            
            source.connect(this.analyser);
            
            console.log('Audio context initialized');
        } catch (error) {
            console.warn('Audio context initialization failed:', error);
        }
    }

    /**
     * Set up MediaRecorder with optimized settings
     */
    setupMediaRecorder(stream) {
        // Choose optimal MIME type
        const mimeTypes = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/mp4',
            'audio/ogg;codecs=opus'
        ];

        let selectedMimeType = 'audio/webm';
        for (const mimeType of mimeTypes) {
            if (MediaRecorder.isTypeSupported(mimeType)) {
                selectedMimeType = mimeType;
                break;
            }
        }

        this.mediaRecorder = new MediaRecorder(stream, {
            mimeType: selectedMimeType,
            audioBitsPerSecond: this.calculateOptimalBitrate()
        });

        this.audioChunks = [];

        this.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                this.audioChunks.push(event.data);
                
                // Process chunks in real-time if enabled
                if (this.config.enableRealTimeProcessing) {
                    this.processAudioChunk(event.data);
                }
            }
        };

        this.mediaRecorder.onstop = () => {
            this.onRecordingComplete();
        };

        this.mediaRecorder.onerror = (error) => {
            console.error('MediaRecorder error:', error);
            this.metrics.errorCount++;
        };
    }

    /**
     * Calculate optimal bitrate based on current conditions
     */
    calculateOptimalBitrate() {
        let bitrate = 64000; // Default 64kbps

        if (this.config.lowLatencyMode) {
            bitrate = 32000; // Lower for latency
        } else if (this.audioQuality === 'high') {
            bitrate = 128000; // Higher for quality
        }

        return bitrate;
    }

    /**
     * Start real-time audio analysis
     */
    startAudioAnalysis() {
        if (!this.analyser) return;

        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        const analyze = () => {
            if (!this.isRecording) return;

            this.analyser.getByteFrequencyData(dataArray);
            
            // Calculate noise and signal levels
            let sum = 0;
            let max = 0;
            
            for (let i = 0; i < bufferLength; i++) {
                sum += dataArray[i];
                max = Math.max(max, dataArray[i]);
            }
            
            this.noiseLevel = sum / bufferLength;
            this.signalLevel = max;
            
            // Adaptive quality adjustment
            if (this.config.adaptiveQuality) {
                this.adjustQualityBasedOnConditions();
            }

            requestAnimationFrame(analyze);
        };

        analyze();
    }

    /**
     * Adjust quality based on audio conditions
     */
    adjustQualityBasedOnConditions() {
        const snr = this.signalLevel / (this.noiseLevel + 1); // Signal-to-noise ratio
        
        if (snr > 10 && this.audioQuality !== 'high') {
            this.audioQuality = 'high';
            console.log('Switched to high quality audio');
        } else if (snr < 3 && this.audioQuality !== 'low') {
            this.audioQuality = 'low';
            console.log('Switched to low quality audio for better processing');
        } else if (snr >= 3 && snr <= 10 && this.audioQuality !== 'balanced') {
            this.audioQuality = 'balanced';
        }
    }

    /**
     * Process individual audio chunk (for real-time processing)
     */
    async processAudioChunk(chunk) {
        if (!this.worker) return;

        try {
            const arrayBuffer = await chunk.arrayBuffer();
            
            this.worker.postMessage({
                type: 'processAudio',
                data: arrayBuffer,
                config: {
                    sampleRate: this.config.sampleRate,
                    channels: this.config.channels,
                    compressionLevel: this.config.enableCompression ? 6 : 0
                },
                id: Date.now()
            });
        } catch (error) {
            console.error('Chunk processing error:', error);
        }
    }

    /**
     * Stop recording and process final audio
     */
    async stopRecording() {
        if (!this.isRecording) return null;

        this.isRecording = false;
        
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }

        // Clean up audio context
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }

        // Update metrics
        const recordingTime = Date.now() - this.recordingStartTime;
        this.metrics.recordingCount++;
        this.metrics.totalRecordingTime += recordingTime;

        console.log(`Recording stopped. Duration: ${recordingTime}ms`);
        
        return this.processAudioData();
    }

    /**
     * Process complete audio data
     */
    async processAudioData() {
        if (this.audioChunks.length === 0) {
            throw new Error('No audio data to process');
        }

        const processingStart = Date.now();

        try {
            // Combine all chunks
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
            
            let processedData;
            
            if (this.worker) {
                // Use Web Worker for processing
                const arrayBuffer = await audioBlob.arrayBuffer();
                processedData = await this.processWithWorker(arrayBuffer);
            } else {
                // Fallback to main thread processing
                processedData = await this.processOnMainThread(audioBlob);
            }

            // Update metrics
            const processingTime = Date.now() - processingStart;
            this.updateProcessingMetrics(processingTime, processedData);

            return processedData;

        } catch (error) {
            this.metrics.errorCount++;
            throw new Error(`Audio processing failed: ${error.message}`);
        }
    }

    /**
     * Process audio using Web Worker
     */
    processWithWorker(arrayBuffer) {
        return new Promise((resolve, reject) => {
            const id = Date.now();
            
            const timeout = setTimeout(() => {
                reject(new Error('Worker processing timeout'));
            }, 10000);

            const handler = (e) => {
                if (e.data.id === id) {
                    clearTimeout(timeout);
                    this.worker.removeEventListener('message', handler);
                    
                    if (e.data.success) {
                        resolve(e.data.data);
                    } else {
                        reject(new Error(e.data.error));
                    }
                }
            };

            this.worker.addEventListener('message', handler);
            
            this.worker.postMessage({
                type: 'processAudio',
                data: arrayBuffer,
                config: {
                    sampleRate: this.config.sampleRate,
                    channels: this.config.channels,
                    compressionLevel: this.config.enableCompression ? 6 : 0
                },
                id: id
            });
        });
    }

    /**
     * Fallback processing on main thread
     */
    async processOnMainThread(audioBlob) {
        // Simple processing - just return the blob as base64
        const arrayBuffer = await audioBlob.arrayBuffer();
        const uint8Array = new Uint8Array(arrayBuffer);
        
        // Convert to base64
        let binary = '';
        for (let i = 0; i < uint8Array.length; i++) {
            binary += String.fromCharCode(uint8Array[i]);
        }
        
        return {
            data: btoa(binary),
            sampleRate: this.config.sampleRate,
            channels: this.config.channels,
            duration: this.audioChunks.length * this.config.chunkDuration / 1000,
            size: arrayBuffer.byteLength
        };
    }

    /**
     * Update processing metrics
     */
    updateProcessingMetrics(processingTime, processedData) {
        this.metrics.averageProcessingTime = (
            (this.metrics.averageProcessingTime * (this.metrics.recordingCount - 1) + processingTime) /
            this.metrics.recordingCount
        );

        if (processedData.compressionRatio) {
            this.metrics.compressionRatio = processedData.compressionRatio;
        }
    }

    /**
     * Handle processed audio from worker
     */
    onAudioProcessed(data) {
        // Emit event or call callback
        if (this.onProcessedCallback) {
            this.onProcessedCallback(data);
        }
    }

    /**
     * Handle batch processed audio from worker
     */
    onBatchProcessed(data) {
        console.log(`Batch processed: ${data.successfulChunks}/${data.totalChunks} chunks`);
    }

    /**
     * Clean up resources
     */
    cleanup() {
        this.stopRecording();
        
        if (this.worker) {
            this.worker.terminate();
            this.worker = null;
        }
        
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        this.audioChunks = [];
    }

    /**
     * Get performance metrics
     */
    getMetrics() {
        return {
            ...this.metrics,
            audioQuality: this.audioQuality,
            noiseLevel: this.noiseLevel,
            signalLevel: this.signalLevel,
            isRecording: this.isRecording
        };
    }

    /**
     * Update configuration
     */
    updateConfig(newConfig) {
        this.config = { ...this.config, ...newConfig };
        
        if (this.worker) {
            this.worker.postMessage({
                type: 'configure',
                config: newConfig,
                id: Date.now()
            });
        }
    }
}

// Export for use in main application
window.OptimizedAudioManager = OptimizedAudioManager;