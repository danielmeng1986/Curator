# Curator AI Worker Deployment Manual

> Target host: Windows 11 with WSL2 Ubuntu 24.04 · Last verified: 2026-08-13

<!-- manual-section: purpose -->
## 1. Purpose and current support status

AI Worker is an out-of-process Curator API client. It claims an Admin-dispatched
Work Item, downloads only Backend-selected evidence, runs local model inference,
and submits ordered Vision and Writer suggestions. It never opens Curator's
database, reads an Album directory, approves a result, or promotes a name.

The supported Python module provides headless Writer enrollment, approval-status
recovery, private credential state, configuration checks, polling, heartbeat,
bounded Evidence handling, llama.cpp execution, two-stage submission, failure
reporting, and graceful Ctrl-C shutdown. It runs from an approved Curator
checkout and does not require a separate Python package installation.

<!-- manual-section: prerequisites -->
## 2. Prepare Windows 11 and Ubuntu 24.04

Before changing Windows, confirm hardware virtualization is enabled and Windows
Update is current. In an Administrator PowerShell window, inspect available
distributions and install the exact Ubuntu 24.04 name shown by the first command:

```powershell
wsl --list --online
wsl --install -d Ubuntu-24.04
```

Restart if Windows requests it, open Ubuntu, and create the Linux user. Keep the
Curator checkout and model files in the WSL Linux filesystem for predictable
Linux permissions and performance, not inside the repository or Curator Server
data directories. See Microsoft's [WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install).

Inside Ubuntu install the runtime and source-management tools:

```bash
sudo apt update
sudo apt install -y python3 python3-venv git ca-certificates curl
```

<!-- manual-section: source -->
## 3. Prepare the Curator Worker source

Place an approved Curator checkout in the Ubuntu filesystem and change to its
root. Do not copy the Backend database, archive, backups, or registration files
to this host. Verify the existing foundation from the repository root:

```bash
python3 -m unittest workers.ai_worker.tests.test_worker
```

A passing test verifies the local Worker foundation. The release acceptance
suite separately proves the complete REST lifecycle with a disposable Backend;
model compatibility still depends on the selected llama.cpp build and model.

<!-- manual-section: network -->
## 4. Expose and reach the Backend safely

On the separate Backend host, follow the [Backend Server manual](../server/apps-backend.md)
to bind Curator explicitly to its private LAN address and restrict TCP port
`8788` to the intended Windows Worker host. Never expose it to the Internet.
First-Administrator bootstrap remains local to the Backend host.

From Ubuntu, replace the placeholder with the Backend host's private IPv4
address and verify the public health endpoint:

```bash
curl --fail --silent --show-error http://BACKEND_PRIVATE_IPV4:8788/api/health
```

