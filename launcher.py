#!/usr/bin/env python3
"""
Paprastas launcher su GUI mygtuku Flask programai paleisti.

Šis scriptas sukuria paprastą langą su mygtuku, kuris:
1. Paleidžia Flask serverį
2. Atidaro naršyklę
3. Rodo statusą
"""

import tkinter as tk
from tkinter import messagebox
import subprocess
import webbrowser
import threading
import time
import os
import sys
import socket

class FlaskLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Mano Startuolis - Serverio paleidimas")
        self.root.geometry("400x200")
        self.root.resizable(False, False)
        
        # Serverio procesas
        self.server_process = None
        self.is_running = False
        self.server_port = None  # Dinamiškai rastas portas
        
        # Sukuriamas UI
        self.create_widgets()
        
        # Patikrinti, ar serveris jau veikia
        self.check_server_status()
    
    def create_widgets(self):
        """Sukuria UI elementus."""
        # Antraštė
        title_label = tk.Label(
            self.root, 
            text="Mano Startuolis - Apskaitos sistema",
            font=("Arial", 14, "bold"),
            pady=20
        )
        title_label.pack()
        
        # Statuso tekstas
        self.status_label = tk.Label(
            self.root,
            text="Serveris neveikia",
            fg="red",
            font=("Arial", 10)
        )
        self.status_label.pack(pady=10)
        
        # Run mygtukas
        self.run_button = tk.Button(
            self.root,
            text="▶ PALEISTI SERVERĮ",
            command=self.toggle_server,
            bg="#28a745",
            fg="white",
            font=("Arial", 12, "bold"),
            width=20,
            height=2,
            cursor="hand2"
        )
        self.run_button.pack(pady=10)
        
        # Atidaryti naršyklėje mygtukas
        self.browser_button = tk.Button(
            self.root,
            text="🌐 Atidaryti naršyklėje",
            command=self.open_browser,
            bg="#007bff",
            fg="white",
            font=("Arial", 10),
            width=20,
            cursor="hand2",
            state="disabled"
        )
        self.browser_button.pack(pady=5)
    
    def find_free_port(self, start_port=3000, max_attempts=100):
        """Randa laisvą portą."""
        for port in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', port))
                    return port
            except OSError:
                continue
        return start_port
    
    def check_server_status(self):
        """Tikrina, ar serveris veikia - bando rasti ant kurio porto."""
        # Bandoma rasti serverį ant įvairių portų
        for port in range(3000, 3100):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                if result == 0:
                    self.is_running = True
                    self.server_port = port
                    self.update_ui_running()
                    return
            except:
                pass
        self.is_running = False
        self.server_port = None
        self.update_ui_stopped()
    
    def toggle_server(self):
        """Paleidžia arba sustabdo serverį."""
        if self.is_running:
            self.stop_server()
        else:
            self.start_server()
    
    def start_server(self):
        """Paleidžia Flask serverį."""
        if self.is_running:
            return
        
        try:
            # Pakeisti į projekto katalogą
            script_dir = os.path.dirname(os.path.abspath(__file__))
            os.chdir(script_dir)
            
            # Paleisti Flask serverį fone
            self.server_process = subprocess.Popen(
                [sys.executable, "app.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # Laukti, kol serveris pasileis
            self.status_label.config(text="Paleidžiama...", fg="orange")
            self.root.update()
            
            # Patikrinti, ar serveris pasileido - rasti ant kurio porto
            for i in range(20):
                time.sleep(0.5)
                # Bandoma rasti serverį ant įvairių portų
                for port in range(3000, 3100):
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(0.1)
                        result = sock.connect_ex(('localhost', port))
                        sock.close()
                        if result == 0:
                            self.is_running = True
                            self.server_port = port
                            self.update_ui_running()
                            messagebox.showinfo("Sėkmė!", f"Serveris sėkmingai paleistas!\n\nAtidarykite naršyklėje:\nhttp://localhost:{port}")
                            return
                    except:
                        pass
            
            # Jei nepasileido
            self.is_running = False
            self.update_ui_stopped()
            messagebox.showerror("Klaida", "Nepavyko paleisti serverio.\nPatikrinkite, ar yra klaidų.")
            
        except Exception as e:
            messagebox.showerror("Klaida", f"Nepavyko paleisti serverio:\n{str(e)}")
            self.is_running = False
            self.update_ui_stopped()
    
    def stop_server(self):
        """Sustabdo Flask serverį."""
        if not self.is_running:
            return
        
        try:
            # Rasti ir sustabdyti procesą, kuris naudoja rastą portą (Mac/Linux)
            if self.server_port:
                result = subprocess.run(
                    ["lsof", f"-ti:{self.server_port}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.stdout.strip():
                    pid = result.stdout.strip()
                    subprocess.run(["kill", "-9", pid], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE)
            # Taip pat sustabdyti pagal procesą
            if self.server_process:
                try:
                    self.server_process.terminate()
                    self.server_process.wait(timeout=5)
                except:
                    try:
                        self.server_process.kill()
                    except:
                        pass
        except:
            pass
        
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
            except:
                try:
                    self.server_process.kill()
                except:
                    pass
        
        self.is_running = False
        self.update_ui_stopped()
        messagebox.showinfo("Sustabdyta", "Serveris sustabdytas.")
    
    def open_browser(self):
        """Atidaro naršyklėje."""
        if self.server_port:
            webbrowser.open(f"http://localhost:{self.server_port}")
        else:
            webbrowser.open("http://localhost:3000")  # Default
    
    def update_ui_running(self):
        """Atnaujina UI, kai serveris veikia."""
        self.status_label.config(text="✓ Serveris veikia", fg="green")
        self.run_button.config(text="⏸ SUSTABDYTI", bg="#dc3545")
        self.browser_button.config(state="normal")
    
    def update_ui_stopped(self):
        """Atnaujina UI, kai serveris sustabdytas."""
        self.status_label.config(text="Serveris neveikia", fg="red")
        self.run_button.config(text="▶ PALEISTI SERVERĮ", bg="#28a745")
        self.browser_button.config(state="disabled")
    
    def on_closing(self):
        """Uždaryti langą - sustabdo serverį."""
        if self.is_running:
            if messagebox.askokcancel("Uždaryti", "Ar tikrai norite uždaryti? Serveris bus sustabdytas."):
                self.stop_server()
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    """Pagrindinė funkcija."""
    root = tk.Tk()
    app = FlaskLauncher(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()

