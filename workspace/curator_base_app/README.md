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
