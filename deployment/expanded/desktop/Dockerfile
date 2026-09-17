# Silent Ridge per-team desktop as a container. Additive to the QCOW2 VM path.
# Build from the repository root (see deployment/expanded/desktop/README.md):
#   docker build -f deployment/expanded/desktop/Dockerfile -t silent-ridge-desktop:dev .
#
# No runtime credentials are baked in. VNC is reached only by guacd on the
# internal `desktop` network; port 5901 is never published to the host.

# ---------------------------------------------------------------------------
# Stage 1: build Sleuth Kit 4.13.0 with Java bindings and stage Autopsy 4.22.0
# ---------------------------------------------------------------------------
FROM ubuntu:24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

ARG SLEUTHKIT_VERSION=4.13.0
ARG SLEUTHKIT_URL=https://github.com/sleuthkit/sleuthkit/releases/download/sleuthkit-4.13.0/sleuthkit-4.13.0.tar.gz
ARG SLEUTHKIT_SHA256=f1490de8487df8708a4287c0d03bf0cb2153a799db98c584ab60def5c55c68f2
ARG AUTOPSY_VERSION=4.22.0
ARG AUTOPSY_URL=https://github.com/sleuthkit/autopsy/releases/download/autopsy-4.22.0/autopsy-4.22.0.zip
ARG AUTOPSY_SHA256=3f9aded0b8b094fabe557b4b8718e9bbbdbfbea5bf17bab335846f132d1fc97a

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl xz-utils unzip \
      build-essential autoconf automake libtool pkg-config ant ant-optional junit4 testdisk \
      openjdk-17-jdk-headless \
      libsqlite3-dev libpq-dev libssl-dev zlib1g-dev \
      libafflib-dev libewf-dev libvhdi-dev libvmdk-dev \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    curl -fsSL "$SLEUTHKIT_URL" -o /tmp/sleuthkit.tar.gz; \
    printf '%s  %s\n' "$SLEUTHKIT_SHA256" /tmp/sleuthkit.tar.gz | sha256sum -c -; \
    mkdir -p /opt/src; \
    tar -xzf /tmp/sleuthkit.tar.gz -C /opt/src; \
    cd "/opt/src/sleuthkit-$SLEUTHKIT_VERSION"; \
    ./configure --prefix=/usr/local --enable-java; \
    make -j1; \
    make install; \
    ldconfig

RUN set -eux; \
    curl -fsSL "$AUTOPSY_URL" -o /tmp/autopsy.zip; \
    printf '%s  %s\n' "$AUTOPSY_SHA256" /tmp/autopsy.zip | sha256sum -c -; \
    unzip -q /tmp/autopsy.zip -d /opt; \
    mv "/opt/autopsy-$AUTOPSY_VERSION" /opt/autopsy; \
    cd /opt/autopsy; \
    sed -i 's/\r$//' etc/autopsy.conf; \
    bash unix_setup.sh -j "$JAVA_HOME" -n autopsy

# ---------------------------------------------------------------------------
# Stage 2: participant desktop runtime
# ---------------------------------------------------------------------------
FROM ubuntu:24.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV HOME=/home/participant
ENV DISPLAY=:1
ENV VNC_PASSWORD_FILE=/etc/silent-ridge/vnc-password
ENV PATH=/usr/local/bin:$PATH

ARG CUTTER_VERSION=2.5.0
ARG CUTTER_URL=https://github.com/rizinorg/cutter/releases/download/v2.5.0/Cutter-v2.5.0-Linux-x86_64.AppImage
ARG CUTTER_SHA256=b8ad215d7a9e2af9e1f463511229f16e1f4745a0fb541413e5f4787f949ac0cf
ARG FIREFOX_VERSION=140.16.0esr
ARG FIREFOX_URL=https://archive.mozilla.org/pub/firefox/releases/140.16.0esr/linux-x86_64/en-US/firefox-140.16.0esr.tar.xz
ARG FIREFOX_SHA256=a90174f8fecfb1767371015a625a2f7ffc1edafd9110717348e797a46a066edf

# wireshark-common asks about setuid capture during install; answer non-interactively.
RUN echo "wireshark-common wireshark-common/install-setuid boolean false" | debconf-set-selections \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      xfce4 xfce4-terminal tigervnc-standalone-server dbus-x11 thunar wireshark \
      zenity openjdk-17-jre libopenjfx-java fonts-dejavu fonts-noto-color-emoji \
      adwaita-icon-theme tini ca-certificates curl xz-utils python3 \
      testdisk libafflib0t64 libewf2 libvhdi1 libvmdk1 libpq5 libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 \
      libgtk-3-0 libdbus-glib-1-2 libasound2t64 libxtst6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/autopsy /opt/autopsy
COPY --from=builder /usr/local /usr/local

RUN set -eux; \
    mkdir -p /opt/cutter; \
    curl -fsSL "$CUTTER_URL" -o /opt/cutter/Cutter.AppImage; \
    printf '%s  %s\n' "$CUTTER_SHA256" /opt/cutter/Cutter.AppImage | sha256sum -c -; \
    chmod 755 /opt/cutter/Cutter.AppImage; \
    curl -fsSL "$FIREFOX_URL" -o /tmp/firefox.tar.xz; \
    printf '%s  %s\n' "$FIREFOX_SHA256" /tmp/firefox.tar.xz | sha256sum -c -; \
    tar -xJf /tmp/firefox.tar.xz -C /opt; \
    rm -f /tmp/firefox.tar.xz; \
    ln -sfn /opt/firefox/firefox /usr/local/bin/firefox; \
    ldconfig

RUN useradd --create-home --uid 1000 --shell /bin/bash participant \
    && install -d -o participant -g participant \
         /home/participant/Desktop /home/participant/Cases \
         /home/participant/Workspace /home/participant/Scratch \
    && install -d /etc/silent-ridge /opt/silent-ridge \
    && mkdir -p /evidence /originals

COPY deployment/expanded/desktop/seed-case.py /opt/silent-ridge/seed-case.py
COPY deployment/expanded/desktop/helpers/ /opt/silent-ridge/helpers/
COPY deployment/expanded/desktop/configure-desktop.sh /opt/silent-ridge/configure-desktop.sh
COPY deployment/expanded/desktop/entrypoint.sh /usr/local/bin/silent-ridge-entrypoint
RUN chmod 755 /opt/silent-ridge/configure-desktop.sh /usr/local/bin/silent-ridge-entrypoint \
    && /opt/silent-ridge/configure-desktop.sh

# VNC for guacd only, on the internal `desktop` network.
EXPOSE 5901

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/usr/local/bin/silent-ridge-entrypoint"]
