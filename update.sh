#!/bin/bash
set -e

# ============================================================
# justask - Update script
# Run as: sudo ./update.sh  (after git pull)
# ============================================================

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$INSTALL_DIR/venv"
USERNAME="justask"

die() {
    echo "ERROR: $1" >&2
    exit 1
}

# ============================================================
echo ""
echo "=== justask Update ==="
echo ""

# --- 1. Root check ---------------------------------------------

if [ "$(id -u)" -ne 0 ]; then
    die "Please run with sudo: sudo ./update.sh"
fi

# --- 2. Sanity checks ------------------------------------------

[ -f "$INSTALL_DIR/requirements.txt" ] || die "requirements.txt not found. Are you in the right directory?"
[ -x "$VENV/bin/pip" ]                 || die "Virtual environment not found. Run setup.sh first."
id "$USERNAME" &>/dev/null             || die "System user '$USERNAME' not found. Run setup.sh first."

echo "Install directory: $INSTALL_DIR"
echo ""
read -p "Continue? (y/N): " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Aborted."
    exit 0
fi
echo ""

# --- 3. Stop service -------------------------------------------

echo "--- Stopping service ---"
systemctl stop justask
echo "  Stopped."
echo ""

# --- 4. Update dependencies ------------------------------------

echo "--- Updating dependencies ---"
"$VENV/bin/pip" install --upgrade pip --quiet
"$VENV/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet
echo "  Done."
echo ""

# --- 5. Database migrations ------------------------------------

echo "--- Database migrations ---"

# Backup the database before migrating.
DB="$INSTALL_DIR/instance/justask.db"
if [ -f "$DB" ]; then
    BACKUP="${DB}.backup-$(date +%Y%m%d-%H%M%S)"
    cp "$DB" "$BACKUP"
    chmod 600 "$BACKUP"
    echo "  Backup: $BACKUP"
fi

if [ -d "$INSTALL_DIR/migrations" ]; then
    sudo -u "$USERNAME" "$VENV/bin/flask" --app "$INSTALL_DIR/app.py" db upgrade
    echo "  Done."
else
    echo "  No migrations directory found - skipping."
fi
echo ""

# --- 6. Fix permissions ----------------------------------------

echo "--- Permissions ---"
chown -R "$USERNAME:$USERNAME" "$INSTALL_DIR"
chmod 750 "$INSTALL_DIR"
chmod 750 "$INSTALL_DIR/instance"
if [ -f "$INSTALL_DIR/config.env" ]; then
    chmod 600 "$INSTALL_DIR/config.env"
fi
if [ -f "$INSTALL_DIR/instance/justask.db" ]; then
    chmod 600 "$INSTALL_DIR/instance/justask.db"
fi
echo "  Done."
echo ""

# --- 7. Restart service ----------------------------------------

echo "--- Starting service ---"
systemctl start justask
echo "  Started."

# --- 8. Done ---------------------------------------------------

echo ""
echo "=========================================="
echo "  Update complete!"
echo "=========================================="
echo ""
echo "View logs: sudo journalctl -u justask -f"
echo ""
