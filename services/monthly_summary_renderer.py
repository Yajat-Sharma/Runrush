"""
Monthly summary HTML renderer — turns a MonthlySummary (from
monthly_summary_service.py) into an email-safe HTML string.

Deliberately separate from both the calculation engine (no DB access here)
and from email transport (no Resend/urllib here, no sending). This module's
only job is: MonthlySummary -> (subject, html).

Email-client constraints followed (see project spec):
- Inline styles only, no external CSS/JS, no backdrop-filter/glassmorphism/
  animation, conservative CSS (flex/grid degrade acceptably in clients that
  ignore them since every stat also has a plain text label).
- Dark near-black / charcoal palette with the app's actual brand accent
  (#1683F7 — the blue used across templates/index.html, public_profile.html,
  leaderboard.html; NOT the #F5A623 orange used only in the weekly email
  and the admin UI, which is not the primary brand color per the CSS
  variables in the main app templates).
- All user-controlled text (display_name) is HTML-escaped — the existing
  send_weekly_summary() in app.py does NOT escape display_name in its
  f-string HTML; this renderer does not repeat that gap.
"""

import calendar
import html as _html

from services.monthly_summary_service import MonthlySummary

_BG = "#09090f"
_PANEL_BG = "#0d0d1a"
_CARD_BG = "#1a1a2e"
_ACCENT = "#1683F7"
_TEXT_DIM = "#888"
_TEXT_FAINT = "#555"


def _e(value):
    """HTML-escape any string that may contain user-controlled content."""
    return _html.escape(str(value), quote=True)


def _sanitize_for_subject(value):
    """Sanitize user-controlled text for use in an email subject line.

    Deliberately NOT html.escape() — a subject line is plain text, not
    HTML, so escaping it would show the recipient literal entities like
    &#39; instead of an apostrophe. The actual risk in a subject line is
    control characters (particularly CR/LF), which could otherwise inject
    stray header-like content depending on how deep in the stack a raw
    value ends up; this strips every C0 control character (0x00-0x1F) and
    DEL (0x7F), keeping everything else as-is."""
    return "".join(ch for ch in str(value) if ord(ch) >= 0x20 and ord(ch) != 0x7F).strip()


