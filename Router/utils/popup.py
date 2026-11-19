import os
import tkinter as tk

from .debug import Debug, catch_exceptions

class PopupNotice:
    """
        Create a temporary popup window, useful for alerts or notices.
        Can be closed by clicking the Close button or after a timeout.
    """

    def __init__(self, notice:str = '', timeout:int = 0, config = None) -> None:
        self.config = config

        self.root = tk.Tk()

        if os.environ.get('XDG_SESSION_TYPE', 'x11').lower() == 'wayland':
            print("Wayland detected: Using window types for borderless effect.")
            # 'splash' or 'tooltip' usually removes decorations in Wayland
            self.root.attributes('-type', 'splash')
        else:
            self.root.overrideredirect(True)

        self.root.attributes("-alpha", 0.6)
        self.root.geometry("350x150-1+0")
        self.root.attributes("-topmost", True)

        self.frame = tk.Frame(self.root, bg='red4', relief="raised")
        self.frame.pack(fill="both", expand=True)

        label = tk.Label(self.frame, text=notice, fg="white", bg="red4", font=("Helvetica", 12, "bold"), justify=tk.CENTER)
        label.pack(pady=20, anchor=tk.CENTER)
        exit_btn = tk.Button(self.frame, text="Close", fg="white", bg="red4", command=self.close)
        exit_btn.pack(pady=10)

        if timeout > 0: self.root.after(timeout, self.close)
        self.frame.bind("<Button-1>", self.start_move)
        self.frame.bind("<B1-Motion>", self.do_move)

    def start_move(self, event) -> None:
        self.x:int = event.x
        self.y:int = event.y

    def do_move(self, event) -> None:
        deltax:int = event.x - self.x
        deltay:int = event.y - self.y
        x:int = self.root.winfo_x() + deltax
        y:int = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    @catch_exceptions
    def close(self) -> None:
        if self.root and self.root.winfo_exists():
            #self.config.window_geometries['Alert'] = self.root.winfo_geometry()
            self.root.destroy()
