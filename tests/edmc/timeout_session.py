"""
Minimal stub of EDMC's timeout_session.py -- returns a (possibly mocked) requests.Session.
Real timeout enforcement isn't needed here since tests/edmc/requests.py never does real I/O.
"""
from requests import Session

def new_session(timeout: int = 10, session=None):
    return session or Session()
