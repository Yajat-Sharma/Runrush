import re

with open("templates/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove mock notifications
mock_pattern = r'<!-- Mock Notification 1 -->.*?<!-- Empty State \(hidden by default initially\) -->'
new_container = """<!-- Empty State (hidden by default initially) -->"""
content = re.sub(mock_pattern, new_container, content, flags=re.DOTALL)

# 2. Insert JS functions
js_code = """
        // Notification Logic (Phase 2)
        function fetchNotifications() {
            fetch('/api/notifications/unread-count')
                .then(r => r.json())
                .then(data => {
                    const badge = document.getElementById('notification-badge');
                    if (badge) {
                        if (data.count > 0) {
                            badge.textContent = data.count > 9 ? '9+' : data.count;
                            badge.style.display = 'block';
                        } else {
                            badge.style.display = 'none';
                        }
                    }
                });

            fetch('/api/notifications')
                .then(r => r.json())
                .then(data => {
                    const list = document.getElementById('notificationList');
                    const empty = document.getElementById('notificationEmptyState');
                    if (!list || !empty) return;
                    
                    // Clear existing items (keep empty state)
                    Array.from(list.children).forEach(child => {
                        if (child.id !== 'notificationEmptyState') child.remove();
                    });

                    if (!data.notifications || data.notifications.length === 0) {
                        empty.classList.remove('d-none');
                        return;
                    }

                    empty.classList.add('d-none');
                    data.notifications.forEach(n => {
                        const isUnread = !n.read_at;
                        const dateStr = new Date(n.created_at).toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
                        
                        let iconClass = 'fa-bell';
                        let colorClass = 'var(--cyan-accent)';
                        if (n.type === 'SYSTEM') { iconClass = 'fa-bullhorn'; colorClass = '#4dadff'; }
                        if (n.type === 'PROMO') { iconClass = 'fa-star'; colorClass = '#F5A623'; }
                        if (n.type === 'ALERT') { iconClass = 'fa-exclamation-circle'; colorClass = '#ff6b6b'; }
                        
                        const item = document.createElement('div');
                        item.className = `notification-item p-3 border-bottom border-secondary ${isUnread ? 'unread' : ''}`;
                        item.style = "border-color: rgba(255,255,255,0.05) !important; cursor: pointer;";
                        item.onclick = () => markAsRead(n.id, item);
                        
                        item.innerHTML = `
                            <div class="d-flex gap-3">
                                <div class="notification-icon" style="color: ${colorClass};">
                                    <i class="fas ${iconClass} mt-1"></i>
                                </div>
                                <div class="flex-grow-1">
                                    <div class="d-flex justify-content-between align-items-center mb-1">
                                        <span style="font-size: 0.65rem; color: ${colorClass}; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px;">${n.type}</span>
                                        ${isUnread ? `<div class="unread-dot" style="width: 8px; height: 8px; background-color: var(--cyan-accent); border-radius: 50%;"></div>` : ''}
                                    </div>
                                    <h6 class="mb-1 ${isUnread ? 'text-white' : ''}" style="font-size: 0.9rem; ${!isUnread ? 'color:#ccc;' : ''}">${n.title}</h6>
                                    <p class="mb-1" style="font-size: 0.8rem; line-height: 1.4; color: ${isUnread ? 'var(--text-muted)' : '#888'};">${n.message}</p>
                                    <small style="font-size: 0.7rem; color: #666;">${dateStr}</small>
                                </div>
                            </div>
                        `;
                        list.insertBefore(item, empty);
                    });
                });
        }

        function markAsRead(notifId, element) {
            if (!element.classList.contains('unread')) return;
            
            fetch(`/api/notifications/${notifId}/read`, { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        element.classList.remove('unread');
                        const dot = element.querySelector('.unread-dot');
                        if (dot) dot.remove();
                        const h6 = element.querySelector('h6');
                        if (h6) { h6.classList.remove('text-white'); h6.style.color = '#ccc'; }
                        const p = element.querySelector('p');
                        if (p) p.style.color = '#888';
                        fetchNotifications(); // Update count
                    }
                });
        }

        window.markAllAsRead = function(e) {
            e.preventDefault();
            e.stopPropagation();
            fetch('/api/notifications/read-all', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.success) fetchNotifications();
                });
        };

        // Initialize fetching on page load and every 60s
        fetchNotifications();
        setInterval(fetchNotifications, 60000);
"""

content = content.replace("});\n  </script>\n</body>", js_code + "\n    });\n  </script>\n</body>")

with open("templates/index.html", "w", encoding="utf-8") as f:
    f.write(content)

print("index.html patched.")
