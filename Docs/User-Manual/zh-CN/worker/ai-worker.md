# Curator AI Worker 部署手册

> 目标主机：Windows 11 + WSL2 Ubuntu 24.04 · 最后核验：2026-08-13

<!-- manual-section: purpose -->
## 1. 用途与当前支持状态

AI Worker 是 Curator 进程外的 API 客户端。它领取 Admin 已派发的 Work Item，
只下载 Backend 选择的 evidence，在本机运行模型推理，再依次提交 Vision 和 Writer
建议。它绝不打开 Curator 数据库、读取 Album 目录、批准结果或提升名称。

受支持的 Python module 已提供无浏览器 Writer 注册、审批状态恢复、私有凭据状态、配置
校验、轮询、heartbeat、有限 Evidence 处理、llama.cpp 执行、两阶段提交、失败上报和
优雅 Ctrl-C。它从获准版本的 Curator checkout 运行，不要求另行安装 Python package。

<!-- manual-section: prerequisites -->
## 2. 准备 Windows 11 与 Ubuntu 24.04

修改 Windows 前，确认已启用硬件虚拟化并完成 Windows Update。在管理员 PowerShell
中查看可用发行版，再使用第一条命令实际显示的 Ubuntu 24.04 名称安装：

```powershell
wsl --list --online
wsl --install -d Ubuntu-24.04
```

