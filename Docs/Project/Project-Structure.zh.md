# Curator 项目结构说明

[English](Project-Structure.en.md)

## 用途

本文描述 Curator 当前的长期项目边界。应用代码、运行数据、配置、文档
和开发工具各自独立；客户端和 Worker 只能通过 Backend 的认证 API 访问
业务数据，不能直接访问 SQLite 数据库。

## 目录概览

```text
Curator/
├── apps/
│   ├── backend/       后端、领域服务、仓储、迁移和回归测试
│   └── web/           Web 客户端源码和客户端测试
├── workers/
│   └── ai_worker/     进程外 AI Worker；仅通过 API 与 Backend 通信
├── config/            受版本控制的配置示例与说明
├── var/               本机运行状态（不提交）
│   ├── data/          当前 SQLite 数据库及其 WAL/SHM 文件
│   ├── backups/       当前数据库快照与迁移恢复备份
│   ├── logs/          Backend 操作和备份日志
│   └── outputs/       可丢弃的运行输出
├── Docs/              规格、架构决策、任务书和项目说明
├── tools/
│   └── dev/           不属于业务运行面的开发工具，例如 benchmark
├── outputs/           旧的本地输出残留；不再是正式运行目录，可按需清理
└── .github/           仓库自动化与协作说明
```

## 应用边界

### `apps/backend/`

唯一的可运行 Backend。使用 `python3 -m apps.backend` 启动；它拥有
数据库访问、迁移、业务规则、认证、`/api/v1` 和后端测试。数据库演进源码
位于 `apps/backend/migrations/`，但迁移只会在明确执行时运行，不会因启动
服务而自动修改数据库。

### `apps/web/`

浏览器客户端源码。静态文件由 Backend 提供，通常从
`http://127.0.0.1:8788` 访问，而不是通过 `file://` 直接打开。
客户端保存当前浏览器配置中的设备 Token，并通过认证后的 `/api/v1` 调用
Backend；它不读取数据库文件。

### `workers/ai_worker/`

独立运行的 AI Worker 基础。它封装模型 Provider、重试和 API Client，当前
只产生本地的建议性结果。它不能打开 `Curator.db`、不能导入 Backend 内部
模块、不能读写已归档的 `workspace_album`；持久化 AI 结果必须等待专门的
AI Workspace 规格和 API。

## 配置和运行数据

### `config/`

只提交 `.example` 配置和说明。机器路径、Token、注册密钥和其他敏感值应放
在忽略的本地配置或环境变量中，不能提交到 Git。

### `var/`

唯一的正式本机运行目录。它不进入 Git；备份、日志、输出和数据库均应位于
这里。删除或移动其中的文件前，应先确认其恢复价值。

## 文档和工具

### `Docs/`

项目的规划源。`Docs/Backend/Specifications/` 定义业务规则；
`Docs/Project/` 记录运行布局、项目结构和迁移任务；`Docs/UI/` 记录 UI
方向与验收要求。

### `tools/dev/`

只保存开发辅助工具，不构成产品运行面。当前包含模型 benchmark 工具；它可
引用历史分析脚本作研究，但不得成为 Backend、Web UI 或 Worker 的运行依赖。

## 历史恢复

旧的脚本、兼容 UI 和 Workspace 应用已经从当前工作树清理。它们由远程 Git
Tag `legacy-preservation-2026-08-08` 保留；需要研究或恢复时，应从该 Tag
检出副本，而不是重新接入当前运行路径。