def _format_pace(pace_min_per_km):
    if pace_min_per_km is None:
        return "--:--"
    minutes = int(pace_min_per_km)
    seconds = int(round((pace_min_per_km - minutes) * 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}"


def _format_duration(total_time_min):
    if total_time_min is None:
        return "0h 0m"
    hours = int(total_time_min // 60)
    minutes = int(total_time_min % 60)
    return f"{hours}h {minutes}m"


def _next_month_label(year, month):
    if month == 12:
        return calendar.month_name[1], year + 1
    return calendar.month_name[month + 1], year


def render_subject(summary: MonthlySummary) -> str:
    name = _sanitize_for_subject(summary.display_name)
    if not summary.has_activity:
        return f"Your {summary.month_label} with RunRush"
    return f"\U0001f3c3 {name}'s {summary.month_label} Running Summary – RunRush"


def _stat_card(value, label, color):
    return (
        f'<div style="background:{_CARD_BG};border-radius:12px;padding:18px;text-align:center;">'
        f'<div style="font-size:1.8rem;font-weight:800;color:{color};">{value}</div>'
        f'<div style="color:{_TEXT_DIM};font-size:0.78rem;margin-top:4px;">{label}</div>'
        f'</div>'
    )


def _comparison_line(comparison, key, label, unit=""):
    cmp = comparison.get(key)
    if cmp is None or not cmp.available:
        return ""
    direction = "+" if cmp.delta >= 0 else ""
    pct = f" ({direction}{cmp.pct_change:.1f}%)" if cmp.pct_change is not None else ""
    color = "#4ade80" if cmp.delta >= 0 else "#f87171"
    return (
        f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
        f'border-bottom:1px solid #22222f;font-size:0.85rem;">'
        f'<span style="color:{_TEXT_DIM};">{label}</span>'
        f'<span style="color:{color};font-weight:600;">{direction}{cmp.delta:.1f}{unit}{pct}</span>'
        f'</div>'
    )


def _weekly_bar_chart(weekly_breakdown):
    if not weekly_breakdown:
        return ""
    max_km = max((b.distance_km for b in weekly_breakdown), default=0) or 1
    rows = []
    for b in weekly_breakdown:
        pct = max(4, round((b.distance_km / max_km) * 100)) if b.distance_km > 0 else 0
        rows.append(
            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">'
            f'<div style="width:56px;color:{_TEXT_DIM};font-size:0.75rem;flex-shrink:0;">{_e(b.label)}</div>'
            f'<div style="flex:1;background:#151522;border-radius:6px;height:14px;overflow:hidden;">'
            f'<div style="width:{pct}%;background:{_ACCENT};height:100%;border-radius:6px;"></div>'
            f'</div>'
            f'<div style="width:56px;color:#ccc;font-size:0.75rem;text-align:right;flex-shrink:0;">{b.distance_km:.1f} km</div>'
            f'</div>'
        )
    return (
        '<div style="margin-bottom:20px;">'
        f'<div style="color:#ccc;font-size:0.85rem;font-weight:700;margin-bottom:10px;">WEEKLY BREAKDOWN</div>'
        + "".join(rows) +
        '</div>'
    )


_PB_LABELS = {
    "fastest_5k": "New 5K PB",
    "fastest_10k": "New 10K PB",
    "longest_run": "New Longest Run",
    "fastest_pace": "New Fastest Pace",
}


def _pb_unit_value(pb):
    if pb.unit == "min/km":
        return f"{_format_pace(pb.value)} /km"
    return f"{pb.value:.1f} km"


def render_html(summary: MonthlySummary) -> str:
    if not summary.has_activity:
        return _render_zero_activity_html(summary)
    return _render_active_html(summary)


def _shell(name, month_label, body_html, footer_note):
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:20px;background:{_BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:560px;margin:0 auto;background:{_PANEL_BG};border-radius:20px;overflow:hidden;">
  <div style="background:{_ACCENT};padding:32px;text-align:center;">
    <div style="font-size:2.2rem;">\U0001f3c3</div>
    <h1 style="margin:8px 0 4px;color:#fff;font-size:1.4rem;font-weight:800;">RunRush</h1>
    <p style="margin:0;color:rgba(255,255,255,0.8);font-size:0.85rem;">Track. Improve. Repeat.</p>
  </div>
  <div style="padding:28px 32px;">
    <p style="color:#666;text-transform:uppercase;letter-spacing:0.05em;font-size:0.75rem;margin:0 0 4px;">Your {_e(month_label)}</p>
    {body_html}
    <div style="text-align:center;margin-top:28px;">
      <a href="https://runrush.app/dashboard"
         style="background:{_ACCENT};color:#fff;padding:13px 32px;border-radius:50px;text-decoration:none;font-weight:700;font-size:0.95rem;display:inline-block;">Open RunRush &rarr;</a>
    </div>
    <p style="color:{_TEXT_FAINT};font-size:0.72rem;text-align:center;margin-top:24px;">{footer_note}
      <a href="https://runrush.app/settings" style="color:{_TEXT_FAINT};">Email preferences / unsubscribe</a>
    </p>
  </div>
</div></body></html>"""


def _render_zero_activity_html(summary: MonthlySummary) -> str:
    next_month_name, _next_year = _next_month_label(summary.year, summary.month)
    name = _e(summary.display_name)
    body = f"""
    <h2 style="color:#fff;font-size:1.3rem;margin:0 0 16px;">Hi {name},</h2>
    <p style="color:#ccc;line-height:1.5;">You didn't log a run in {_e(summary.month_label)}. No pressure &mdash; every runner has quiet months.</p>
    <p style="color:#ccc;line-height:1.5;">Ready for {_e(next_month_name)}?</p>
    """
    return _shell(name, summary.month_label, body, "You're receiving this because you opted in to monthly summaries.")


def _render_active_html(summary: MonthlySummary) -> str:
    name = _e(summary.display_name)

    stats_html = (
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:16px 0 20px;">'
        + _stat_card(f"{summary.total_distance_km:.1f}", "KM THIS MONTH", _ACCENT)
        + _stat_card(f"{summary.total_runs}", "RUNS LOGGED", "#4dadff")
        + _stat_card(_format_pace(summary.avg_pace_min_per_km), "AVG MIN/KM", "#d988ff")
        + _stat_card(_format_duration(summary.total_time_min), "TOTAL TIME", "#b0ff4f")
        + '</div>'
    )

    highlight_rows = []
    if summary.longest_run_km is not None:
        highlight_rows.append(("Longest Run", f"{summary.longest_run_km:.1f} km"))
    if summary.fastest_pace_min_per_km is not None:
        highlight_rows.append(("Fastest Pace", f"{_format_pace(summary.fastest_pace_min_per_km)} /km"))
    if summary.longest_streak_in_month:
        highlight_rows.append(("Best Streak", f"{summary.longest_streak_in_month} day{'s' if summary.longest_streak_in_month != 1 else ''}"))
    if summary.most_active_day:
        highlight_rows.append(("Most Active Day", f"{_e(summary.most_active_day)} ({summary.most_active_day_count} run{'s' if summary.most_active_day_count != 1 else ''})"))

    highlights_html = ""
    if highlight_rows:
        rows_html = "".join(
            f'<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #22222f;">'
            f'<span style="color:{_TEXT_DIM};font-size:0.85rem;">{_e(label)}</span>'
            f'<span style="color:#fff;font-weight:700;font-size:0.85rem;">{value}</span>'
            f'</div>'
            for label, value in highlight_rows
        )
        highlights_html = (
            '<div style="margin-bottom:20px;">'
            '<div style="color:#ccc;font-size:0.85rem;font-weight:700;margin-bottom:6px;">YOUR HIGHLIGHTS</div>'
            + rows_html + '</div>'
        )

    weekly_html = _weekly_bar_chart(summary.weekly_breakdown)

    goal_html = ""
    if summary.goal is not None:
        pct_display = min(100, summary.goal.percent)
        complete_badge = (
            '<span style="color:#4ade80;font-weight:700;">&#10003; Monthly Goal Complete</span>'
            if summary.goal.completed else ""
        )
        goal_html = (
            '<div style="margin-bottom:20px;">'
            '<div style="color:#ccc;font-size:0.85rem;font-weight:700;margin-bottom:8px;">GOAL PROGRESS</div>'
            f'<div style="color:#fff;font-size:0.95rem;margin-bottom:6px;">{summary.goal.actual_km:.1f} / {summary.goal.target_km:.0f} km &mdash; {summary.goal.percent:.0f}%</div>'
            f'<div style="background:#151522;border-radius:6px;height:10px;overflow:hidden;">'
            f'<div style="width:{pct_display}%;background:{_ACCENT};height:100%;border-radius:6px;"></div>'
            f'</div>'
            + (f'<div style="margin-top:6px;">{complete_badge}</div>' if complete_badge else '')
            + '</div>'
        )

    achievements_html = ""
    if summary.achievements:
        badge_spans = "".join(
            f'<span style="display:inline-block;background:{_CARD_BG};border-radius:20px;padding:6px 14px;margin:0 6px 6px 0;color:#fff;font-size:0.8rem;">'
            f'{_e(a.icon)} {_e(a.name)}</span>'
            for a in summary.achievements
        )
        achievements_html = (
            '<div style="margin-bottom:20px;">'
            '<div style="color:#ccc;font-size:0.85rem;font-weight:700;margin-bottom:8px;">ACHIEVEMENTS</div>'
            f'<div>{badge_spans}</div>'
            '</div>'
        )

    pb_html = ""
    if summary.personal_bests:
        badge_spans = "".join(
            f'<span style="display:inline-block;background:{_CARD_BG};border-radius:20px;padding:6px 14px;margin:0 6px 6px 0;color:{_ACCENT};font-size:0.8rem;font-weight:700;">'
            f'⚡ {_e(_PB_LABELS[pb.metric])}: {_pb_unit_value(pb)}</span>'
            for pb in summary.personal_bests
        )
        pb_html = (
            '<div style="margin-bottom:20px;">'
            '<div style="color:#ccc;font-size:0.85rem;font-weight:700;margin-bottom:8px;">PERSONAL BESTS</div>'
            f'<div>{badge_spans}</div>'
            '</div>'
        )

    comparison_html = ""
    if summary.has_previous_month_data and summary.comparison:
        lines = (
            _comparison_line(summary.comparison, "total_distance_km", "Distance", " km")
            + _comparison_line(summary.comparison, "total_runs", "Runs", "")
            + _comparison_line(summary.comparison, "longest_run_km", "Longest Run", " km")
        )
        if lines:
            comparison_html = (
                '<div style="margin-bottom:20px;">'
                '<div style="color:#ccc;font-size:0.85rem;font-weight:700;margin-bottom:6px;">VS LAST MONTH</div>'
                + lines + '</div>'
            )
    elif not summary.has_previous_month_data:
        comparison_html = (
            '<p style="color:#666;font-size:0.8rem;font-style:italic;margin:0 0 20px;">This is your first month with data on RunRush.</p>'
        )

    sentence_html = (
        '<div style="background:#151522;border-radius:12px;padding:16px 18px;margin-bottom:8px;">'
        '<div style="color:#666;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">Your month in one line</div>'
        f'<div style="color:#fff;font-size:0.95rem;line-height:1.4;">{_e(summary.summary_sentence)}</div>'
        '</div>'
    )

    body = (
        f'<h2 style="color:#fff;font-size:1.3rem;margin:0 0 12px;">Hi {name},</h2>'
        + stats_html
        + highlights_html
        + weekly_html
        + goal_html
        + pb_html
        + achievements_html
        + comparison_html
        + sentence_html
    )

    return _shell(name, summary.month_label, body, "You're receiving this because you opted in to monthly summaries.")
