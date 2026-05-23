# platforms/sparx/display.py
import discord
from datetime import datetime
import random

# ═══════════════════════════════════════════════
# YOUR ACTUAL CUSTOM EMOJIS (from your repo)
# ═══════════════════════════════════════════════

PROGRESS = {
    "full":  {"l": "<:lb_g:5988>",  "m": "<:emojigg_l_g:2827>", "r": "<:lb4_g:3166>"},
    "empty": {"l": "<:lb2_g:5499>", "m": "<:l2_g:3451>",        "r": "<:lb3_g:2881>"},
}

def progress_bar(pct):
    """3-segment progress bar using your PROGRESS emojis"""
    filled = max(0, min(3, round(pct / 100 * 3)))
    if filled == 0: 
        return PROGRESS["empty"]["l"] + PROGRESS["empty"]["m"] + PROGRESS["empty"]["r"]
    if filled >= 3: 
        return PROGRESS["full"]["l"] + PROGRESS["full"]["m"] + PROGRESS["full"]["r"]
    if filled == 1: 
        return PROGRESS["full"]["l"] + PROGRESS["empty"]["m"] + PROGRESS["empty"]["r"]
    return PROGRESS["full"]["l"] + PROGRESS["full"]["m"] + PROGRESS["empty"]["r"]

def text_progress_bar(pct, width=12):
    """Simple text progress bar as fallback"""
    filled = max(0, min(width, round(pct / 100 * width)))
    return "█" * filled + "░" * (width - filled)

def create_task_message(
    account_name,
    assignment_name,
    tasks,
    page_current,
    page_total,
    simulated_seconds,
    fake_min=60,
    fake_max=70,
    correct_count=0,
    xp_gained=0,
    finish_timestamp=None,
    warning=None,
):
    """
    Creates DM progress message with task-by-task percentage view.
    Uses your PROGRESS emojis for the bar.
    """
    lines = []
    lines.append(f"Account: `{account_name}`")
    lines.append(f"Name: `{assignment_name}`")
    
    completed = sum(1 for t in tasks if t.get("pct", 0) >= 100)
    total = len(tasks)
    
    if completed == total:
        lines.append("Status: `Completed ✓`")
    else:
        lines.append("Status: `Getting activity...`")
    
    if warning:
        lines.append(f"Warning: `{warning}`")
    
    lines.append("")
    
    for i, task in enumerate(tasks, 1):
        pct = task.get("pct", 0)
        name_display = task.get("name", task.get("title", f"Task {i}"))[:45]
        bar = text_progress_bar(pct, 10)
        status_icon = "✅" if pct >= 100 else "🔄" if pct > 0 else "⏳"
        lines.append(f"{status_icon} `{bar}` **{pct}%** — {name_display}")
    
    lines.append("")
    
    total_qs = sum(t.get("total_q", 1) for t in tasks) if tasks else 1
    lines.append(f"-# **Correct:** {correct_count}/{total_qs}")
    lines.append(f"-# **Simulated time:** {simulated_seconds//60}m {simulated_seconds%60}s")
    lines.append(f"-# **Fake Question Time:** {fake_min}s - {fake_max}s")
    lines.append(f"-# **XP Gained:** {xp_gained}")
    
    if finish_timestamp:
        lines.append(f"-# **Finishes:** <t:{finish_timestamp}:R>")
    
    return "\n".join(lines)

def create_completion_message(account_name, assignment_name, total_questions, correct_count, simulated_seconds, fake_min=60, fake_max=70, xp_gained=0):
    """Final completion message with full bars"""
    lines = []
    lines.append(f"Account: `{account_name}`")
    lines.append(f"Name: `{assignment_name}`")
    lines.append("Status: `Completed ✓`")
    lines.append("")
    bar = text_progress_bar(100, 12)
    lines.append(f"✅ `{bar}` **100% — All tasks completed**")
    lines.append("")
    lines.append(f"-# **Correct:** {correct_count}/{total_questions}")
    lines.append(f"-# **Simulated time:** {simulated_seconds//60}m {simulated_seconds%60}s")
    lines.append(f"-# **Fake Question Time:** {fake_min}s - {fake_max}s")
    lines.append(f"-# **XP Gained:** {xp_gained}")
    return "\n".join(lines)

def format_homeworks_for_display(homeworks, username):
    """Format homework list with percentage and task breakdown for Discord"""
    if not homeworks:
        return f"**Homework for {username}**\nNo homework found! All caught up."
    
    # Separate incomplete and complete
    incomplete = [h for h in homeworks if not h.get('completed')]
    complete = [h for h in homeworks if h.get('completed')]
    
    lines = [f"**Homework for {username}**"]
    
    display_hw = incomplete + complete[:3]  # Incomplete first, then up to 3 completed
    
    for i, hw in enumerate(display_hw, 1):
        title = hw.get('title', 'Homework')
        subject = f" ({hw.get('subject_text', '')})" if hw.get('subject_text') else ""
        status = hw.get('status', '')
        total_q = hw.get('total_q', 0)
        completed_q = hw.get('completed_q', 0)
        due = hw.get('due', '')
        
        pct = (completed_q / total_q * 100) if total_q > 0 else 0
        bar = text_progress_bar(pct, 10)
        
        # Determine status
        is_done = (str(status).lower() in ('complete', 'completed', 'done', 'submitted', 'finished')
                  or (total_q and completed_q and completed_q >= total_q))
        status_icon = "✅" if is_done else "📝"
        
        lines.append(f"\n{status_icon} **{i}. {title}**{subject}")
        lines.append(f"   `{bar}` **{pct:.0f}%** ({completed_q}/{total_q})")
        
        if due:
            from shared.utils.helpers import fmt_date
            lines.append(f"   ⏰ Due: {fmt_date(due)}")
        
        if status and not is_done:
            lines.append(f"   📊 Status: {status}")
    
    if len(complete) > 3:
        lines.append(f"\n*...and {len(complete) - 3} completed homeworks*")
    
    return "\n".join(lines)

# Embed color palette
EMBED_COLORS = [
    0x5865F2, 0x57F287, 0xFEE75C, 0xEB459E,
    0xED4245, 0x00FFCC, 0xFF6600, 0x9B59B6,
]

def random_color():
    return random.choice(EMBED_COLORS)
