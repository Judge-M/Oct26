#!/usr/bin/env bash
# Build only the pinned case-preparation tools in an Ubuntu 24.04 build environment.
set -euo pipefail
: "${AUTOPSY_ZIP:?Supply the official autopsy-4.22.0.zip download}"
BUILD_ROOT=${BUILD_ROOT:-/opt/silent-ridge-build}
mkdir -p "$BUILD_ROOT"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y openjdk-17-jdk openjfx xvfb curl unzip git build-essential testdisk \
  autoconf automake libtool ant libsqlite3-dev libpq-dev libssl-dev \
  libafflib-dev libewf-dev libvhdi-dev libvmdk-dev zlib1g-dev \
  libgtk-3-0 libgstreamer1.0-0 libgstreamer-plugins-base1.0-0
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
if [[ ! -d "$BUILD_ROOT/sleuthkit/.git" ]]; then
  git clone --depth 1 --branch sleuthkit-4.13.0 https://github.com/sleuthkit/sleuthkit.git "$BUILD_ROOT/sleuthkit"
fi
cd "$BUILD_ROOT/sleuthkit"
[[ $(git describe --tags --exact-match) == sleuthkit-4.13.0 ]]
test -z "$(git status --porcelain --untracked-files=no)"
./bootstrap
./configure --enable-java
# The upstream Java and case-UCO targets require sequential ordering.
make -j1
make install
ldconfig
if [[ ! -d "$BUILD_ROOT/autopsy-4.22.0" ]]; then
  unzip -q "$AUTOPSY_ZIP" -d "$BUILD_ROOT"
fi
cd "$BUILD_ROOT/autopsy-4.22.0"
bash unix_setup.sh -j "$JAVA_HOME" -n autopsy
# The upstream ZIP includes CRLF in the shell-sourced configuration.
sed -i 's/\r$//' etc/autopsy.conf
# Cap the JVM heap below the container/VM cgroup ceiling: upstream -J-Xmx4G
# invites an OOM-kill under load. Measured with the WS17 case open: JVM RSS
# 1.69 GB, so 2500m leaves ~50% headroom (override via AUTOPSY_XMX).
AUTOPSY_XMX=${AUTOPSY_XMX:-2500m}
sed -i "s/-J-Xmx4G/-J-Xmx${AUTOPSY_XMX}/" etc/autopsy.conf
grep -q -- "-J-Xmx${AUTOPSY_XMX}" etc/autopsy.conf
sha256sum "$AUTOPSY_ZIP" > "$BUILD_ROOT/autopsy-download.sha256"
git -C "$BUILD_ROOT/sleuthkit" rev-parse HEAD > "$BUILD_ROOT/sleuthkit-commit.txt"
dpkg-query -W > "$BUILD_ROOT/installed-packages.tsv"
java -version 2> "$BUILD_ROOT/java-version.txt"
printf 'Pinned Autopsy toolchain built at %s\n' "$BUILD_ROOT"
