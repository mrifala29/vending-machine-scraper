#!/usr/bin/env python3
"""
Debug script to test login manually and capture error messages.
"""
import time
from config.config import Config
from utils.session_manager import SessionManager
from utils.logging_setup import logger

def debug_login():
    """Test login and capture detailed error information."""
    session_manager = SessionManager()
    
    try:
        # Initialize driver
        logger.info("Initializing WebDriver...")
        driver = session_manager.initialize_driver()
        
        # Navigate to login page
        logger.info(f"Navigating to login page: {Config.LOGIN_URL}")
        driver.get(Config.LOGIN_URL)
        time.sleep(3)
        
        # Save screenshot before login
        try:
            driver.save_screenshot("/tmp/login_page_before.png")
            logger.info("Screenshot saved: /tmp/login_page_before.png")
        except Exception as e:
            logger.warning(f"Could not save screenshot: {e}")
        
        # Fill credentials
        logger.info("Filling credentials...")
        username_field = driver.find_element("css selector", "#username")
        username_field.clear()
        username_field.send_keys(Config.WEBSITE_MSISDN)
        logger.info(f"Username filled (length: {len(Config.WEBSITE_MSISDN)})")
        
        password_field = driver.find_element("css selector", "#password")
        password_field.clear()
        password_field.send_keys(Config.WEBSITE_PASSWORD)
        logger.info(f"Password filled (length: {len(Config.WEBSITE_PASSWORD)})")
        
        # Click login
        logger.info("Clicking login button...")
        login_button = driver.find_element("css selector", "#sub")
        login_button.click()
        
        # Wait for response
        logger.info("Waiting for response...")
        time.sleep(5)
        
        # Capture result
        current_url = driver.current_url
        logger.info(f"Current URL after login: {current_url}")
        
        page_title = driver.title
        logger.info(f"Page title: {page_title}")
        
        # Save screenshot after login
        try:
            driver.save_screenshot("/tmp/login_page_after.png")
            logger.info("Screenshot saved: /tmp/login_page_after.png")
        except Exception as e:
            logger.warning(f"Could not save screenshot: {e}")
        
        # Check for error messages
        page_source = driver.page_source
        
        # Look for common error patterns
        error_patterns = [
            "error", "错误", "失败", "invalid", 
            "用户名或密码错误", "账号不存在", "密码错误",
            "登录失败", "验证失败"
        ]
        
        found_errors = []
        for pattern in error_patterns:
            if pattern in page_source.lower():
                found_errors.append(pattern)
        
        if found_errors:
            logger.error(f"Found error patterns: {found_errors}")
            
            # Extract context around errors
            lines = page_source.split('\n')
            for i, line in enumerate(lines):
                if any(err in line.lower() for err in found_errors):
                    # Print context: 2 lines before and after
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    context = lines[start:end]
                    logger.error(f"Error context (lines {start}-{end}):")
                    for ctx_line in context:
                        clean = ctx_line.strip()
                        if clean:
                            logger.error(f"  {clean[:200]}")
        else:
            logger.info("No obvious error patterns found")
        
        # Check for success indicators
        success_patterns = ["退出", "logout", "dashboard", "operator"]
        found_success = []
        for pattern in success_patterns:
            if pattern in page_source.lower():
                found_success.append(pattern)
        
        if found_success:
            logger.info(f"Found success indicators: {found_success}")
            logger.info("✓ Login appears successful!")
        else:
            logger.warning("No success indicators found")
            logger.warning("✗ Login likely failed")
        
        # Save page source for manual inspection
        with open("/tmp/login_page_source.html", "w", encoding="utf-8") as f:
            f.write(page_source)
        logger.info("Page source saved: /tmp/login_page_source.html")
        
        # Keep browser open for manual inspection if needed
        logger.info("Waiting 10 seconds before closing browser...")
        time.sleep(10)
        
    except Exception as e:
        logger.error(f"Debug login failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    finally:
        logger.info("Closing browser...")
        session_manager.quit_driver()
        logger.info("Debug complete")

if __name__ == "__main__":
    debug_login()
