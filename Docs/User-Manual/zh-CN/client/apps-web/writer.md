# Curator Web Writer 使用手册

> 所需角色：Writer（或 Administrator）· 最后核验：2026-08-11

<!-- manual-section: purpose -->
## 1. 角色用途与连接

Writer 维护 Album 级目录数据，执行经审核的 Import 与获准的 Issue/Repair 决策。
按[客户端概览](README.md)使用获准 Writer Token 连接。Writer 没有恢复或授权管理权。

<!-- manual-section: entities -->
## 2. Albums 与永久实体

1. 搜索/筛选 **Albums**，打开记录，编辑允许的元数据、Studio、Model、Album 关系并 **Save**。
2. 多个 Album：选择行，点击 **Batch edit selected**，设置变更，点击 **Review changes**，
   审核阻止/影响数量，再点击 **Execute reviewed batch**。
3. 在 **Models** 和 **Studios** 创建/编辑获准实体。Album 仍引用实体时删除可能被阻止；
   应处理关系，不要强制删除。
4. 将 **Statuses** 视为受治理的目录词汇，并遵循 UI 显示的控制。

Album 是资产管理单位。本客户端不提供通用照片浏览或直接照片删除。

<!-- manual-section: import -->
## 3. Import Albums

1. 打开 **Import**，选择对整批生效的 **Import Action**。
2. 添加 Album 来源/名称条目，选择 **Preview**。
3. 审核校验、标识、目标、冲突和 `can_import`；只选择有效且确实需要的条目，
   点击 **Confirm selected**。
4. 再次核对最终摘要，只点击一次 **Execute reviewed … Import**。
5. 查看 **Import Results** 并打开 **View Operation**。部分失败须先调查，再创建新 Preview。

修改批次会使旧 Preview 失效。绝不能对不同选择或来源假设已变化的内容执行旧 Preview。

<!-- manual-section: issues -->
## 4. Issues 与 Repair Cases

打开 **Issues**，按状态筛选并查看详情/证据。只能选择 `allowed_actions` 中的动作；
Backend 会拒绝无效状态转换。在 **Repair Cases** 中，决定前审核建议的文件系统影响。
批准本身不一定执行文件操作，除非结果明确说明已经执行。

<!-- manual-section: operations -->
## 5. Operation 证据

使用 **Operations** 的筛选与分页查找结果记录。核对状态、时间、执行者/类型、摘要及
关联 Issue/Repair 证据。升级报告失败或部分失败时保留 Operation 标识。

<!-- manual-section: denials -->
## 6. 仅管理员边界

Writer 不能管理 Token、有限范围 suppression、Repair Quarantine、Backup、Snapshot 清理、
数据库 Restore、AI 配置、Work Dispatch、AI 审核、Promotion、Group release 或 Workspace
关闭/归档。应请求管理员处理，不要尝试直接请求。Digital Asset Trash 对所有角色尚不可用。

<!-- manual-section: checklist -->
## 7. 安全、故障排查与核验清单

- [ ] 已连接设备显示 Writer 或 Administrator。
- [ ] Album/实体变更仅覆盖目标记录。
- [ ] 每次批量操作或 Import 都重新 Preview 并审核后才 Execute。
- [ ] Issue/Repair 只使用当前允许的动作。
- [ ] 执行或部分失败后检查 Operation 证据。
- [ ] 管理员工作已升级处理，且未分享 Writer Token。
