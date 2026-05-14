#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
XCODE_PROJECT="$PROJECT_ROOT/native/ForgeApp/ForgeApp.xcodeproj"
SCHEME="Forge_macOS"
CONFIGURATION="Release"
DERIVED_DATA="$PROJECT_ROOT/build/native-macos"
APP_NAME="Forge"
APP_PATH="$DERIVED_DATA/Build/Products/$CONFIGURATION/${APP_NAME}.app"
STAGING_DIR="$PROJECT_ROOT/build/macos-installer"
DMG_NAME="Forge-macOS.dmg"
DMG_PATH="$PROJECT_ROOT/dist/$DMG_NAME"

mkdir -p "$PROJECT_ROOT/dist"
rm -rf "$DERIVED_DATA" "$STAGING_DIR"

xcodebuild \
  -project "$XCODE_PROJECT" \
  -scheme "$SCHEME" \
  -configuration "$CONFIGURATION" \
  -destination 'generic/platform=macOS' \
  -derivedDataPath "$DERIVED_DATA" \
  CODE_SIGNING_ALLOWED=NO \
  build

if [[ ! -d "$APP_PATH" ]]; then
  echo "Expected app bundle not found at: $APP_PATH" >&2
  exit 1
fi

mkdir -p "$STAGING_DIR"
cp -R "$APP_PATH" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"
rm -f "$DMG_PATH"

hdiutil create \
  -volname "Forge" \
  -srcfolder "$STAGING_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "Created installer: $DMG_PATH"
