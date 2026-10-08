#!/usr/bin/env bash
# Builds whisper-cli (whisper.cpp, CPU) with its own static ggml into linux/bin/.
# Use this when the distro package `whisper-cpp` isn't an option, e.g. on Arch it conflicts with llama.cpp-cuda
# (both ship ggml). The app finds linux/bin/whisper-cli by itself.
set -euo pipefail
here="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
tag="${WHISPER_TAG:-v1.9.4}"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
git clone --depth 1 --branch "$tag" https://github.com/ggml-org/whisper.cpp "$work/src"
cmake -S "$work/src" -B "$work/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
      -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_SERVER=OFF -DWHISPER_BUILD_EXAMPLES=ON >/dev/null
cmake --build "$work/build" --target whisper-cli -j"$(nproc)"
mkdir -p "$here/bin"
install -m755 "$work/build/bin/whisper-cli" "$here/bin/whisper-cli"
echo "Built $here/bin/whisper-cli ($tag)"