WSL2's default NAT mode supports outbound access to another LAN host; mirrored
mode is not required for this topology. Windows 11 22H2 and later can use
mirrored mode when VPN or network compatibility requires it. Review Microsoft's
[WSL networking guide](https://learn.microsoft.com/en-us/windows/wsl/networking)
before changing `.wslconfig` or firewall policy. The Worker is an outbound
client and does not require an inbound public port.

<!-- manual-section: access -->
## 5. Enroll the dedicated Writer identity

Read [Access and Device Registration](../client/apps-web/access-and-registration.md)
for the meaning of Registration Proof, Device Token, approval, renewal, and
revocation. The AI Worker needs Writer—not Admin—access.

Do not register Chrome and then copy its browser-owned Token into WSL2. In
Ubuntu, request a separate Worker identity; the command asks for Registration
Proof with hidden input and writes candidate material only to a mode-`0600`
state file:

```bash
python3 -m workers.ai_worker enroll --backend-url http://BACKEND_PRIVATE_IPV4:8788 --device-name "Windows 11 WSL2 AI Worker"
```

Ask an Admin to approve that pending device as Writer in **Devices and Tokens**.
Then complete activation from the same WSL2 installation:

```bash
python3 -m workers.ai_worker status
```

Repeat `status` safely if approval is delayed. Do not move the state file to
another host or register through developer tools/raw REST calls.

<!-- manual-section: configuration -->
## 6. Configuration and secret boundaries

Runtime configuration combines the private state file, CLI host paths, and the
Admin-created AI Model Configuration snapshot. `model_file` in the Admin UI is
a portable path relative to `--model-root`; `--llama-cli` names
`llama-mtmd-cli` for Vision, `--text-cli` names standard `llama-cli` for the
single-turn Writer stage, and multimodal builds that require it use `--mmproj`.

Before the first dispatch, an Administrator opens **Administrator Center → AI
Model Configurations** and selects **New Configuration**. Enter a recognizable
name, model identifier, relative `model_file`, Vision/Writer prompt versions,
and runtime parameters, then leave the configuration Enabled. For example, with
`--model-root /opt/curator-models`, `qwen2.5-vl-7b/model.gguf` resolves to
`/opt/curator-models/qwen2.5-vl-7b/model.gguf`. Do not enter an absolute path;
the Backend cannot and does not verify files on a remote Worker. Return to **AI
Work Dispatch** after creation to select the configuration.

`--mmproj` is currently a Worker-process option. For a controlled run, select
only model configurations compatible with that projector; do not use one
projector to mix unrelated multimodal model families in one Worker process.

Model-family limits are not global Curator defaults. For the controlled
Qwen2.5-VL 7B run, start with `sample_count=8`, `context_size=16384`, and
`image_max_tokens=1024`; the context must leave room for all selected images,
the prompt, and generated output. Editing a configuration creates a new version
for future Dispatch snapshots and never rewrites existing Work Items.

- Never put a Device Token in source, Git, a command argument, screenshot, log,
  chat, model prompt, or Windows environment shared with unrelated processes.
- Keep model files outside the repository and outside Backend-managed paths.
- The Worker may use only opaque evidence UUIDs and downloaded bounded bytes;
  it must never mount or browse the Server's Album/archive storage.
- Do not grant Admin merely to simplify setup.

<!-- manual-section: workflow -->
## 7. Start and process tasks

Confirm the Admin configuration's `model_file` exists below the chosen model
root, then start the Worker:

```bash
python3 -m workers.ai_worker run --worker-kind album_name_analysis --llama-cli /opt/llama.cpp/build/bin/llama-mtmd-cli --text-cli /opt/llama.cpp/build/bin/llama-cli --model-root /opt/curator-models --mmproj /opt/curator-models/mmproj.gguf
```

After updating llama.cpp, verify one non-sensitive local image before claiming
production work (replace all three paths):

```bash
/opt/llama.cpp/build/bin/llama-mtmd-cli \
  -m /opt/curator-models/MODEL/model.gguf \
  --mmproj /opt/curator-models/MODEL/mmproj.gguf \
  --image /path/to/test.jpg \
  --image-max-tokens 1024 \
  -c 16384 -ngl 999 -n 128 \
  -p 'Return one JSON object describing this image.'
```

The Worker checks both executables before asking the Backend for work. Vision
requires the multimodal image/projector options. Writer requires
`--single-turn`, `--simple-io`, and bounded-output options so a text-only prompt
cannot enter an interactive chat loop. Writer output is JSON-Schema constrained
and locally checked against Curator's six-name rules before submission; invalid
model output receives bounded corrective retries.

Omit `--mmproj` only when the chosen llama.cpp/model combination does not
require a separate projector. Normal mode waits on outbound HTTP requests of at
most 30 seconds for `album_name_analysis` work. A committed Dispatch wakes a
compatible Worker without rerunning the command or opening a WSL listener.
Normal timeout renews quietly; transient network or Backend restart failures
use bounded backoff, while authentication, authorization, and configuration
errors stop visibly. Use `--once` for one immediate non-waiting compatible
claim: it processes at most one available item or exits successfully when none
is ready.

The runtime performs this sequence:

1. Validate configuration and Backend reachability before claiming.
2. Declare `album_name_analysis` on every claim and wait for a matching Work Item.
3. Maintain the lease with heartbeats while processing.
4. Download only the immutable Evidence Manifest items through the API.
5. Run Vision processing and submit the versioned Vision result.
6. Run Writer processing and submit exactly six valid name suggestions.
7. Remove temporary evidence and wait for the next item.
8. Report a truthful failure if safe completion is impossible.

Admin Review and Promotion remain in Curator Web UI.

<!-- manual-section: lifecycle -->
## 8. Stop, restart, supervise, and update

Press Ctrl-C once for a graceful stop. The process stops its heartbeat, cleans
temporary evidence, and exits without a traceback. If interrupted during a
claimed item, it does not fabricate completion; after lease expiry the Backend
may make the item retryable according to Admin policy.

Start it again with the same command after verifying no prior Worker process is
active. Automatic startup under `systemd` or Windows Task Scheduler is optional
operator work: run the command as the dedicated Linux user, do not embed a Token
in the unit/Task, and keep restart backoff rather than a tight loop.

Update the checkout only while no Worker process is active. After an update,
rerun Worker tests, inspect `--help`, and review release notes before restarting.

<!-- manual-section: troubleshooting -->
## 9. Troubleshooting

| Symptom | Safe response |
| --- | --- |
| Health request cannot connect | Verify Backend LAN binding, printed LAN URL, private address, port, and host firewall. Do not disable the firewall globally. |
| Health works in Windows but not Ubuntu | Check WSL DNS/VPN/NAT behavior and the Microsoft networking guide; use the Backend's private IPv4 for a separate host. |
| `401` | Credential is missing, expired, revoked, replaced, or not yet approved. Never print it while diagnosing. |
| `403` | Confirm the dedicated Worker device was approved as Writer with required scopes; do not elevate to Admin. |
| No Work Item is claimed | Confirm the process uses `--worker-kind album_name_analysis` and Admin dispatched the same Worker kind; `--once` exits normally when the queue is empty. |
| Model/provider failure | Preserve redacted diagnostics and leave Review/Promotion untouched; the Worker reports failure or retries inference according to its lease policy. |
| Backend rejects a request | The Worker reports the HTTP status plus the Backend `error.code` and safe message. Act on that application error instead of guessing from 400/409 alone. |

<!-- manual-section: security -->
## 10. Security and data boundaries

Treat the Windows host, WSL distribution, Writer Token, model, and downloaded
evidence as private Curator components. Use disk protection appropriate to the
host, restrict interactive users, revoke the Worker device when retired or
compromised, and delete temporary evidence after each task. No Worker success
is an approval: only an Admin can Review and Promote results.

<!-- manual-section: checklist -->
## 11. Deployment checklist

- [ ] Windows 11, WSL2, and Ubuntu 24.04 are updated and working.
- [ ] Curator source is in the Linux filesystem and Worker tests pass.
- [ ] The Backend is reachable only on the intended trusted LAN path.
- [ ] No database, archive root, Album directory, or Admin Token is on the Worker.
- [ ] The dedicated WSL2 identity shows `Registration status: Approved` as Writer.
- [ ] `model_file`, `--model-root`, llama.cpp CLI, and optional mmproj agree.
- [ ] An Administrator created and enabled the corresponding AI Model Configuration.
- [ ] A `--once` smoke run exits cleanly or produces one Admin-visible ReadyForReview item.
