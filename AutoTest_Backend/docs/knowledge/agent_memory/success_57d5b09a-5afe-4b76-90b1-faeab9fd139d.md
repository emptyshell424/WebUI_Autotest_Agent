# Success Pattern: 打开 http://127.0.0.1:9528/login 登录页面，输入用户名 admin 和密码 111111，点击 Login 按钮，并验证页面成功进入 Dashboard 页面。

Keywords: agent_memory, self-heal, healed_completed, first_success, http://127.0.0.1:9528/login, 登录页面, 输入用户名, admin, 和密码, 111111, Login, 并验证页面成功进入, Dashboard, CSS_SELECTOR=input, name=, CSS_SELECTOR=button.el-button--primary, url=http://127.0.0.1:9528/login.

## 场景
打开 http://127.0.0.1:9528/login 登录页面，输入用户名 admin 和密码 111111，点击 Login 按钮，并验证页面成功进入 Dashboard 页面。

## 成功策略
首次执行即通过，以下脚本和选择器经验证稳定。

## 稳定选择器
- CSS_SELECTOR=input[name=
- CSS_SELECTOR=button.el-button--primary
- url=http://127.0.0.1:9528/login

## 执行元数据
- execution_id: `57d5b09a-5afe-4b76-90b1-faeab9fd139d`
- card_type: `success`
