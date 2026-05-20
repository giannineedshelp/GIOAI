#!/usr/bin/env python3
import os, subprocess, json, sys

def run(cmd):
    print(f"> {cmd}")
    subprocess.run(cmd, shell=True, check=True)

if len(sys.argv) < 2:
    print("Usage: python update_github.py 'your commit message'")
    sys.exit(1)

msg = sys.argv[1]
run("git add .")
run(f'git commit -m "{msg}"')
run("git push origin main")
print("✅ Pushed to GitHub successfully!")
