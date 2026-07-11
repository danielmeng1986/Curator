# Curator Normalize App

本地浏览器可用的 `workspace_album` 编辑器，默认连接：

- 数据库：`database/Curator.db`
- Query 目录：`database/`
- 变更日志：`workspace/curator_base_app/logs/changes.log`
- 备份日志：`workspace/curator_base_app/logs/backup.log`
- 回滚日志：`workspace/curator_base_app/logs/rollback.log`
- 快照目录：`workspace/curator_base_app/backups/`

## 已支持能力

1. 从 Query 文件导入数据（默认可直接选择 `need_confirm_album_wowgirls`）。
2. 在 UI 中展示查询结果字段并可编辑（主键列不可编辑）。
3. 字段列支持显示/隐藏，支持拖拽调整列宽。
4. 提交修改后，页面会弹出成功/失败提示。
5. 后端记录每次提交日志（JSON Lines），包括更新结果与错误信息。
6. 每天凌晨自动创建数据库快照（SQLite backup）。
7. 快照自动保留 15 天；超过 15 天的非 Tag 快照会被自动清理。
8. 手动备份支持 Tag；带 Tag 的快照不会被自动清理（可手动删除）。
9. 支持一键回滚：可按“上一次操作前 / 指定时间点 / 指定 Tag”回滚。
10. 每次批量修改会附带可回滚 SQL 片段记录到日志中。
11. 支持导入单个影集文件夹，文件夹名格式为 `{model_name} in {album_name}`。

## 单个影集导入

导入入口在页面的“导入影集”区域。

流程：

1. 输入源文件夹完整路径，或用“辅助选择文件夹”先解析文件夹名。
2. App 从 `{model_name} in {album_name}` 中提取 `model_name` 和 `album_name`。
3. Studio 默认使用 `MetArt`，也可以从已有 Studio 中选择或输入新的 Studio。
4. 如果 `model` 表中不存在该 Model，会自动创建。
5. 如果 `studio` 表中不存在该 Studio，会自动创建，并默认写入 `media_scope = 'p'`。
6. 点击“预览”后确认目标路径、实体创建状态和冲突状态。
7. 点击“导入”后先写入 `workspace_album`，再复制或移动文件夹。

导入写入规则：

- `expected_path`: `{alphabet}/{model_name}/p/{studio_name}/{album_name}`
- `current_path`: 与 `expected_path` 相同
- `status_id`: 写入时为 `3`，文件夹复制/移动完成后更新为 `4`
- 默认移动源文件夹；勾选“保留源文件”时改为复制
- 导入前会创建数据库快照，并写入变更日志
- 如果目标文件夹或 `workspace_album` 路径已存在，导入会拒绝执行

注意：

- 浏览器不会向网页暴露所选文件夹的完整本机路径，因此“辅助解析名称”只用于读取文件夹名，源文件夹完整路径仍需要手动粘贴。
- 默认移动源文件夹需要对源目录和 Archive 目标目录都有写权限；如果权限不足，可以先勾选“保留源文件”改为复制，但仍需要 Archive 写权限。

## 启动方式

在仓库根目录执行：

```bash
python3 workspace/curator_base_app/server.py
```

启动后在浏览器打开：

```text
http://127.0.0.1:8787/normalize
```

## 注意事项

- 目前只允许更新 `workspace_album` 表。
- 提交接口是参数化 SQL，会拒绝主键和非法列更新。
- Query 文件必须是 `SELECT` 语句。
- API 支持两种前缀：`/api/*` 与 `/normalize/api/*`（便于平滑迁移）。
- 可用接口：`/api/backup-now`、`/api/backups`、`/api/backups/cleanup`、`/api/backups/delete`、`/api/rollback`。
