# Curator Normalize App

本地浏览器可用的 `workspace_album` 编辑器，默认连接：

- 数据库：`database/Curator.db`
- Query 目录：`database/`
- 变更日志：`workspace/normalize_app/logs/changes.log`

## 已支持能力

1. 从 Query 文件导入数据（默认可直接选择 `need_confirm_album_wowgirls`）。
2. 在 UI 中展示查询结果字段并可编辑（主键列不可编辑）。
3. 字段列支持显示/隐藏，支持拖拽调整列宽。
4. 提交修改后，页面会弹出成功/失败提示。
5. 后端记录每次提交日志（JSON Lines），包括更新结果与错误信息。

## 启动方式

在仓库根目录执行：

```bash
python3 workspace/normalize_app/server.py
```

启动后在浏览器打开：

```text
http://127.0.0.1:8787
```

## 注意事项

- 目前只允许更新 `workspace_album` 表。
- 提交接口是参数化 SQL，会拒绝主键和非法列更新。
- Query 文件必须是 `SELECT` 语句。
