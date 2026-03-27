#!/bin/bash
set -e

# ============================================================
# justask - Interactive setup script
# Run as: sudo ./setup.sh
# ============================================================

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$INSTALL_DIR/venv"
USERNAME="justask"

# --- Helper functions -----------------------------------------------

die() {
    echo "ERROR: $1" >&2
    exit 1
}

# Read a password with confirmation and minimum length check.
# Usage: read_password "Label" VARNAME
read_password() {
    local label="$1"
    local varname="$2"
    local pw1 pw2

    while true; do
        read -s -p "$label: " pw1
        echo
        if [ ${#pw1} -lt 8 ]; then
            echo "  Minimum 8 characters required. Try again."
            continue
        fi
        read -s -p "$label (confirm): " pw2
        echo
        if [ "$pw1" != "$pw2" ]; then
            echo "  Passwords do not match. Try again."
            continue
        fi
        eval "$varname=\$pw1"
        break
    done
}

# Hash a password via bcrypt using the project venv.
hash_password() {
    "$VENV/bin/python" -c "
import bcrypt, sys
pw = sys.argv[1].encode()
print(bcrypt.hashpw(pw, bcrypt.gensalt()).decode())
" "$1"
}

# ============================================================
echo ""
echo "=== justask Setup ==="
echo ""

# --- 1. Root check -------------------------------------------------

if [ "$(id -u)" -ne 0 ]; then
    die "Please run with sudo: sudo ./setup.sh"
fi

# --- 2. Overview + confirmation ------------------------------------

echo "This script will:"
echo "  - Install python3-venv if missing (apt)"
echo "  - Create a system user 'justask'"
echo "  - Set up a Python virtual environment + dependencies"
echo "  - Generate config.env with your passwords"
echo "  - Initialize the SQLite database"
echo "  - Install and start a systemd service"
echo ""
read -p "Continue? (y/N): " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Aborted."
    exit 0
fi
echo ""

# --- 3. System dependencies ----------------------------------------

echo "--- Checking system dependencies ---"

if ! command -v python3 &>/dev/null; then
    die "python3 not found. Install it first (e.g. apt install python3 python3-venv python3-pip)."
fi

# Auto-install python3-venv if missing (Debian/Ubuntu)
# The real test is whether ensurepip is available - venv --help may succeed without it
if ! python3 -c "import ensurepip" &>/dev/null 2>&1; then
    echo "  python3-venv not found. Installing..."
    if command -v apt-get &>/dev/null; then
        PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        apt-get install -y "python${PYTHON_VERSION}-venv" --quiet || die "Failed to install python3-venv. Run: apt install python${PYTHON_VERSION}-venv"
    else
        die "python3-venv is missing. Please install it manually."
    fi
fi

echo "  OK"
echo ""
echo "Install directory: $INSTALL_DIR"
echo ""

# --- 3. Interactive prompts -----------------------------------------

echo "--- Passwords ---"
echo ""
echo "Staff password: for employee login (dashboard, create questionnaires)"
read_password "Staff password" STAFF_PW
echo ""

echo "Admin password: for admin login (manage leaders, export, delete links)"
while true; do
    read_password "Admin password" ADMIN_PW
    if [ "$ADMIN_PW" = "$STAFF_PW" ]; then
        echo "  Admin and staff passwords must be different. Try again."
        echo ""
        continue
    fi
    break
done
echo ""

echo "--- Base URL ---"
echo ""
read -p "Base URL (e.g. https://feedback.example.com): " BASE_URL
# Strip trailing slash
BASE_URL="${BASE_URL%/}"
if [ -z "$BASE_URL" ]; then
    die "Base URL cannot be empty."
fi
echo ""

# --- Check existing config.env --------------------------------------

if [ -f "$INSTALL_DIR/config.env" ]; then
    echo "config.env already exists."
    read -p "Overwrite? (y/N): " OVERWRITE
    if [ "$OVERWRITE" != "y" ] && [ "$OVERWRITE" != "Y" ]; then
        echo "  Keeping existing config.env."
        SKIP_CONFIG=1
    fi
    echo ""
fi

# --- 4. System user ------------------------------------------------

echo "--- System user ---"
if id "$USERNAME" &>/dev/null; then
    echo "  User '$USERNAME' already exists."
else
    echo "  Creating system user '$USERNAME'..."
    useradd --system --shell /usr/sbin/nologin --home-dir "$INSTALL_DIR" "$USERNAME"
fi

# --- 5. Python venv + dependencies ---------------------------------

echo ""
echo "--- Python environment ---"

# Recreate venv if missing or broken (e.g. from a previous failed attempt)
if [ ! -x "$VENV/bin/pip" ]; then
    echo "  Creating virtual environment..."
    rm -rf "$VENV"
    python3 -m venv "$VENV"
fi

echo "  Installing dependencies..."
"$VENV/bin/pip" install --upgrade pip --quiet
"$VENV/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet

echo "  Done."

# --- 6. Generate config.env ----------------------------------------

if [ "${SKIP_CONFIG:-0}" != "1" ]; then
    echo ""
    echo "--- Configuration ---"

    SECRET_KEY=$("$VENV/bin/python" -c "import secrets; print(secrets.token_hex(32))")

    echo "  Hashing staff password..."
    STAFF_HASH=$(hash_password "$STAFF_PW")

    echo "  Hashing admin password..."
    ADMIN_HASH=$(hash_password "$ADMIN_PW")

    cp "$INSTALL_DIR/config.env.example" "$INSTALL_DIR/config.env"

    # Fill in generated values. Python handles special chars in bcrypt hashes safely.
    SECRET_KEY="$SECRET_KEY" STAFF_HASH="$STAFF_HASH" ADMIN_HASH="$ADMIN_HASH" BASE_URL_VAL="$BASE_URL" \
    "$VENV/bin/python" - "$INSTALL_DIR/config.env" <<'PYEOF'
import os, re, sys
path = sys.argv[1]
content = open(path).read()
for key, val in [
    ('SECRET_KEY',          os.environ['SECRET_KEY']),
    ('STAFF_PASSWORD_HASH', os.environ['STAFF_HASH']),
    ('ADMIN_PASSWORD_HASH', os.environ['ADMIN_HASH']),
    ('BASE_URL',            os.environ['BASE_URL_VAL']),
]:
    content = re.sub(rf'^{key}=.*', f'{key}={val}', content, flags=re.MULTILINE)
open(path, 'w').write(content)
PYEOF

    chmod 600 "$INSTALL_DIR/config.env"
    echo "  config.env created."
fi

# --- 7. Set permissions + init database -----------------------------

echo ""
echo "--- Database ---"

mkdir -p "$INSTALL_DIR/instance"
chown -R "$USERNAME:$USERNAME" "$INSTALL_DIR"

# Lock down directory and file permissions.
chmod 750 "$INSTALL_DIR"
chmod 750 "$INSTALL_DIR/instance"

echo "  Initializing database..."
sudo -u "$USERNAME" "$VENV/bin/python" "$INSTALL_DIR/init_db.py"

# Ensure the database file is not world-readable.
if [ -f "$INSTALL_DIR/instance/justask.db" ]; then
    chmod 600 "$INSTALL_DIR/instance/justask.db"
fi

# --- 8. systemd service --------------------------------------------

echo ""
echo "--- systemd service ---"

cat > /etc/systemd/system/justask.service <<SVCEOF
[Unit]
Description=justask - Customer Feedback Tool
After=network.target

[Service]
User=$USERNAME
Group=$USERNAME
WorkingDirectory=$INSTALL_DIR
Environment=FLASK_ENV=production
ExecStart=$VENV/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 "app:app"
Restart=always

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable justask --quiet
systemctl restart justask

echo "  Service installed and started."

# --- 9. Done -------------------------------------------------------

echo ""
echo "=========================================="
echo "  Setup complete!"
echo "=========================================="
echo ""
echo "justask is running on: http://127.0.0.1:8000"
echo "Set up your reverse proxy (Caddy/nginx) to point to this address."
echo ""
echo "  Staff login:  $BASE_URL"
echo "  Admin login:  $BASE_URL (use admin password)"
echo ""
echo "Configuration:  $INSTALL_DIR/config.env"
echo ""
echo "Manage service: sudo systemctl [start|stop|restart|status] justask"
echo "View logs:      sudo journalctl -u justask -f"
echo "Uninstall:      sudo $INSTALL_DIR/uninstall.sh"
echo ""
