#!/bin/bash
# Paprastas scriptas Flask programai paleisti

# Sustabdo seną procesą, jei veikia
lsof -ti:8080 | xargs kill -9 2>/dev/null

# Laukia sekundę
sleep 1

# Paleidžia Flask programą
cd "$(dirname "$0")"
python app.py

