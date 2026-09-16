#!/bin/bash
# Launch Autopsy with participant-writable Solr log and PID directories.
set -euo pipefail
cd "$HOME"
export SOLR_LOGS_DIR="$HOME/.local/state/autopsy-solr/logs"
export SOLR_PID_DIR="$HOME/.local/state/autopsy-solr"
mkdir -p "$SOLR_LOGS_DIR" "$SOLR_PID_DIR"
exec /opt/autopsy/bin/autopsy -J--module-path=/usr/share/openjfx/lib \
  -J--add-modules=javafx.controls,javafx.swing "$@"
