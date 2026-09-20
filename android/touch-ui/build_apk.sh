#!/usr/bin/env bash
# Build a controls-only diagnostic APK with SDK/NDK, without Gradle downloads.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SDK=${ANDROID_HOME:?Set ANDROID_HOME}
NDK=${SM64DS_NDK:-"$SDK/ndk/28.2.13676358"}
BT="$SDK/build-tools/35.0.0"
JAR="$SDK/platforms/android-35/android.jar"
OUT=${1:-"$HERE/build-apk"}
mkdir -p "$OUT";OUT=$(cd "$OUT" && pwd)
mkdir -p "$OUT/classes" "$OUT/gen" "$OUT/dex" "$OUT/package/lib"
for ABI in armeabi-v7a x86;do
    cmake -S "$HERE" -B "$OUT/native-$ABI" -G Ninja \
      -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
      -DANDROID_ABI="$ABI" -DANDROID_PLATFORM=android-23 -DANDROID_STL=c++_static -DCMAKE_BUILD_TYPE=Release
    cmake --build "$OUT/native-$ABI" --parallel 2
    mkdir -p "$OUT/package/lib/$ABI"
    cp "$OUT/native-$ABI/libsm64ds_controls.so" "$OUT/package/lib/$ABI/"
done
"$BT/aapt2" compile --dir "$HERE/res" -o "$OUT/res.zip"
"$BT/aapt2" link -I "$JAR" --manifest "$HERE/AndroidManifest.xml" --java "$OUT/gen" -o "$OUT/unsigned.apk" "$OUT/res.zip"
find "$HERE/java" "$OUT/gen" -name '*.java' > "$OUT/sources.txt"
javac --release 8 -encoding UTF-8 -classpath "$JAR" -d "$OUT/classes" @"$OUT/sources.txt"
jar cf "$OUT/classes.jar" -C "$OUT/classes" .
"$BT/d8" --min-api 23 --lib "$JAR" --output "$OUT/dex" "$OUT/classes.jar"
cp "$OUT/dex/classes.dex" "$OUT/package/"
(cd "$OUT/package" && zip -q -r "$OUT/unsigned.apk" classes.dex lib)
"$BT/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"
# Isolated disposable debug identity: no game save data or production signing key.
KEY="$OUT/controls-debug.jks"
if [[ ! -f "$KEY" ]];then
    keytool -genkeypair -keystore "$KEY" -storepass android -keypass android -alias androiddebugkey \
      -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=SM64DS Controls Test,O=Development,C=PA'
fi
"$BT/apksigner" sign --ks "$KEY" --ks-pass pass:android --key-pass pass:android --out "$OUT/SM64DS-Controles-Prueba.apk" "$OUT/aligned.apk"
"$BT/apksigner" verify --verbose "$OUT/SM64DS-Controles-Prueba.apk" | tee "$OUT/signature.txt"
sha256sum "$OUT/SM64DS-Controles-Prueba.apk" > "$OUT/SHA256SUMS.txt"
echo 'Built controls diagnostic only, NOT Super Mario 64 DS gameplay.'