Windows 要求时重启，然后打开 Ubuntu 并创建 Linux 用户。为获得可预测的 Linux 权限
和性能，把 Curator checkout 与模型文件放在 WSL Linux 文件系统中；模型不要放进仓库
或 Curator Server 数据目录。参阅 Microsoft 的
[WSL 安装指南](https://learn.microsoft.com/en-us/windows/wsl/install)。

在 Ubuntu 中安装 runtime 与源码管理工具：

```bash
sudo apt update
sudo apt install -y python3 python3-venv git ca-certificates curl
```

<!-- manual-section: source -->
## 3. 准备 Curator Worker 源码

把获准版本的 Curator checkout 放入 Ubuntu 文件系统并进入仓库根目录。不要把
Backend 数据库、archive、backup 或注册文件复制到本主机。在仓库根目录核验现有基础：

```bash
python3 -m unittest workers.ai_worker.tests.test_worker
```

测试通过会核验本地 Worker 基础；release acceptance suite 会用一次性 Backend 另行证明
完整 REST 生命周期。真实模型兼容性仍取决于所选 llama.cpp build 与模型。

<!-- manual-section: network -->
## 4. 安全开放并连接 Backend

在另一台 Backend 主机上，按照 [Backend Server 手册](../server/apps-backend.md)
显式绑定其私有局域网地址，并在主机防火墙中只允许预期的 Windows Worker 主机访问
TCP `8788`。绝不要开放到 Internet。首位 Administrator bootstrap 仍只能在 Backend
主机本地完成。

在 Ubuntu 中把占位符替换为 Backend 主机私有 IPv4，并核验公开 health endpoint：

```bash
curl --fail --silent --show-error http://BACKEND_PRIVATE_IPV4:8788/api/health
```

WSL2 默认 NAT 模式支持向另一台局域网主机发起连接；这种拓扑不要求 mirrored mode。
Windows 11 22H2 及以上版本可在 VPN 或网络兼容性确有需要时采用 mirrored mode。
修改 `.wslconfig` 或防火墙策略前，先阅读 Microsoft 的
[WSL 网络指南](https://learn.microsoft.com/en-us/windows/wsl/networking)。Worker 是
出站客户端，不需要开放入站公共端口。

<!-- manual-section: access -->
## 5. 注册专用 Writer 身份

先阅读[访问与设备注册](../client/apps-web/access-and-registration.md)，理解 Registration
Proof、Device Token、批准、续期和撤销。AI Worker 只需要 Writer，不需要 Admin。

不要先在 Chrome 注册，再把浏览器拥有的 Token 复制进 WSL2。在 Ubuntu 中申请独立
Worker 身份；命令会以隐藏输入读取 Registration Proof，并只把候选材料写入 mode `0600`
的状态文件：

```bash
python3 -m workers.ai_worker enroll --backend-url http://BACKEND_PRIVATE_IPV4:8788 --device-name "Windows 11 WSL2 AI Worker"
```

请 Admin 在 **Devices and Tokens** 中把该 pending 设备批准为 Writer。然后在同一个 WSL2
安装中完成激活：

```bash
python3 -m workers.ai_worker status
```

如果审批延迟，可以安全地重复执行 `status`。不要把状态文件移到另一台主机，也不要通过
开发者工具或原始 REST 调用注册。

<!-- manual-section: configuration -->
## 6. 配置与机密边界

runtime 配置由私有状态文件、CLI 主机路径和 Admin 创建的 AI Model Configuration snapshot
共同组成。Admin UI 中的 `model_file` 是相对于 `--model-root` 的可移植路径；
`--llama-cli` 指定 Vision 使用的 `llama-mtmd-cli`，`--text-cli` 指定单轮 Writer 使用的标准
`llama-cli`，需要独立 projector 的多模态 build 使用 `--mmproj`。

首次派遣前，Administrator 在 **Administrator Center → AI Model
Configurations** 中选择 **New Configuration**。填写可辨识的名称、模型标识、相对
`model_file`、Vision/Writer prompt 版本和运行参数，然后保持配置为 Enabled。例如，当
Worker 以 `--model-root /opt/curator-models` 启动时，配置中的
`qwen2.5-vl-7b/model.gguf` 解析为
`/opt/curator-models/qwen2.5-vl-7b/model.gguf`。不要填写绝对路径；Backend 不会也不能
检查远程 Worker 上是否存在该文件。配置创建后返回 **AI Work Dispatch** 即可选择它。

当前 `--mmproj` 是 Worker 进程级参数。一次受控验证只选择与该 projector 匹配的模型
配置；不要让同一个 Worker 进程用一个 projector 混合运行不同多模态模型家族。

模型家族限制不是 Curator 的全局默认值。Qwen2.5-VL 7B 的受控测试可先使用
`sample_count=8`、`context_size=16384`、`image_max_tokens=1024`；context 必须同时为全部
选中图片、prompt 和生成结果留出空间。编辑配置只会为未来 Dispatch snapshot 产生新版本，
不会改写现有 Work Item。

- Device Token 绝不能进入源码、Git、命令参数、截图、日志、聊天、模型 prompt，或与无关
  进程共享的 Windows 环境。
- 模型文件应位于仓库之外，也不能位于 Backend 管理的路径中。
- Worker 只能使用不透明 evidence UUID 与下载的有限字节；绝不能挂载或浏览 Server 的
  Album/archive 存储。
- 不要为了简化设置而授予 Admin。

<!-- manual-section: workflow -->
## 7. 启动并处理任务

确认 Admin 配置中的 `model_file` 位于所选 model root 下，然后启动 Worker：

```bash
python3 -m workers.ai_worker run --worker-kind album_name_analysis --llama-cli /opt/llama.cpp/build/bin/llama-mtmd-cli --text-cli /opt/llama.cpp/build/bin/llama-cli --model-root /opt/curator-models --mmproj /opt/curator-models/mmproj.gguf
```

更新 llama.cpp 后，先用一张不敏感的本地图片验证，再领取生产任务（替换以下三个路径）：

```bash
/opt/llama.cpp/build/bin/llama-mtmd-cli \
  -m /opt/curator-models/MODEL/model.gguf \
  --mmproj /opt/curator-models/MODEL/mmproj.gguf \
  --image /path/to/test.jpg \
  --image-max-tokens 1024 \
  -c 16384 -ngl 999 -n 128 \
  -p 'Return one JSON object describing this image.'
```

Worker 在向 Backend 领取任务前会检查两个可执行文件。Vision 必须具备图片/projector 参数；
Writer 必须具备 `--single-turn`、`--simple-io` 与有界输出参数，确保纯文本 prompt 不会进入
交互式 chat 循环。Writer 输出会受结构型 JSON Schema 约束，并在提交前按照 Curator 的字段
长度与六个名称规则进行本地校验；不合格的模型输出会收到有界纠错重试。长度上限不直接写入
llama.cpp grammar，以避免大范围重复规则超过其复杂度限制，但 Worker 与 Backend 均不会因此
接受超出 Curator 契约的数据。
Vision 输出同样会在提交前按照 schema v1 的精确字段、人数范围、数组、置信度和文本上限进行
本地校验；模型格式发生偏移时，Worker 会先进行有界纠错重试，而不是把无效结果提交成 HTTP 400。

仅当所选 llama.cpp/模型组合不要求独立 projector 时才省略 `--mmproj`。正常模式会用最长
30 秒的 outbound HTTP 请求等待 `album_name_analysis` 任务；Backend Dispatch 提交后会立即
唤醒兼容 Worker，不需要重新运行命令，也不会在 WSL 开放监听端口。正常超时会安静地开始
下一次等待。临时网络或 Backend 重启会使用有上限的退避重连；认证、授权和配置错误会明确
停止。使用 `--once` 进行受控 smoke run：只做一次不等待的匹配 claim，最多处理一个 item，
没有任务时正常退出。

runtime 执行以下顺序：

1. claim 前校验配置与 Backend 连通性。
2. 每次 claim 声明 `album_name_analysis` 能力并等待一个匹配的 Work Item。
3. 处理期间通过 heartbeat 维持 lease。
4. 只通过 API 下载不可变 Evidence Manifest 中的项目。
5. 执行 Vision 处理并提交带版本的 Vision 结果。
6. 执行 Writer 处理并提交恰好六个有效名称建议。
7. 删除临时 evidence，然后等待下一项任务。
8. 无法安全完成时提交真实的失败状态。

Admin Review 与 Promotion 仍在 Curator Web UI 中完成。

<!-- manual-section: lifecycle -->
## 8. 停止、重启、托管与更新

按一次 Ctrl-C 即可优雅停止。进程会停止 heartbeat、清理临时 evidence，并且不输出
traceback。若在已 claim item 的处理中断，它不会伪造完成；lease 过期后，Backend 可按
Admin policy 让 item 可重试。

确认没有旧 Worker 进程后，用同一命令重新启动。通过 `systemd` 或 Windows Task Scheduler
自动启动属于可选 operator 工作：使用专用 Linux 用户运行，不要把 Token 写入 unit/Task，
并设置 restart backoff，不能形成紧密循环。

只有在没有 Worker 进程运行时才可更新 checkout。更新后重新运行 Worker 测试，检查
`--help`，并阅读 release notes 后再启动。

<!-- manual-section: troubleshooting -->
## 9. 故障排查

| 表现 | 安全处理方式 |
| --- | --- |
| Health 请求无法连接 | 核对 Backend LAN 绑定、启动时显示的 LAN URL、私有地址、端口及主机防火墙；不要全局关闭防火墙。 |
| Windows 可访问但 Ubuntu 不可访问 | 检查 WSL DNS/VPN/NAT 行为并参考 Microsoft 网络指南；连接另一台主机时使用 Backend 私有 IPv4。 |
| `401` | 凭据缺失、过期、已撤销、已替换或尚未批准；排障时绝不要打印它。 |
| `403` | 确认专用 Worker 设备已按所需 scopes 批准为 Writer；不要提升为 Admin。 |
| 没有领取 Work Item | 确认进程使用 `--worker-kind album_name_analysis`，Admin 已派发相同 Worker kind 的 Album 与配置；队列为空时 `--once` 会正常退出。 |
| 模型/provider 失败 | 查看 Worker 输出与 Work Item 中限长、脱敏后的 llama.cpp 诊断；核对参数、模型/mmproj、GPU、context 与 image token。保持 Review/Promotion 不变。 |
| Backend 拒绝请求 | Worker 会显示 HTTP 状态以及 Backend `error.code` 和安全 message；按应用错误处理，不要仅凭 400/409 猜测。 |

<!-- manual-section: security -->
## 10. 安全与数据边界

把 Windows 主机、WSL 发行版、Writer Token、模型和已下载 evidence 都视作 Curator 私有
组件。采用适合主机的磁盘保护，限制交互用户，Worker 退役或受损时撤销其设备，并在每项
任务后删除临时 evidence。Worker 成功不等于批准；只有 Admin 可以 Review 和 Promote。

<!-- manual-section: checklist -->
## 11. 部署核验清单

- [ ] Windows 11、WSL2 与 Ubuntu 24.04 已更新并正常工作。
- [ ] Curator 源码位于 Linux 文件系统，Worker 测试通过。
- [ ] Backend 只能通过预期的可信局域网路径访问。
- [ ] Worker 主机上没有数据库、archive root、Album 目录或 Admin Token。
- [ ] WSL2 专用身份以 Writer 显示 `Registration status: Approved`。
- [ ] `model_file`、`--model-root`、llama.cpp CLI 和可选 mmproj 相互一致。
- [ ] Administrator 已在 AI Model Configurations 中创建并启用对应配置。
- [ ] `--once` smoke run 能干净退出，或生成一个 Admin 可见的 ReadyForReview item。
