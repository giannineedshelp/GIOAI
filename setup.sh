#!/data/data/com.termux/files/usr/bin/bash
# GIOAI Setup
cd /storage/emulated/0/Documents/GIOAI
echo "Installing dependencies..."
pip install -r requirements.txt -q
mkdir -p data/cache logs
echo "Downloading school data..."
curl -s -o data/cache/schools.txt "https://static.sparxhomework.uk/sl/spx001/data.txt"
if [ -f data/cache/schools.txt ]; then echo "Schools saved ($(wc -c < data/cache/schools.txt) bytes)"; fi
echo "Done! Run: python platforms/sparx/main.py"
