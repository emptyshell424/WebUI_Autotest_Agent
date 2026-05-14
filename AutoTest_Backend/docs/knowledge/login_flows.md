# Login Flow Patterns / 登录流程模式

Keywords: login, 登录, 登陆, username, password, dashboard, admin, /login, vue-admin-template, name: admin.

For login flows, wait until the username and password inputs are visible, clear them, enter credentials, click the login button, and then assert a stable post-login anchor. Do not treat a successful click as a successful login.

对于中文登录 prompt，应把"登录""输入用户名和密码""验证进入 Dashboard"映射为完整登录流程：打开 `/login`，等待用户名和密码输入框可见，输入 `admin` 和 `111111`，点击 `Login`，再验证登录后的稳定锚点。

For vue-admin-template, reliable post-login anchors include the `/dashboard` route, the `Dashboard` heading text, and the user info display `name: Super Admin` (note: the display name is "Super Admin", NOT "admin" — "admin" is the login username, "Super Admin" is the displayed role name).

## vue-admin-template Login Page DOM Structure

The login page is at `/login` and uses Element UI (`<el-input>`, `<el-button>`) components.

### Rendered HTML (what Selenium actually sees):

**Username input:**
```html
<input name="username" placeholder="Username" type="text"
       autocomplete="on" class="el-input__inner">
```

**Password input:**
```html
<input name="password" placeholder="Password" type="password"
       autocomplete="on" class="el-input__inner">
```

**Login button** (Element UI `<el-button type="primary">Login</el-button>` renders to):
```html
<button type="button" class="el-button el-button--primary" style="width:100%;">
  <span>Login</span>
</button>
```

### Working Selectors:

- **Username field**: `By.NAME, "username"` or `By.CSS_SELECTOR, "input[name='username']"`
- **Password field**: `By.NAME, "password"` or `By.CSS_SELECTOR, "input[name='password']"`
- **Login button**: `By.CSS_SELECTOR, "button.el-button--primary"` or `By.XPATH, "//button[contains(@class,'el-button--primary')]"` or `By.XPATH, "//span[text()='Login']/parent::button"`

### Selectors That DO NOT WORK:

- `button[type='submit']` — Element UI renders `type="button"`, NOT `type="submit"`
- `button:contains('Login')` — `:contains()` is jQuery syntax, NOT supported by Selenium CSS selector engine. Use XPath `contains(.,'text')` instead.
- `By.XPATH, "//button[contains(text(), 'Login')]"` — Fails because the text "Login" is inside a `<span>` child element. Use `contains(., 'Login')` (dot instead of `text()`).

### Recommended login flow template:

```python
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

driver.get("http://localhost:9528/login")
wait = WebDriverWait(driver, 15)

username = wait.until(EC.visibility_of_element_located((By.NAME, "username")))
username.clear()
username.send_keys("admin")

password = driver.find_element(By.NAME, "password")
password.clear()
password.send_keys("111111")

login_btn = wait.until(EC.element_to_be_clickable(
    (By.CSS_SELECTOR, "button.el-button--primary")))
login_btn.click()

# Verify login success
wait.until(EC.url_contains("/dashboard"))
```
