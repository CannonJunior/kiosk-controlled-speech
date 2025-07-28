/**
 * Web Worker for Audio Processing
 * Handles audio compression and preprocessing in a separate thread
 * to improve main thread performance
 */

class AudioProcessor {
    constructor() {
        this.sampleRate = 16000;
        this.channels = 1;
        this.bufferSize = 4096;
        this.compressionLevel = 6;
    }

    /**
     * Process and compress audio data
     */
    processAudio(audioBuffer, config = {}) {
        try {
            // Apply configuration
            const {
                sampleRate = this.sampleRate,
                channels = this.channels,
                compressionLevel = this.compressionLevel,
                applyFilters = true
            } = config;

            let processedBuffer = audioBuffer;

            // Apply noise reduction if enabled
            if (applyFilters) {
                processedBuffer = this.applyNoiseReduction(processedBuffer);
                processedBuffer = this.normalizeAudio(processedBuffer);
            }

            // Resample if needed
            if (audioBuffer.sampleRate !== sampleRate) {
                processedBuffer = this.resample(processedBuffer, audioBuffer.sampleRate, sampleRate);
            }

            // Convert to desired format
            const outputData = this.convertToWAV(processedBuffer, sampleRate, channels);

            // Apply compression
            const compressedData = this.compressAudio(outputData, compressionLevel);

            return {
                success: true,
                data: compressedData,
                sampleRate: sampleRate,
                channels: channels,
                duration: processedBuffer.length / sampleRate,
                originalSize: audioBuffer.length,
                compressedSize: compressedData.length,
                compressionRatio: (audioBuffer.length / compressedData.length).toFixed(2)
            };

        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Apply simple noise reduction
     */
    applyNoiseReduction(audioBuffer) {
        const threshold = 0.01;
        const output = new Float32Array(audioBuffer.length);

        for (let i = 0; i < audioBuffer.length; i++) {
            if (Math.abs(audioBuffer[i]) < threshold) {
                output[i] = 0;
            } else {
                output[i] = audioBuffer[i];
            }
        }

        return output;
    }

    /**
     * Normalize audio levels
     */
    normalizeAudio(audioBuffer) {
        let max = 0;
        for (let i = 0; i < audioBuffer.length; i++) {
            max = Math.max(max, Math.abs(audioBuffer[i]));
        }

        if (max === 0) return audioBuffer;

        const scale = 0.95 / max;
        const output = new Float32Array(audioBuffer.length);

        for (let i = 0; i < audioBuffer.length; i++) {
            output[i] = audioBuffer[i] * scale;
        }

        return output;
    }

    /**
     * Simple resampling (linear interpolation)
     */
    resample(audioBuffer, inputSampleRate, outputSampleRate) {
        if (inputSampleRate === outputSampleRate) {
            return audioBuffer;
        }

        const ratio = inputSampleRate / outputSampleRate;
        const outputLength = Math.floor(audioBuffer.length / ratio);
        const output = new Float32Array(outputLength);

        for (let i = 0; i < outputLength; i++) {
            const srcIndex = i * ratio;
            const index = Math.floor(srcIndex);
            const fraction = srcIndex - index;

            if (index + 1 < audioBuffer.length) {
                output[i] = audioBuffer[index] * (1 - fraction) + audioBuffer[index + 1] * fraction;
            } else {
                output[i] = audioBuffer[index];
            }
        }

        return output;
    }

    /**
     * Convert Float32Array to WAV format
     */
    convertToWAV(audioBuffer, sampleRate, channels) {
        const length = audioBuffer.length;
        const arrayBuffer = new ArrayBuffer(44 + length * 2);
        const view = new DataView(arrayBuffer);

        // WAV header
        const writeString = (offset, string) => {
            for (let i = 0; i < string.length; i++) {
                view.setUint8(offset + i, string.charCodeAt(i));
            }
        };

        writeString(0, 'RIFF');
        view.setUint32(4, 36 + length * 2, true);
        writeString(8, 'WAVE');
        writeString(12, 'fmt ');
        view.setUint32(16, 16, true);
        view.setUint16(20, 1, true);
        view.setUint16(22, channels, true);
        view.setUint32(24, sampleRate, true);
        view.setUint32(28, sampleRate * channels * 2, true);
        view.setUint16(32, channels * 2, true);
        view.setUint16(34, 16, true);
        writeString(36, 'data');
        view.setUint32(40, length * 2, true);

        // Convert float samples to 16-bit PCM
        let offset = 44;
        for (let i = 0; i < length; i++) {
            const sample = Math.max(-1, Math.min(1, audioBuffer[i]));
            view.setInt16(offset, sample * 0x7FFF, true);
            offset += 2;
        }

        return arrayBuffer;
    }

    /**
     * Simple audio compression (reduce bit depth)
     */
    compressAudio(audioData, level) {
        if (level <= 0) return audioData;

        // For simplicity, we'll just return the original data
        // In a real implementation, you might apply lossy compression
        return audioData;
    }

    /**
     * Process audio chunks in batches for better performance
     */
    processBatch(audioChunks, config = {}) {
        const results = [];
        
        for (const chunk of audioChunks) {
            results.push(this.processAudio(chunk, config));
        }

        return {
            success: true,
            results: results,
            totalChunks: audioChunks.length,
            successfulChunks: results.filter(r => r.success).length
        };
    }
}

// Web Worker message handling
const processor = new AudioProcessor();

self.onmessage = function(e) {
    const { type, data, config, id } = e.data;

    try {
        let result;

        switch (type) {
            case 'processAudio':
                result = processor.processAudio(data, config);
                break;

            case 'processBatch':
                result = processor.processBatch(data, config);
                break;

            case 'configure':
                Object.assign(processor, config);
                result = { success: true, message: 'Configuration updated' };
                break;

            default:
                result = { success: false, error: 'Unknown message type' };
        }

        self.postMessage({
            id: id,
            type: type,
            success: result.success,
            data: result.data || result,
            error: result.error
        });

    } catch (error) {
        self.postMessage({
            id: id,
            type: type,
            success: false,
            error: error.message
        });
    }
};