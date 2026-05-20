# GIOAI Helpers
import os
from dotenv import load_dotenv

def load_env():
    dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)

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
