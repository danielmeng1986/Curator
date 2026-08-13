# Curator Web Administrator 使用手册

> 所需角色：Administrator · 最后核验：2026-08-11

<!-- manual-section: purpose -->
## 1. 角色用途与前置条件

Administrator 在 Writer 能力上增加认证、恢复、Quarantine 与 AI 工作流权限。
请先阅读 [Writer 手册](writer.md)，并了解 Backend 备份健康状态。使用专用管理员
设备/浏览器配置，并保护其 Token。

<!-- manual-section: bootstrap -->
## 2. 初始化首位管理员

1. 在 Backend 主机启动服务器并打开其 `127.0.0.1` URL。
2. 在本机终端运行：

   ```bash
   python3 -m apps.backend auth create-bootstrap-code
   ```

3. 选择 **Initialize administrator**，输入十分钟有效的一次性 Code 与管理员设备名并初始化。
4. 将只显示一次的 Admin Token 复制到获准的安全存储。勾选 **I have stored the Token
   securely**，继续并确认 **Administrator Center** 可用。

终端边界用于证明本机控制权。已有管理员后，它不是恢复捷径。完整服务器说明见
[Backend 手册](../../server/apps-backend.md)。

<!-- manual-section: authentication -->
## 3. Devices and Tokens

按[访问与设备注册](access-and-registration.md)生成/轮换/停用 Registration Proof，并审批完全通过 UI 提交的 Reader/Writer 申请。

在 **Administrator Center → Devices and Tokens**：

1. 核对待处理注册的设备身份以及申请角色/scopes。
2. 仅按最小权限批准，否则拒绝。新 Token 只显示一次；安全传递，并在确认存储后关闭结果。
3. 批准续期前审核申请；替代 Token 同样只显示一次。
4. **Revoke** 前核对设备/Token，输入要求的高风险确认。撤销会立即终止访问。

已存 Token 明文与 hash 永不显示。Backend 会保护最后一个可用 Admin Token；但仍需建立
第二套恢复方案，不能只依赖此保护。

<!-- manual-section: issue-admin -->
## 4. Issue、Repair、suppression 与 Quarantine

审核 Issue/Repair 证据，只使用当前允许的决定。bounded suppression 只能针对显示的
候选范围和已记录理由创建。

对于已批准的修复冲突，选择 **Review Quarantine move**，核对原始与隔离目标，再执行
**Execute reviewed Quarantine**。Quarantine 不会解决 Issue。要返回隔离条目，打开
**Repair Quarantine**，选择条目和 **Review restore to original path**，检查冲突并执行
新 Preview。它不是 Digital Asset Trash；后者尚不可用。

<!-- manual-section: backup -->
## 5. Backups、Snapshots 与数据库 Restore

通过 **Backups and Snapshots** 查看已登记恢复点、创建管理员 Snapshot，并在依赖前验证。
Snapshot 清理要求新 Preview 和高风险确认；必须保留所需恢复点。

数据库 Restore 会替换活动目录：

1. 建立禁止写入的维护窗口，打开 **Database Restore**。
2. 只选择已验证恢复点，点击 **Review Restore**。
3. 阅读预检影响和受保护 Restore 前 Snapshot 行为；准确输入确认短语，只点击一次
   **Restore reviewed database**。
4. 等待 Restore 后完整性校验。成功后会清除管理员缓存和连接；用恢复后数据库中有效 Token 重连。
5. 失败时停止操作并保留 Operation、日志和恢复证据。不要盲目重试或手动替换数据库文件。

<!-- manual-section: ai-config -->
## 6. AI 配置、Workspace 与 Dispatch

在 **Administrator Center → AI Model Configurations** 创建/版本化 llama.cpp 模型与采样
参数，包括要求的样本数。应禁用过时配置，不要重写历史证据。

创建/选择 AI Workspace 后打开 **AI Work Dispatch**：

1. 筛选可派发 Album 池，明确选择 Album（或有上限的筛选数量）、Worker、Workspace 和
   一个或多个启用的模型配置。
2. Preview 并核对 Album、Group、Work Item 数量与独占冲突。
3. 确认已审核影响，点击 **Dispatch reviewed Albums**。

Dispatch 不改变 Album Status。活动 dispatch key 会防止同一 Album 同时派给另一 Worker；
release/closure 后才恢复可派发资格。

<!-- manual-section: ai-review -->
## 7. AI 审核、rework、Promotion 与关闭

打开 **AI Review**，筛选队列并查看 Work Item。决定前审核分析 JSON、推荐名称、模型配置
和准确的采样照片证据。

- **Approve** 接受结果供后续使用，但不会自行重命名 Album。
- **Request rework** 在同一 Dispatch Group 创建新 Work Item，继承模型配置，并关联旧条目作证据。
- **Reject** 记录该结果不可 Promotion。
- 管理员评价仅针对该 Work Item 结果，不是对模型的全局评价。

Promotion 独立执行：为 Album 选择恰好一个获批候选或有效人工修订名，Preview 后执行一次。
即使多个模型配置分析过 Album，也只能有一个最终 `album_name`。检查 Operation/Issue 输出。
人工 Review 字段会保存为浏览器配置文件草稿。刷新或重启会恢复兼容草稿。如果 Backend
审核版本已经变化，Curator 会要求先选择 **Keep text and rebase** 或
**Discard local draft**，之后才能提交。
释放已完成 Group，并仅在无活动工作且满足保留规则时关闭/归档 Workspace。不要为了清理队列
而 purge 审计证据。

<!-- manual-section: risk -->
## 8. 高风险行为与预期拒绝

输入确认短语、阅读确认、新 Preview token、当前版本与最后管理员校验都是安全控制，绝不能
绕过。`400` 表示输入/转换需要修正；`409` 表示当前状态冲突或已陈旧，应刷新后重新判断。
Reader/Writer 被拒绝访问本手册各项内容属于预期行为。

<!-- manual-section: checklist -->
## 9. 核验清单

- [ ] Admin Token 安全保存，未出现在截图/日志中。
- [ ] 授权采用最小权限，最后管理员安全仍然有效。
- [ ] 每个破坏性/恢复动作均使用新 Preview 和准确确认。
- [ ] Restore 有已验证的前后证据，且已理解重连行为。
- [ ] AI 决策引用模型配置和采样照片证据。
- [ ] Promotion 只选择一个名称；rework 保留旧 Work Item。
- [ ] Operations 与 Issues 证明持久结果，包括部分失败。
