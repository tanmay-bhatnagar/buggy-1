#!/bin/bash
# ==========================================================
#   jetson.sh — One-stop Mac → Jetson remote dev wrapper
# ==========================================================
#
#   First time:   ./jetson.sh setup
#   Then:         ./jetson.sh run phase-2/test.py
#                 ./jetson.sh push
#                 ./jetson.sh shell
#                 ./jetson.sh status
#
# ==========================================================

set -e

# --- Paths ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$SCRIPT_DIR/.jetson_config"

# --- Remote defaults ---
REMOTE_PROJECT="~/Desktop/buggy-1"
CONDA_ENV="buggy"

# --- rsync exclusions (mirrors .gitignore) ---
EXCLUDES=(
    --exclude='.git/'
    --exclude='__pycache__/'
    --exclude='.DS_Store'
    --exclude='*.pyc'
    --exclude='phase-2/dataset/'
    --exclude='phase-2/training/runs/'
    --exclude='*.pt'
    --exclude='*.onnx'
    --exclude='*.engine'
    --exclude='*.pth'
    --exclude='.vscode/'
    --exclude='.idea/'
    --exclude='node_modules/'
    --exclude='jetson_pull/'
)

# --- Colors ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

# ============================================================
#   CONFIG
# ============================================================

load_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${RED}❌ Jetson not configured yet. Run:${NC}"
        echo -e "   ${BOLD}./jetson.sh setup${NC}"
        exit 1
    fi
    source "$CONFIG_FILE"
}

save_config() {
    cat > "$CONFIG_FILE" << EOF
JETSON_IP="$JETSON_IP"
JETSON_USER="$JETSON_USER"
EOF
}

# ============================================================
#   CONNECTION CHECK
# ============================================================

check_connection() {
    if ! ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no \
         "${JETSON_USER}@${JETSON_IP}" "echo ok" &>/dev/null; then
        echo -e "${RED}❌ Can't reach Jetson at ${JETSON_USER}@${JETSON_IP}${NC}"
        echo -e "   Jetson might be off, or IP may have changed."
        echo -e "   Run ${BOLD}./jetson.sh setup${NC} to reconfigure."
        exit 1
    fi
}

# ============================================================
#   SCAN — find Jetson on the network from Mac
# ============================================================

