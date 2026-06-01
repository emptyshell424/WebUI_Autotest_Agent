# Success Pattern: Open http://localhost:9528/login, wait for the Login Form, submit admin credentials, and check th...

Keywords: agent_memory, self-heal, healed_completed, first_success, http://localhost:9528/login, Login, Form, submit, admin, credentials, check, dashboard, text, appears, login., CSS_SELECTOR=input, name=, CSS_SELECTOR=button.el-button--primary, XPATH=//, contains, url=http://localhost:9528/login.

## 场景
Open http://localhost:9528/login, wait for the Login Form, submit admin credentials, and check that the dashboard text appears after login.

## 成功策略
首次执行即通过，以下脚本和选择器经验证稳定。

## 稳定选择器
- CSS_SELECTOR=input[name=
- CSS_SELECTOR=button.el-button--primary
- XPATH=//*[contains(.,
- url=http://localhost:9528/login

## 执行元数据
- execution_id: `d09f7cf5-adeb-4165-9d37-7c195c5a53a9`
- card_type: `success`
