# tee_logger.py
import os
import sys
import datetime

class _TeeStream:
    def __init__(self, stream_a, stream_b):
        self.a = stream_a
        self.b = stream_b

    def write(self, data):
        # tulis ke terminal
        try:
            self.a.write(data)
        except Exception:
            pass
        # tulis ke file
        try:
            self.b.write(data)
        except Exception:
            pass

    def flush(self):
        try:
            self.a.flush()
        except Exception:
            pass
        try:
            self.b.flush()
        except Exception:
            pass

class Tee:
    """
    Context manager untuk menduplikasi stdout & stderr ke file log,
    tanpa mengubah kode print() yang sudah ada.
    Pemakaian:
        with Tee("/path/to/logfile.log"):
            ... jalankan apa saja ...
    """
    def __init__(self, log_path, mode="a", ensure_dir=True):
        self.log_path = log_path
        self.mode = mode
        self.ensure_dir = ensure_dir
        self._log_file = None
        self._old_out = None
        self._old_err = None

    def __enter__(self):
        if self.ensure_dir:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        self._log_file = open(self.log_path, self.mode, buffering=1, encoding="utf-8")
        # tulis header kecil
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._log_file.write(f"\n===== LOG START {ts} =====\n")
        self._log_file.flush()
        # simpan stream lama
        self._old_out = sys.stdout
        self._old_err = sys.stderr
        # ganti ke tee
        sys.stdout = _TeeStream(sys.stdout, self._log_file)
        sys.stderr = _TeeStream(sys.stderr, self._log_file)
        return self

    def __exit__(self, exc_type, exc, tb):
        # kembalikan stream awal
        if self._old_out is not None:
            sys.stdout = self._old_out
        if self._old_err is not None:
            sys.stderr = self._old_err
        if self._log_file:
            self._log_file.flush()
            self._log_file.close()
