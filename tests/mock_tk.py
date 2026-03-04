from typing import Callable

class tk:
    def call(self, *args, **kw): pass
class MockTk:
    """ Mock tkinter module """
    class Widget:
        tk = tk()
        _last_child_ids = {}
        _w = ''
        children = {}
        def __init__(self, *args, **kw): pass
        def winfo_toplevel(self, **kw): pass
    class Frame(Widget): 
        def __init__(self, *args, **kw): pass
        def after(*args, **kw): pass
        def grid(*args, **kw): pass
    class Toplevel(Widget): pass
    class Label(Widget): pass
    class Button(Widget): pass
    class Radiobutton(Widget): pass
    class Checkbutton(Widget): pass
    class Entry(Widget): pass
    class Image(Widget): 
        def __init__(self, *args, **kw): pass
        def _get_default_root(self, *args, **kw): pass
    class Text(Widget): pass
    class Canvas(Widget): pass
    class Listbox(Widget): pass
    class Scale(Widget): pass
    class Spinbox(Widget): pass
    class LabelFrame(Widget): pass
    class Message(Widget): pass
    class PhotoImage(Image): 
        def __init__(self, *args, **kw): pass         
    class Scrollbar(Widget): pass
    class OptionMenu(Widget): pass
    class Menubutton(Widget): pass
    class Menu(Widget): pass
    
    # Constants
    NSEW = "nsew"
    NW = "nw"
    N = "n"
    NE = "ne"
    W = "w"
    CENTER = "center"
    E = "e"
    SW = "sw"
    S = "s"
    SE = "se"
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    BOTH = "both"
    NONE = "none"
    X = "x"
    Y = "y"
    END = "end"
    DISABLED = "disabled"
    NORMAL = "normal"

    StringVar: Callable[[], None] = lambda: None
    IntVar: Callable[[], None] = lambda: None
    BooleanVar: Callable[[], None] = lambda: None

    def _get_default_root(*kw): pass
class MockFont:
    @staticmethod
    def families(): pass

class MockFileDialog:
    def __init__(self, master, title=None, **kw): pass
    @staticmethod
    def families(): pass

class MockTtk:
    """ Mock tkinter.ttk module """
    class Frame(MockTk.Frame): pass
    class Label(MockTk.Label): pass
    class Button(MockTk.Button): pass
    class Entry(MockTk.Entry): pass
    class Combobox(MockTk.Entry): pass
    class Checkbutton(MockTk.Checkbutton): pass
    class Radiobutton(MockTk.Radiobutton): pass
    class Scrollbar(MockTk.Scrollbar): pass
    class LabelFrame(MockTk.LabelFrame): pass
    class Notebook(MockTk.Frame): pass
    class Scale(MockTk.Scale): pass
    class Progressbar(MockTk.Canvas): pass
    class Treeview(MockTk.Widget): pass

class MockMessagebox:
    """ Mock tkinter.messagebox module """
    @staticmethod
    def showinfo(title, message): pass
    @staticmethod
    def showerror(title, message): pass
    @staticmethod
    def showwarning(title, message): pass
    @staticmethod
    def askyesno(title, message): return False
    @staticmethod
    def askokcancel(title, message): return False

# Mock myNotebook module
class MockNotebook:
    """ Mock myNotebook (nb) module """
    class Frame:
        def __init__(self, parent=None, **kw): pass
    class Label:
        def __init__(self, parent=None, **kw): pass
    class Button:
        def __init__(self, parent=None, **kw): pass
    class Entry:
        def __init__(self, parent=None, **kw): pass
    class Combobox:
        def __init__(self, parent=None, **kw): pass
    class Checkbutton:
        def __init__(self, parent=None, **kw): pass
    class Radiobutton:
        def __init__(self, parent=None, **kw): pass
    class Scrollbar:
        def __init__(self, parent=None, **kw): pass
    class LabelFrame:
        def __init__(self, parent=None, **kw): pass
    class Notebook:
        def __init__(self, parent=None, **kw): pass
