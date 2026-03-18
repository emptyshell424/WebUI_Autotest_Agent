from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

driver = webdriver.Chrome()
driver.maximize_window()

try:
    driver.get("https://www.baidu.com")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    
    search_box = driver.find_element(By.ID, "kw")
    search_box.send_keys("DeepSeek")
    
    search_button = driver.find_element(By.ID, "su")
    search_button.click()
    
    time.sleep(3)
    
except TimeoutException:
    print("页面加载超时")
except NoSuchElementException as e:
    print(f"未找到元素: {e}")
except Exception as e:
    print(f"发生错误: {e}")
finally:
    driver.quit()
    print("Test Completed")