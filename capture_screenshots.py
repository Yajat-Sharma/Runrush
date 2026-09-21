import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By

def main():
    mobile_emulation = { "deviceMetrics": { "width": 390, "height": 844, "pixelRatio": 3.0 } }
    options = webdriver.ChromeOptions()
    options.add_experimental_option("mobileEmulation", mobile_emulation)
    options.add_argument("--headless")
    options.add_argument("--window-size=390,844")

    print("Starting Chrome...")
    driver = webdriver.Chrome(options=options)
    
    driver.get("http://127.0.0.1:5000/test_screenshots")
    time.sleep(2)
    
    try:
        full_meta_card = driver.find_element(By.ID, "runCardDetails-99991")
        driver.execute_script("arguments[0].classList.add('show');", full_meta_card)
        time.sleep(1)
        driver.save_screenshot("C:/Users/Yajat Sharma/.gemini/antigravity/brain/c78d3d6f-4c73-46cc-ab86-e162014c6749/.user_uploaded/full_metadata_390px.png")
        print("Saved full_metadata_390px.png")
    except Exception as e:
        print("Error capturing full metadata:", e)
        
    try:
        sparse_meta_card = driver.find_element(By.ID, "runCardDetails-99992")
        driver.execute_script("arguments[0].classList.add('show');", sparse_meta_card)
        time.sleep(1)
        driver.save_screenshot("C:/Users/Yajat Sharma/.gemini/antigravity/brain/c78d3d6f-4c73-46cc-ab86-e162014c6749/.user_uploaded/sparse_metadata_390px.png")
        print("Saved sparse_metadata_390px.png")
    except Exception as e:
        print("Error capturing sparse metadata:", e)
        
    driver.quit()

if __name__ == "__main__":
    main()
