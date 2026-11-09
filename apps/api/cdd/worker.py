"""Worker independiente para procesos prolongados: python -m cdd.worker"""
from __future__ import annotations

import signal

from .config import get_settings
from .db import close_pool
from .harness.engine import Worker

if __name__ == "__main__":
    w = Worker(get_settings().worker_poll_interval_s)
    signal.signal(signal.SIGTERM, lambda *_: w.stop())
    w.start()
    try:
        while w.is_alive():
            w.join(1)
    except KeyboardInterrupt:
        w.stop()
    close_pool()
