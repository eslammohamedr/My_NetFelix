#!/bin/sh
set -eu
cd "$(dirname "$0")"
CHECK_DIR=$(mktemp -d)
trap 'rm -rf "$CHECK_DIR"' EXIT
javac -d "$CHECK_DIR" app/src/main/java/com/netfelix/watch/DirectionDetector.java tests/DirectionDetectorCheck.java app/src/main/java/com/netfelix/watch/DirectionCalibration.java tests/DirectionCalibrationCheck.java app/src/main/java/com/netfelix/watch/TouchGesture.java tests/TouchGestureCheck.java app/src/main/java/com/netfelix/watch/CommandBatch.java tests/CommandBatchCheck.java
java -cp "$CHECK_DIR" DirectionDetectorCheck
java -cp "$CHECK_DIR" DirectionCalibrationCheck
java -cp "$CHECK_DIR" TouchGestureCheck
java -cp "$CHECK_DIR" CommandBatchCheck
