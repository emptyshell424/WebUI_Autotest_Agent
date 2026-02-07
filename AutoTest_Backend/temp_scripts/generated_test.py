from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

driver = webdriver.Chrome()
try:
    driver.get("https://www.baidu.com")
    driver.maximize_window()
    
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    
    search_box = wait.until(EC.presence_of_element_located((By.ID, "kw")))
    search_box.send_keys("DeepSeek")
    
    time.sleep(3)
    
    search_button = wait.until(EC.element_to_be_clickable((By.ID, "su")))
    search_button.click()
    
    print(driver.title)
    
except TimeoutException:
    print("Timeout occurred while waiting for an element.")
except NoSuchElementException:
    print("Element not found. Check if the page structure changed or if the element is inside an iframe.")
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    driver.quit()
    print("Test Completed")