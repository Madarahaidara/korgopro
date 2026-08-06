from collections import defaultdict
from datetime import datetime, timedelta
import threading

class BruteForceProtection:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self.failed_attempts = defaultdict(list)
        self.lockout_durations = {}
        self.max_attempts = 5
        self.lockout_duration = timedelta(minutes=15)
        self._initialized = True

    def is_locked_out(self, username: str) -> bool:
        now = datetime.utcnow()
        if username in self.lockout_durations:
            if now < self.lockout_durations[username]:
                return True
            else:
                del self.lockout_durations[username]
                self.failed_attempts[username] = []
        return False

    def record_failed_attempt(self, username: str):
        now = datetime.utcnow()
        self.failed_attempts[username].append(now)
        if len(self.failed_attempts[username]) >= self.max_attempts:
            self.lockout_durations[username] = now + self.lockout_duration
            return True
        return False

    def record_successful_attempt(self, username: str):
        if username in self.failed_attempts:
            del self.failed_attempts[username]
        if username in self.lockout_durations:
            del self.lockout_durations[username]
