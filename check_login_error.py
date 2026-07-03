#!/usr/bin/env python3
"""
Script sederhana untuk cek error message login
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from config.config import Config
from utils.session_manager import SessionManager

session_manager = SessionManager()
driver = session_manager.initialize_driver()

try:
    # Go to login page
    print(f"Opening: {Config.LOGIN_URL}")
    driver.get(Config.LOGIN_URL)
    time.sleep(3)
    
    # Fill form
    print(f"Filling username: {Config.WEBSITE_MSISDN[:4]}****")
    driver.find_element(By.ID, "username").send_keys(Config.WEBSITE_MSISDN)
    
    print(f"Filling password: ****")
    driver.find_element(By.ID, "password").send_keys(Config.WEBSITE_PASSWORD)
    
    # Click login
    print("Clicking login...")
    driver.find_element(By.ID, "sub").click()
    time.sleep(5)
    
    # Check result
    current_url = driver.current_url
    print(f"\nCurrent URL: {current_url}")
    
    # Check for error field
    try:
        error_field = driver.find_element(By.ID, "error")
        error_value = error_field.get_attribute("value")
        if error_value:
            print(f"\n❌ ERROR FROM WEBSITE: {error_value}")
        else:
            print("\n✅ No error in #error field")
    except:
        print("\n⚠️  No #error field found")
    
    # Check if still on login page
    if "login" in current_url.lower():
        print("\n❌ STILL ON LOGIN PAGE - LOGIN FAILED")
        
        # Try to find any alert/error message
        page_source = driver.page_source
        if "alert(" in page_source:
            print("\nFound alert() in page source - extracting...")
            lines = [l.strip() for l in page_source.split('\n') if 'alert(' in l]
            for line in lines[:5]:
                print(f"  {line}")
    else:
        print("\n✅ LOGIN SUCCESS - Redirected to:", current_url)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    print("\nClosing browser in 5 seconds...")
    time.sleep(5)
    session_manager.quit_driver()
