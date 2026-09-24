ARG base=karas/workload-generic

FROM ${base} AS generic

COPY --chown=worker home /home/worker
COPY --chown=worker --from=shared generic.md /home/worker/.codex/AGENTS.md

ENTRYPOINT ["/bin/sh", "-c", "exec /opt/codex/bin/codex --yolo \"$@\"", "codex"]

FROM generic AS amnesic

COPY --chown=worker --from=shared amnesic.md /home/worker/.codex/AGENTS.md

ENTRYPOINT ["/bin/sh", "-c", "exec /opt/codex/bin/codex --yolo -c features.memories=false -c history.persistence=\"none\" \"$@\"", "codex"]
