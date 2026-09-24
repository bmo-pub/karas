ARG base=karas/workload-generic

FROM ${base} AS generic

COPY --chown=worker home /home/worker
COPY --chown=worker --from=shared generic.md /home/worker/.copilot/copilot-instructions.md

ENTRYPOINT ["/bin/sh", "-c", "exec /opt/copilot/bin/copilot --allow-all --no-auto-update --no-experimental --no-remote --no-remote-export \"$@\"", "copilot"]

FROM generic AS amnesic

RUN jq '.memory = false' /home/worker/.copilot/settings.json > /tmp/settings.json \
&&  mv /tmp/settings.json /home/worker/.copilot/settings.json

COPY --chown=worker --from=shared amnesic.md /home/worker/.copilot/copilot-instructions.md
