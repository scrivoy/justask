#!/bin/bash
set -e

# ============================================================
# justask - Uninstall script
# Run as: sudo ./uninstall.sh
# ============================================================

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
USERNAME="justask"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Please run with sudo: sudo ./uninstall.sh"
    exit 1
fi

echo ""
echo "=== justask Uninstall ==="
echo ""
echo "This will remove:"
echo "  - systemd service (justask)"
echo "  - System user '$USERNAME'"
echo "  - All application files in $INSTALL_DIR"
echo "  - The SQLite database (all data will be lost!)"
echo ""
read -p "Are you sure? This cannot be undone. (yes/N): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi
echo ""

# Stop and disable service
if systemctl is-active --quiet justask 2>/dev/null; then
    echo "Stopping service..."
    systemctl stop justask
fi
if systemctl is-enabled --quiet justask 2>/dev/null; then
    echo "Disabling service..."
    systemctl disable justask --quiet
fi
if [ -f /etc/systemd/system/justask.service ]; then
    echo "Removing service file..."
    rm /etc/systemd/system/justask.service
    systemctl daemon-reload
fi

# Remove system user
if id "$USERNAME" &>/dev/null; then
    echo "Removing system user '$USERNAME'..."
    userdel "$USERNAME"
fi

# Remove application directory
echo "Removing application files..."
rm -rf "$INSTALL_DIR"

echo ""
echo "=========================================="
echo "  Uninstall complete."
echo "=========================================="
echo ""
