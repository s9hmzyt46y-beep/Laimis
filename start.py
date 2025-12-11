#!/usr/bin/env python3
"""
Paprastas būdas paleisti Flask programą.

Tiesiog paleiskite: python3 start.py
"""

import socket
from app import app

def find_free_port(start_port=3000, max_attempts=100):
    """
    Randa laisvą portą, pradedant nuo start_port.
    
    HOW IT WORKS:
    - Bando sukurti socket'ą ant kiekvieno porto
    - Jei portas užimtas, bando kitą
    - Grąžina pirmą laisvą portą
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            # Bandoma sukurti socket'ą ant porto
            # Jei pavyks, portas laisvas
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            # Portas užimtas, bandoma kitą
            continue
    # Jei nerasta laisvo porto, naudojame paskutinį
    return start_port

if __name__ == '__main__':
    # Automatiškai rasti laisvą portą
    # Pradedame nuo 3000, nes šis portas retai būna užimtas
    port = find_free_port(3000)
    
    print("=" * 50)
    print("Paleidžiama Mano Startuolis programa...")
    print("=" * 50)
    print(f"\nAtidarykite naršyklėje: http://localhost:{port}")
    print("\nNorėdami sustabdyti, paspauskite CTRL+C\n")
    print("=" * 50)
    
    # Paleisti serverį ant rasto porto
    app.run(debug=True, host='127.0.0.1', port=port)
