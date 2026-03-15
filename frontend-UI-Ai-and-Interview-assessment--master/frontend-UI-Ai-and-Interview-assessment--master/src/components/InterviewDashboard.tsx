import { useState, useRef, useEffect, useCallback } from 'react';
import { Camera, CameraOff, Mic, MicOff, PhoneOff, User, AlertCircle, Monitor, MonitorOff, LogOut } from 'lucide-react';

/**
 * Premium Interview Dashboard - Google Meet Style
 */
interface DashboardProps {
    onEnd: () => void;
}

export default function InterviewDashboard({ onEnd }: DashboardProps) {
    const [phase, setPhase] = useState<'loading' | 'live' | 'error'>('loading');
    const [isCameraOn, setIsCameraOn] = useState(true);
    const [isMicOn, setIsMicOn] = useState(true);
    const [isScreenSharing, setIsScreenSharing] = useState(false);
    const [isSecured, setIsSecured] = useState(false);
    const [violations, setViolations] = useState(0);
    const [showWarning, setShowWarning] = useState(false);
    const [warningMsg, setWarningMsg] = useState('');
    const [infoMsg, setInfoMsg] = useState('');
    const [errorHeader, setErrorHeader] = useState('');
    const [errorMessage, setErrorMessage] = useState('');
    const [liveTranscript, setLiveTranscript] = useState('');   // live Whisper transcript
    const [isEnding, setIsEnding] = useState(false);             // Is user confirming exit?

    // Persistent Refs
    const streamRef = useRef<MediaStream | null>(null);
    const screenStreamRef = useRef<MediaStream | null>(null);
    const isScreenSharingRef = useRef(false);
    const isRequestingScreenRef = useRef(false);
    const hasRequestedRef = useRef(false);
    const videoRef = useRef<HTMLVideoElement>(null);
    const [sessionId, setSessionId] = useState<number | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const sttWsRef = useRef<WebSocket | null>(null);         // Whisper STT socket
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const lastAlertTimeRef = useRef<number>(0);
    const serverViolationsRef = useRef<number>(0);

    /**
     * Media Management - Singleton Pattern
     */
    const stopTracks = useCallback(() => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
        if (screenStreamRef.current) {
            screenStreamRef.current.getTracks().forEach(track => track.stop());
            screenStreamRef.current = null;
        }
    }, []);

    const toggleCamera = useCallback(() => {
        if (streamRef.current) {
            const videoTrack = streamRef.current.getVideoTracks()[0];
            if (videoTrack) {
                videoTrack.enabled = !videoTrack.enabled;
                setIsCameraOn(videoTrack.enabled);
            }
        }
    }, []);

    const toggleMic = useCallback(() => {
        if (streamRef.current) {
            const audioTrack = streamRef.current.getAudioTracks()[0];
            if (audioTrack) {
                audioTrack.enabled = !audioTrack.enabled;
                setIsMicOn(audioTrack.enabled);
            }
        }
    }, []);

    const handleEndInterview = useCallback(() => {
        setIsEnding(true);
    }, []);

    const confirmEndInterview = useCallback(async (status: string = "COMPLETED") => {
        if (sessionId) {
            try {
                await fetch(`http://localhost:8000/session/${sessionId}/end?status=${status}`, { method: 'POST' });
            } catch (err) {
                console.error("Failed to sync session end:", err);
            }
        }
        stopTracks();
        onEnd();
    }, [sessionId, stopTracks, onEnd]);

    const handleForcedTermination = useCallback(() => {
        confirmEndInterview("TERMINATED_BY_SYSTEM");
    }, [confirmEndInterview]);

    const cancelEndInterview = useCallback(() => {
        setIsEnding(false);
    }, []);

    /**
     * Security: Fullscreen Enforcement & Backend Session Sync
     */
    const enterFullscreen = useCallback(async () => {
        try {
            if (!document.fullscreenElement) {
                await document.documentElement.requestFullscreen();
            }
            setIsSecured(true);
            setShowWarning(false);

            // NEW: Initialize the Backend AI Monitoring Session
            if (!sessionId) {
                try {
                    const res = await fetch('http://localhost:8000/session/start?user_id=1', { method: 'POST' });
                    const data = await res.json();
                    setSessionId(data.session_id);
                    console.log("[AI] Monitoring Session Active:", data.session_id);
                } catch (err) {
                    console.error("[AI] Failed to sync session with backend:", err);
                }
            }
        } catch (err) {
            console.error("Security: Fullscreen entry failed:", err);
            setPhase('error');
            setErrorHeader('Security Required');
            setErrorMessage('Assessments require fullscreen mode for integrity. Please retry.');
        }
    }, [sessionId]);

    const handleScreenShareEnd = useCallback(() => {
        if (screenStreamRef.current) {
            screenStreamRef.current.getTracks().forEach(track => track.stop());
            screenStreamRef.current = null;
        }
        isScreenSharingRef.current = false;
        setIsScreenSharing(false);

        // Notify and Force Fullscreen
        setInfoMsg("Screen sharing has ended. You have entered Fullscreen Mode. Please continue your interview.");
        enterFullscreen();
    }, [enterFullscreen]);

    const toggleScreenShare = useCallback(async () => {
        if (isScreenSharing) {
            handleScreenShareEnd();
        } else {
            // Start screen sharing
            isRequestingScreenRef.current = true;
            try {
                const screenStream = await navigator.mediaDevices.getDisplayMedia({
                    video: true,
                    audio: false // We keep the mic from the user audio stream
                });

                screenStreamRef.current = screenStream;

                // SECURITY: Enforce "Entire Screen" sharing (not tab/window)
                const settings = screenStream.getVideoTracks()[0].getSettings();
                if (settings && settings.displaySurface && settings.displaySurface !== 'monitor') {
                    screenStream.getTracks().forEach(track => track.stop());
                    alert("SECURITY REQUIREMENT: You MUST share your ENTIRE SCREEN (desktop), not just a tab or window, to maintain assessment integrity.");
                    return;
                }

                // Handle when user clicks "Stop sharing" in browser UI
                screenStream.getVideoTracks()[0].onended = () => {
                    handleScreenShareEnd();
                };

                isScreenSharingRef.current = true;
                setIsScreenSharing(true);
                setInfoMsg(''); // Clear any previous info message

                // Re-enforce Fullscreen after sharing starts
                setTimeout(() => {
                    enterFullscreen();
                }, 500);
            } catch (err) {
                console.error("Screen sharing failed:", err);
            } finally {
                isRequestingScreenRef.current = false;
            }
        }
    }, [isScreenSharing, handleScreenShareEnd, enterFullscreen]);

    /**
     * Security: Keyboard & UI Restrictions
     */
    const handleViolation = useCallback(async (msg: string) => {
        if (!isSecured || isEnding) return;

        setViolations(v => {
            const next = v + 1;
            if (next >= 3) {
                handleForcedTermination();
            }
            return next;
        });

        // Backend Sync
        if (sessionId) {
            try {
                const eventType = msg.includes("Tab switch") ? "TAB_SWITCH" : "WINDOW_BLUR";
                await fetch(`http://localhost:8000/session/${sessionId}/proctor/event?event_type=${eventType}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ risk_increment: 0.1, severity: 2 })
                });
            } catch (err) {
                console.error("Failed to sync manual violation:", err);
            }
        }

        setWarningMsg(msg);
        setShowWarning(true);
    }, [isSecured, stopTracks, sessionId]);

    const startInterview = useCallback(async () => {
        if (hasRequestedRef.current) return;
        hasRequestedRef.current = true;

        setPhase('loading');
        setErrorMessage('');

        try {
            const mediaStream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
                audio: true,
            });

            streamRef.current = mediaStream;
            setPhase('live');
        } catch (err: any) {
            hasRequestedRef.current = false; // Reset if failed so retry is possible
            setPhase('error');
            setErrorHeader('Connection Error');
            if (err.name === 'NotAllowedError') {
                setErrorMessage('Camera or microphone access denied. Please allow permissions in your browser bar.');
            } else {
                setErrorMessage('No media gear detected. Ensure your devices are connected.');
            }
        }
    }, []);

    useEffect(() => {
        return () => stopTracks();
    }, [stopTracks]);

    /**
     * Security: Multi-Tab Prevention
     */
    useEffect(() => {
        const channel = new BroadcastChannel('interview_session');
        channel.postMessage('new_tab_attempt');

        channel.onmessage = (msg) => {
            if (msg.data === 'new_tab_attempt') {
                channel.postMessage('session_exists');
            } else if (msg.data === 'session_exists' && phase === 'live') {
                setPhase('error');
                setErrorHeader('Security Violation');
                setErrorMessage('Another session is already active in a different tab/window. Please close all other tabs and retry.');
            }
        };

        return () => channel.close();
    }, [phase]);

    useEffect(() => {
        if (!isSecured) return;

        const isExempt = () => isScreenSharingRef.current || isRequestingScreenRef.current;

        const handleBlur = () => {
            if (!isExempt() && !isEnding) handleViolation("Window focus lost! Please stay on the assessment page.");
        };
        const handleVisibilityChange = () => {
            if (document.visibilityState === 'hidden' && !isExempt()) {
                handleViolation("Tab switch detected! This activity is logged.");
            }
        };
        const handleContextMenu = (e: MouseEvent) => {
            e.preventDefault();
            return false;
        };
        const handleFullscreenChange = () => {
            if (!document.fullscreenElement && !isExempt() && !isEnding) {
                handleViolation("Fullscreen exited! Assessment must be taken in fullscreen mode.");
            } else if (!document.fullscreenElement && (isExempt() || isEnding)) {
                setTimeout(() => {
                    if (!document.fullscreenElement && (isExempt() || isEnding)) {
                        enterFullscreen().catch(() => { });
                    }
                }, 1000);
            }
        };

        window.addEventListener('blur', handleBlur);
        document.addEventListener('visibilitychange', handleVisibilityChange);
        window.addEventListener('contextmenu', handleContextMenu);
        document.addEventListener('fullscreenchange', handleFullscreenChange);

        return () => {
            window.removeEventListener('blur', handleBlur);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
            window.removeEventListener('contextmenu', handleContextMenu);
            document.removeEventListener('fullscreenchange', handleFullscreenChange);
        };
    }, [isSecured, handleViolation, enterFullscreen]);

    /**
     * Keyboard Shortcuts Handler
     */
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (phase !== 'live') return;

            switch (e.key.toLowerCase()) {
                case 'm':
                    if (isSecured) toggleMic();
                    break;
                case 'c':
                    if (isSecured) toggleCamera();
                    break;
                case 's':
                    if (isSecured) toggleScreenShare();
                    break;
                case 'escape':
                    if (isSecured) handleEndInterview();
                    break;
            }

            // Security: Block sensitive hotkeys
            const isCtrl = e.ctrlKey || e.metaKey;
            const key = e.key.toLowerCase();

            if (
                (isCtrl && (key === 'u' || key === 's' || key === 'i' || key === 'j')) ||
                (isCtrl && e.shiftKey && (key === 'i' || key === 'j' || key === 'c')) ||
                key === 'f12'
            ) {
                e.preventDefault();
                handleViolation("Developer tools and source viewing are disabled.");
                return false;
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [phase, toggleMic, toggleCamera, toggleScreenShare, handleEndInterview, handleViolation, isSecured]);

    useEffect(() => {
        startInterview();
    }, [startInterview]);

    /**
     * Video Attachment Effect
     */
    useEffect(() => {
        const videoElement = videoRef.current;
        const currentStream = isScreenSharing ? screenStreamRef.current : streamRef.current;

        if (videoElement && currentStream && phase === 'live') {
            if (videoElement.srcObject !== currentStream) {
                videoElement.srcObject = currentStream;
            }

            videoElement.play().catch(err => {
                if (err.name !== 'AbortError') {
                    console.error("Video play failed:", err);
                }
            });
        }
    }, [phase, isScreenSharing]);

    /**
     * Tablet Safety: Restrict Touch Gestures
     */
    useEffect(() => {
        if (!isSecured) return;

        const preventGestures = (e: TouchEvent) => {
            if (e.touches.length > 1) {
                e.preventDefault();
                handleViolation("Multi-touch gestures are restricted during the assessment.");
            }
        };

        window.addEventListener('touchstart', preventGestures, { passive: false });
        return () => window.removeEventListener('touchstart', preventGestures);
    }, [isSecured, handleViolation]);

    // --- COMPONENTS ---

    /**
     * AI Processing Bridge (WebSockets)
     */
    useEffect(() => {
        if (!sessionId || !isSecured) return;

        console.log("[AI] Connecting to proctoring engine...");
        const socket = new WebSocket(`ws://localhost:8000/ws/proctor/${sessionId}`);
        wsRef.current = socket;

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                const now = Date.now();
                const canAlert = (now - lastAlertTimeRef.current) > 3000;

                // 1. Handle Critical Visual Violations (Multi-person)
                // Note: Phone detection is logged to the DB by the backend but no longer triggers a frontend warning
                if (data.multiple_persons) {
                    if (canAlert) {
                        const msg = "AI CRITICAL ALERT: Multiple persons detected in frame!";

                        setViolations(v => {
                            const next = v + 1;
                            if (next >= 3) handleForcedTermination();
                            return next;
                        });
                        setWarningMsg(msg);
                        setShowWarning(true);
                        lastAlertTimeRef.current = now;
                    }
                }

                // 2. Sync regular violations (Face/Eye)
                if (data.violations) {
                    const totalServer = data.violations.face + data.violations.eye;
                    // We only care if the server's TOTAL count is higher than our last recorded server count
                    if (totalServer > serverViolationsRef.current) {
                        const diff = totalServer - serverViolationsRef.current;
                        serverViolationsRef.current = totalServer;

                        setViolations(v => {
                            const next = v + diff;
                            if (next >= 3) handleForcedTermination();
                            return next;
                        });

                        if (canAlert) {
                            setWarningMsg("AI Alert: Face or Gaze violation detected.");
                            setShowWarning(true);
                            lastAlertTimeRef.current = now;
                        }
                    }
                }
            } catch (err) {
                console.error("[AI] Message decode error:", err);
            }
        };

        // Capture Loop: Send frame to AI backend every 1 second
        const captureInterval = setInterval(() => {
            if (socket.readyState === WebSocket.OPEN && videoRef.current && isCameraOn) {
                const video = videoRef.current;

                // Use a hidden canvas to grab the frame
                if (!canvasRef.current) canvasRef.current = document.createElement('canvas');
                const canvas = canvasRef.current;
                canvas.width = 1280; // Match 720p high-precision YOLO
                canvas.height = 720;
                const ctx = canvas.getContext('2d');

                if (ctx) {
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    const base64Frame = canvas.toDataURL('image/jpeg', 0.8); // Slightly higher quality
                    socket.send(base64Frame);
                }
            }
        }, 2000);

        return () => {
            clearInterval(captureInterval);
            socket.close();
            console.log("[AI] Disconnected from server.");
        };
    }, [sessionId, isSecured, isCameraOn]); // Removed violations to prevent constant reconnects

    /**
     * Whisper STT — connects to /ws/stt and records audio in 5-second chunks
     */
    const [isListeningPaused, setIsListeningPaused] = useState(false);

    /**
     * Whisper STT — Silence Detection Logic
     * Speaks -> Wait 3s Silence -> Send Blob -> Cool Down 10s -> Restart
     */
    /**
     * Whisper STT — Dual Mode: Live Captions + Silence-based Sentence Blocking
     */
    /**
     * Whisper STT — "Snapshot" Mode
     * Captures valid 3s chunks while speaking (for live captions)
     * Stops after 3s of silence and waits 10s before resuming (user requirement)
     */
    /**
     * Chrome Native STT — Web Speech API
     * Extremely fast, accurate, and avoids audio chunking issues.
     * Rule: Wait for 3s silence -> Stop & Save -> Wait 10s Cool Down -> Restart
     */
    useEffect(() => {
        if (!sessionId || !isSecured || isListeningPaused) return;

        // Check for Web Speech API Support
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        if (!SpeechRecognition) {
            console.warn("Speech Recognition not supported in this browser.");
            return;
        }

        console.log("[STT] Starting Native Chrome Recognition...");
        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        const sttSocket = new WebSocket(`ws://localhost:8000/ws/stt/${sessionId}`);
        sttWsRef.current = sttSocket;

        let silenceTimer: any = null;

        recognition.onresult = (event: any) => {
            let finalTranscript = '';
            let interimTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }

            // Update Live UI
            if (interimTranscript || finalTranscript) {
                setLiveTranscript(interimTranscript || finalTranscript);

                // --- RULE: 3s SILENCE DETECTION ---
                if (silenceTimer) clearTimeout(silenceTimer);
                silenceTimer = setTimeout(() => {
                    if (sttSocket.readyState === WebSocket.OPEN) {
                        const fullText = finalTranscript || interimTranscript;
                        sttSocket.send(JSON.stringify({ text: fullText, is_final: true }));
                        console.log("[STT] 3s Silence. Stopping for cooldown...");
                        recognition.stop();
                    }
                }, 3000);
            }
        };

        recognition.onend = () => {
            console.log("[STT] Recognition Session Ended. Starting 10s Cool Down...");
            setIsListeningPaused(true);
            setTimeout(() => {
                setIsListeningPaused(false);
                console.log("[STT] 10s Cool Down Finished. Re-starting...");
            }, 10000);
        };

        recognition.onerror = (event: any) => {
            console.error("[STT] Recognition Error:", event.error);
        };

        recognition.start();

        return () => {
            recognition.stop();
            if (silenceTimer) clearTimeout(silenceTimer);
            sttSocket.close();
        };
    }, [sessionId, isSecured, isListeningPaused]);

    // --- SECURITY OVERLAY ---
    const SecurityOverlay = () => {
        if (!isSecured && phase === 'live') {
            return (
                <div className="fixed inset-0 z-[200] flex items-center justify-center bg-slate-950/90 backdrop-blur-xl animate-fade-in p-6">
                    <div className="glass-card max-w-lg p-10 text-center border-indigo-500/20">
                        <div className="w-20 h-20 bg-indigo-500/10 rounded-full flex items-center justify-center mx-auto mb-8 animate-pulse">
                            <AlertCircle className="w-10 h-10 text-indigo-400" />
                        </div>
                        <h2 className="text-2xl font-bold mb-4 text-[var(--text-primary)]">Start Secure Assessment</h2>
                        <ul className="text-white text-sm text-left mb-10 space-y-4 px-4 bg-slate-900 shadow-inner p-6 rounded-2xl border border-white/5">
                            <li className="flex items-start gap-3">
                                <span className="w-5 h-5 bg-indigo-500/20 rounded-full flex items-center justify-center text-[10px] text-indigo-400 font-bold shrink-0 mt-0.5">1</span>
                                Fullscreen mode is required to maintain integrity.
                            </li>
                            <li className="flex items-start gap-3">
                                <span className="w-5 h-5 bg-indigo-500/20 rounded-full flex items-center justify-center text-[10px] text-indigo-400 font-bold shrink-0 mt-0.5">2</span>
                                AI proctoring will monitor your presence and gaze.
                            </li>
                            <li className="flex items-start gap-3">
                                <span className="w-5 h-5 bg-indigo-500/30 rounded-full flex items-center justify-center text-[10px] text-indigo-300 font-bold shrink-0 mt-0.5">3</span>
                                Tab switching is strictly prohibited and logged.
                            </li>
                        </ul>
                        <button
                            onClick={enterFullscreen}
                            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 rounded-xl shadow-[0_10px_30px_rgba(79,70,229,0.3)] transition-all active:scale-[0.98] text-sm"
                        >
                            Agree & Enter Fullscreen
                        </button>
                    </div>
                </div>
            );
        }

        if (showWarning && isSecured) {
            return (
                <div className="fixed inset-0 z-[300] flex items-center justify-center bg-red-950/80 backdrop-blur-md animate-fade-in p-6">
                    <div className="glass-card max-w-sm p-8 text-center border-red-500/30">
                        <div className="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
                            <AlertCircle className="w-8 h-8 text-red-500" />
                        </div>
                        <h3 className="text-xl font-bold text-[var(--accent-red)] mb-2">Warning: {violations}/3</h3>
                        <p className="text-[var(--text-primary)] font-bold text-sm mb-8 leading-relaxed">{warningMsg}</p>
                        <button
                            onClick={enterFullscreen}
                            className="w-full bg-[var(--accent-red)] text-white font-bold py-3.5 rounded-xl shadow-lg hover:shadow-red-500/20 transition-all text-xs"
                        >
                            Refocus & Re-enter Fullscreen
                        </button>
                    </div>
                </div>
            );
        }

        if (infoMsg && isSecured) {
            return (
                <div className="fixed inset-0 z-[250] flex items-center justify-center bg-slate-950/80 backdrop-blur-md animate-fade-in p-6">
                    <div className="glass-card max-w-md p-8 text-center border-indigo-500/20">
                        <div className="w-16 h-16 bg-indigo-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
                            <Monitor className="w-8 h-8 text-indigo-400" />
                        </div>
                        <h3 className="text-xl font-bold text-[var(--text-primary)] mb-2">Assessment Secured</h3>
                        <p className="text-[var(--text-secondary)] text-sm mb-8 leading-relaxed font-bold">{infoMsg}</p>
                        <button
                            onClick={() => {
                                setInfoMsg('');
                                enterFullscreen();
                            }}
                            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-3.5 rounded-xl shadow-lg transition-all text-xs"
                        >
                            Continue Interview
                        </button>
                    </div>
                </div>
            );
        }

        if (isEnding && isSecured) {
            return (
                <div className="fixed inset-0 z-[400] flex items-center justify-center bg-slate-950/90 backdrop-blur-xl animate-fade-in p-6">
                    <div className="glass-card max-w-sm p-8 text-center border-indigo-500/20">
                        <div className="w-16 h-16 bg-indigo-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
                            <LogOut className="w-8 h-8 text-indigo-400" />
                        </div>
                        <h3 className="text-xl font-bold text-[var(--text-primary)] mb-2">End Assessment?</h3>
                        <p className="text-[var(--text-secondary)] text-sm mb-8 leading-relaxed font-bold">Are you sure you want to submit your assessment and end the call now?</p>
                        <div className="flex gap-4">
                            <button
                                onClick={() => confirmEndInterview()}
                                className="flex-1 bg-red-600 hover:bg-red-500 text-white font-bold py-3.5 rounded-xl shadow-lg transition-all text-xs"
                            >
                                Yes, Submit
                            </button>
                            <button
                                onClick={cancelEndInterview}
                                className="flex-1 bg-slate-800 hover:bg-slate-700 text-white font-bold py-3.5 rounded-xl border border-white/5 transition-all text-xs"
                            >
                                Continue
                            </button>
                        </div>
                    </div>
                </div>
            );
        }

        return null;
    };

    // --- RENDERING ---

    // --- FINAL RENDER ---
    return (
        <div className="min-h-screen bg-[var(--bg-primary)]">
            <SecurityOverlay />

            {phase === 'loading' && (
                <div className="relative w-full h-screen flex flex-col items-center justify-center p-4 animate-fade-in bg-[var(--bg-primary)]">
                    <div className="flex flex-col items-center gap-6">
                        <div className="w-16 h-16 rounded-full border-4 border-indigo-500/20 border-t-indigo-500 animate-spin" />
                        <div className="text-center">
                            <h2 className="text-xl font-bold mb-2">Setting Up Hardware</h2>
                            <p className="text-sm text-[var(--text-secondary)]">Please allow camera and microphone access...</p>
                        </div>
                    </div>
                </div>
            )}

            {phase === 'error' && (
                <div className="relative w-full h-screen flex items-center justify-center bg-[var(--bg-primary)] overflow-hidden">
                    <div className="w-full max-w-md mx-auto p-4 z-10 animate-fade-in">
                        <div className="glass-card p-10 text-center">
                            <div className="w-16 h-16 bg-red-500/10 border border-red-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
                                <AlertCircle className="w-8 h-8 text-red-400" />
                            </div>
                            <h2 className="text-xl font-bold text-[var(--accent-red)] mb-3 leading-tight drop-shadow-sm">{errorHeader}</h2>
                            <p className="text-[var(--text-secondary)] text-xs mb-8 leading-relaxed font-bold px-4">{errorMessage}</p>
                            <button
                                onClick={() => {
                                    hasRequestedRef.current = false;
                                    startInterview();
                                }}
                                className="w-full bg-slate-800/80 hover:bg-slate-700 text-white font-bold py-3.5 rounded-xl border border-white/5 transition-all active:scale-95 text-xs"
                            >
                                Go Back & Retry
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {phase === 'live' && (
                <div className="h-screen w-full bg-[var(--bg-primary)] flex flex-col items-center justify-center p-6 relative overflow-hidden">
                    <div className="flex flex-col items-center gap-8 w-full max-w-5xl z-10">
                        <div className={`video-surface shadow-2xl ${isCameraOn ? 'active' : ''}`}>
                            <video
                                ref={videoRef}
                                autoPlay
                                playsInline
                                muted
                                className={`w-full h-full object-cover transform scale-x-[-1] transition-opacity duration-700 ${isCameraOn ? 'opacity-100' : 'opacity-0'}`}
                            />

                            {/* Camera OFF Layout */}
                            {!isCameraOn && (
                                <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900 animate-fade-in">
                                    <User className="w-16 h-16 text-slate-700 mb-4" />
                                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Camera Off</span>
                                </div>
                            )}

                            {/* Live Whisper Transcript Caption */}
                            {liveTranscript && (
                                <div className="absolute bottom-4 left-4 right-4 bg-black/70 backdrop-blur-sm rounded-xl px-4 py-2 text-center animate-fade-in">
                                    <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-widest mr-2">● LIVE</span>
                                    <span className="text-white text-sm font-medium">{liveTranscript}</span>
                                </div>
                            )}

                            {/* Violation Counter (Mini) */}
                            {violations > 0 && (
                                <div className="absolute top-4 left-4 bg-red-600/80 text-white px-3 py-1 rounded-full text-[10px] font-bold animate-pulse">
                                    WARNINGS: {violations}/3
                                </div>
                            )}
                        </div>

                        {/* Controls - Strictly BELOW video card */}
                        <div className="flex items-center gap-4 py-4 px-8 bg-[var(--glass-bg)] border border-[var(--glass-border)] rounded-full shadow-2xl backdrop-blur-xl">
                            <button
                                onClick={toggleCamera}
                                className={`meet-btn ${!isCameraOn ? 'off' : ''}`}
                                aria-label="Toggle camera"
                                data-tip={isCameraOn ? "Turn off camera" : "Turn on camera"}
                            >
                                {isCameraOn ? <Camera size={20} strokeWidth={2.5} /> : <CameraOff size={20} strokeWidth={2.5} />}
                            </button>

                            <button
                                onClick={toggleMic}
                                className={`meet-btn ${!isMicOn ? 'off' : ''}`}
                                aria-label="Toggle microphone"
                                data-tip={isMicOn ? "Mute microphone" : "Unmute microphone"}
                            >
                                {isMicOn ? <Mic size={20} strokeWidth={2.5} /> : <MicOff size={20} strokeWidth={2.5} />}
                            </button>

                            <button
                                onClick={toggleScreenShare}
                                className={`meet-btn ${isScreenSharing ? 'active-share' : ''}`}
                                aria-label="Share screen"
                                data-tip={isScreenSharing ? "Stop sharing" : "Share screen"}
                            >
                                {isScreenSharing ? <MonitorOff size={20} strokeWidth={2.5} /> : <Monitor size={20} strokeWidth={2.5} />}
                            </button>

                            <button
                                onClick={handleEndInterview}
                                className="meet-btn danger"
                                aria-label="End call"
                                data-tip="End call"
                            >
                                <PhoneOff size={24} strokeWidth={2.5} />
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