scan_network() {
    echo -e "${CYAN}🔍 Scanning local network for Jetson...${NC}"
    echo ""

    # Get local subnet
    local local_ip
    local_ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "")
    if [ -z "$local_ip" ]; then
        echo -e "${YELLOW}⚠️  Couldn't detect WiFi IP. Are you on WiFi?${NC}"
        return 1
    fi

    local subnet_prefix
    subnet_prefix=$(echo "$local_ip" | sed 's/\.[0-9]*$//')
    echo -e "${DIM}   Your Mac IP: ${local_ip}${NC}"
    echo -e "${DIM}   Scanning:    ${subnet_prefix}.0/24${NC}"
    echo ""

    # Quick ARP scan — parallel ping sweep with macOS-correct timeout
    echo -e "${DIM}   Pinging subnet (takes ~3 seconds)...${NC}"

    for i in $(seq 1 254); do
        # macOS ping: -t is timeout in seconds, -c is count
        ping -c 1 -t 1 "${subnet_prefix}.${i}" &>/dev/null &
    done

    # Wait max 4 seconds for pings (some hosts may not respond)
    sleep 3
    kill $(jobs -p) 2>/dev/null
    wait 2>/dev/null

    echo ""
    echo -e "${BOLD}   Devices found on your network:${NC}"
    echo ""

    # Parse ARP table — hostname is the first field, IP is in parens
    local found_devices=()
    local index=0

    while IFS= read -r line; do
        # arp -a format: "hostname (IP) at MAC on iface ..."
        local ip
        ip=$(echo "$line" | grep -oE '\(([0-9]{1,3}\.){3}[0-9]{1,3}\)' | tr -d '()')
        [ -z "$ip" ] && continue
        [ "$ip" = "$local_ip" ] && continue

        # First field is the hostname (or ? if unknown)
        local arp_hostname
        arp_hostname=$(echo "$line" | awk '{print $1}')
        [ "$arp_hostname" = "?" ] && arp_hostname="unknown"

        index=$((index + 1))
        found_devices+=("$ip")
        printf "   ${GREEN}[%d]${NC}  %-16s  %s\n" "$index" "$ip" "$arp_hostname"
    done < <(arp -a 2>/dev/null | grep -v incomplete)

    echo ""

    if [ ${#found_devices[@]} -eq 0 ]; then
        echo -e "${YELLOW}   No devices found. Enter Jetson IP manually.${NC}"
        return 1
    fi

    # Let user pick
    echo -n -e "   ${BOLD}Which one is your Jetson? [number or IP]: ${NC}"
    read -r pick

    if [[ "$pick" =~ ^[0-9]+$ ]] && [ "$pick" -ge 1 ] && [ "$pick" -le ${#found_devices[@]} ]; then
        JETSON_IP="${found_devices[$((pick - 1))]}"
    elif [[ "$pick" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        JETSON_IP="$pick"
    else
        echo -e "${RED}   Invalid selection.${NC}"
        return 1
    fi

    return 0
}

# ============================================================
#   SETUP — one-time configuration
# ============================================================

cmd_setup() {
    echo ""
    echo -e "${BOLD}═══════════════════════════════════════${NC}"
    echo -e "${BOLD}   🤖 Jetson SSH Setup (Mac-side)${NC}"
    echo -e "${BOLD}═══════════════════════════════════════${NC}"
    echo ""

    # --- Step 1: Find Jetson IP ---
    echo -e "${CYAN}Step 1: Find Jetson on the network${NC}"
    echo ""
    echo -e "   ${DIM}[1] Auto-scan network${NC}"
    echo -e "   ${DIM}[2] Enter IP manually${NC}"
    echo ""
    echo -n -e "   ${BOLD}Choice [1]: ${NC}"
    read -r method
    method="${method:-1}"

    if [ "$method" = "1" ]; then
        if ! scan_network; then
            echo ""
            echo -n -e "   ${BOLD}Enter Jetson IP manually: ${NC}"
            read -r JETSON_IP
        fi
    else
        echo -n -e "   ${BOLD}Jetson IP: ${NC}"
        read -r JETSON_IP
    fi

    if [ -z "$JETSON_IP" ]; then
        echo -e "${RED}❌ No IP provided. Aborting.${NC}"
        exit 1
    fi

    echo ""
    echo -e "   ✅ Jetson IP: ${GREEN}${JETSON_IP}${NC}"

    # --- Step 2: Username ---
    echo ""
    echo -e "${CYAN}Step 2: Jetson username${NC}"
    echo -n -e "   ${BOLD}Username [tanmay-jetson]: ${NC}"
    read -r JETSON_USER
    JETSON_USER="${JETSON_USER:-tanmay-jetson}"

    # --- Step 3: SSH key ---
    echo ""
    echo -e "${CYAN}Step 3: SSH key setup${NC}"

    SSH_KEY="$HOME/.ssh/id_ed25519"
    if [ ! -f "$SSH_KEY" ]; then
        echo -e "   Generating SSH key..."
        ssh-keygen -t ed25519 -C "mac-to-jetson" -f "$SSH_KEY" -N "" -q
        echo -e "   ${GREEN}✅ Key generated${NC}"
    else
        echo -e "   ${GREEN}✅ Key already exists${NC}"
    fi

    # --- Step 4: Copy key ---
    echo ""
    echo -e "${CYAN}Step 4: Copying key to Jetson (enter Jetson password if prompted)${NC}"
    echo ""
    ssh-copy-id -i "${SSH_KEY}.pub" "${JETSON_USER}@${JETSON_IP}" 2>/dev/null || {
        echo -e "${YELLOW}   ssh-copy-id had an issue. Trying manual method...${NC}"
        cat "${SSH_KEY}.pub" | ssh "${JETSON_USER}@${JETSON_IP}" \
            "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
    }

    # --- Step 5: SSH config alias ---
    echo ""
    echo -e "${CYAN}Step 5: Creating 'jetson' SSH alias${NC}"

    SSH_CONFIG="$HOME/.ssh/config"
    mkdir -p "$HOME/.ssh"

    # Remove old jetson block if it exists
    if [ -f "$SSH_CONFIG" ] && grep -q "^Host jetson" "$SSH_CONFIG"; then
        # Use perl for reliable multi-line block removal on macOS
        perl -i -0pe 's/\nHost jetson\n.*?(?=\nHost |\Z)//s' "$SSH_CONFIG" 2>/dev/null || true
    fi

    cat >> "$SSH_CONFIG" << EOF

Host jetson
    HostName ${JETSON_IP}
    User ${JETSON_USER}
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
    StrictHostKeyChecking no
EOF

    chmod 600 "$SSH_CONFIG"
    echo -e "   ${GREEN}✅ 'ssh jetson' configured${NC}"

    # --- Step 6: Save config & test ---
    save_config

    echo ""
    echo -e "${CYAN}Step 6: Testing connection${NC}"
    echo ""
    if ssh -o ConnectTimeout=5 jetson "echo '   ✅ Connected! Jetson says hello from \$(hostname)'" 2>/dev/null; then
        echo ""
        echo -e "${GREEN}${BOLD}═══════════════════════════════════════${NC}"
        echo -e "${GREEN}${BOLD}   ✅ Setup complete! You're connected.${NC}"
        echo -e "${GREEN}${BOLD}═══════════════════════════════════════${NC}"
        echo ""
        echo -e "   ${DIM}Try these:${NC}"
        echo -e "   ${BOLD}./jetson.sh shell${NC}       — open Jetson terminal"
        echo -e "   ${BOLD}./jetson.sh push${NC}        — sync code to Jetson"
        echo -e "   ${BOLD}./jetson.sh run test.py${NC} — sync + run script"
        echo -e "   ${BOLD}./jetson.sh status${NC}      — Jetson health check"
        echo ""
    else
        echo -e "${RED}   ❌ Connection test failed.${NC}"
        echo -e "   Config saved. Debug with: ${BOLD}ssh -v jetson${NC}"
    fi
}

# ============================================================
#   SHELL — SSH into Jetson
# ============================================================

cmd_shell() {
    load_config
    check_connection
    echo -e "${CYAN}🔗 Connecting to Jetson (${JETSON_IP})...${NC}"
    echo ""
    ssh jetson
}

# ============================================================
#   PUSH — sync code Mac → Jetson
# ============================================================

cmd_push() {
    load_config
    check_connection

    local target="$1"

    if [ -n "$target" ]; then
        # Push single file/folder
        local full_path="${PROJECT_DIR}/${target}"
        if [ ! -e "$full_path" ]; then
            echo -e "${RED}❌ Not found: ${target}${NC}"
            exit 1
        fi

        local remote_dir
        remote_dir=$(dirname "${REMOTE_PROJECT}/${target}")
        ssh jetson "mkdir -p ${remote_dir}"

        echo -e "${CYAN}📤 Pushing: ${target}${NC}"
        if [ -d "$full_path" ]; then
            rsync -avz --progress "${EXCLUDES[@]}" "${full_path}/" "jetson:${REMOTE_PROJECT}/${target}/"
        else
            scp "$full_path" "jetson:${REMOTE_PROJECT}/${target}"
        fi
        echo -e "${GREEN}✅ Done${NC}"
    else
        # Push everything
        echo -e "${CYAN}📤 Pushing project to Jetson...${NC}"
        ssh jetson "mkdir -p ${REMOTE_PROJECT}"
        rsync -avz --progress "${EXCLUDES[@]}" "${PROJECT_DIR}/" "jetson:${REMOTE_PROJECT}/"
        echo -e "${GREEN}✅ Push complete${NC}"
    fi
}

# ============================================================
#   PULL — sync Jetson → Mac
# ============================================================

cmd_pull() {
    load_config
    check_connection

    local target="$1"

    if [ -n "$target" ]; then
        # Pull single file
        local local_dir
        local_dir=$(dirname "${PROJECT_DIR}/${target}")
        mkdir -p "$local_dir"

        echo -e "${CYAN}📥 Pulling: ${target}${NC}"
        scp "jetson:${REMOTE_PROJECT}/${target}" "${PROJECT_DIR}/${target}"
        echo -e "${GREEN}✅ Done${NC}"
    else
        # Pull everything into jetson_pull/
        local pull_dir="${PROJECT_DIR}/jetson_pull"
        mkdir -p "$pull_dir"

        echo -e "${CYAN}📥 Pulling from Jetson → jetson_pull/${NC}"
        rsync -avz --progress "${EXCLUDES[@]}" "jetson:${REMOTE_PROJECT}/" "${pull_dir}/"
        echo -e "${GREEN}✅ Files in jetson_pull/ — review before copying into working tree${NC}"
    fi
}

# ============================================================
#   RUN — sync code + run script on Jetson
# ============================================================

cmd_run() {
    load_config
    check_connection

    local no_sync=false
    if [ "$1" = "--no-sync" ]; then
        no_sync=true
        shift
    fi

    if [ $# -lt 1 ]; then
        echo "Usage: ./jetson.sh run [--no-sync] <script.py|command> [args...]"
        exit 1
    fi

    local script_or_cmd="$1"
    shift
    local extra_args="$*"

    # --- Sync first ---
    if [ "$no_sync" = false ]; then
        echo -e "${CYAN}📤 Syncing...${NC}"
        ssh jetson "mkdir -p ${REMOTE_PROJECT}"
        rsync -az "${EXCLUDES[@]}" "${PROJECT_DIR}/" "jetson:${REMOTE_PROJECT}/" 2>&1 | tail -1
        echo -e "${GREEN}✅ Synced${NC}"
        echo ""
    fi

    # --- Build remote command ---
    local remote_cmd

    if [[ "$script_or_cmd" == *.py ]]; then
        local remote_path="${REMOTE_PROJECT}/${script_or_cmd}"
        local remote_dir
        remote_dir=$(dirname "$remote_path")

        remote_cmd="source ~/miniforge3/etc/profile.d/conda.sh && \
conda activate ${CONDA_ENV} && \
cd ${remote_dir} && \
python3 $(basename "$remote_path") ${extra_args}"

        echo -e "${CYAN}🚀 Running: ${script_or_cmd} ${extra_args}${NC}"
        echo -e "${DIM}   env: conda ${CONDA_ENV}${NC}"
    else
        # Raw command
        remote_cmd="source ~/miniforge3/etc/profile.d/conda.sh && \
conda activate ${CONDA_ENV} 2>/dev/null; \
${script_or_cmd} ${extra_args}"

        echo -e "${CYAN}🚀 Running: ${script_or_cmd} ${extra_args}${NC}"
    fi

    echo ""
    echo -e "${YELLOW}══════════════ JETSON ══════════════${NC}"
    echo ""

    ssh -t jetson "$remote_cmd"
    local exit_code=$?

    echo ""
    echo -e "${YELLOW}════════════════════════════════════${NC}"

    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ Done${NC}"
    else
        echo -e "${RED}❌ Exit code: ${exit_code}${NC}"
    fi

    return $exit_code
}

# ============================================================
#   STATUS — quick Jetson health check
# ============================================================

cmd_status() {
    load_config
    check_connection

    echo ""
    echo -e "${CYAN}═══════════ JETSON STATUS ═══════════${NC}"
    echo ""

    ssh jetson bash -c "'
        echo \"🖥️  \$(hostname) — \$(hostname -I | awk \"{print \\\$1}\")\"
        echo \"⏰ \$(uptime -p 2>/dev/null || uptime)\"
        echo \"\"

        echo \"💾 Memory\"
        free -h | awk \"/Mem:/{printf \\\"   Used: %s / %s\\n\\\", \\\$3, \\\$2}\"

        echo \"\"
        echo \"💿 Disk\"
        df -h / | tail -1 | awk \"{printf \\\"   Used: %s / %s (%s)\\n\\\", \\\$3, \\\$2, \\\$5}\"

        echo \"\"
        echo \"🌡️  Temperature\"
        for zone in /sys/devices/virtual/thermal/thermal_zone*/; do
            if [ -f \"\${zone}type\" ] && [ -f \"\${zone}temp\" ]; then
                type=\$(cat \"\${zone}type\")
                temp=\$(cat \"\${zone}temp\")
                temp_c=\$(echo \"scale=1; \$temp / 1000\" | bc 2>/dev/null || echo \"?\")
                echo \"   \${type}: \${temp_c}°C\"
            fi
        done

        echo \"\"
        echo \"🐍 Python processes\"
        ps aux | grep \"[p]ython\" | awk \"{printf \\\"   PID %s — %s %s %s\\n\\\", \\\$2, \\\$11, \\\$12, \\\$13}\" || echo \"   None running\"
    '"

    echo ""
    echo -e "${CYAN}════════════════════════════════════${NC}"
}

# ============================================================
#   LOGS — tail remote files or dmesg
# ============================================================

cmd_logs() {
    load_config
    check_connection

    case "${1:-}" in
        --dmesg)
            echo -e "${CYAN}📋 Jetson kernel logs (Ctrl+C to stop)${NC}"
            ssh jetson "sudo dmesg --follow"
            ;;
        "")
            echo "Usage: ./jetson.sh logs <file_path|--dmesg>"
            ;;
        *)
            echo -e "${CYAN}📋 Tailing $1 (Ctrl+C to stop)${NC}"
            ssh jetson "tail -f $1"
            ;;
    esac
}

# ============================================================
#   IP — quickly show/update Jetson IP
# ============================================================

cmd_ip() {
    if [ -n "$1" ]; then
        # Update IP
        if [ -f "$CONFIG_FILE" ]; then
            source "$CONFIG_FILE"
        fi
        JETSON_IP="$1"
        JETSON_USER="${JETSON_USER:-tanmay-jetson}"
        save_config

        # Update SSH config too
        SSH_CONFIG="$HOME/.ssh/config"
        if [ -f "$SSH_CONFIG" ] && grep -q "^Host jetson" "$SSH_CONFIG"; then
            sed -i '' "s/HostName .*/HostName ${JETSON_IP}/" "$SSH_CONFIG" 2>/dev/null || \
            perl -i -pe "s/HostName .*/HostName ${JETSON_IP}/ if /HostName/ && \$seen++ == 0" "$SSH_CONFIG"
        fi

        echo -e "${GREEN}✅ Jetson IP updated to ${JETSON_IP}${NC}"

        # Quick test
        if ssh -o ConnectTimeout=3 jetson "echo ok" &>/dev/null; then
            echo -e "${GREEN}✅ Connection verified${NC}"
        else
            echo -e "${YELLOW}⚠️  Can't connect — is Jetson on?${NC}"
        fi
    else
        # Show current IP
        if [ -f "$CONFIG_FILE" ]; then
            source "$CONFIG_FILE"
            echo "$JETSON_IP"
        else
            echo -e "${RED}Not configured. Run: ./jetson.sh setup${NC}"
        fi
    fi
}

# ============================================================
#   MAIN — route commands
# ============================================================

usage() {
    echo ""
    echo -e "${BOLD}  jetson.sh — Mac → Jetson remote dev tool${NC}"
    echo ""
    echo -e "  ${BOLD}Setup${NC}"
    echo -e "    ./jetson.sh setup            Guided first-time setup (scan + SSH keys)"
    echo -e "    ./jetson.sh ip [NEW_IP]      Show or update Jetson IP"
    echo ""
    echo -e "  ${BOLD}Connect${NC}"
    echo -e "    ./jetson.sh shell            SSH into Jetson"
    echo -e "    ./jetson.sh status           GPU, memory, temp overview"
    echo -e "    ./jetson.sh logs <path>      Tail a remote log file"
    echo ""
    echo -e "  ${BOLD}Code${NC}"
    echo -e "    ./jetson.sh push [file]      Sync code → Jetson"
    echo -e "    ./jetson.sh pull [file]      Sync Jetson → Mac"
    echo -e "    ./jetson.sh run <script.py>  Sync + run on Jetson (streams output)"
    echo ""
}

case "${1:-}" in
    setup)    cmd_setup ;;
    shell)    cmd_shell ;;
    push)     shift; cmd_push "$@" ;;
    pull)     shift; cmd_pull "$@" ;;
    run)      shift; cmd_run "$@" ;;
    status)   cmd_status ;;
    logs)     shift; cmd_logs "$@" ;;
    ip)       shift; cmd_ip "$@" ;;
    help|-h|--help|"")  usage ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        usage
        exit 1
        ;;
esac
