#!/usr/bin/env bash
# Woohoo! Flight School - Android APK builder, one click on Bazzite (and other Fedora Atomic / immutable desktops).
#
#   ./android-builder.sh            set up (first run) and open the builder window
#   ./android-builder.sh --install  also add "Woohoo! Flight School (Android builder)" to the app menu
#   ./android-builder.sh --remove   delete the container (the SDK and your builds in ~/.local/share/pwr-android stay)
#
# Bazzite's system is read-only, so the build tools (Python with Tk, a JDK, CMake, Ninja, git) live in a distrobox
# container named wfs-android. Your home folder is shared with it: the Android SDK, the work files and the finished APK
# go to ~/.local/share/pwr-android. The first run downloads the container image and later the Android SDK and NDK
# (about 3 GB in all); after that it opens straight away.
set -euo pipefail

BOX=wfs-android
IMAGE=registry.fedoraproject.org/fedora-toolbox:41
PACKAGES="python3 python3-tkinter java-21-openjdk-devel cmake ninja-build git unzip which xdg-utils"
HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"

say() { printf '\033[1m%s\033[0m\n' "$*"; }

install_entry() {
    local apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications" icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
    mkdir -p "$apps" "$icons"
    cp "$HERE/launcher/assets/icon@2x.png" "$icons/woohoo-android-builder.png"
    cat > "$apps/woohoo-android-builder.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Woohoo! Flight School (Android builder)
Comment=Build an Android APK of Pilotwings Resort from your own dump
Exec="$HERE/android-builder.sh"
Icon=woohoo-android-builder
Terminal=true
Categories=Game;Development;
EOF
    update-desktop-database "$apps" >/dev/null 2>&1 || true
    say "Added to the app menu: Woohoo! Flight School (Android builder)"
}

# ---- inside the container: open the builder window
if [ "${1:-}" = "--inside" ]; then
    shift
    exec python3 "$HERE/launcher/android_launcher.py" "$@"
fi

case "${1:-}" in
    --install) install_entry ;;
    --remove)
        distrobox rm --force "$BOX"; say "Removed the $BOX container."; exit 0 ;;
    "") ;;
    *) echo "usage: $0 [--install | --remove]"; exit 2 ;;
esac

if [ -f /run/.containerenv ] || [ -f /.dockerenv ]; then   # already in a toolbox/distrobox with the tools: just run
    exec "$0" --inside
fi

if ! command -v distrobox >/dev/null 2>&1; then
    echo "distrobox not found. Bazzite ships it; on other systems install distrobox and podman first." >&2
    read -rp "Press Enter to close." _ || true; exit 1
fi

if ! distrobox list --no-color 2>/dev/null | awk -F'|' '{gsub(/ /,"",$2); print $2}' | grep -qx "$BOX"; then
    say "First run: creating the '$BOX' container with the build tools (a few minutes)..."
    distrobox create --yes --name "$BOX" --image "$IMAGE" --additional-packages "$PACKAGES"
fi

say "Opening the builder window (this terminal shows the build log too; closing it closes the builder)."
if ! distrobox enter "$BOX" -- "$HERE/android-builder.sh" --inside; then
    echo; echo "The builder exited with an error (see above)."
    read -rp "Press Enter to close." _ || true
fi
