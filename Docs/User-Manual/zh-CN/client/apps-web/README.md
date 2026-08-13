# Curator Web 客户端使用手册

> 支持的应用：`apps.web` · 最后核验：2026-08-11

<!-- manual-section: purpose -->
## 1. 用途与边界

Curator Web 是以 Album 为单位的数字资产管理客户端，用于目录元数据、Import、
操作审核、恢复和 AI 辅助命名。它不是照片浏览或策展应用：这里没有 Album 照片的
通用浏览/删除入口。Digital Asset Trash 当前尚不可用，**Repair Quarantine** 仅用于
临时隔离修复冲突。

<!-- manual-section: connect -->
## 2. 打开与连接

新的 Reader 或 Writer 浏览器应先阅读[访问与设备注册](access-and-registration.md)。正常流程全部在 Web UI 中完成。

1. 向服务器运维人员获取回环 URL，并确认 Backend 正在运行。
2. 使用分配给本设备的浏览器配置打开该 URL。
3. 打开连接设置，输入 **Approved device Token**，选择 **Validate and connect**。
4. 确认显示的角色和导航符合已批准权限。

Token 由管理员在设备注册后签发，属于凭据：不要分享、粘贴到报告，或在不同人员/
设备间复用。**Disconnect** 只删除当前浏览器连接，并不会撤销 Token。

<!-- manual-section: navigation -->
## 3. 导航与共同概念

共同导航包括 **Dashboard**、**Albums**、**Models**、**Studios**、**Statuses**、
**Operations** 与 **Issues**。有写权限的用户还会看到 **Import**。仅管理员可访问
**Repair Quarantine**、**Administrator Center**、**AI Work Dispatch** 和 **AI Review**。

**Album** 是管理单位。**Preview** 计算待审核影响，**Execute** 才会应用变更。
**Operation** 是一次变更尝试的持久证据；**Issue** 记录待审核状况，**Repair Case**
记录建议处理。AI Workspace、Dispatch Group 与 Work Item 将派发、证据、审核和
Promotion 与 Album status 分离。

<!-- manual-section: roles -->
## 4. 角色与能力矩阵

| 工作流 | Reader | Writer | Administrator |
| --- | --- | --- | --- |
| 浏览 Albums/实体/Operations/Issues | 是 | 是 | 是 |
| 编辑 Albums/实体并执行 Import | 否 | 是 | 是 |
| 获准的 Issue/Repair 决策 | 否 | 是 | 是 |
| Token 管理与恢复操作 | 否 | 否 | 是 |
| Quarantine、AI 派发/审核/Promotion | 否 | 否 | 是 |

导航隐藏不代表授权依据；每个请求仍由 Backend 强制校验。参见[访问与设备注册](access-and-registration.md)、[Reader](reader.md)、
[Writer](writer.md) 或 [Administrator](administrator.md) 手册。

<!-- manual-section: feedback -->
## 5. 反馈、取消与重试

- 按钮禁用表示前置条件、选择、确认阅读或确认短语尚未完成。
- Cancel 会关闭当前审核，不会执行。
- 表单校验错误应修正输入；权限错误需要管理员处理，重复提交无效。
- Preview 过期、陈旧或已使用时，返回来源页面重新创建，绝不能复用其 token。
- 结果不确定或部分失败时，重试前查看 **Operations** 和关联 **Issues**；结果页面
  才是依据，按钮动画不是。
- 导航会取消过时的列表刷新；返回页面可请求新数据。
- 实体表单和 AI Review 会在此浏览器配置文件中保存带版本的草稿。刷新或重启会恢复
  兼容草稿；完成后应保存或明确丢弃。Import 同样会恢复批次，并提供
  **Abandon saved Import**。
- 重要审核对话框不会响应 Escape 或遮罩点击，请使用可见的 Cancel 操作。浏览器中断后，
  应按提示重新打开来源操作并生成新 Preview。

<!-- manual-section: safety -->
## 6. 安全与故障排查

无法连接时，在不泄露 Token 的前提下核对 Backend URL 与 Token。权限变更后使用
新签发 Token 重连。`403` 表示当前角色权限不足。数据库 Restore 会刻意清除连接。

破坏性确认前必须复核目标与影响。不要绕过支持的工作流修改数据库或受管文件。
服务器设置与恢复边界见 [Backend 服务器手册](../../server/apps-backend.md)。

<!-- manual-section: checklist -->
## 7. 核验清单

- [ ] 浏览器连接到预期的本机 Backend。
- [ ] 当前角色与可见导航符合预期。
- [ ] 共享材料中没有凭据或私人路径。
- [ ] Execute 前 Preview 的目标和影响仍然一致。
- [ ] 已完成变更有 Operation/结果记录。
