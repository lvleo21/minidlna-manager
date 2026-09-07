#!/usr/bin/env bash
# Installs a built .deb, checks that what it ships actually works, then purges
# it and checks nothing is left behind. Used by CI (see .github/workflows/)
# and runnable by hand inside a Debian/Ubuntu container -- see README.md.
#
# Usage: ./test-deb.sh dist/minidlna-manager_0.1.0-1_all.deb
set -euo pipefail

deb="${1:?usage: test-deb.sh <package.deb>}"
deb="$(cd "$(dirname "$deb")" && pwd)/$(basename "$deb")"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

sudo=()
[ "$(id -u)" -eq 0 ] || sudo=(sudo)
export DEBIAN_FRONTEND=noninteractive

echo "--> installing $(basename "$deb")"
"${sudo[@]}" apt-get update -qq
"${sudo[@]}" apt-get install -y -qq desktop-file-utils xvfb
"${sudo[@]}" apt-get install -y -qq "$deb"

echo "--> app code resolves on the launcher's sys.path"
python3 -c 'import sys; sys.path.insert(0, "/usr/share/minidlna-manager"); import ui.app, core.service_client'

echo "--> the main window opens on this distro's GTK/libadwaita"
xvfb-run -a python3 "$here/ui-smoke.py"

echo "--> postinst byte-compiled the app"
test -d /usr/share/minidlna-manager/core/__pycache__

echo "--> helper runs and rejects a subcommand outside its whitelist"
/usr/lib/minidlna-manager/helper --help >/dev/null
! /usr/lib/minidlna-manager/helper definitely-not-a-subcommand >/dev/null 2>&1

echo "--> polkit action parses and points at the installed helper"
python3 - <<'PY'
import xml.etree.ElementTree as ET
root = ET.parse("/usr/share/polkit-1/actions/com.lvleo21.minidlnamanager.policy").getroot()
paths = [a.text for a in root.iter("annotate")
         if a.get("key") == "org.freedesktop.policykit.exec.path"]
assert paths == ["/usr/lib/minidlna-manager/helper"], paths
PY

echo "--> desktop entry and man page are in place"
desktop-file-validate /usr/share/applications/minidlna-manager.desktop
if grep -rqs "path-exclude.*share/man" /etc/dpkg/dpkg.cfg /etc/dpkg/dpkg.cfg.d/; then
    # Ubuntu's container images tell dpkg to drop man pages on unpack, so the
    # file legitimately isn't there; lintian already checked it ships in the .deb.
    echo "    (dpkg is configured to exclude man pages here; skipping that check)"
else
    test -e /usr/share/man/man1/minidlna-manager.1.gz
    # minimal Debian images ship no man-db, so only check indexing where man exists
    ! command -v man >/dev/null || man -w minidlna-manager >/dev/null
fi

echo "--> purging"
"${sudo[@]}" apt-get purge -y -qq minidlna-manager
# py3clean in prerm must leave no orphan __pycache__ holding the dir open
test ! -e /usr/share/minidlna-manager
test ! -e /usr/bin/minidlna-manager
test ! -e /usr/lib/minidlna-manager

echo "OK"
