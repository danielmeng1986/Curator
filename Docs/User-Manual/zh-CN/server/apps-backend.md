# Curator 后端服务器使用手册

> 支持的应用：`apps.backend`  
> 适用对象：本机服务器运维人员与管理员  
> 最后核验：2026-08-11

<!-- manual-section: purpose -->
## 1. 用途与支持状态

Curator Backend 负责目录数据库、文件变更工作流、认证、审计记录、备份操作，
并提供静态 `apps.web` 客户端。打开 Web 客户端前应先启动此服务器。它是本机
管理服务，不是公开网站。

<!-- manual-section: prerequisites -->
## 2. 前置条件

- 在仓库根目录使用受支持的 `python3` 环境运行命令。
- 确保配置的数据库、归档、导入、Quarantine、备份与日志位置已挂载，且服务器账户可写。
- 执行迁移或替换/恢复数据库前停止 Backend。
- 绝不能在正式目录数据库上测试维护或破坏性工作流。

<!-- manual-section: configuration -->
## 3. 配置与受管路径

将 `config/backend.example.json` 复制为已被忽略的 `config/backend.json`，再替换
示例绝对路径。不要提交本机配置文件。

| 设置 | 用途 |
| --- | --- |
| `import_source_root` | 经审核的 Import 可读取的根目录 |
| `archive_root` | 受管数字资产归档根目录 |
| `default_import_studio` | Import 时默认分配的 Studio |
| `quarantine_root` | Quarantine 操作使用的可选隔离根目录 |

默认运行位置为 `var/data/Curator.db`、`var/backups/` 与 `var/logs/`。部署时可用
`CURATOR_DATABASE_PATH`、`CURATOR_RUNTIME_DIR`、`CURATOR_BACKUP_DIR` 和
`CURATOR_LOG_DIR` 覆盖；`CURATOR_CONFIG_PATH` 指定其他配置文件，
`CURATOR_STATIC_DIR` 指定 Web 客户端文件；`CURATOR_PORT` 可修改默认端口 `8788`。
默认仅监听 `127.0.0.1`。仅在受信任局域网及已配置主机防火墙时，才用
`CURATOR_HOST=0.0.0.0` 显式启用 LAN 访问。

路径和配置可能泄露私人资产布局。Token 与凭据必须通过受保护的本机配置提供，
绝不能提交，或粘贴到日志、截图和支持报告中。

<!-- manual-section: initialize -->
## 4. 初始化或迁移数据库

停止 Backend 并确认有可用备份后，执行规范迁移：

```bash
python3 -m apps.backend.migrations
```

仅重启 Backend 不会自动执行迁移。每次更新包含新迁移时，都需要显式运行上述维护命令，并在
启动或重启 Backend 前确认输出中的已应用版本。

必须使用服务器将使用的同一数据库路径。不要打开 SQLite 执行临时结构修改。
正常启动会拒绝缺失的数据库，而不会静默创建一个替代目录数据库。

<!-- manual-section: lifecycle -->
## 5. 启动、核验、停止与重启

启动应用：

```bash
python3 -m apps.backend
```

需要让另一台局域网主机使用时：

```bash
CURATOR_HOST=0.0.0.0 python3 -m apps.backend
```

启动输出会同时列出 **Local URL** 和检测到的 **LAN URL**。应使用显示的私有 IPv4
地址（例如 `http://192.168.x.x:8788`），不要在其他主机使用 `127.0.0.1`。

启动成功后会显示回环 URL、数据库路径和备份目录。在同一主机打开显示的 URL
（通常为 `http://127.0.0.1:8788`），确认 Curator 客户端可以加载。使用终端中断
（`Ctrl-C`）正常停止，并等待进程退出。旧进程释放端口后才能重启。

启动时会创建数据库 Snapshot 并启动每日备份维护。Snapshot 失败会写入备份日志；
执行高风险操作前必须调查该失败。

<!-- manual-section: bootstrap -->
## 6. 初始化首位管理员

这是唯一受支持的 UI 辅助首位管理员流程。它刻意要求本机终端访问权限，且仅在
尚无管理员时有效。

1. 启动 Backend，并在同一机器打开其回环 URL。
2. 在另一个终端生成一次性 Code：

   ```bash
   python3 -m apps.backend auth create-bootstrap-code
   ```

