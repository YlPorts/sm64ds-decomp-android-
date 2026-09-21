#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
SDK=${ANDROID_HOME:?Set ANDROID_HOME}
BT="$SDK/build-tools/35.0.0"
JAR="$SDK/platforms/android-35/android.jar"
NATIVE=${1:?Pass native build output}
OUT=${2:?Pass APK output directory}
mkdir -p "$OUT"
DEST=$(cd "$OUT" && pwd)
OUT=$(mktemp -d "$DEST/.apk-build.XXXXXX")
trap 'rm -rf "$OUT"' EXIT
mkdir -p "$OUT/classes" "$OUT/gen" "$OUT/dex" "$OUT/package/lib/armeabi-v7a" "$OUT/assets"
cp "$NATIVE/libsm64ds_engine.so" "$NATIVE/libsm64ds_bootstrap.so" "$OUT/package/lib/armeabi-v7a/"
# Only reconstruction metadata. Never put ROM-derived payloads into the APK.
cp "$ROOT/build/assets/romdata.recipe.tsv" "$ROOT/build/assets/romdata.manifest" "$OUT/assets/"
python3 - "$ROOT" "$OUT" <<'PY'
import json,sys
from pathlib import Path
root,out=map(Path,sys.argv[1:])
j=json.loads((root/'build/assets/android-preparation.json').read_text())
(out/'assets/build.properties').write_text('rom.sha256='+j['rom_sha256']+'\n')
PY
"$BT/aapt2" compile --dir "$ROOT/android/touch-ui/res" -o "$OUT/res.zip"
"$BT/aapt2" link -I "$JAR" --manifest "$HERE/AndroidManifest.xml" --java "$OUT/gen" -A "$OUT/assets" -o "$OUT/unsigned.apk" "$OUT/res.zip"
rg --files "$HERE/java" "$OUT/gen" -g '*.java' > "$OUT/sources.txt"
for SOURCE in TouchOverlay TouchControls DsLayout;do
    echo "$ROOT/android/touch-ui/java/org/ylports/sm64ds/controls/$SOURCE.java" >> "$OUT/sources.txt"
done
javac --release 8 -encoding UTF-8 -classpath "$JAR" -d "$OUT/classes" @"$OUT/sources.txt"
jar cf "$OUT/classes.jar" -C "$OUT/classes" .
"$BT/d8" --min-api 23 --lib "$JAR" --output "$OUT/dex" "$OUT/classes.jar"
cp "$OUT/dex/classes.dex" "$OUT/package/"
(cd "$OUT/package" && zip -q -r "$OUT/unsigned.apk" classes.dex lib)
"$BT/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"
KEY="$DEST/engine-debug.jks"
if [[ ! -f "$KEY" ]];then
    keytool -genkeypair -keystore "$KEY" -storepass android -keypass android -alias androiddebugkey \
      -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=SM64DS Android Development,O=Development,C=PA'
fi
"$BT/apksigner" sign --ks "$KEY" --ks-pass pass:android --key-pass pass:android --out "$DEST/SM64DS-Motor-Prueba.apk" "$OUT/aligned.apk"
"$BT/apksigner" verify --verbose "$DEST/SM64DS-Motor-Prueba.apk" > "$DEST/signature.txt"
python3 - "$DEST/SM64DS-Motor-Prueba.apk" <<'PY'
import sys,zipfile
with zipfile.ZipFile(sys.argv[1]) as apk:
    assets={name for name in apk.namelist() if name.startswith('assets/') and not name.endswith('/')}
    assert assets == {'assets/romdata.recipe.tsv','assets/romdata.manifest','assets/build.properties'}, assets
    libraries={name for name in apk.namelist() if name.endswith('.so')}
    assert libraries == {'lib/armeabi-v7a/libsm64ds_engine.so','lib/armeabi-v7a/libsm64ds_bootstrap.so'}, libraries
PY
sha256sum "$DEST/SM64DS-Motor-Prueba.apk" > "$DEST/SHA256SUMS.txt"
echo "$DEST/SM64DS-Motor-Prueba.apk"
