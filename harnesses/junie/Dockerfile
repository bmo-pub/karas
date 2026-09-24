ARG base=karas/workload-generic

FROM ${base} AS generic

COPY --chown=worker home /home/worker
COPY --chown=worker --from=shared generic.md /home/worker/.junie/AGENTS.md

ENV JUNIE_SKIP_UPDATE_CHECK=1

ENTRYPOINT ["/bin/sh", "-c", "export PATH=\"/opt/junie/.local/bin:$PATH\" HOME=/opt/junie JUNIE_HOME=/home/worker/.junie JUNIE_DATA=/opt/junie/.local/share/junie; exec junie --brave --skip-update-check --share-anonymous-statistics false \"$@\"", "junie"]

FROM generic AS amnesic

COPY --chown=worker --from=shared amnesic.md /home/worker/.junie/AGENTS.md
