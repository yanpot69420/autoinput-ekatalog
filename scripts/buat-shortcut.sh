#!/bin/bash
# Membuat pintasan "INAPROC Autoinput.app" yang bisa diklik dua kali dari
# Finder atau Dock, tanpa membuka jendela Terminal.
#
#   ./scripts/buat-shortcut.sh              -> taruh di folder proyek
#   ./scripts/buat-shortcut.sh ~/Applications -> taruh di folder lain
#
# Pintasannya hanya penunjuk: kode dan lingkungan Python tetap di folder
# proyek, jadi setiap perbaikan langsung ikut terpakai tanpa dibuat ulang.

set -euo pipefail

PROYEK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TUJUAN="${1:-$PROYEK}"
APP="$TUJUAN/INAPROC Autoinput.app"
PYTHON="$PROYEK/.venv/bin/inaproc-autoinput"

if [ ! -x "$PYTHON" ]; then
  echo "Belum ada $PYTHON" >&2
  echo "Siapkan dulu:  python3 -m venv .venv && .venv/bin/pip install -e . playwright" >&2
  exit 1
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>INAPROC Autoinput</string>
  <key>CFBundleDisplayName</key><string>INAPROC Autoinput</string>
  <key>CFBundleIdentifier</key><string>id.inaproc.autoinput</string>
  <key>CFBundleVersion</key><string>0.1.0</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>jalankan</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/jalankan" <<LAUNCHER
#!/bin/bash
# Dibuat oleh scripts/buat-shortcut.sh -- jangan diedit langsung.
cd "$PROYEK" || exit 1
exec "$PYTHON" "\$@"
LAUNCHER

chmod +x "$APP/Contents/MacOS/jalankan"

echo "Pintasan dibuat: $APP"
echo
echo "Klik dua kali untuk menjalankan. Supaya menetap di Dock, jalankan sekali,"
echo "lalu klik kanan ikonnya di Dock -> Options -> Keep in Dock."
