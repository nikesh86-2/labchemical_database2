import os
import atexit

class DBLock:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock_path = db_path + ".lock"
        self.lock_acquired = False

    def acquire(self, override=False):
        """Attempt to acquire the database lock. Returns True if read-only."""
        if os.path.exists(self.lock_path):
            if override:
                print("⚠️ Lock overridden by user.")
                os.remove(self.lock_path)
                self._create_lock()
                return False
            else:
                print("🔒 Lock file exists. Opening DB in read-only mode.")
                return True
        else:
            self._create_lock()
            return False

    def _create_lock(self):
        with open(self.lock_path, "w") as f:
            f.write("LOCKED")
        self.lock_acquired = True
        atexit.register(self.release)
        print("✅ Lock acquired.")

    def release(self):
        """Release the lock file if held."""
        if self.lock_acquired and os.path.exists(self.lock_path):
            os.remove(self.lock_path)
            print("🗑️ Lock released.")
            self.lock_acquired = False