#!/usr/bin/env bash
# Builds the minidlna-manager .deb straight from the working tree this script
# lives in, using only dpkg-deb -- no debhelper, so it also runs on the
# Arch-based development machine (see README.md).
#
# Usage: ./build-deb.sh [output-dir]   (default: packaging/deb/dist)
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$here/../.." && pwd)"
out_dir="${1:-$here/dist}"
mkdir -p "$out_dir"
out_dir="$(cd "$out_dir" && pwd)"

pkgname="minidlna-manager"
debrel="$(sed -n '1s/.*(\(.*\)).*/\1/p' "$here/changelog")"   # e.g. 0.1.0-1
version="${debrel%-*}"

pyver="$(sed -n 's/^version = "\(.*\)"/\1/p' "$repo_root/pyproject.toml" | head -1)"
if [[ "$version" != "$pyver" ]]; then
  echo "error: changelog version ($version) != pyproject version ($pyver)" >&2
  echo "       bump packaging/deb/changelog before building." >&2
  exit 1
fi

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
chmod 755 "$stage"   # mktemp -d is 0700; the package root must be world-readable

# --- payload -----------------------------------------------------------------
# core/ and ui/ go to a private dir instead of dist-packages: those top-level
# names are too generic to claim in the shared system namespace.
install -d -m 755 "$stage/usr/share/$pkgname"
for pkg in core ui; do
  (cd "$repo_root" && find "$pkg" -name '__pycache__' -prune -o -name '*.py' -print) \
    | while read -r f; do
        install -Dm644 "$repo_root/$f" "$stage/usr/share/$pkgname/$f"
      done
done

install -Dm755 "$here/launcher"                        "$stage/usr/bin/$pkgname"
install -Dm755 "$repo_root/helper/minidlna_manager_helper.py" \
                                                       "$stage/usr/lib/$pkgname/helper"
install -Dm644 "$repo_root/policy/com.leo.minidlnamanager.policy" \
                        "$stage/usr/share/polkit-1/actions/com.leo.minidlnamanager.policy"
install -Dm644 "$repo_root/packaging/arch/$pkgname.desktop" \
                                    "$stage/usr/share/applications/$pkgname.desktop"
install -Dm644 "$here/copyright"       "$stage/usr/share/doc/$pkgname/copyright"
gzip -9nc "$here/changelog" > "$stage/usr/share/doc/$pkgname/changelog.Debian.gz"
chmod 644 "$stage/usr/share/doc/$pkgname/changelog.Debian.gz"

install -d -m 755 "$stage/usr/share/man/man1"
gzip -9nc "$here/$pkgname.1" > "$stage/usr/share/man/man1/$pkgname.1.gz"
chmod 644 "$stage/usr/share/man/man1/$pkgname.1.gz"

# --- control archive ---------------------------------------------------------
install -d -m 755 "$stage/DEBIAN"
installed_size="$(du -k -s --apparent-size "$stage" | cut -f1)"
sed -e "s/@VERSION@/$debrel/" -e "s/@INSTALLED_SIZE@/$installed_size/" \
  "$here/control.in" > "$stage/DEBIAN/control"
chmod 644 "$stage/DEBIAN/control"

(cd "$stage" && find . -path ./DEBIAN -prune -o -type f -print0 \
  | sed -z 's|^\./||' | xargs -0 md5sum > DEBIAN/md5sums)
chmod 644 "$stage/DEBIAN/md5sums"

install -m 755 "$here/postinst" "$here/prerm" "$stage/DEBIAN/"

# --- build -------------------------------------------------------------------
deb="$out_dir/${pkgname}_${debrel}_all.deb"
dpkg-deb -Zxz --root-owner-group --build "$stage" "$deb" >/dev/null
echo "$deb"
