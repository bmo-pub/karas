ARG base=karas/workload-generic

FROM ${base} AS generic

RUN mkdir -p \
    /home/worker/.opencode/data \
    /home/worker/.opencode/config \
    /home/worker/.opencode/cache \
    /home/worker/.opencode/state

COPY --chown=worker home /home/worker
COPY --chown=worker --from=shared generic.md /home/worker/.opencode/config/AGENTS.md
COPY --chmod=755 entrypoint.sh /usr/local/bin/opencode-entrypoint

ENTRYPOINT ["/usr/local/bin/opencode-entrypoint"]

FROM generic AS amnesic

COPY --chown=worker --from=shared amnesic.md /home/worker/.opencode/config/AGENTS.md

ENV OPENCODE_PURE=1
