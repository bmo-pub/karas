ARG base=karas/workload-generic

FROM ${base} AS generic

COPY --chown=worker home /home/worker
COPY --chown=worker --from=shared generic.md /home/worker/.claude/CLAUDE.md

ENV CLAUDE_CONFIG_DIR="/home/worker/.claude" \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    DISABLE_AUTOUPDATER=1 \
    AGENT_MODE=bypassPermissions \
    IS_DEMO=1

ENTRYPOINT ["/bin/sh", "-c", "exec /opt/claude/bin/claude --allow-dangerously-skip-permissions --no-chrome --permission-mode $AGENT_MODE --verbose \"$@\"", "claude"]

FROM generic AS amnesic

COPY --chown=worker --from=shared amnesic.md /home/worker/.claude/CLAUDE.md

ENV CLAUDE_CODE_DISABLE_AUTO_MEMORY=1

ENTRYPOINT ["/bin/sh", "-c", "exec /opt/claude/bin/claude --allow-dangerously-skip-permissions --no-chrome --permission-mode $AGENT_MODE --verbose --disallowed-tools Artifact,EnterWorktree,ExitWorktree,NotebookEdit,PushNotification,RemoteTrigger,SendFeedback \"$@\"", "claude"]
