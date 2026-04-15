# Login Flow Patterns / 登录流程模式

Keywords: login, 登录, username, password, dashboard, admin, /login.

Wait for the username and password inputs, complete the login action, and assert a stable post-login anchor such as dashboard text, a visible user label, or a URL change.

应等待用户名和密码输入框可见，完成登录操作，并断言登录后的稳定锚点，例如 dashboard 文本、可见的用户标识或 URL 变化。

For vue-admin-template style pages, `name: admin` is a reliable post-login anchor.