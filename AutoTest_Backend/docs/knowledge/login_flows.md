# Login Flow Patterns / 登录流程模式

Keywords: login, 登录, 登陆, username, password, dashboard, admin, /login, vue-admin-template, name: admin.

For login flows, wait until the username and password inputs are visible, clear them, enter credentials, click the login button, and then assert a stable post-login anchor. Do not treat a successful click as a successful login.

对于中文登录 prompt，应把“登录”“输入用户名和密码”“验证进入 Dashboard”映射为完整登录流程：打开 `/login`，等待用户名和密码输入框可见，输入 `admin` 和 `111111`，点击 `Login`，再验证登录后的稳定锚点。

For vue-admin-template, reliable post-login anchors include the `/dashboard` route, the `Dashboard` sidebar/breadcrumb text, and the visible dashboard content `name: admin`.
