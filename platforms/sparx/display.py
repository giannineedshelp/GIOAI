# platforms/sparx/display.py
import discord
from datetime import datetime

# Your custom emojis
PROGRESS = {
    "full":  {"l": "<:lb_g:5988>",  "m": "<:emojigg_l_g:2827>", "r": "<:lb4_g:3166>"},
    "empty": {"l": "<:lb2_g:5499>", "m": "<:l2_g:3451>",        "r": "<:lb3_g:2881>"},
}

def progress_bar(pct):
    filled = max(0, min(3, round(pct / 100 * 3)))
    if filled == 0: 
        return PROGRESS["empty"]["l"] + PROGRESS["empty"]["m"] + PROGRESS["empty"]["r"]
    if filled >= 3: 
        return PROGRESS["full"]["l"] + PROGRESS["full"]["m"] + PROGRESS["full"]["r"]
    if filled == 1: 
        return PROGRESS["full"]["l"] + PROGRESS["empty"]["m"] + PROGRESS["empty"]["r"]
    return PROGRESS["full"]["l"] + PROGRESS["full"]["m"] + PROGRESS["empty"]["r"]

def create_task_message(account_name, assignment_name, tasks, page_current, page_total, simulated_seconds, fake_min=5, fake_max=8):
    lines = []
    lines.append(f"Account: `{account_name}`")
    lines.append(f"Name: `{assignment_name}`")
    completed = sum(1 for t in tasks if t["pct"] >= 100)
    status = "Completed ✓" if completed == len(tasks) else f"{completed}/{len(tasks)}"
    lines.append(f"Status: `{status}`")
    lines.append(f"Page: `{page_current} of {page_total}`")
    lines.append("")
    for i, task in enumerate(tasks, 1):
        lines.append(f"-# {i}. {task['name']} **` {task['pct']}% `**")
        lines.append(progress_bar(task['pct']))
    lines.append("")
    lines.append(f"-# **Simulated time:** {simulated_seconds//60}m {simulated_seconds%60}s")
    lines.append(f"-# **Fake Question Time:** {fake_min}s - {fake_max}s")
    return "\n".join(lines)
