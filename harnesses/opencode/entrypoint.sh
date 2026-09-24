#!/bin/sh
set -e

mkdir -p /home/worker/.local/share /home/worker/.local/state /home/worker/.config /home/worker/.cache
ln -sfnT /home/worker/.opencode/data /home/worker/.local/share/opencode
ln -sfnT /home/worker/.opencode/config /home/worker/.config/opencode
ln -sfnT /home/worker/.opencode/cache /home/worker/.cache/opencode
ln -sfnT /home/worker/.opencode/state /home/worker/.local/state/opencode

exec /opt/opencode/bin/opencode --auto "$@"
