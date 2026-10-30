#!/bin/sh
set -eu
cd "$(dirname "$0")"
NETFELIX_TOOLS="${XDG_DATA_HOME:-$HOME/.local/share}/netfelix-tools"
export JAVA_HOME="${JAVA_HOME:-$NETFELIX_TOOLS/jdk}"
export ANDROID_HOME="${ANDROID_HOME:-$NETFELIX_TOOLS/android-sdk}"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"
./check-motion.sh
./gradlew :app:assembleDebug :app:lintDebug
