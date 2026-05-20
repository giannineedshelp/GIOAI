# GIOAI Helpers
import asyncio, json, re, time, random, os
from datetime import datetime

def load_env():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

def get(key, default=""):
    return os.getenv(key, default)

def fmt_bar(completed, total, width=12):
    if not total: return "▱" * width
    fi = max(0, min(width, int((completed / total) * width)))
    return "▰" * fi + "▱" * (width - fi)

def fmt_time(secs):
    if secs < 60: return f"{secs:.0f}s"
    if secs < 3600: return f"{secs//60}m {secs%60}s"
    return f"{secs//3600}h {(secs%3600)//60}m"

def clamp(n, lo, hi): return max(lo, min(hi, n))
