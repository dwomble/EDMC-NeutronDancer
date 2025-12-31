# Enhanced version of treeview with sortable columns and click callback
# Modified from BGS-Tally
import tkinter as tk
from tkinter import ttk
from functools import partial
from datetime import datetime
import re
from re import Pattern, compile, Match
from utils.dateutil.parser import parse

PAT_HUMAN_READABLE_NUM_OR_PERC:Pattern = compile(r"^(\d*\.?\d*)([KkMmBbTt%]?)$")

class TreeviewPlus(ttk.Treeview):
    def __init__(self, parent:tk.Frame, callback = None, datetime_format = None, *args, **kwargs):
        ttk.Treeview.__init__(self, parent, *args, **kwargs)
        self.callback = callback
        self.datetime_format = datetime_format
        self.bind('<ButtonRelease-1>', self._select_item)

    def heading(self, column, sort_by=None, **kwargs):
        if sort_by and not hasattr(kwargs, 'command'):
            func = getattr(self, f"_sort_by_{sort_by}", None)
            if func:
                kwargs['command'] = partial(func, column, False)

        return super().heading(column, **kwargs)

    def _select_item(self, event):
        clicked_item = self.item(self.focus())
        clicked_column_ref = self.identify_column(event.x)
        if type(clicked_item['values']) is not list: return

        clicked_column = int(clicked_column_ref[1:]) - 1
        if clicked_column < 0: return

        iid:str = self.identify('item', event.x, event.y)

        if self.callback is not None:
            self.callback(clicked_item['values'], clicked_column, self, iid)

    def _sort(self, column, reverse, data_type, callback):
        l = [(self.set(k, column), k) for k in self.get_children('')]
        l.sort(key=lambda t: data_type(t[0]), reverse=reverse)
        for index, (_, k) in enumerate(l):
            self.move(k, '', index)

        self.heading(column, command=partial(callback, column, not reverse))

    def _sort_by_num(self, column, reverse):
        def _str_to_int(string) -> int:
            if not isinstance(string, str) or string.replace(' ', '') == '': return 0
            string = re.sub(r'[, ]', '', string) # Remove commas and spaces.
            match:Match[str]|None = PAT_HUMAN_READABLE_NUM_OR_PERC.match(string)

            if match:
                num:float = float(match.group(1))
                multiplier:int = {'%': 0.01, '': 1, 'k': 1000, 'm': 1000000, 'b': 1000000000, 't': 1000000000000}[match.group(2).lower()]
                return int(num * multiplier)
            return int(string)

        self._sort(column, reverse, _str_to_int, self._sort_by_num)

    def _sort_by_name(self, column, reverse):
        self._sort(column, reverse, str, self._sort_by_name)

    def _sort_by_datetime(self, column, reverse):
        def _str_to_datetime(string):
            if self.datetime_format is None:
                return parse(string)
            return datetime.strptime(string, self.datetime_format)

        self._sort(column, reverse, _str_to_datetime, self._sort_by_datetime)
