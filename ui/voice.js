// path: ui/voice.js
// Voice modulation module for Private Personal Assistant:
// Provides Speech-to-Text (STT) and Text-to-Speech (TTS) capabilities.
// Features: Real-time speed & pitch modulation, Hindi & Hinglish support,
// continuous listening with 3.5s silence detection, reactive audio waveform visualizer,
// synthesized earcon chimes, and markdown table cleaning.
// Fully isolated from panel.js to ensure robust error boundaries.

(() => {
    "use strict";

    try {
        const STORAGE_KEYS = {
            AUTOSPEAK: "assistant_voice_autospeak",
            VOICE: "assistant_voice_name",
            RATE: "assistant_voice_rate",
            PITCH: "assistant_voice_pitch",
            RECLANG: "assistant_recognition_lang",
        };

        const SILENCE_TIMEOUT_MS = 3500; // 3.5s silence window before auto-sending speech

        let recognition = null;
        let isListening = false;
        let shouldSubmitOnEnd = false;
        let silenceTimer = null;
        let voices = [];
        let lastAssistantResponse = "";

        // Real-time speech modulation state
        let isSpeakingActive = false;
        let isRespeaking = false;
        let activeFullText = "";
        let activeCharIndex = 0;
        let currentStartOffset = 0;
        let respeakDebounceTimer = null;

        // Visualizer & AudioContext state
        let visualizerAudioCtx = null;
        let visualizerAnalyser = null;
        let visualizerStream = null;
        let visualizerAnimFrame = null;
        let visualizerMode = null; // "listening" | "speaking" | null

        // Synthesize modern soft earcon audio chimes
        function playChime(type) {
            try {
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                if (!AudioCtx) return;
                const ctx = new AudioCtx();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                const now = ctx.currentTime;

                if (type === "start") {
                    // Soft ascending modern chime (C5 523Hz -> E5 659Hz)
                    osc.type = "sine";
                    osc.frequency.setValueAtTime(523.25, now);
                    osc.frequency.exponentialRampToValueAtTime(659.25, now + 0.08);
                    gain.gain.setValueAtTime(0.06, now);
                    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.22);
                    osc.start(now);
                    osc.stop(now + 0.22);
                } else if (type === "stop") {
                    // Soft descending confirmation chime (E5 659Hz -> C5 523Hz)
                    osc.type = "sine";
                    osc.frequency.setValueAtTime(659.25, now);
                    osc.frequency.exponentialRampToValueAtTime(523.25, now + 0.08);
                    gain.gain.setValueAtTime(0.05, now);
                    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
                    osc.start(now);
                    osc.stop(now + 0.2);
                }
            } catch (_) {
                // AudioContext autoplay policies or unsupported
            }
        }

        // Preference persistence helpers
        function getSavedPref(key, defaultValue) {
            try {
                const val = localStorage.getItem(key);
                return val !== null ? val : defaultValue;
            } catch (e) {
                return defaultValue;
            }
        }

        function setSavedPref(key, value) {
            try {
                localStorage.setItem(key, String(value));
            } catch (e) {
                // Ignore storage errors (private mode, quota)
            }
        }

        // Clean text for speech: strips markdown, provenance tags, memory chips, and table syntax
        function cleanSpokenText(text) {
            if (!text) return "";
            return text
                // Remove memories used markers
                .replace(/memories\s+used\s*:?[^\n]*/gi, " ")
                .replace(/\[(user_said|tool_output)\]/gi, " ")
                // Remove code blocks
                .replace(/```[\s\S]*?```/g, " ")
                // Remove inline code
                .replace(/`([^`]+)`/g, "$1")
                // Remove images
                .replace(/!\[([^\]]*)\]\([^)]*\)/g, "")
                // Remove markdown links but keep anchor text
                .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
                // Remove headers
                .replace(/^#{1,6}\s+/gm, "")
                // Remove blockquotes and list bullets
                .replace(/^\s*>\s+/gm, "")
                .replace(/^\s*[-*+]\s+/gm, "")
                .replace(/^\s*\d+\.\s+/gm, "")
                // Clean markdown table syntax (remove separator rows and soften cell pipes)
                .replace(/\|[-:\s|]+\|/g, " ")
                .replace(/\|/g, ", ")
                // Remove bold and italics formatting
                .replace(/[*_]{1,3}([^*_]+)[*_]{1,3}/g, "$1")
                // Remove HTML tags
                .replace(/<[^>]+>/g, " ")
                // Collapse whitespace
                .replace(/\s+/g, " ")
                .trim();
        }

        // Initialize voice features when DOM is ready
        function initVoice() {
            const voiceBtn = document.getElementById("voice-btn");
            const micIcon = voiceBtn?.querySelector(".mic-icon");
            const micListening = voiceBtn?.querySelector(".mic-listening");
            const inputEl = document.getElementById("input");
            const formEl = document.getElementById("chat-form");
            const voiceControls = document.getElementById("voice-controls");
            const autoSpeak = document.getElementById("auto-speak");
            const voiceSelect = document.getElementById("voice-select");
            const recognitionLang = document.getElementById("recognition-lang");
            const rateSlider = document.getElementById("voice-rate");
            const pitchSlider = document.getElementById("voice-pitch");
            const rateVal = document.getElementById("rate-val");
            const pitchVal = document.getElementById("pitch-val");
            const speakLastBtn = document.getElementById("speak-last");
            const voiceStatus = document.getElementById("voice-status");

            // Visualizer DOM elements
            const visualizerContainer = document.getElementById("voice-visualizer-container");
            const visualizerCanvas = document.getElementById("voice-canvas");
            const visualizerLabel = document.getElementById("visualizer-label");

            // Setup Reactive Glowing Canvas Visualizer
            function startVisualizer(mode) {
                if (!visualizerContainer || !visualizerCanvas) return;
                visualizerMode = mode;
                visualizerContainer.classList.remove("hidden");

                if (mode === "speaking") {
                    visualizerContainer.classList.add("speaking");
                    if (visualizerLabel) visualizerLabel.textContent = "Speaking reply...";
                } else {
                    visualizerContainer.classList.remove("speaking");
                    if (visualizerLabel) visualizerLabel.textContent = "Listening... (speak now)";
                }

                const ctx = visualizerCanvas.getContext("2d");
                if (!ctx) return;

                // Attempt live microphone stream for true audio reactivity when listening
                if (mode === "listening" && navigator.mediaDevices?.getUserMedia && !visualizerStream) {
                    navigator.mediaDevices.getUserMedia({ audio: true, video: false })
                        .then(stream => {
                            if (visualizerMode !== "listening") {
                                stream.getTracks().forEach(t => t.stop());
                                return;
                            }
                            visualizerStream = stream;
                            const AudioCtx = window.AudioContext || window.webkitAudioContext;
                            visualizerAudioCtx = new AudioCtx();
                            visualizerAnalyser = visualizerAudioCtx.createAnalyser();
                            visualizerAnalyser.fftSize = 256;
                            const source = visualizerAudioCtx.createMediaStreamSource(stream);
                            source.connect(visualizerAnalyser);
                        })
                        .catch(() => {
                            // Non-fatal: will fall back to smooth synthetic waveform
                        });
                }

                let phase = 0;
                function render() {
                    if (!visualizerMode) return;

                    const width = visualizerCanvas.width;
                    const height = visualizerCanvas.height;
                    const centerY = height / 2;
                    ctx.clearRect(0, 0, width, height);

                    let volume = 0.35;
                    if (visualizerAnalyser && visualizerMode === "listening") {
                        const dataArray = new Uint8Array(visualizerAnalyser.frequencyBinCount);
                        visualizerAnalyser.getByteFrequencyData(dataArray);
                        let sum = 0;
                        for (let i = 0; i < dataArray.length; i++) {
                            sum += dataArray[i];
                        }
                        const avg = sum / dataArray.length;
                        volume = Math.max(0.15, Math.min(1.0, avg / 60));
                    } else if (visualizerMode === "speaking") {
                        volume = 0.45 + Math.sin(phase * 1.5) * 0.25;
                    }

                    phase += 0.08;

                    // Draw primary glowing wave
                    ctx.beginPath();
                    ctx.lineWidth = 2.5;
                    ctx.strokeStyle = visualizerMode === "speaking" ? "#a371f7" : "#76b900";
                    ctx.shadowBlur = 10;
                    ctx.shadowColor = visualizerMode === "speaking" ? "#a371f7" : "#76b900";

                    for (let x = 0; x < width; x++) {
                        const progress = x / width;
                        const envelope = Math.sin(progress * Math.PI); // Pin ends to zero
                        const y = centerY + Math.sin(progress * 10 + phase) * (height * 0.38 * volume * envelope);
                        if (x === 0) ctx.moveTo(x, y);
                        else ctx.lineTo(x, y);
                    }
                    ctx.stroke();

                    // Draw secondary subtle harmonic wave
                    ctx.beginPath();
                    ctx.lineWidth = 1.2;
                    ctx.strokeStyle = visualizerMode === "speaking" ? "rgba(163, 113, 247, 0.45)" : "rgba(88, 166, 255, 0.45)";
                    ctx.shadowBlur = 4;
                    ctx.shadowColor = visualizerMode === "speaking" ? "#a371f7" : "#58a6ff";

                    for (let x = 0; x < width; x++) {
                        const progress = x / width;
                        const envelope = Math.sin(progress * Math.PI);
                        const y = centerY + Math.cos(progress * 14 - phase * 0.8) * (height * 0.24 * volume * envelope);
                        if (x === 0) ctx.moveTo(x, y);
                        else ctx.lineTo(x, y);
                    }
                    ctx.stroke();

                    visualizerAnimFrame = requestAnimationFrame(render);
                }

                if (visualizerAnimFrame) cancelAnimationFrame(visualizerAnimFrame);
                visualizerAnimFrame = requestAnimationFrame(render);
            }

            function stopVisualizer() {
                visualizerMode = null;
                if (visualizerAnimFrame) {
                    cancelAnimationFrame(visualizerAnimFrame);
                    visualizerAnimFrame = null;
                }
                if (visualizerStream) {
                    visualizerStream.getTracks().forEach(t => t.stop());
                    visualizerStream = null;
                }
                if (visualizerAudioCtx) {
                    try { visualizerAudioCtx.close(); } catch (_) {}
                    visualizerAudioCtx = null;
                    visualizerAnalyser = null;
                }
                if (visualizerContainer) {
                    visualizerContainer.classList.add("hidden");
                    visualizerContainer.classList.remove("speaking");
                }
            }

            function showStatus(message, isError = false) {
                if (!voiceStatus) return;
                voiceStatus.textContent = message;
                voiceStatus.classList.remove("hidden");
                if (isError) {
                    voiceStatus.classList.add("error");
                } else {
                    voiceStatus.classList.remove("error");
                }
            }

            function clearStatus() {
                if (!voiceStatus) return;
                voiceStatus.textContent = "";
                voiceStatus.classList.add("hidden");
                voiceStatus.classList.remove("error");
            }

            // --- Context & Feature Detection ---
            const hostname = window.location?.hostname || "";
            const isLocalhost = Boolean(
                hostname === "localhost" ||
                hostname === "127.0.0.1" ||
                hostname === "[::1]" ||
                hostname === ""
            );
            const isSecure = Boolean(window.isSecureContext || isLocalhost);
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            const hasSynthesis = "speechSynthesis" in window;

            // 1. Text-to-Speech (TTS) Setup
            if (hasSynthesis) {
                function populateVoices() {
                    try {
                        voices = window.speechSynthesis.getVoices() || [];
                        if (!voiceSelect) return;

                        const savedVoice = getSavedPref(STORAGE_KEYS.VOICE, "");
                        // Include English, Indian English, Hindi, and general system voices
                        const filtered = voices.filter(v => {
                            if (!v.lang) return true;
                            const l = v.lang.toLowerCase();
                            return l.startsWith("en") || l.startsWith("hi");
                        });
                        const listToRender = filtered.length > 0 ? filtered : voices;

                        if (listToRender.length > 0) {
                            voiceSelect.innerHTML = listToRender.map(v => {
                                const isSelected = v.name === savedVoice ? " selected" : "";
                                const langLabel = v.lang ? ` (${v.lang})` : "";
                                return `<option value="${escapeHtml(v.name)}"${isSelected}>${escapeHtml(v.name)}${langLabel}</option>`;
                            }).join("");
                        } else {
                            voiceSelect.innerHTML = `<option value="">Default Voice</option>`;
                        }
                    } catch (err) {
                        console.warn("Error populating voices:", err);
                    }
                }

                window.speechSynthesis.onvoiceschanged = populateVoices;
                populateVoices();

                // Restore saved preferences
                if (autoSpeak) {
                    autoSpeak.checked = getSavedPref(STORAGE_KEYS.AUTOSPEAK, "false") === "true";
                    autoSpeak.addEventListener("change", () => {
                        setSavedPref(STORAGE_KEYS.AUTOSPEAK, autoSpeak.checked);
                        if (!autoSpeak.checked) {
                            stopSpeaking();
                        }
                    });
                }

                if (voiceSelect) {
                    voiceSelect.addEventListener("change", () => {
                        setSavedPref(STORAGE_KEYS.VOICE, voiceSelect.value);
                    });
                }

                if (recognitionLang) {
                    const savedLang = getSavedPref(STORAGE_KEYS.RECLANG, "en-US");
                    recognitionLang.value = savedLang;
                    recognitionLang.addEventListener("change", () => {
                        setSavedPref(STORAGE_KEYS.RECLANG, recognitionLang.value);
                    });
                }

                // Stop speaking helper
                function stopSpeaking() {
                    try {
                        isSpeakingActive = false;
                        isRespeaking = false;
                        activeFullText = "";
                        activeCharIndex = 0;
                        currentStartOffset = 0;
                        if (respeakDebounceTimer) {
                            clearTimeout(respeakDebounceTimer);
                            respeakDebounceTimer = null;
                        }
                        window.speechSynthesis.cancel();
                        stopVisualizer();
                    } catch (e) {
                        // Ignore
                    }
                }

                // Real-time pitch and speed handler:
                // When slider moves during active playback, seamlessly re-modulate from current word
                function handleRealtimeModulation() {
                    if (!isSpeakingActive || !window.speechSynthesis.speaking) return;

                    if (respeakDebounceTimer) {
                        clearTimeout(respeakDebounceTimer);
                    }

                    respeakDebounceTimer = setTimeout(() => {
                        if (!isSpeakingActive || !window.speechSynthesis.speaking) return;
                        if (!activeFullText) return;

                        const remainingText = activeFullText.slice(activeCharIndex).trim();
                        if (remainingText.length > 2) {
                            isRespeaking = true;
                            window.speechSynthesis.cancel();
                            speak(remainingText, activeCharIndex);
                            isRespeaking = false;
                        }
                    }, 50);
                }

                if (rateSlider && rateVal) {
                    const savedRate = getSavedPref(STORAGE_KEYS.RATE, "1.0");
                    rateSlider.value = savedRate;
                    rateVal.textContent = `${parseFloat(savedRate).toFixed(1)}x`;

                    rateSlider.addEventListener("input", () => {
                        const val = parseFloat(rateSlider.value) || 1.0;
                        rateVal.textContent = `${val.toFixed(1)}x`;
                        setSavedPref(STORAGE_KEYS.RATE, rateSlider.value);
                        handleRealtimeModulation();
                    });
                }

                if (pitchSlider && pitchVal) {
                    const savedPitch = getSavedPref(STORAGE_KEYS.PITCH, "1.0");
                    pitchSlider.value = savedPitch;
                    pitchVal.textContent = parseFloat(savedPitch).toFixed(1);

                    pitchSlider.addEventListener("input", () => {
                        const val = parseFloat(pitchSlider.value) || 1.0;
                        pitchVal.textContent = val.toFixed(1);
                        setSavedPref(STORAGE_KEYS.PITCH, pitchSlider.value);
                        handleRealtimeModulation();
                    });
                }

                function speak(text, startCharOffset = 0) {
                    if (!text || !hasSynthesis) return;
                    const clean = cleanSpokenText(text);
                    if (!clean) return;

                    try {
                        if (!isRespeaking) {
                            window.speechSynthesis.cancel();
                            activeFullText = clean;
                            activeCharIndex = 0;
                            currentStartOffset = 0;
                        } else {
                            currentStartOffset = startCharOffset || 0;
                        }

                        const utterance = new SpeechSynthesisUtterance(clean);

                        // Hindi script auto-detection: if text has Devanagari characters, pick a Hindi voice
                        const isHindiScript = /[\u0900-\u097F]/.test(clean);
                        let chosen = null;

                        if (isHindiScript) {
                            chosen = voices.find(v => v.lang && v.lang.toLowerCase().startsWith("hi"));
                        }

                        if (!chosen && voiceSelect && voiceSelect.value) {
                            chosen = voices.find(v => v.name === voiceSelect.value);
                        }

                        // Hinglish or Indian English fallback
                        if (!chosen && recognitionLang && (recognitionLang.value === "en-IN" || recognitionLang.value === "hi-IN")) {
                            chosen = voices.find(v => v.lang && v.lang.toLowerCase().includes("in"));
                        }

                        if (chosen) utterance.voice = chosen;

                        if (rateSlider) {
                            utterance.rate = parseFloat(rateSlider.value) || 1.0;
                        }
                        if (pitchSlider) {
                            utterance.pitch = parseFloat(pitchSlider.value) || 1.0;
                        }

                        // Track spoken boundary for seamless real-time pitch/speed adjustments
                        utterance.onboundary = (e) => {
                            if (e.name === "word" || e.name === "sentence" || typeof e.charIndex === "number") {
                                activeCharIndex = currentStartOffset + e.charIndex;
                            }
                        };

                        utterance.onstart = () => {
                            isSpeakingActive = true;
                            startVisualizer("speaking");
                        };

                        utterance.onend = () => {
                            if (!isRespeaking) {
                                isSpeakingActive = false;
                                activeFullText = "";
                                activeCharIndex = 0;
                                currentStartOffset = 0;
                                stopVisualizer();
                            }
                        };

                        utterance.onerror = () => {
                            if (!isRespeaking) {
                                isSpeakingActive = false;
                                activeFullText = "";
                                activeCharIndex = 0;
                                currentStartOffset = 0;
                                stopVisualizer();
                            }
                        };

                        window.speechSynthesis.speak(utterance);
                    } catch (err) {
                        console.warn("Speech synthesis error:", err);
                        isSpeakingActive = false;
                        stopVisualizer();
                    }
                }

                // Auto-speak on incoming assistant message
                window.addEventListener("assistant-message", (e) => {
                    lastAssistantResponse = e.detail?.response || "";
                    if (autoSpeak?.checked && lastAssistantResponse) {
                        speak(lastAssistantResponse);
                    }
                });

                // Speak last response manually
                if (speakLastBtn) {
                    speakLastBtn.addEventListener("click", () => {
                        if (lastAssistantResponse) {
                            speak(lastAssistantResponse);
                        } else {
                            showStatus("No response to speak yet");
                            setTimeout(clearStatus, 3000);
                        }
                    });
                }

                // Cancel speech when user sends a new message
                window.addEventListener("chat-send", () => {
                    stopSpeaking();
                });
            } else {
                // Synthesis not supported
                if (voiceControls) {
                    voiceControls.style.display = "none";
                }
            }

            // 2. Speech-to-Text (STT) Setup with continuous listening, 3.5s silence timer & reactive visualizer
            if (!isSecure) {
                if (voiceBtn) {
                    voiceBtn.disabled = true;
                    voiceBtn.title = "Microphone access requires HTTPS or localhost";
                }
                showStatus("Microphone requires HTTPS or localhost", true);
            } else if (!SpeechRecognition) {
                if (voiceBtn) {
                    voiceBtn.disabled = true;
                    voiceBtn.title = "Speech recognition is not supported in this browser";
                }
                showStatus("Voice input unsupported (use Chrome or Edge)", true);
            } else if (voiceBtn) {
                try {
                    recognition = new SpeechRecognition();
                    recognition.continuous = true;
                    recognition.interimResults = true;
                    recognition.lang = recognitionLang?.value || "en-US";

                    function onSilenceTimeout() {
                        if (!isListening) return;
                        showStatus("Done speaking, sending...");
                        shouldSubmitOnEnd = true;
                        try {
                            recognition.stop();
                        } catch (e) {
                            // Ignore if already stopping
                        }
                    }

                    recognition.onstart = () => {
                        isListening = true;
                        shouldSubmitOnEnd = false;
                        if (silenceTimer) {
                            clearTimeout(silenceTimer);
                            silenceTimer = null;
                        }

                        // Play soft pleasant start chime
                        playChime("start");

                        // Start reactive visualizer
                        startVisualizer("listening");

                        // Cancel any active speech output when user begins speaking
                        if (hasSynthesis) {
                            window.speechSynthesis.cancel();
                            isSpeakingActive = false;
                        }
                        voiceBtn.classList.add("active");
                        if (micIcon) micIcon.style.display = "none";
                        if (micListening) micListening.style.display = "block";
                        if (inputEl) inputEl.placeholder = "Listening... (3.5s silence sends)";
                        showStatus("Listening... (pausing for 3.5s will send message)");
                    };

                    recognition.onresult = (e) => {
                        // Reset silence timer on every speech event
                        if (silenceTimer) {
                            clearTimeout(silenceTimer);
                            silenceTimer = null;
                        }

                        let finalTranscript = "";
                        let interimTranscript = "";

                        for (let i = 0; i < e.results.length; i++) {
                            const res = e.results[i];
                            if (res.isFinal) {
                                finalTranscript += res[0].transcript;
                            } else {
                                interimTranscript += res[0].transcript;
                            }
                        }

                        const current = (finalTranscript + (interimTranscript ? " " + interimTranscript : "")).trim();
                        if (inputEl && current) {
                            inputEl.value = current;
                        }

                        // As soon as user speaks, schedule silence timer for 3.5s
                        if (current) {
                            showStatus("Listening... (pausing for 3.5s will send)");
                            silenceTimer = setTimeout(onSilenceTimeout, SILENCE_TIMEOUT_MS);
                        }
                    };

                    recognition.onend = () => {
                        if (silenceTimer) {
                            clearTimeout(silenceTimer);
                            silenceTimer = null;
                        }
                        isListening = false;
                        voiceBtn.classList.remove("active");
                        if (micIcon) micIcon.style.display = "block";
                        if (micListening) micListening.style.display = "none";
                        if (inputEl) inputEl.placeholder = "Type a message...";
                        clearStatus();

                        // Play soft confirmation stop chime
                        playChime("stop");

                        // Stop reactive visualizer
                        stopVisualizer();

                        // Send message through the EXACT same code path as typed input
                        const finalMessage = inputEl?.value.trim();
                        if (finalMessage && shouldSubmitOnEnd) {
                            shouldSubmitOnEnd = false;
                            if (inputEl) inputEl.value = "";
                            if (typeof window.sendChatMessage === "function") {
                                window.sendChatMessage(finalMessage);
                            } else if (formEl) {
                                inputEl.value = finalMessage;
                                if (formEl.requestSubmit) {
                                    formEl.requestSubmit();
                                } else {
                                    formEl.dispatchEvent(new Event("submit", { cancelable: true }));
                                }
                            }
                        }
                    };

                    recognition.onerror = (e) => {
                        if (silenceTimer) {
                            clearTimeout(silenceTimer);
                            silenceTimer = null;
                        }

                        // In continuous mode, "no-speech" occurs if silence persists
                        if (e.error === "no-speech") {
                            const current = inputEl?.value.trim();
                            if (current) {
                                shouldSubmitOnEnd = true;
                                try {
                                    recognition.stop();
                                } catch (_) {}
                                return;
                            }
                            clearStatus();
                            stopVisualizer();
                            return;
                        }

                        isListening = false;
                        shouldSubmitOnEnd = false;
                        voiceBtn.classList.remove("active");
                        if (micIcon) micIcon.style.display = "block";
                        if (micListening) micListening.style.display = "none";
                        if (inputEl) inputEl.placeholder = "Type a message...";
                        stopVisualizer();

                        if (e.error === "not-allowed" || e.error === "service-not-allowed") {
                            showStatus("Microphone permission denied. Allow mic in browser settings.", true);
                        } else {
                            showStatus(`Speech recognition error: ${e.error}`, true);
                        }
                    };

                    voiceBtn.addEventListener("click", () => {
                        if (!recognition) return;
                        if (isListening) {
                            // User clicked mic while listening: stop immediately and send
                            shouldSubmitOnEnd = true;
                            if (silenceTimer) {
                                clearTimeout(silenceTimer);
                                silenceTimer = null;
                            }
                            try {
                                recognition.stop();
                            } catch (e) {
                                // Ignore
                            }
                        } else {
                            clearStatus();
                            try {
                                if (hasSynthesis) {
                                    window.speechSynthesis.cancel();
                                    isSpeakingActive = false;
                                }
                                if (inputEl) inputEl.value = "";
                                // Set recognition language from selector (en-US, en-IN, hi-IN)
                                recognition.lang = recognitionLang?.value || "en-US";
                                recognition.start();
                            } catch (err) {
                                console.warn("Failed to start speech recognition:", err);
                                showStatus("Could not start speech recognition", true);
                            }
                        }
                    });
                } catch (err) {
                    console.error("SpeechRecognition initialization failed:", err);
                    if (voiceBtn) voiceBtn.disabled = true;
                }
            }

            // Keyboard shortcuts:
            // Ctrl+Space toggles microphone
            // Escape cancels active speech or active listening without sending
            document.addEventListener("keydown", (e) => {
                if (e.ctrlKey && e.code === "Space") {
                    e.preventDefault();
                    if (voiceBtn && !voiceBtn.disabled) {
                        voiceBtn.click();
                    }
                }
                if (e.key === "Escape") {
                    if (hasSynthesis) {
                        window.speechSynthesis.cancel();
                        isSpeakingActive = false;
                    }
                    if (isListening && recognition) {
                        shouldSubmitOnEnd = false;
                        if (silenceTimer) {
                            clearTimeout(silenceTimer);
                            silenceTimer = null;
                        }
                        if (inputEl) inputEl.value = "";
                        try {
                            recognition.stop();
                        } catch (_) {}
                    }
                    stopVisualizer();
                }
            });
        }

        function escapeHtml(str) {
            if (!str) return "";
            return String(str)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#39;");
        }

        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", initVoice);
        } else {
            initVoice();
        }
    } catch (criticalErr) {
        // Never let voice initialization errors break the page
        console.error("Critical error in voice module:", criticalErr);
    }
})();
