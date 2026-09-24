ARG base=karas/workload-generic

FROM ${base} AS generic

COPY --chown=worker home /home/worker
COPY --chown=worker --from=shared generic.md /home/worker/.gemini/GEMINI.md

ENV AGENT_MODE=yolo

ENTRYPOINT ["/bin/sh", "-c", "exec /opt/gemini/bin/gemini --approval-mode=$AGENT_MODE \"$@\"", "gemini"]

FROM generic AS amnesic

COPY --chown=worker --from=shared amnesic.md /home/worker/.gemini/GEMINI.md
