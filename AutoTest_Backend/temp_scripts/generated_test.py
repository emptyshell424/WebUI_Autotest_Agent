from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

driver = webdriver.Chrome()
driver.get("https://www.bing.com")
driver.maximize_window()

time.sleep(2)

element = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.ID, "fake_error_button_123"))
)
element.click()

print("Test Completed")