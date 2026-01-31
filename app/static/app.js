/**
 * Forge Communicator - Client-side JavaScript
 * Theme toggle, keyboard shortcuts, command palette, notifications, session monitoring, and @mentions
 */

(function() {
    'use strict';

    // ============================================
    // Session Monitor - Prevents unexpected logouts
    // ============================================
    
    window.sessionMonitor = {
        // Configuration
        WARNING_THRESHOLD_SECONDS: 300, // Show warning 5 minutes before expiry
        CHECK_INTERVAL_MS: 60000, // Check every minute
        COUNTDOWN_INTERVAL_MS: 1000, // Update countdown every second
        
        // State
        checkIntervalId: null,
        countdownIntervalId: null,
        secondsRemaining: null,
        warningShown: false,
        hasUnsavedWork: false,
        
        // Initialize session monitoring
        init: function() {
            // Start periodic session checks
            this.checkSession();
            this.checkIntervalId = setInterval(() => this.checkSession(), this.CHECK_INTERVAL_MS);
            
            // Track unsaved work in forms
            this.trackUnsavedWork();
            
            console.log('Session monitor initialized');
        },
        
        // Check session status from server
        checkSession: async function() {
            try {
                const response = await fetch('/auth/session-status');
                if (!response.ok) {
                    console.error('Session check failed:', response.status);
                    return;
                }
                
                const data = await response.json();
                
                if (!data.authenticated) {
                    // Session already expired
                    this.showExpiredModal();
                    return;
                }
                
                this.secondsRemaining = data.seconds_remaining;
                
                // Check if we should show warning
                if (this.secondsRemaining <= this.WARNING_THRESHOLD_SECONDS && !this.warningShown) {
                    this.showWarningModal();
                } else if (this.secondsRemaining > this.WARNING_THRESHOLD_SECONDS && this.warningShown) {
                    // Session was extended, hide warning
                    this.hideWarningModal();
                }
                
            } catch (error) {
                console.error('Session check error:', error);
            }
        },
        
        // Show warning modal with countdown
        showWarningModal: function() {
            this.warningShown = true;
            
            const modal = document.getElementById('session-timeout-modal');
            const unsavedWarning = document.getElementById('unsaved-work-warning');
            
            if (modal) {
                modal.classList.remove('hidden');
                
                // Show unsaved work warning if applicable
                if (unsavedWarning) {
                    if (this.hasUnsavedWork) {
                        unsavedWarning.classList.remove('hidden');
                    } else {
                        unsavedWarning.classList.add('hidden');
                    }
                }
            }
            
            // Start countdown
            this.startCountdown();
            
            // Play warning sound
            this.playWarningSound();
        },
        
        // Hide warning modal
        hideWarningModal: function() {
            this.warningShown = false;
            
            const modal = document.getElementById('session-timeout-modal');
            if (modal) {
                modal.classList.add('hidden');
            }
            
            // Stop countdown
            if (this.countdownIntervalId) {
                clearInterval(this.countdownIntervalId);
                this.countdownIntervalId = null;
            }
        },
        
        // Show expired modal
        showExpiredModal: function() {
            // Hide warning modal if showing
            this.hideWarningModal();
            
            const modal = document.getElementById('session-expired-modal');
            if (modal) {
                modal.classList.remove('hidden');
            }
            
            // Stop all intervals
            if (this.checkIntervalId) {
                clearInterval(this.checkIntervalId);
            }
        },
        
        // Start countdown timer in modal
        startCountdown: function() {
            const countdownEl = document.getElementById('session-countdown');
            
            const updateCountdown = () => {
                if (this.secondsRemaining <= 0) {
                    this.showExpiredModal();
                    return;
                }
                
                const minutes = Math.floor(this.secondsRemaining / 60);
                const seconds = this.secondsRemaining % 60;
                
                if (countdownEl) {
                    countdownEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
                    
                    // Change color as time runs out
                    if (this.secondsRemaining <= 60) {
                        countdownEl.classList.remove('text-yellow-400');
                        countdownEl.classList.add('text-red-400');
                    }
                }
                
                this.secondsRemaining--;
            };
            
            // Initial update
            updateCountdown();
            
            // Update every second
            this.countdownIntervalId = setInterval(updateCountdown, this.COUNTDOWN_INTERVAL_MS);
        },
        
        // Extend session via server
        extendSession: async function() {
            try {
                const response = await fetch('/auth/session-status?refresh=true');
                const data = await response.json();
                
                if (data.authenticated) {
                    this.secondsRemaining = data.seconds_remaining;
                    this.hideWarningModal();
                    
                    // Show success toast
                    if (window.showToast) {
                        window.showToast('Session extended successfully', 'success');
                    }
                } else {
                    this.showExpiredModal();
                }
            } catch (error) {
                console.error('Failed to extend session:', error);
                if (window.showToast) {
                    window.showToast('Failed to extend session', 'error');
                }
            }
        },
        
        // Log out user
        logout: function() {
            window.location.href = '/auth/logout';
        },
        
        // Play warning sound
        playWarningSound: function() {
            try {
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioCtx.createOscillator();
                const gainNode = audioCtx.createGain();
                
                oscillator.connect(gainNode);
                gainNode.connect(audioCtx.destination);
                
                // Two-tone warning beep
                oscillator.type = 'sine';
                oscillator.frequency.setValueAtTime(880, audioCtx.currentTime);
                oscillator.frequency.setValueAtTime(660, audioCtx.currentTime + 0.15);
                oscillator.frequency.setValueAtTime(880, audioCtx.currentTime + 0.3);
                
                gainNode.gain.setValueAtTime(0.2, audioCtx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.45);
                
                oscillator.start(audioCtx.currentTime);
                oscillator.stop(audioCtx.currentTime + 0.45);
            } catch (e) {
                console.log('Could not play warning sound:', e);
            }
        },
        
        // Track unsaved work in forms/inputs
        trackUnsavedWork: function() {
            // Track changes on input fields
            document.addEventListener('input', (e) => {
                const target = e.target;
                if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
                    // Check if field has content
                    if (target.value && target.value.trim().length > 0) {
                        // Exclude search inputs and other non-critical fields
                        if (!target.classList.contains('search-input') && 
                            !target.id?.includes('search') &&
                            !target.id?.includes('command')) {
                            this.hasUnsavedWork = true;
                        }
                    }
                }
            });
            
            // Clear unsaved work flag on form submit
            document.addEventListener('submit', () => {
                this.hasUnsavedWork = false;
            });
            
            // Clear unsaved work flag when htmx request succeeds
            document.body.addEventListener('htmx:afterOnLoad', () => {
                // Small delay to allow for any UI updates
                setTimeout(() => {
                    const activeInput = document.activeElement;
                    if (!activeInput || !activeInput.value || activeInput.value.trim().length === 0) {
                        this.hasUnsavedWork = false;
                    }
                }, 100);
            });
        },
        
        // Mark that user has unsaved work
        markUnsavedWork: function() {
            this.hasUnsavedWork = true;
        },
        
        // Clear unsaved work flag
        clearUnsavedWork: function() {
            this.hasUnsavedWork = false;
        }
    };
    
    // Initialize session monitor when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        // Only initialize if user is logged in (check for session-related elements)
        // Session monitor will handle unauthenticated state gracefully
        window.sessionMonitor.init();
    });

    // ============================================
    // Notification Sound System (Global)
    // ============================================
    
    window.notificationSoundEnabled = localStorage.getItem('notificationSound') !== 'muted';
    
    // Notification sound using chirp.mp3
    let globalNotificationAudio = null;
    
    window.playNotificationSound = function() {
        if (!window.notificationSoundEnabled) return;
        
        try {
            if (!globalNotificationAudio) {
                globalNotificationAudio = new Audio('/static/chirp.mp3');
                globalNotificationAudio.volume = 0.5;
            }
            globalNotificationAudio.currentTime = 0;
            globalNotificationAudio.play().catch(e => console.log('Audio play failed:', e));
        } catch (e) {
            console.log('Notification sound not available:', e);
        }
    };
    
    window.toggleGlobalNotificationSound = function() {
        window.notificationSoundEnabled = !window.notificationSoundEnabled;
        localStorage.setItem('notificationSound', window.notificationSoundEnabled ? 'enabled' : 'muted');
        return window.notificationSoundEnabled;
    };

    // ============================================
    // Theme Management
    // ============================================
    
    window.toggleTheme = function() {
        if (document.documentElement.classList.contains('dark')) {
            document.documentElement.classList.remove('dark');
            localStorage.theme = 'light';
        } else {
            document.documentElement.classList.add('dark');
            localStorage.theme = 'dark';
        }
    };

    // ============================================
    // Command Palette
    // ============================================
    
    const palette = document.getElementById('command-palette');
    const paletteInput = document.getElementById('command-input');
    const paletteResults = document.getElementById('command-results');

    // Open command palette
    window.openCommandPalette = function() {
        if (palette) {
            palette.classList.remove('hidden');
            paletteInput.value = '';
            paletteInput.focus();
            updatePaletteResults('');
        }
    };

    // Close command palette
    window.closeCommandPalette = function() {
        if (palette) {
            palette.classList.add('hidden');
        }
    };

    // Update palette results based on query
    function updatePaletteResults(query) {
        if (!paletteResults) return;

        const commands = [
            { name: 'Create Decision', shortcut: '/decision', icon: '⚖️', desc: 'Record an architectural decision' },
            { name: 'Create Feature', shortcut: '/feature', icon: '✨', desc: 'Track a feature request' },
            { name: 'Create Issue', shortcut: '/issue', icon: '🐛', desc: 'Report a bug or issue' },
            { name: 'Create Task', shortcut: '/task', icon: '✅', desc: 'Create a todo task' },
            { name: 'Mention User', shortcut: '@', icon: '👤', desc: 'Mention someone in the channel' },
            { name: 'Direct Message', shortcut: '/dm @', icon: '✉️', desc: 'Send a direct message' },
            { name: 'Join Channel', shortcut: '/join #', icon: '#️⃣', desc: 'Join another channel' },
            { name: 'Leave Channel', shortcut: '/leave', icon: '👋', desc: 'Leave current channel' },
            { name: 'Set Topic', shortcut: '/topic', icon: '📝', desc: 'Set the channel topic' },
            { name: 'Toggle Theme', shortcut: '', icon: '🌓', desc: 'Switch light/dark mode', action: 'toggleTheme' },
        ];

        const filtered = query 
            ? commands.filter(c => 
                c.name.toLowerCase().includes(query.toLowerCase()) ||
                c.shortcut.toLowerCase().includes(query.toLowerCase()) ||
                c.desc.toLowerCase().includes(query.toLowerCase())
            )
            : commands;

        const isDark = document.documentElement.classList.contains('dark');
        
        paletteResults.innerHTML = filtered.map(cmd => `
            <button type="button" 
                    onclick="${cmd.action ? cmd.action + '(); closeCommandPalette();' : "insertCommand('" + cmd.shortcut + " ')"}"
                    class="w-full flex items-center px-4 py-3 text-left hover:bg-gray-100 dark:hover:bg-gray-700 focus:bg-gray-100 dark:focus:bg-gray-700 focus:outline-none">
                <span class="text-xl mr-3">${cmd.icon}</span>
                <div class="flex-1">
                    <div class="text-sm font-medium text-gray-900 dark:text-white">${cmd.name}</div>
                    <div class="text-xs text-gray-500 dark:text-gray-400">${cmd.desc}</div>
                </div>
                ${cmd.shortcut ? `<kbd class="ml-2 px-2 py-1 text-xs bg-gray-100 dark:bg-gray-600 text-gray-500 dark:text-gray-300 rounded">${cmd.shortcut}</kbd>` : ''}
            </button>
        `).join('');
    }

    // Insert command into message input
    window.insertCommand = function(command) {
        const messageInput = document.getElementById('message-input');
        if (messageInput) {
            messageInput.value = command;
            messageInput.focus();
            // Place cursor at end
            messageInput.selectionStart = messageInput.selectionEnd = messageInput.value.length;
            // Trigger input event for @mention detection
            messageInput.dispatchEvent(new Event('input'));
        }
        closeCommandPalette();
    };

    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K - Open command palette
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            openCommandPalette();
        }

        // Escape - Close command palette
        if (e.key === 'Escape' && palette && !palette.classList.contains('hidden')) {
            e.preventDefault();
            closeCommandPalette();
        }

        // Ctrl/Cmd + Shift + D - Quick Decision
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'D') {
            e.preventDefault();
            insertCommand('/decision');
        }

        // Ctrl/Cmd + Shift + F - Quick Feature
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'F') {
            e.preventDefault();
            insertCommand('/feature');
        }
    });

    // Command palette input handler
    if (paletteInput) {
        paletteInput.addEventListener('input', function(e) {
            updatePaletteResults(e.target.value);
        });

        paletteInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const firstResult = paletteResults.querySelector('button');
                if (firstResult) {
                    firstResult.click();
                }
            }
        });
    }

    // Auto-scroll message list to bottom
    window.scrollToBottom = function() {
        const messageList = document.getElementById('message-list');
        if (messageList) {
            messageList.scrollTop = messageList.scrollHeight;
        }
    };

    // Message editing
    window.startEditMessage = function(messageId) {
        const messageEl = document.getElementById('message-' + messageId);
        if (!messageEl) return;

        const bodyEl = messageEl.querySelector('.whitespace-pre-wrap');
        if (!bodyEl) return;

        const currentText = bodyEl.textContent;
        const workspaceId = window.location.pathname.split('/')[2];
        const channelId = window.location.pathname.split('/')[4];

        bodyEl.innerHTML = `
            <form hx-post="/workspaces/${workspaceId}/channels/${channelId}/messages/${messageId}/edit"
                  hx-target="#message-${messageId}"
                  hx-swap="outerHTML"
                  class="flex space-x-2">
                <input type="text" name="body" value="${currentText.replace(/"/g, '&quot;')}" 
                       class="flex-1 px-2 py-1 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                       autofocus>
                <button type="submit" class="px-2 py-1 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700">Save</button>
                <button type="button" onclick="location.reload()" class="px-2 py-1 text-sm text-gray-600 hover:text-gray-800">Cancel</button>
            </form>
        `;

        // Initialize HTMX on the new form
        htmx.process(bodyEl);
    };

    // Toast notifications
    window.showToast = function(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const colors = {
            info: 'bg-blue-500',
            success: 'bg-green-500',
            error: 'bg-red-500',
            warning: 'bg-yellow-500',
        };

        const toast = document.createElement('div');
        toast.className = `${colors[type]} text-white px-4 py-2 rounded-lg shadow-lg transform transition-all duration-300 translate-y-2 opacity-0`;
        toast.textContent = message;
        container.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.classList.remove('translate-y-2', 'opacity-0');
        });

        // Remove after 3 seconds
        setTimeout(() => {
            toast.classList.add('translate-y-2', 'opacity-0');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };

    // HTMX event listeners
    document.body.addEventListener('htmx:afterSwap', function(e) {
        // Scroll to bottom after new messages
        if (e.target.id === 'message-list') {
            scrollToBottom();
        }
    });

    // Track if we're navigating away to suppress spurious errors
    let isNavigating = false;
    let isInitialLoad = true; // Suppress errors during initial page load
    let lastErrorTime = 0;
    const ERROR_DEBOUNCE_MS = 1000; // Don't show multiple errors within 1 second
    
    // Clear initial load flag after page is fully loaded
    window.addEventListener('load', function() {
        setTimeout(() => { isInitialLoad = false; }, 2000);
    });
    
    // Mark navigation start
    document.body.addEventListener('htmx:beforeRequest', function(e) {
        // Check if this is a full page navigation (hx-boost)
        const target = e.detail.target;
        if (target === document.body || e.detail.boosted) {
            isNavigating = true;
            // Reset after navigation should complete
            setTimeout(() => { isNavigating = false; }, 5000);
        }
    });
    
    document.body.addEventListener('htmx:afterOnLoad', function(e) {
        // Navigation completed
        isNavigating = false;
    });
    
    // Handle beforeSwap to catch redirect scenarios
    document.body.addEventListener('htmx:beforeSwap', function(e) {
        // If we're getting a 300-level response (redirect), htmx handles it
        // Mark as navigating to suppress any subsequent errors
        if (e.detail.xhr && e.detail.xhr.status >= 300 && e.detail.xhr.status < 400) {
            isNavigating = true;
            setTimeout(() => { isNavigating = false; }, 5000);
        }
    });

    document.body.addEventListener('htmx:responseError', function(e) {
        // Don't show errors during page navigation or initial load
        if (isNavigating || isInitialLoad) {
            console.log('Suppressing error during navigation/initial load:', e.detail);
            return;
        }
        
        // Handle 401 Unauthorized - session expired
        if (e.detail.xhr && e.detail.xhr.status === 401) {
            console.log('Session expired (401 response)');
            // Show session expired modal instead of generic error
            if (window.sessionMonitor) {
                window.sessionMonitor.showExpiredModal();
            }
            return;
        }
        
        // Debounce: don't show multiple errors in quick succession
        const now = Date.now();
        if (now - lastErrorTime < ERROR_DEBOUNCE_MS) {
            console.log('Debouncing error:', e.detail);
            return;
        }
        lastErrorTime = now;
        
        // Don't show errors for aborted requests (user navigated away)
        if (e.detail.xhr && e.detail.xhr.status === 0) {
            console.log('Suppressing aborted request error');
            return;
        }
        
        // Don't show errors for redirect responses (302, 303, etc.)
        if (e.detail.xhr && e.detail.xhr.status >= 300 && e.detail.xhr.status < 400) {
            console.log('Suppressing redirect response error');
            return;
        }
        
        showToast('An error occurred. Please try again.', 'error');
    });
    
    // Also handle send errors (network failures during navigation)
    document.body.addEventListener('htmx:sendError', function(e) {
        // Don't show errors during page navigation or initial load
        if (isNavigating || isInitialLoad) {
            console.log('Suppressing send error during navigation/initial load:', e.detail);
            return;
        }
        
        // Debounce
        const now = Date.now();
        if (now - lastErrorTime < ERROR_DEBOUNCE_MS) {
            return;
        }
        lastErrorTime = now;
        
        showToast('Network error. Please check your connection.', 'error');
    });
    
    // Handle WebSocket errors (htmx ws extension)
    document.body.addEventListener('htmx:wsError', function(e) {
        // WebSocket errors during navigation or initial load are expected - suppress them
        if (isNavigating || isInitialLoad) {
            console.log('Suppressing WebSocket error during navigation/initial load:', e.detail);
            return;
        }
        
        // Debounce WebSocket errors
        const now = Date.now();
        if (now - lastErrorTime < ERROR_DEBOUNCE_MS) {
            return;
        }
        lastErrorTime = now;
        
        // Only show error if it's a genuine connection issue
        // and not during initial connection attempts
        console.log('WebSocket error:', e.detail);
    });
    
    // Handle WebSocket close events
    document.body.addEventListener('htmx:wsClose', function(e) {
        // WebSocket closing during navigation is expected
        if (isNavigating) {
            console.log('WebSocket closed during navigation (expected)');
            return;
        }
        console.log('WebSocket closed:', e.detail);
    });

})();
