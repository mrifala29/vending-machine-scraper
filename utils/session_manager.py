"""
Selenium WebDriver session management.
Handles browser initialization, cleanup, and request delays.
"""
import time
import random
import os
import shutil
import stat
import psutil
import subprocess
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
import undetected_chromedriver as uc
from webdriver_manager.firefox import GeckoDriverManager
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from config.config import Config
from utils.logging_setup import logger
from utils.exceptions import NetworkError


class SessionManager:
    """Manage Selenium WebDriver lifecycle and request behavior."""

    def __init__(self):
        """Initialize session manager."""
        self.driver = None
        self.wait = None
        self.driver_process_id = None

    def initialize_driver(self) -> WebDriver:
        """
        Initialize and return Selenium WebDriver.
        
        IMPORTANT: This method is stateless - safe to call multiple times.
        Each call creates fresh ChromeOptions. Any previous failed attempt
        is cleaned up automatically.

        Returns:
            Initialized WebDriver instance

        Raises:
            NetworkError: If driver initialization fails
        """
        try:
            # Kill any leftover Chrome/chromedriver from a previous run
            self._cleanup_orphan_chrome_processes()

            # Pastikan DBUS_SESSION_BUS_ADDRESS di-set ke /dev/null.
            # Tanpa ini Chrome bisa hang 60+ detik mencoba connect ke D-Bus
            # session bus yang tidak ada di cron/headless environment.
            if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
                os.environ["DBUS_SESSION_BUS_ADDRESS"] = "/dev/null"
                logger.debug("Set DBUS_SESSION_BUS_ADDRESS=/dev/null (no session bus detected)")

            if Config.BROWSER_TYPE == "chrome":
                chrome_version = self._detect_chrome_version()
                logger.info(f"Detected Chrome major version: {chrome_version}")

                # Uji Chrome binary secara langsung — jika gagal di sini berarti
                # masalah ada di Chrome binary/library, bukan di UC/ChromeDriver.
                self._test_chrome_direct()

                options = self._build_chrome_options()

                # Simpan log ChromeDriver ke file untuk keperluan diagnosis.
                chdr_log = f"/tmp/chromedriver_{os.getpid()}.log"
                try:
                    # ChromeService tidak selalu ada di semua versi UC — fallback ke init biasa
                    try:
                        service = uc.ChromeService(log_path=chdr_log)
                        logger.info(f"Initializing undetected ChromeDriver (log: {chdr_log})")
                        self.driver = uc.Chrome(options=options, version_main=chrome_version, service=service)
                    except AttributeError:
                        logger.info("Initializing undetected ChromeDriver")
                        self.driver = uc.Chrome(options=options, version_main=chrome_version)
                except Exception:
                    self._dump_log_file(chdr_log, "ChromeDriver")
                    raise

                # Capture driver process ID for cleanup tracking
                try:
                    self.driver_process_id = self.driver.service.process.pid
                    logger.info(f"Chrome process ID: {self.driver_process_id}")
                except Exception:
                    pass

            elif Config.BROWSER_TYPE == "firefox":
                options = FirefoxOptions()
                if Config.HEADLESS_MODE:
                    options.add_argument("--headless")
                options.add_argument(f"user-agent={Config.USER_AGENT}")
                
                geckodriver_path = shutil.which("geckodriver")
                if geckodriver_path:
                    logger.info(f"Using system GeckoDriver: {geckodriver_path}")
                    service = FirefoxService(geckodriver_path)
                else:
                    logger.info("System GeckoDriver not found, using webdriver-manager")
                    driver_path = GeckoDriverManager().install()
                    os.chmod(driver_path, stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
                    service = FirefoxService(driver_path)
                
                self.driver = webdriver.Firefox(service=service, options=options)
                
                # Capture driver process ID for cleanup tracking
                try:
                    self.driver_process_id = self.driver.service.process.pid
                    logger.info(f"Firefox process ID: {self.driver_process_id}")
                except Exception:
                    pass

            else:
                raise ValueError(f"Unsupported browser type: {Config.BROWSER_TYPE}")

            # Set implicit wait
            self.driver.implicitly_wait(Config.REQUEST_TIMEOUT)
            self.wait = WebDriverWait(self.driver, Config.REQUEST_TIMEOUT)

            logger.info(f"WebDriver initialized successfully ({Config.BROWSER_TYPE})")
            return self.driver

        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {str(e)}")
            logger.error("Tip: sudo apt-get install -y xvfb libxrender1 libxrandr2")
            
            # Force cleanup any lingering processes before raising
            try:
                self._force_cleanup_processes()
            except Exception as cleanup_error:
                logger.debug(f"Cleanup during exception: {cleanup_error}")
            
            time.sleep(3)
            raise NetworkError(f"WebDriver initialization failed: {str(e)}")

    def quit_driver(self) -> None:
        """
        Close and quit the WebDriver with aggressive cleanup for headless servers.
        Handles stuck processes and ensures full resource release.
        """
        if not self.driver:
            return
        
        try:
            # Step 1: Graceful quit with timeout
            logger.info("Closing WebDriver connections...")
            self.driver.quit()
            # Longer wait for graceful cleanup on headless servers
            time.sleep(1.0)
            logger.info("WebDriver quit successfully")
            
        except Exception as e:
            logger.warning(f"Error during graceful quit: {str(e)}")
        
        finally:
            # Step 2: Force kill lingering processes (zombie cleanup)
            try:
                self._force_cleanup_processes()
            except Exception as cleanup_error:
                logger.error(f"Error during process cleanup: {cleanup_error}")
            
            self.driver = None
            self.wait = None

    def _force_cleanup_processes(self) -> None:
        """
        Force terminate lingering browser processes.
        Essential for headless servers where zombie processes accumulate.
        
        This runs AFTER quit_driver() fails to close cleanly, so it's a last resort
        to ensure resources are freed before next Chrome spawn attempt.
        """
        if not self.driver_process_id:
            return
        
        logger.debug(f"Starting aggressive process cleanup for driver PID {self.driver_process_id}")
        
        try:
            # Try to get parent process
            try:
                parent = psutil.Process(self.driver_process_id)
                logger.debug(f"Found parent process: {parent.pid} ({parent.name()})")
                
                # Get all children (Chrome spawns multiple processes)
                children = parent.children(recursive=True)
                logger.debug(f"Found {len(children)} child processes to cleanup")
                
                if parent.is_running():
                    logger.warning(f"Parent Chrome process {self.driver_process_id} still running, terminating...")
                    parent.terminate()
                    # Longer wait for graceful termination on headless servers
                    time.sleep(1.0)
                    
                    if parent.is_running():
                        logger.warning(f"Parent did not terminate gracefully, force killing {self.driver_process_id}")
                        parent.kill()
                        time.sleep(0.5)
                
                # Kill any child processes (Chrome spawns renderer, GPU, etc.)
                for child in children:
                    try:
                        if child.is_running():
                            logger.debug(f"Terminating child Chrome process {child.pid}")
                            child.terminate()
                            time.sleep(0.2)
                            if child.is_running():
                                logger.debug(f"Child {child.pid} did not terminate, killing...")
                                child.kill()
                                time.sleep(0.1)
                    except psutil.NoSuchProcess:
                        pass  # Already dead
                    except Exception as e:
                        logger.debug(f"Could not kill child process {child.pid}: {e}")
                
                logger.debug(f"Process cleanup complete for {self.driver_process_id}")
                        
            except psutil.NoSuchProcess:
                logger.debug(f"Driver process {self.driver_process_id} already terminated (not found)")
            except Exception as e:
                logger.debug(f"Could not access driver process details: {e}")
        
        except Exception as e:
            logger.error(f"Force cleanup encountered error: {e}")

    def _detect_chrome_version(self) -> int | None:
        """Return Chrome major version as int, or None if detection fails."""
        candidates = ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]
        for binary in candidates:
            try:
                out = subprocess.check_output(
                    [binary, "--version"], stderr=subprocess.DEVNULL, timeout=5
                ).decode()
                # e.g. "Google Chrome 124.0.6367.91" or "Chromium 124.0.6367.91"
                parts = out.strip().split()
                for part in parts:
                    if part[0].isdigit():
                        major = int(part.split(".")[0])
                        return major
            except Exception:
                continue
        logger.warning("Could not detect Chrome version; passing version_main=None")
        return None

    def _test_chrome_direct(self) -> None:
        """Jalankan Chrome binary langsung dan log hasilnya. Mendeteksi masalah library/permission."""
        chrome_bins = ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]
        for binary in chrome_bins:
            if not shutil.which(binary):
                continue
            try:
                result = subprocess.run(
                    [binary, "--headless=new", "--no-sandbox", "--disable-gpu",
                     "--disable-dev-shm-usage", "--dump-dom", "about:blank"],
                    capture_output=True, text=True, timeout=20,
                )
                if result.returncode == 0:
                    logger.info(f"Chrome direct test PASSED ({binary})")
                else:
                    logger.error(f"Chrome direct test FAILED exit={result.returncode} ({binary})")
                    if result.stderr:
                        logger.error(f"Chrome stderr:\n{result.stderr[-2000:]}")
            except subprocess.TimeoutExpired:
                logger.error(f"Chrome direct test TIMEOUT — Chrome tidak mau start ({binary})")
            except Exception as exc:
                logger.error(f"Chrome direct test error: {exc}")
            return  # hanya test binary pertama yang ditemukan

    def _dump_log_file(self, path: str, label: str) -> None:
        """Baca file log dan cetak isinya ke application log."""
        try:
            if os.path.exists(path):
                with open(path, "r", errors="replace") as f:
                    content = f.read()
                if content.strip():
                    logger.error(f"--- {label} log ({path}) ---\n{content[-3000:]}")
                os.unlink(path)
        except Exception as exc:
            logger.debug(f"Could not read {label} log: {exc}")

    def _build_chrome_options(self) -> uc.ChromeOptions:
        """Build a fresh ChromeOptions with all required flags for headless Linux."""
        options = uc.ChromeOptions()
        # Gunakan --headless=new hanya jika tidak ada DISPLAY (tidak ada virtual/real display).
        # Saat dijalankan via xvfb-run, DISPLAY sudah di-set ke virtual display.
        # Flag --headless=new akan override DISPLAY dan menyebabkan Chrome crash di UC.
        if Config.HEADLESS_MODE and not os.environ.get("DISPLAY"):
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-crash-reporter")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-hang-monitor")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-prompt-on-repost")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-breakpad")
        options.add_argument("--disable-component-update")
        options.add_argument("--window-size=1920,1080")
        # Mencegah Chrome connect ke D-Bus/keyring/kwallet yang tidak ada di cron.
        # Tanpa ini Chrome bisa hang menunggu session bus sebelum crash.
        options.add_argument("--password-store=basic")
        options.add_argument("--disable-features=SystemNotifications")
        options.add_argument(f"user-agent={Config.USER_AGENT}")
        return options

    def _cleanup_orphan_chrome_processes(self) -> None:
        """
        Kill any orphan Chrome/Chromium/chromedriver processes and clear stale
        undetected_chromedriver temp files before a new spawn attempt.
        """
        import glob
        killed = 0
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if any(k in name for k in ("chrome", "chromium", "chromedriver")):
                    proc.kill()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed:
            logger.info(f"Cleaned up {killed} orphan Chrome/chromedriver process(es)")

        # Clear stale uc temp dirs/files so next spawn starts clean
        stale_patterns = [
            "/tmp/.com.google.Chrome*",
            "/tmp/undetected_chromedriver*",
            "/tmp/.org.chromium*",
        ]
        for pattern in stale_patterns:
            for path in glob.glob(pattern):
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        os.remove(path)
                except Exception:
                    pass

        if killed:
            time.sleep(2)  # Allow OS to release ports/file descriptors

        # Clear undetected_chromedriver binary cache so it re-patches on next run.
        # A stale/incompatible patched binary is the most common cause of
        # "cannot connect to chrome" on repeated runs.
        uc_cache_dirs = [
            os.path.expanduser("~/.local/share/undetected_chromedriver"),
            os.path.expanduser("~/.cache/undetected_chromedriver"),
            "/tmp/undetected_chromedriver",
        ]
        for d in uc_cache_dirs:
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
                logger.debug(f"Cleared uc cache: {d}")

    @staticmethod
    def apply_request_delay() -> None:
        """Apply random delay between requests to avoid rate limiting."""
        delay = random.uniform(Config.MIN_REQUEST_DELAY, Config.MAX_REQUEST_DELAY)
        logger.debug(f"Applying request delay: {delay:.2f} seconds")
        time.sleep(delay)

    def wait_for_element(self, by: By, value: str, timeout: Optional[int] = None) -> None:
        """
        Wait for element to be present in DOM.

        Args:
            by: Selenium By locator type
            value: Locator value
            timeout: Custom timeout in seconds

        Raises:
            NetworkError: If element is not found within timeout
        """
        if timeout is None:
            timeout = Config.REQUEST_TIMEOUT

        try:
            self.wait.until(
                EC.presence_of_element_located((by, value))
            )
            logger.debug(f"Element found: {by}={value}")
        except Exception as e:
            logger.error(f"Element not found: {by}={value} - {str(e)}")
            raise NetworkError(f"Element not found: {str(e)}")

    def get_page_source(self) -> str:
        """
        Get current page source.

        Returns:
            Page HTML source
        """
        return self.driver.page_source
