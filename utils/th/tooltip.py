# tooltip for use with th objects.

from utils.tkrichtext import RichLabel
import tkinter as tk


DELAY: int = 500 # Delay before tooltip appears in ms

class TooltipBase:

    def __init__(self, button):
        self.button = button.obj if hasattr(button, 'obj') else button
        self.alt = None
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        self._id1 = self.button.bind("<Enter>", self.enter)
        self._id2 = self.button.bind("<Leave>", self.leave)
        self._id3 = self.button.bind("<ButtonPress>", self.leave)
        if hasattr(button, 'alt'):
            self.alt = button.alt
            self._id4 = self.alt.bind("<Enter>", self.enter)
            self._id5 = self.alt.bind("<Leave>", self.leave)
            self._id6 = self.alt.bind("<ButtonPress>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.button.after(DELAY, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.button.after_cancel(id)

    def showtip(self):
        if self.tipwindow:
            return
        # The tip window must be completely outside the button;
        # otherwise when the mouse enters the tip window we get
        # a leave event and it disappears, and then we get an enter
        # event and it reappears, and so on forever :-(
        if self.alt is not None and self.alt.winfo_viewable():
            x = self.alt.winfo_rootx() + 20
            y = self.alt.winfo_rooty() + self.alt.winfo_height() + 1
            self.tipwindow = tw = tk.Toplevel(self.button)
        else:
            x = self.button.winfo_rootx() + 20
            y = self.button.winfo_rooty() + self.button.winfo_height() + 1
            self.tipwindow = tw = tk.Toplevel(self.button)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        self.showcontents()

    def showcontents(self, **kwargs):
        if 'markdown' in kwargs:
            label:tk.Label|RichLabel = RichLabel(self.tipwindow, markdown=kwargs['markdown'],
                                                 background="#ffffe0", relief=tk.SOLID, borderwidth=1)
        elif 'html' in kwargs:
            label:tk.Label|RichLabel = RichLabel(self.tipwindow, html=kwargs['html'],
                                                 background="#ffffe0", relief=tk.SOLID, borderwidth=1)
        else:
            label:tk.Label|RichLabel = tk.Label(self.tipwindow, text=kwargs['text'], justify=tk.LEFT,
                                                background="#ffffe0", relief=tk.SOLID, borderwidth=1)

        label.pack()

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

class Tooltip(TooltipBase):

    def __init__(self, button, text:str='', **kwargs):
        TooltipBase.__init__(self, button)
        self.args = kwargs
        if text != '':
            self.args['text'] = text

    def showcontents(self):
        TooltipBase.showcontents(self, **self.args)
