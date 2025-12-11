#!/bin/bash
# Paprastas paleidimo scriptas - dukart spustelėkite šį failą

cd "$(dirname "$0")"

echo "=========================================="
echo "Paleidžiama Mano Startuolis programa..."
echo "=========================================="
echo ""
echo "Programa automatiškai ras laisvą portą"
echo "Atidarykite naršyklėje adresą, kuris bus rodomas žemiau"
echo ""
echo "Norėdami sustabdyti, uždarykite šį langą"
echo "=========================================="
echo ""

python3 start.py
