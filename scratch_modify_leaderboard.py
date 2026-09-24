import re
import sys

def modify_leaderboard():
    with open("templates/leaderboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Add lb-nav-pill CSS to the style block
    style_addition = """
    /* ── TABS ── */
    .lb-nav-pill {
      border-radius: 999px;
      padding: 0.4rem 1.2rem;
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-tertiary);
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      transition: all 0.2s ease;
      text-decoration: none;
      white-space: nowrap;
    }
    .lb-nav-pill:hover {
      color: var(--text-primary);
      background: var(--bg-card-hover);
      border-color: var(--border-color);
    }
    .lb-nav-pill.active {
      background: var(--accent-soft);
      color: var(--accent);
      border-color: var(--accent);
    }
    .hide-scrollbar::-webkit-scrollbar {
      display: none;
    }
    .hide-scrollbar {
      -ms-overflow-style: none;
      scrollbar-width: none;
    }
    
    .avatar-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      border-radius: 50%;
    }
    .avatar-initials {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      border-radius: 50%;
    }
    
    .streak-subtitle {
      font-size: 0.72rem;
      color: var(--accent-orange);
      font-weight: 600;
      margin-top: -2px;
    }
"""
    html = html.replace("    /* ── HEADER ── */", style_addition + "\n    /* ── HEADER ── */")

    # 2. Header and Tabs
    header_old = """    <!-- HEADER -->
    <div class="d-flex align-items-center justify-content-between mb-4 flex-wrap gap-2">
      <div>
        <h1 class="header-title mb-0" style="font-size: 1.7rem;">🏆 All-Time Leaderboard</h1>
        <small class="text-muted">Total distance — ever</small>
      </div>
      <a href="/dashboard" class="btn-back">⬅ Back to Dashboard</a>
    </div>"""
    
    header_new = """    <!-- HEADER -->
    <div class="d-flex align-items-center justify-content-between mb-3 flex-wrap gap-2">
      <div>
        <h1 class="header-title mb-0" style="font-size: 1.7rem;">🏆 {{ active_tab|title if active_tab != 'all-time' else 'All-Time' }} Leaderboard</h1>
        <small class="text-muted">Total distance — {{ active_tab|title if active_tab != 'all-time' else 'ever' }}</small>
      </div>
      <a href="/dashboard" class="btn-back">⬅ Back to Dashboard</a>
    </div>

    <!-- TABS -->
    <div class="d-flex gap-2 mb-4 overflow-auto pb-1 hide-scrollbar">
      <a href="/leaderboard?tab=daily" class="lb-nav-pill {% if active_tab == 'daily' %}active{% endif %}">Daily</a>
      <a href="/leaderboard?tab=weekly" class="lb-nav-pill {% if active_tab == 'weekly' %}active{% endif %}">Weekly</a>
      <a href="/leaderboard?tab=monthly" class="lb-nav-pill {% if active_tab == 'monthly' %}active{% endif %}">Monthly</a>
      <a href="/leaderboard?tab=all-time" class="lb-nav-pill {% if active_tab == 'all-time' %}active{% endif %}">All-Time</a>
    </div>"""
    html = html.replace(header_old, header_new)

    # 3. Podium Update (use macro for podium item to reduce duplication)
    podium_old = """      <div class="podium-section">
        <!-- 2nd place -->
        {% if top3|length >= 2 %}
        <div class="podium-item podium-2nd">
          <div class="podium-avatar">🥈</div>
          <div class="podium-name" title="{{ top3[1].display_name }}">
            {{ top3[1].display_name }}
            {% if top3[1].username == username %}<span class="me-tag">YOU</span>{% endif %}
          </div>
          <div class="podium-km">{{ top3[1].total_dist }} km</div>
          <div class="podium-bar">2</div>
        </div>
        {% endif %}

        <!-- 1st place -->
        <div class="podium-item podium-1st">
          <div class="podium-avatar">🥇</div>
          <div class="podium-name" title="{{ top3[0].display_name }}">
            {{ top3[0].display_name }}
            {% if top3[0].username == username %}<span class="me-tag">YOU</span>{% endif %}
          </div>
          <div class="podium-km">{{ top3[0].total_dist }} km</div>
          <div class="podium-bar">1</div>
        </div>

        <!-- 3rd place -->
        {% if top3|length >= 3 %}
        <div class="podium-item podium-3rd">
          <div class="podium-avatar">🥉</div>
          <div class="podium-name" title="{{ top3[2].display_name }}">
            {{ top3[2].display_name }}
            {% if top3[2].username == username %}<span class="me-tag">YOU</span>{% endif %}
          </div>
          <div class="podium-km">{{ top3[2].total_dist }} km</div>
          <div class="podium-bar">3</div>
        </div>
        {% endif %}
      </div>"""
      
    podium_new = """      <div class="podium-section">
        {% macro podium_user(u, place_class, bar_num, crown_icon) %}
        <div class="podium-item {{ place_class }}">
          <div class="podium-avatar position-relative">
            {% if crown_icon %}
            <div class="position-absolute" style="top: -24px; font-size: 1.4rem;">{{ crown_icon }}</div>
            {% endif %}
            {% if u.has_avatar %}
              <img src="/avatar/{{ u.username }}" alt="Avatar" class="avatar-img">
            {% else %}
              <div class="avatar-initials text-uppercase">{{ u.display_name[0] if u.display_name else u.username[0] }}</div>
            {% endif %}
          </div>
          <div class="podium-name" title="{{ u.display_name }}">
            <a href="/u/{{ u.username }}" class="text-decoration-none" style="color:inherit;">
              {{ u.display_name }}
              {% if u.username == username %}<span class="me-tag">YOU</span>{% endif %}
            </a>
            {% if u.current_streak > 0 %}
            <div class="streak-subtitle">🔥 {{ u.current_streak }} day streak</div>
            {% endif %}
          </div>
          <div class="podium-km">{{ u.total_dist }} km</div>
          <div class="podium-bar">
            <span style="font-size: 0.9rem; font-weight: 800; color: rgba(255,255,255,0.7);">
              {% if bar_num == 1 %}WINNER{% elif bar_num == 2 %}2ND{% elif bar_num == 3 %}3RD{% endif %}
            </span>
          </div>
        </div>
        {% endmacro %}

        <!-- 2nd place -->
        {% if top3|length >= 2 %}
          {{ podium_user(top3[1], 'podium-2nd', 2, '') }}
        {% endif %}

        <!-- 1st place -->
        {% if top3|length >= 1 %}
          {{ podium_user(top3[0], 'podium-1st', 1, '👑') }}
        {% endif %}

        <!-- 3rd place -->
        {% if top3|length >= 3 %}
          {{ podium_user(top3[2], 'podium-3rd', 3, '') }}
        {% endif %}
      </div>"""
    html = html.replace(podium_old, podium_new)

    # 4. Update the styling for the podium colors
    # User said: "Use RunRush's existing accent colors for the rank rings/badges (cyan/teal primary accent for #1, and use existing secondary accent colors already in your palette — e.g. --accent-lime, --accent-orange — for #2/#3 rather than introducing new colors)."
    
    color_replacements = {
        "var(--gold)": "var(--accent)",
        "var(--gold-soft)": "var(--accent-soft)",
        "rgba(255, 215, 0, 0.3)": "rgba(0, 242, 255, 0.3)",
        "rgba(255, 215, 0, 0.4)": "rgba(0, 242, 255, 0.4)",
        "rgba(255, 215, 0, 0.35)": "rgba(0, 242, 255, 0.35)",
        "rgba(255, 215, 0, 0.08)": "rgba(0, 242, 255, 0.08)",
        
        "var(--silver)": "var(--accent-lime)",
        "var(--silver-soft)": "rgba(176, 255, 79, 0.12)",
        "rgba(192, 192, 192, 0.2)": "rgba(176, 255, 79, 0.2)",
        "rgba(192, 192, 192, 0.25)": "rgba(176, 255, 79, 0.25)",
        "rgba(192, 192, 192, 0.06)": "rgba(176, 255, 79, 0.06)",
        "rgba(192, 192, 192, 0.3)": "rgba(176, 255, 79, 0.3)",
        
        "var(--bronze)": "var(--accent-orange)",
        "var(--bronze-soft)": "rgba(255, 110, 58, 0.12)",
        "rgba(205, 127, 50, 0.2)": "rgba(255, 110, 58, 0.2)",
        "rgba(205, 127, 50, 0.25)": "rgba(255, 110, 58, 0.25)",
        "rgba(205, 127, 50, 0.06)": "rgba(255, 110, 58, 0.06)",
        "rgba(205, 127, 50, 0.3)": "rgba(255, 110, 58, 0.3)"
    }
    for old, new in color_replacements.items():
        html = html.replace(old, new)

    # 5. Full table updates (from rank 4+)
    # We only show ranks 4+ in the list! Wait, the original shows ALL qualified runners in the table.
    # The requirement says: "Below the podium, render ranks 4+ as a numbered list"
    
    table_loop_old = """            {% for u in leaderboard %}"""
    table_loop_new = """            {% for u in leaderboard %}
            {% if loop.index > 3 %}"""
            
    html = html.replace(table_loop_old, table_loop_new)
    
    table_loop_end_old = """            {% endfor %}
          </tbody>"""
    table_loop_end_new = """            {% endif %}
            {% endfor %}
          </tbody>"""
    html = html.replace(table_loop_end_old, table_loop_end_new)
    
    # 6. Include avatar and streak in the table.
    td_old = """              <td>
                <a href="/u/{{ u.username }}" class="text-decoration-none" style="color:inherit;">
                  <span class="fw-bold">{{ u.display_name }}</span>
                  {% if u.username == username %}
                  <span class="me-tag">YOU</span>
                  {% endif %}
                  <br>
                  <small class="text-muted" style="font-size:0.72rem;">@{{ u.username }}</small>
                </a>
              </td>"""
              
    td_new = """              <td>
                <div class="d-flex align-items-center gap-3">
                  <div style="width: 40px; height: 40px; flex-shrink: 0;">
                    {% if u.has_avatar %}
                      <img src="/avatar/{{ u.username }}" alt="Avatar" class="avatar-img" style="border: 1px solid var(--border-subtle);">
                    {% else %}
                      <div class="avatar-initials text-uppercase" style="background: var(--bg-card-hover); border: 1px solid var(--border-subtle);">{{ u.display_name[0] if u.display_name else u.username[0] }}</div>
                    {% endif %}
                  </div>
                  <a href="/u/{{ u.username }}" class="text-decoration-none" style="color:inherit;">
                    <span class="fw-bold">{{ u.display_name }}</span>
                    {% if u.username == username %}
                    <span class="me-tag">YOU</span>
                    {% endif %}
                    {% if u.current_streak > 0 %}
                    <br><small class="streak-subtitle">🔥 {{ u.current_streak }} day streak</small>
                    {% else %}
                    <br><small class="text-muted" style="font-size:0.72rem;">@{{ u.username }}</small>
                    {% endif %}
                  </a>
                </div>
              </td>"""
    html = html.replace(td_old, td_new)

    with open("templates/leaderboard.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    modify_leaderboard()
    print("Done")
