import os
from pathlib import Path
import sys
import tempfile
import threading

if sys.platform == "win32":
    import msvcrt
    OPEN_MODE = os.O_RDWR | os.O_CREAT | os.O_TRUNC
else:
    import fcntl
    NON_BLOCKING = fcntl.LOCK_EX | fcntl.LOCK_NB
    BLOCKING = fcntl.LOCK_EX

_locks = {}
_base_lock = threading.Lock()


def get_process_lock(lock_id):
    with _base_lock:
        if lock_id not in _locks:
            if sys.platform == "win32":
                _locks[lock_id] = WindowsLock(lock_id)
            else:
                _locks[lock_id] = UnixLock(lock_id)
        return _locks[lock_id]


class _ProcessLock:

    def __init__(self, lock_id):
        self._lock = threading.Lock()
        self._lock_path = Path(tempfile.gettempdir()).joinpath(f'.solcx-lock-{lock_id}')
        self._lock_file = self._lock_path.open('w')

    def wait(self):
        self.acquire(True)
        self.release()


class UnixLock(_ProcessLock):

    def acquire(self, blocking):
        if not self._lock.acquire(blocking):
            return False
        try:
            fcntl.flock(self._lock_file, BLOCKING if blocking else NON_BLOCKING)
        except BlockingIOError:
            return False
        return True

    def release(self):
        fcntl.flock(self._lock_file, fcntl.LOCK_UN)
        self._lock.release()


class WindowsLock(_ProcessLock):

    def acquire(self, blocking):
        fd = os.open(self._lock_path, OPEN_MODE)
        if not self._lock.acquire(blocking):
            return False
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                if not blocking:
                    return False

    def release(self):
        fd = os.open(self._lock_path, OPEN_MODE)
        msvcrt.locking(fd, msvcrt.LK_UNLCK)
        self._lock.release()
