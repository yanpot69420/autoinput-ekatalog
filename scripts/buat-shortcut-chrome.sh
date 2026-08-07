#!/bin/bash
# Membuat pintasan "Chrome Portal INAPROC.app" -- pembuka Chrome berport debug
# yang berdiri sendiri, terpisah dari jendela aplikasi.
#
#   ./scripts/buat-shortcut-chrome.sh              -> taruh di folder proyek
#   ./scripts/buat-shortcut-chrome.sh ~/Applications -> taruh di folder lain
#
# Gunanya: Chrome tidak lagi terikat pada aplikasi. Buka sekali lewat pintasan
# ini, login, lalu biarkan terbuka berhari-hari. Aplikasi cukup menempel lewat
# "Uji koneksi browser" dan tidak pernah menjalankan maupun menutup Chrome.
#
# Profilnya mengikuti pilihan yang tersimpan di aplikasi, jadi keduanya selalu
# menunjuk browser yang sama.

set -euo pipefail

PROYEK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TUJUAN="${1:-$PROYEK}"
APP="$TUJUAN/Chrome Portal INAPROC.app"
PYTHON="$PROYEK/.venv/bin/python"

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
  <key>CFBundleName</key><string>Chrome Portal INAPROC</string>
  <key>CFBundleDisplayName</key><string>Chrome Portal INAPROC</string>
  <key>CFBundleIdentifier</key><string>id.inaproc.autoinput.chrome</string>
  <key>CFBundleVersion</key><string>0.1.0</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>jalankan</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

# Pintasan ini tidak membuka jendela Terminal, jadi pesan gagal tidak akan
# terlihat di mana pun kalau cuma dicetak. Karena itu kegagalan ditampilkan
# sebagai kotak peringatan macOS -- terutama "Chrome harus ditutup dulu", yang
# tanpa penjelasan cuma terlihat seperti pintasan yang tidak berfungsi.
#
# Pesannya dikirim sebagai argumen ke osascript, bukan disisipkan ke dalam
# skripnya: isinya berbaris banyak dan bertanda kutip, dan begitu disisipkan
# AppleScript-nya gagal diurai -- peringatannya justru tidak pernah muncul.
cat > "$APP/Contents/MacOS/jalankan" <<LAUNCHER
#!/bin/bash
# Dibuat oleh scripts/buat-shortcut-chrome.sh -- jangan diedit langsung.
cd "$PROYEK" || exit 1
if ! pesan=\$("$PYTHON" -m inaproc_autoinput.buka_chrome 2>&1); then
  osascript \\
    -e 'on run {pesan}' \\
    -e 'display alert "Chrome Portal INAPROC" message pesan' \\
    -e 'end run' -- "\$pesan" >/dev/null 2>&1
  exit 1
fi
LAUNCHER

chmod +x "$APP/Contents/MacOS/jalankan"

echo "Pintasan dibuat: $APP"
echo "Klik dua kali untuk membuka Chrome portal, lalu login sekali di sana."
