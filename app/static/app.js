/**
 * Forge Communicator - Client-side JavaScript
 * Theme toggle, keyboard shortcuts, command palette, and @mentions
 */

(function() {
    'use strict';

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

    document.body.addEventListener('htmx:responseError', function(e) {
        showToast('An error occurred. Please try again.', 'error');
    });

})();
