# Curator Web 访问与设备注册

> 适用角色：Administrator、Writer、Reader · 最后核验：2026-08-12

<!-- manual-section: concepts -->
## 1. 凭据区别

Curator 使用获准的浏览器/设备 Token，而不是用户名密码。Bootstrap Code 只初始化首位管理员；Registration Proof 只允许浏览器提交 Reader/Writer 申请，不授予访问权；Device Token 由申请浏览器生成并保留，Backend 只保存其 hash，并在管理员批准后激活。

<!-- manual-section: bootstrap -->
## 2. 初始化首位管理员

在 Backend 主机运行：

```bash
python3 -m apps.backend auth create-bootstrap-code
```

十分钟内选择 **Initialize administrator**，输入 Code 和设备名称，并安全保存只显示一次的 Admin Token。Bootstrap 不是普通注册或恢复入口。

<!-- manual-section: proof -->
## 3. 生成 Registration Proof

所需角色：Administrator。打开 **Administrator Center → Devices and Tokens → Registration access**，选择 **Generate Registration Proof**，把只显示一次的值复制到可信密码管理器。Rotate 会使旧 Proof 立即失效；Disable 会阻止新申请；两者都不影响已批准 Token。

<!-- manual-section: request -->
## 4. 申请 Reader 或 Writer

在新浏览器配置中：

1. 打开 **Connect → Request device access**。
2. 输入易识别的设备名，选择 Reader 或 Writer，并输入 Registration Proof。
3. 选择 **Request access**。浏览器会在本地生成并安全保留候选 Device Token 和 enrollment capability。
4. 保持 Pending，或关闭窗口后在同一浏览器配置中返回。

整个过程不需要终端、开发者工具、UUID 复制、JSON 或 `curl`。

<!-- manual-section: approval -->
## 5. 批准或拒绝

所需角色：Administrator。在 **Pending registrations** 核对完整设备身份、角色和 scopes，按最小权限批准或拒绝。UI 注册不会在 Admin 浏览器显示 Device Token；批准只激活申请浏览器已经提交的 hash。

<!-- manual-section: connection -->
## 6. 完成连接

回到申请浏览器，选择 **Check status**。批准后会校验本地 Token 并自动连接；拒绝或过期绝不会激活 Token。申请期间不要清除站点数据或更换浏览器配置。

<!-- manual-section: lifecycle -->
## 7. 续期、撤销与遗失

过期前在原浏览器请求续期。设备遗失或疑似泄露时，立即在 **Devices and Tokens** 撤销。现有 Token 明文无法找回。**Disconnect** 只清除浏览器连接，不会撤销服务器 Token。

<!-- manual-section: troubleshooting -->
## 8. 故障排查

- Proof 无效：核对当前值；管理员可能已经 Rotate 或 Disable。
- 看不到申请：刷新 **Devices and Tokens**，并确认申请端显示 Pending。
- 浏览器不匹配：回到提交申请的同一浏览器配置。
- `401`：Token 无效、过期、已撤销、已替换或尚未批准。
- `403`：当前角色/scopes 不允许该操作。

<!-- manual-section: checklist -->
## 9. 核验清单

- [ ] Proof 和 Token 未进入截图、日志、聊天或文档。
- [ ] 审批期间没有更换申请浏览器配置。
- [ ] 管理员核对完整身份并批准最小角色/scopes。
- [ ] 申请端以预期角色自动连接。
