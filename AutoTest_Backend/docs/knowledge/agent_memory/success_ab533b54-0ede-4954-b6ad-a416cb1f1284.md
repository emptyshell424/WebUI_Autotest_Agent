# Success Pattern: 打开 http://127.0.0.1:9528/login，填写用户名 admin、密码 111111，提交后验证页面中出现 Dashboard。

Keywords: agent_memory, self-heal, healed_completed, first_success, http://127.0.0.1:9528/login, 填写用户名, admin, 111111, 提交后验证页面中出现, Dashboard, CSS_SELECTOR=input, name=, CSS_SELECTOR=button.el-button--primary, XPATH=//, contains, url=http://127.0.0.1:9528/login.

## 场景
打开 http://127.0.0.1:9528/login，填写用户名 admin、密码 111111，提交后验证页面中出现 Dashboard。

## 成功策略
首次执行即通过，以下脚本和选择器经验证稳定。

## 稳定选择器
- CSS_SELECTOR=input[name=
- CSS_SELECTOR=button.el-button--primary
- XPATH=//*[contains(.,
- url=http://127.0.0.1:9528/login

## 执行元数据
- execution_id: `ab533b54-0ede-4954-b6ad-a416cb1f1284`
- card_type: `success`
