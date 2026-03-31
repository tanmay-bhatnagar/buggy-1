# Utils: `jetson.sh`

Single CLI wrapper for all Mac ↔ Jetson communication over SSH. One script, one entry point.

```
┌──────────┐       SSH        ┌──────────┐
│   Mac    │ ◄──── 🔗 ────► │  Jetson  │
│  (IDE)   │  jetson.sh      │  (GPU)   │
└──────────┘                 └──────────┘
```

---

## Prerequisites

- Both devices on the **same WiFi network**
- Jetson is powered on and booted

---

## First-Time Setup

### 1. Clean SSH slate (if you have old keys with passphrases)

If you've never used SSH or want a fresh start:

```bash
# Remove old keys and known hosts
rm -f ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub ~/.ssh/known_hosts

# Generate fresh key with NO passphrase (just press enter if prompted)
ssh-keygen -t ed25519 -C "mac-to-jetson" -f ~/.ssh/id_ed25519 -N ""
```

> [!NOTE]
> If you have an existing key from GitHub/work that you want to keep, skip this step.
> But if setup asks for a "passphrase" and you don't know it, come back and do this.

### 2. Run setup

```bash
cd buggy-1/utils
chmod +x jetson.sh
./jetson.sh setup
```

The script will:
1. **Scan your WiFi** for devices (or let you enter the Jetson IP manually)
2. Ask for the **Jetson username** (default: `tanmay-jetson`)
3. Copy SSH key to Jetson — you enter the **Jetson login password once**, then never again
4. Create an `ssh jetson` alias
5. Verify the connection

> [!TIP]
> To find the Jetson's IP manually, run `hostname -I` in a terminal on the Jetson.

---

## Commands

| Command | What it does |
|---|---|
| `./jetson.sh setup` | Guided first-time setup (scan WiFi + SSH keys) |
| `./jetson.sh shell` | Open Jetson terminal from Mac |
| `./jetson.sh push` | Sync all code Mac → Jetson |
| `./jetson.sh push phase-2/test.py` | Push a single file |
| `./jetson.sh pull` | Pull all files Jetson → Mac (into `jetson_pull/`) |
| `./jetson.sh pull phase-2/output.log` | Pull a single file |
| `./jetson.sh run phase-2/test.py` | **Sync + run on Jetson** (output streams to Mac terminal) |
| `./jetson.sh run --no-sync "nvidia-smi"` | Run a command without syncing first |
| `./jetson.sh status` | Jetson health check: memory, disk, temperature |
| `./jetson.sh logs /path/to/file` | Live-tail a log file on Jetson |
| `./jetson.sh ip` | Show saved Jetson IP |
| `./jetson.sh ip 192.168.x.x` | Update Jetson IP (if DHCP changed it) |

---

## Typical Workflow

```bash
# 1. Edit code on Mac in IDE

# 2. Push + run on Jetson — output streams right here in Mac terminal
./jetson.sh run phase-2/YOLO_testing/vanilla/test_yolo.py

# 3. See error? Fix in IDE, re-run. No copy-paste needed.

# 4. Need to poke around on Jetson directly?
./jetson.sh shell

# 5. Jetson acting weird?
./jetson.sh status
```

---

## What Gets Synced

`push` and `pull` use `rsync` and exclude large/sensitive files (mirrors `.gitignore`):

- ❌ `.git/`, `__pycache__/`, `*.pyc`
- ❌ `phase-2/dataset/` (personal images)
- ❌ `phase-2/training/runs/` (large training outputs)
- ❌ `*.pt`, `*.onnx`, `*.engine` (model weights)
- ✅ Everything else (code, scripts, configs)

To transfer model weights specifically:

```bash
scp phase-2/training/runs/.../best.pt jetson:~/Desktop/buggy-1/phase-2/best.pt
```

---

## If Jetson IP Changes

DHCP can reassign the IP after a reboot. Quick fix:

```bash
./jetson.sh ip 192.168.x.NEW
```

Or re-run `./jetson.sh setup` to scan again.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Can't reach Jetson" | Check both devices on same WiFi. Try `./jetson.sh setup` again. |
| "Enter passphrase for key" | Your SSH key has a passphrase. Run the "Clean SSH slate" steps above. |
| "Permission denied" | SSH key issue. Run `./jetson.sh setup` to re-copy keys. |
| "Connection timed out" | Jetson IP changed. Update with `./jetson.sh ip NEW_IP`. |
| Scan finds no devices | Use option `[2]` manual IP entry instead. Get IP from Jetson: `hostname -I`. |

---

## Files

```
utils/
├── jetson.sh           # The CLI wrapper (this is the only script you run)
├── .jetson_config      # Saved Jetson IP + username (gitignored, auto-created by setup)
└── implementation.md   # This file
```
