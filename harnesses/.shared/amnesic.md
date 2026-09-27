## Environment
- The agent runs in a amnesic (stateless) Docker container as a non-root user.
- The workspace directory is mounted from the host and is the only writable, persistent storage available to the agent.
- Secrets are available as `SECRET_*` environment variables.
- Repositories (Git, SVN, etc.) may exist in the workspace, but treat them as ordinary files only. Ignore version control metadata, and do not perform version control operations. The user will handle those manually from the host.

## Operating Guidelines
- If a required tool is unavailable, report the limitation and suggest alternatives rather than attempting workarounds.
- Minimize code comments; prefer self-documenting code with clear function and variable names.
- Communicate concisely and directly.

## Machine-specific instructions
If `~/workspace/AGENTS.md` exists, read and follow it.
If it does not exist, continue normally without reporting an error.

@~/workspace/AGENTS.md