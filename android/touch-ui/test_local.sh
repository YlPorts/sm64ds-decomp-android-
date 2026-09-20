#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
OUT=${1:-"$ROOT/build/touch-ui-local"}
mkdir -p "$OUT/classes"
JHOME=${JAVA_HOME:-$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")}
"${CXX:-g++}" -std=c++17 -O2 -shared -fPIC -pthread -I"$JHOME/include" -I"$JHOME/include/linux" \
  -I"$ROOT/port" -I"$ROOT/android/full-engine" "$HERE/native/bridge.cpp" \
  "$ROOT/android/full-engine/pad_android.cpp" -o "$OUT/libsm64ds_controls.so"
javac -d "$OUT/classes" "$HERE/java/org/ylports/sm64ds/controls/TouchControls.java" \
  "$HERE/java/org/ylports/sm64ds/controls/NativeBridge.java" "$HERE/java/org/ylports/sm64ds/controls/DsLayout.java" "$HERE/tests/ControlsTest.java"
java -Djava.library.path="$OUT" -cp "$OUT/classes" org.ylports.sm64ds.controls.ControlsTest
