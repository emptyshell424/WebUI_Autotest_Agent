# Vue Admin Template Selector Reference / 选择器速查表

Keywords: vue-admin-template, selector, 选择器, element plus, el-input, el-button, el-table, el-dialog, sidebar, navbar, dashboard.

This document provides working CSS and XPath selectors for the vue-admin-template target application. Use these as reference when generating or repairing Selenium scripts — they are verified against the actual rendered DOM.

---

## Login Page (`/login`)

| Element | Working Selector | Notes |
|---------|-----------------|-------|
| Username input | `By.NAME, "username"` | Simplest and most reliable |
| Username input (alt) | `By.CSS_SELECTOR, "input[name='username']"` | CSS alternative |
| Password input | `By.NAME, "password"` | Simplest and most reliable |
| Password input (alt) | `By.CSS_SELECTOR, "input[name='password']"` | CSS alternative |
| Login button | `By.CSS_SELECTOR, "button.el-button--primary"` | Element UI primary button |
| Login button (alt) | `By.XPATH, "//button[contains(@class,'el-button--primary')]"` | XPath alternative |
| Login button (alt2) | `By.XPATH, "//span[text()='Login']/parent::button"` | By visible text |

### Avoid these broken selectors on the login page:

- `button[type='submit']` — Element UI renders `type="button"`
- `button:contains('Login')` — jQuery-only, not valid CSS
- `//button[contains(text(),'Login')]` — Text inside `<span>` child, use `.` not `text()`

---

## Dashboard (`/dashboard`)

| Element | Working Selector |
|---------|-----------------|
| Dashboard heading | `By.XPATH, "//*[contains(.,'Dashboard')]"` |
| User info ("name: Super Admin") | `By.XPATH, "//*[contains(.,'Super Admin')]"` |
| Sidebar container | `By.CSS_SELECTOR, ".sidebar-container"` |
| Navbar | `By.CSS_SELECTOR, ".navbar"` |

---

## Sidebar Navigation

| Element | Working Selector |
|---------|-----------------|
| Sidebar menu items | `By.CSS_SELECTOR, ".el-menu-item"` |
| Sidebar submenu | `By.CSS_SELECTOR, ".el-submenu"` |
| Menu item by text | `By.XPATH, "//li[contains(@class,'el-menu-item')]//span[text()='Form']"` |

---

## Element UI Table (`<el-table>`)

Element UI tables render with these CSS classes:

| Element | Working Selector |
|---------|-----------------|
| Table container | `By.CSS_SELECTOR, ".el-table"` |
| Table header | `By.CSS_SELECTOR, ".el-table__header"` |
| Table header row | `By.CSS_SELECTOR, ".el-table__header-wrapper thead tr"` |
| Table body | `By.CSS_SELECTOR, ".el-table__body"` |
| Table body rows | `By.CSS_SELECTOR, ".el-table__body-wrapper tbody tr"` |
| Specific column cells | `By.CSS_SELECTOR, ".el-table__body-wrapper tbody td:nth-child(N)"` |
| Header column by text | `By.XPATH, "//th[contains(@class,'el-table')]//div[contains(.,'Title')]"` |

---

## Element UI Form (`<el-form>`)

| Element | Working Selector |
|---------|-----------------|
| el-input inner | `By.CSS_SELECTOR, "input.el-input__inner"` |
| el-input by name | `By.CSS_SELECTOR, "input[name='FIELD_NAME']"` |
| el-select | `By.CSS_SELECTOR, ".el-select"` |
| el-date-picker | `By.CSS_SELECTOR, ".el-date-editor input"` |
| Form submit button | `By.CSS_SELECTOR, ".el-form button.el-button--primary"` |

---

## Element UI Dialog (`<el-dialog>`)

| Element | Working Selector |
|---------|-----------------|
| Dialog wrapper (visible) | `By.CSS_SELECTOR, ".el-dialog:not([style*='display: none'])"` |
| Dialog title | `By.CSS_SELECTOR, ".el-dialog__title"` |
| Dialog close button | `By.CSS_SELECTOR, ".el-dialog__headerbtn"` |
| Dialog confirm button | `By.XPATH, "//div[contains(@class,'el-dialog')]//button[contains(@class,'el-button--primary')]"` |

---

## General Element UI Patterns

- `<el-button>` renders as `<button type="button" class="el-button ...">`
- `<el-input>` renders as `<div class="el-input"><input class="el-input__inner" ...></div>`
- `<el-select>` renders as `<div class="el-select"><div class="el-select__tags">...`
- Use `EC.visibility_of_element_located` or `EC.element_to_be_clickable` — NOT `EC.presence_of_element_located` — for Element UI components that have CSS transitions
- Always use `WebDriverWait` with timeout >= 10 seconds for Element UI pages (they have JavaScript rendering delays)
