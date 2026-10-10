#!/usr/bin/env bash
# Build "HSC Companion.app" and a drag-to-Applications DMG. Run on a Mac from the repo root.
set -euo pipefail
VERSION=$(cat VERSION)
python -m pip install -r requirements.txt pyinstaller
pyinstaller packaging/hsc_companion.spec --noconfirm --clean
APP="dist/HSC Companion.app"
"$APP/Contents/MacOS/HSC Companion" --self-test
codesign --force --deep --sign - "$APP"   # ad-hoc signature (not notarised)
STAGE=$(mktemp -d)
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp packaging/INSTALL-macOS.txt "$STAGE/Read me first.txt"
ARCH=$(uname -m)
DMG="dist/HSC-Companion-${VERSION}-macOS-${ARCH}.dmg"
hdiutil create -volname "HSC Companion ${VERSION}" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
echo "Built $DMG"
