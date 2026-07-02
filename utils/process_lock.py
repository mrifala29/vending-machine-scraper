"""
Process-level locking to prevent concurrent scraper execution.
Prevents race conditions between machine.py and main.py jobs.
"""
import os
import time
import atexit
from pathlib import Path
from typing import Optional
from utils.logging_setup import logger


def _is_process_alive(pid: int) -> bool:
    """Check if a process is alive using kill signal 0."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


class ProcessLock:
    """
    File-based lock to prevent concurrent job execution.
    
    Usage:
        lock = ProcessLock("machine_scraper")
        if lock.acquire(timeout=5):
            try:
                do_work()
            finally:
                lock.release()
        else:
            logger.warning("Could not acquire lock within timeout")
    """

    def __init__(self, lock_name: str):
        """
        Initialize lock with unique name.
        
        Args:
            lock_name: Unique identifier for this lock (e.g., "machine_scraper", "sales_scraper")
        """
        self.lock_name = lock_name
        self.lock_dir = Path("logs")
        self.lock_dir.mkdir(exist_ok=True)
        self.lock_file = self.lock_dir / f".{lock_name}.lock"
        self.held = False
        
        # Auto-cleanup on exit
        atexit.register(self.release)

    def acquire(self, timeout: int = 10) -> bool:
        """
        Try to acquire lock within timeout.
        
        Args:
            timeout: Max seconds to wait for lock
            
        Returns:
            True if lock acquired, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Atomic operation: create file only if it doesn't exist
                fd = os.open(
                    str(self.lock_file),
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o644
                )
                with os.fdopen(fd, 'w') as f:
                    f.write(str(os.getpid()))
                
                self.held = True
                logger.info(f"Lock acquired: {self.lock_name} (PID: {os.getpid()})")
                return True
                
            except FileExistsError:
                # Lock is held — check if holder process is still alive
                try:
                    lock_content = self.lock_file.read_text().strip()
                    holder_pid = int(lock_content)
                    
                    if not _is_process_alive(holder_pid):
                        # Stale lock: holder process is dead, steal it
                        logger.warning(
                            f"Stale lock detected for {self.lock_name} "
                            f"(PID {holder_pid} is dead), stealing lock"
                        )
                        self.lock_file.unlink(missing_ok=True)
                        continue  # Retry acquire immediately
                    
                    # Holder is alive — another instance is running
                    elapsed = time.time() - start_time
                    remaining = timeout - elapsed
                    
                    if remaining > 0:
                        wait_time = min(1.0, remaining)
                        logger.debug(f"Waiting for lock {self.lock_name} (retry in {wait_time:.1f}s)")
                        time.sleep(wait_time)
                    else:
                        logger.warning(f"Lock acquire timeout for {self.lock_name}")
                        return False
                        
                except (ValueError, OSError):
                    # Cannot read PID from lock file — treat as stale
                    logger.warning(f"Unreadable lock file for {self.lock_name}, removing stale lock")
                    self.lock_file.unlink(missing_ok=True)
        
        return False

    def release(self) -> None:
        """Release lock (safe to call even if not held)."""
        if not self.held:
            return
        
        try:
            if self.lock_file.exists():
                os.remove(self.lock_file)
            self.held = False
            logger.info(f"Lock released: {self.lock_name}")
        except Exception as e:
            logger.error(f"Error releasing lock {self.lock_name}: {e}")

    def __enter__(self):
        """Context manager entry."""
        if not self.acquire():
            raise RuntimeError(f"Could not acquire lock: {self.lock_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
