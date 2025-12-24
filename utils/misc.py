from typing import Any
from functools import reduce
import operator

"""
  Miscellaneous utility functions
"""
def get_by_path(dic:dict[str, Any], keys:list[str], default:Any = None) -> Any:
    """ Return an element from a nested object by item sequence. """
    try:
        return reduce(operator.getitem, keys, dic) or default
    except (KeyError, IndexError, TypeError):
        return default
