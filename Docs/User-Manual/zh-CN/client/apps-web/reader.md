# Curator Web Reader 使用手册

> 所需角色：Reader（或更高）· 最后核验：2026-08-11

<!-- manual-section: purpose -->
## 1. 角色用途与前置条件

Reader 用于查看目录和操作信息，不修改数据。获取本设备获准的 Reader Token，
并先阅读[客户端概览](README.md)。

<!-- manual-section: login -->
## 2. 首次连接

在连接设置输入 **Approved device Token**，选择 **Validate and connect**，确认角色为
Reader。Token 待批准、过期或已撤销时，请管理员审核设备；不要借用其他 Token。

<!-- manual-section: workflows -->
## 3. 允许的工作流

1. 在 **Dashboard** 查看向该角色开放的目录/健康摘要。
2. 在 **Albums** 搜索、按日期/元数据筛选、翻页并打开 Album 元数据。这里刻意不提供照片库浏览。
3. 在 **Models**、**Studios**、**Statuses** 查看永久实体及其 Album 摘要。
4. 在 **Operations** 筛选/翻页历史并打开可用证据。
5. 在 **Issues** 与 **Repair Cases** 查看状态和审核上下文。

<!-- manual-section: denials -->
## 4. 预期拒绝与升级请求

Reader 不能保存实体、批量编辑、Import、决定 Issue/Repair，也不能访问管理员工作流。
写入/管理员导航会隐藏，直接请求会返回权限不足。说明工作理由，向管理员申请最小额外角色。

<!-- manual-section: security -->
## 5. 审核与披露边界

Reader 没有执行确认。部分恢复、文件系统、凭据与 AI 管理上下文会刻意隐藏。
摘要未显示时，不要推测或索取原始路径/机密。

<!-- manual-section: troubleshooting -->
## 6. 故障排查与核验清单

- [ ] 连接标识为预期 Reader 设备。
- [ ] 浏览页面可加载，修改/管理员控件保持不可用。
- [ ] 可清除筛选和翻页而不改变数据。
- [ ] 操作被拒绝后申请升级，而非使用他人的 Token 重试。

服务器不可用时，请联系运维人员并参照 [Backend 服务器手册](../../server/apps-backend.md)。
