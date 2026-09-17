#!/usr/bin/env bash
# Run only on an isolated disposable Docker build worker after the image build.
set -euo pipefail
root=$(pwd)
work=$(mktemp -d)
name="ridge-desktop-smoke-${GITHUB_RUN_ID:-$$}"
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT
python -m ridge.deploy verify-build --component desktop
python -m ridge.case_template --destination "$work/template"
mkdir -p "$work/evidence" "$work/originals"
printf 'build-only-password\n' > "$work/password"
docker run -d --name "$name" --network none --shm-size 1g \
  --mount "type=bind,src=$work/password,dst=/run/secrets/vnc_password,readonly" \
  --mount "type=bind,src=$work/template,dst=/opt/silent-ridge/prepared-case,readonly" \
  --mount "type=bind,src=$work/evidence,dst=/evidence,readonly" \
  --mount "type=bind,src=$work/originals,dst=/originals,readonly" \
  silent-ridge-desktop:dev
for attempt in $(seq 1 60); do
  if docker exec "$name" bash -c 'test -S /tmp/.X11-unix/X1 && pgrep -u participant xfce4-session'; then break; fi
  if [ "$attempt" = 60 ]; then docker logs "$name"; exit 1; fi
  sleep 2
done
docker exec "$name" bash -ec '
  test -s /home/participant/Cases/WS17/WS17.aut
  test -s /home/participant/Cases/WS17/autopsy.db
  test "$(stat -c %s /etc/silent-ridge/vnc-password)" = 8
  runuser -u participant -- touch /home/participant/Cases/WS17/smoke-marker
  runuser -u participant -- env DISPLAY=:1 /usr/local/bin/firefox --version
  runuser -u participant -- env DISPLAY=:1 wireshark --version
  runuser -u participant -- env DISPLAY=:1 /opt/cutter/Cutter.AppImage --appimage-extract-and-run --version
  ldd /usr/local/lib/libtsk_jni.so | tee /tmp/tsk-libraries
  ! grep "not found" /tmp/tsk-libraries
'
docker restart "$name"
sleep 5
docker exec "$name" test -f /home/participant/Cases/WS17/smoke-marker
echo 'Built desktop starts offline, seeds the real case and preserves work on restart. Full GUI and Guacamole acceptance remains required.'