3. 十分钟内在 **Initialize administrator** 输入 Code，填写管理员设备名称并提交。
4. 立即复制只显示一次的 Admin Token；将其存入获准的凭据管理器，在 UI 中确认已保存后继续。
5. 确认可以进入 **Administrator Center**。

Code 过期或已使用时应重新生成。首位管理员存在后 Bootstrap 会被拒绝。不要把
`bootstrap-admin` 当作日常登录或 Token 恢复方式。

<!-- manual-section: security -->
## 7. 认证与网络安全

默认服务器绑定 `127.0.0.1`。LAN 绑定必须显式启用，并由主机防火墙限制在受信任私有
网络；绝不能把端口公开到 Internet、添加未经审核的反向代理或削弱认证。首位管理员
Bootstrap 仍只允许 Backend 本机。每台设备使用经批准且受角色限制的 Token。
非必要时授予 Reader 或 Writer；遗失的 Token 应尽快撤销；绝不能撤销最后一个可用管理员 Token。

<!-- manual-section: recovery -->
## 8. Backup、Snapshot、Restore 与日志

常规启动/每日 Snapshot 及其日志位于配置的备份与日志根目录。管理员通过
**Administrator Center** 管理已登记 Backup、Snapshot 清理与受保护数据库 Restore。

Restore 前核对所选产物，审核 Preview，阅读预检结果，并准确输入要求的确认内容。
Restore 属于维护操作：阻止并发写入，保留 Restore 前 Snapshot，并遵循 UI 返回结果。
数据库 Restore 成功会使现有会话失效；请使用有效凭据重新连接。服务器运行时绝不能
手动替换正式数据库文件。

<!-- manual-section: upgrade -->
## 9. 维护与升级流程

1. 公告禁止写入的维护窗口并停止 Backend。
2. 确认当前备份可恢复，并核对准确的数据库配置路径。
3. 更新应用文件与配置示例，不覆盖本机机密。
4. 执行一次 `python3 -m apps.backend.migrations`。
5. 正常启动，并核对服务器显示的数据库、备份目录和回环 URL。
6. 重新连接客户端，核验相关角色工作流和备份状态。

仅在发布说明明确指出数据库需要时，才采用历史 Workspace 归档流程；它不是日常维护。

<!-- manual-section: troubleshooting -->
## 10. 故障排查

| 表现 | 安全处理方式 |
| --- | --- |
| `Database not found` | 检查配置/挂载的数据库路径；不要在预期目录数据库位置创建空替代文件。 |
| `Static directory not found` | 恢复或正确配置 `apps/web/static`；不要指向无关目录。 |
| 端口已占用 | 停止之前的 Curator 进程或选择获准的 `CURATOR_PORT`；不要终止身份不明的进程。 |
| Bootstrap 被拒绝 | 确认尚无管理员，且服务器与命令解析到同一数据库。 |
| Bootstrap Code 被拒绝 | 在本机生成新 Code；Code 只能使用一次且十分钟后过期。 |
| Token 被拒绝 | 核对 Token 与设备状态；请管理员批准/续期访问。绝不要为排障打印 Token。 |
| Backup/Restore 失败 | 停止高风险操作，保留日志与产物，查看结构化 UI 结果后再重试。 |

<!-- manual-section: warnings -->
## 11. 高风险警告

- Import 执行、Repair、Quarantine、Restore、Snapshot 清理、Token 撤销、AI Promotion、
  Group release 与 Workspace closure 都可能改变持久状态。
- Preview 不等于执行。确认前应立即重新核对目标与影响。
- 过期、陈旧或已使用的 Preview 必须重新创建；绝不能绕过防重放检查。
- 部分失败后保留操作/审计证据。不要用直接 SQL “修复”状态。
- 只有确认存在且适合恢复的备份才真正有用。

<!-- manual-section: checklist -->
## 12. 核验清单与客户端手册

- [ ] 配置仅解析到获准的本机/挂载路径。
- [ ] Backend 停止期间迁移成功完成。
- [ ] 启动解析到目标数据库与静态客户端。
- [ ] 启动显示预期回环 URL，并创建备份证据。
- [ ] 受角色限制的客户端可重新连接，且仅看到获准工作流。
- [ ] 记录中没有 Token、凭据、私人路径或资产名称。

请继续阅读 [Web 客户端概览](../client/apps-web/README.md)，UI 管理操作尤其参见
[管理员手册](../client/apps-web/administrator.md)。
