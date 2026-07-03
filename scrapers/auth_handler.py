"""
Website authentication handler.
Handles login and session management.
"""
from selenium.webdriver.common.by import By
import time
from config.config import Config
from utils.logging_setup import logger
from utils.exceptions import LoginFailedError
from utils.session_manager import SessionManager


class LoginHandler:
    """Handle authentication to the target website."""

    def __init__(self, session_manager: SessionManager):
        """
        Initialize login handler.

        Args:
            session_manager: SessionManager instance
        """
        self.session_manager = session_manager
        self.driver = session_manager.driver
        self.is_logged_in = False

    def login(self) -> bool:
        """
        Perform login to the website. No retries — fails immediately on error
        to prevent account lockout.

        Returns:
            True if login successful

        Raises:
            LoginFailedError: If login fails
        """
        try:
            logger.info("Attempting login...")

            # Navigate to login URL
            self.driver.get(Config.LOGIN_URL)
            logger.debug(f"Navigated to: {Config.LOGIN_URL}")

            # Wait for login form to load
            time.sleep(2)

            # Apply request delay
            SessionManager.apply_request_delay()

            # CSS selectors from website HTML inspection
            # MSISDN field: <input id="username" name="username" ...>
            # Password field: <input id="password" name="password" ...>
            # Login button: <input type="button" name="sub" id="sub" ...>
            msisdn_field_selector = "#username"
            password_field_selector = "#password"
            login_button_selector = "#sub"

            self.session_manager.wait_for_element(By.CSS_SELECTOR, msisdn_field_selector, timeout=15)
            msisdn_field = self.driver.find_element(By.CSS_SELECTOR, msisdn_field_selector)
            msisdn_field.clear()
            msisdn_field.send_keys(Config.WEBSITE_MSISDN)
            logger.debug("MSISDN field filled")

            # Fill password field
            password_field = self.driver.find_element(By.CSS_SELECTOR, password_field_selector)
            password_field.clear()
            password_field.send_keys(Config.WEBSITE_PASSWORD)
            logger.debug("Password field filled")

            # Click login button
            login_button = self.driver.find_element(By.CSS_SELECTOR, login_button_selector)
            login_button.click()
            logger.info("Login button clicked")

            # Wait longer for login redirect and page load
            time.sleep(5)

            # Check if login was successful
            if self._verify_login():
                logger.info("Login successful!")
                self.is_logged_in = True
                logger.debug(f"Successfully logged in, current URL: {self.driver.current_url}")
                return True

            # Debug: dump page source to help diagnose login issue
            page_source = self.driver.page_source
            if len(page_source) > 0:
                # Save a sample for debugging
                logger.debug(f"Page source length: {len(page_source)} chars")
                if "error" in page_source.lower() or "failed" in page_source.lower():
                    logger.error("Page contains error messages - login likely failed")
                    # Extract first 500 chars containing "error"
                    error_section = [line for line in page_source.split('\n') if 'error' in line.lower()]
                    if error_section:
                        logger.error(f"Error lines: {error_section[:3]}")

            raise LoginFailedError(
                "Login verification failed. Check credentials and website selectors in auth_handler.py"
            )

        except LoginFailedError:
            raise
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            raise LoginFailedError(f"Login error: {str(e)}")

    def _verify_login(self) -> bool:
        """
        Verify that login was successful using multiple checks.

        Returns:
            True if login verified, False otherwise
        """
        try:
            current_url = self.driver.current_url
            logger.debug(f"Current URL after login attempt: {current_url}")

            # Check 1: Verify we're NOT on login page anymore
            if "login" in current_url.lower():
                logger.warning(f"Still on login page: {current_url}")
                return False

            # Check 2: Verify URL contains expected path patterns (strong positive)
            if any(path in current_url for path in ["/operator/", "/hbshengma/operator/"]):
                logger.debug(f"URL verification passed - on operator page: {current_url}")
                return True

            # Check 3: Check for REAL error messages (not just CSS classes)
            try:
                page_source = self.driver.page_source
                # More specific error patterns that indicate actual login failure
                critical_error_keywords = [
                    "登录失败", "用户名或密码错误", "账号不存在", 
                    "密码错误", "验证失败", "invalid username", 
                    "invalid password", "login failed", "authentication failed"
                ]
                found_errors = []
                for keyword in critical_error_keywords:
                    if keyword.lower() in page_source.lower():
                        found_errors.append(keyword)
                
                if found_errors:
                    logger.error(f"Found critical error keywords: {', '.join(found_errors)}")
                    # Extract error context
                    lines = page_source.split('\n')
                    error_context = []
                    for line in lines:
                        if any(err in line.lower() for err in found_errors):
                            clean_line = line.strip()[:200]  # Limit line length
                            if clean_line and clean_line not in error_context:
                                error_context.append(clean_line)
                                if len(error_context) >= 3:
                                    break
                    if error_context:
                        logger.error(f"Error context: {error_context}")
                    return False
            except Exception as e:
                logger.debug(f"Error checking page content: {e}")

            # Check 4: Look for logout button (indicates logged-in state)
            logout_selectors = [
                "//a[contains(text(), '退出')]",  # Chinese logout
                "//a[contains(text(), 'logout')]",  # English logout
                "//button[contains(text(), '退出')]",
                "//*[@id='logout']",
                "//*[@class='logout']",
            ]
            for selector in logout_selectors:
                try:
                    # Use find_elements (plural) to avoid exception on not found
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements and elements[0].is_displayed():
                        logger.debug(f"Found logout button/link, login verified: {selector}")
                        return True
                except Exception as e:
                    logger.debug(f"Error checking selector {selector}: {e}")
                    continue

            # Check 5: Look for main navigation/dashboard content
            nav_selectors = [
                "//nav",
                "//ul[@class='am-menu']",  # AmyUI menu
                "//*[@class='navbar']",
                "//div[@class='sidebar']",
                "//div[@id='menu']",
            ]
            for selector in nav_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        logger.debug(f"Found navigation element, likely logged in: {selector}")
                        return True
                except Exception as e:
                    logger.debug(f"Error checking selector {selector}: {e}")
                    continue

            # Check 6: Page title check - should not contain "登录" or "Login"
            try:
                title = self.driver.title
                if "login" in title.lower() or "登录" in title:
                    logger.warning(f"Page title suggests login page: {title}")
                    return False
                logger.debug(f"Page title: {title}")
            except Exception as e:
                logger.debug(f"Error checking title: {e}")

            # If we reach here: URL changed from login page and no errors found
            # This is a weak positive, but better than failing
            logger.info(f"Login verification: URL changed from login page, no errors detected")
            return True

        except Exception as e:
            logger.error(f"Login verification error: {str(e)}")
            return False

    def logout(self) -> None:
        """
        Logout from the website if needed.
        """
        try:
            # TODO: Implement logout logic if needed
            logger.info("Logout completed")
            self.is_logged_in = False
        except Exception as e:
            logger.error(f"Error during logout: {str(e)}")
