# Curator Normalize / Import App

本地浏览器可用的 `workspace_album` 编辑器，默认连接：

- 数据库：`database/Curator.db`
- Query 目录：`database/`
- 变更日志：`workspace/curator_base_app/logs/changes.log`
- 备份日志：`workspace/curator_base_app/logs/backup.log`
- 回滚日志：`workspace/curator_base_app/logs/rollback.log`
- 快照目录：`workspace/curator_base_app/backups/`
- 配置文件：`workspace/curator_base_app/app_config.json`

默认配置如下：

```json
{
  "import_source_root": "/Volumes/NAS-RAID5/RAID/Prime_Media/[Temp]/p",
  "archive_root": "/Volumes/NAS-RAID5/RAID/Prime_Media/Archive",
  "default_import_studio": "MetArt"
}
```

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
11. `/import` 页面支持导入单个或多个影集文件夹，文件夹名格式为 `{model_name} in {album_name}`。

## 页面入口

- Normalize 页面：`/normalize`
- Import 页面：`/import`

其中：

- `/normalize` 只负责查询、编辑、备份、回滚 `workspace_album`
- `/import` 负责单个与批量影集导入

## Import 页面

导入页支持“单个影集导入”和“批量影集导入”；单个影集本质上就是只选择 1 个影集。

流程：

1. 在浏览器中选择导入根目录，或选择包含多个影集的目录。
1. App 从所选目录中的顶层文件夹提取多个影集名。
1. 若未手填完整路径，App 会用配置项 `import_source_root + 文件夹名` 自动拼接每条 `source_path`。
1. App 从 `{model_name} in {album_name}` 中提取 `model_name` 和 `album_name`。
1. 可为选中项统一设置 Studio，也可逐条调整 Studio。
1. 预览结果会标识是否需要新建 `model`、是否需要新建 `studio`、目标目录是否已存在，以及 `workspace_album` 中是否已有冲突路径。
1. 点击“导入选中项”后，按条目逐个写入 `workspace_album` 并复制或移动文件夹。

导入写入规则：

- `expected_path`: `{alphabet}/{model_name}/p/{studio_name}/{album_name}`
- `current_path`: 与 `expected_path` 相同
- `status_id`: 写入时为 `3`，文件夹复制/移动完成后更新为 `4`
- 默认移动源文件夹；勾选“保留源文件”时改为复制
- 导入前会创建数据库快照，并写入变更日志
- 如果目标文件夹或 `workspace_album` 路径已存在，导入会拒绝执行

注意：

- 浏览器不会向网页暴露所选文件夹的完整本机路径，因此 Import 页面按文件夹名配合 `app_config.json` 中的 `import_source_root` 自动拼接完整 `source_path`。
- 默认移动源文件夹需要对源目录和 Archive 目标目录都有写权限；如果权限不足，可以先勾选“保留源文件”改为复制，但仍需要 Archive 写权限。

## 启动方式

在仓库根目录执行：

```bash
python3 workspace/curator_base_app/server.py
```

如 8787 已被占用，可指定端口：

```bash
CURATOR_APP_PORT=8790 python3 workspace/curator_base_app/server.py
```

启动后在浏览器打开：

```text
http://127.0.0.1:8787/normalize
http://127.0.0.1:8787/import
```

## 注意事项

- 目前只允许更新 `workspace_album` 表。
- 提交接口是参数化 SQL，会拒绝主键和非法列更新。
- Query 文件必须是 `SELECT` 语句。
- API 支持三种前缀：`/api/*`、`/normalize/api/*`、`/import/api/*`。
- 可用接口：`/api/backup-now`、`/api/backups`、`/api/backups/cleanup`、`/api/backups/delete`、`/api/rollback`。
