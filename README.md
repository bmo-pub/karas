<!-- prettier-ignore -->
<div align="center">

# Karas

*Run AI coding assistants in isolated containers*

[Quickstart](#quickstart) • [Usage](#usage) • [Credentials](#credentials) • [Secrets](#secrets) • [Workloads](#workloads) • [Build](#build)

</div>

Karas runs agentic coding CLIs inside Docker or Podman containers, mounting your current folder as the working tree (`/home/worker/workspace`). Agents run as a non-root user (`worker`), keeping stray files, packages, and agent state off your host system.

> [!NOTE]
> In amnesic mode, the mounted host workspace is the only persistent, writable storage. Everything else is wiped when the container exits.

## Quickstart

Requires Python 3.9+ (no other dependencies) and Docker or Podman, on Linux, macOS, or Windows.

Add the Karas folder to your `PATH`, then run it from your project folder:

```bash
cd /path/to/project
karas run
```

Log in when prompted. The first run builds the base and workload images, installs the harness, and builds the harness image. Later runs start immediately.

## Usage

```text
karas [--engine docker|podman] [--dry-run] <command> ...
```

| Command | Description |
|---|---|
| `run` | Run a harness (amnesic, or persistent with `-n`). |
| `build` | Build or refresh images and harness installs. |
| `ls` | List workload and harness images and harness install volumes. |
| `ps` | List workers and whether they are running. |
| `rm` | Remove workers. |
| `rmi` | Remove images and harness install volumes. |

- **`--engine`**: Container engine. Defaults to `$KARAS_ENGINE`, then `docker` if available, otherwise `podman`.
- **`--dry-run`**: Print engine commands instead of executing them.

Both options may also be given after the command.

### Run

**Amnesic runs** (default) discard all container state on exit, leaving only the files edited in the mounted workspace.

**Persistent runs** (`-n WORKER`) keep a dedicated home directory and harness settings across sessions in named volumes.

In both modes, the agent's global instructions tell it to read `AGENTS.md` from the workspace root, if present.

```text
karas run [-n WORKER] [--workspace PATH] [ENGINE OPTIONS] [harness] [workload]
```

| Option | Default | Description |
|---|---|---|
| `-n`, `--name`, `--worker` | — | Run as a persistent worker with this name. Without it, the run is amnesic. |
| `--workspace` | current directory | Host folder mounted into `/home/worker/workspace`. |
| `-s`, `--secrets` | — | `GROUP[=PREFIX]`: [Secrets](#secrets) group to pass as environment variables (default prefix `SECRET_`). Repeatable. |
| `--secrets-db` | `~/.karas/secrets.kdbx` | KeePassXC database used by `--secrets`. |
| `harness` | `opencode` | `claude`, `codex`, `copilot`, `gemini`, `junie`, or `opencode`. |
| `workload` | `generic` | `generic`, `cpp`, `android`, or custom. |

These engine options are forwarded to the engine's `run` command and may be repeated:

| Option | Description |
|---|---|
| `-e`, `--env VAR[=VALUE]` | Set an environment variable (without a value, it is taken from the host). |
| `--env-file FILE` | Read environment variables from a file. |
| `-v`, `--volume SRC:DST[:OPTS]` | Bind mount a host path or named volume. |
| `-p`, `--publish [IP:]HOST:CONTAINER` | Publish a container port to the host. |
| `--network NETWORK` | Connect the container to a network. |
| `--add-host HOST:IP` | Add a custom host-to-IP mapping. |
| `--device DEVICE` | Add a host device. |
| `--gpus GPUS` | GPU devices to add (Docker only). |

Extra arguments are taken from environment variables:

- **`KARAS_ENGINE_ARGS`**: Forwarded to the engine's `run`, for options not listed above (e.g. `--memory 4g --cpus 2`).
- **`KARAS_HARNESS_ARGS`**: Forwarded to the agent (e.g. `--model haiku`).

Missing images and volumes of built-in workloads are built on demand. Custom workloads must be built first with [`build`](#build). Existing images are reused even if outdated; use `build --rm` to refresh them.

**Examples**:

```bash
# Amnesic OpenCode session in the current directory
karas run

# Persistent worker 'alice' with Claude and the C++ workload on a specific folder
karas run -n alice --workspace /path/to/project claude cpp

# Set a variable, publish a port and mount an extra folder read-only
karas run -e PORT=80 -p 8080:80 -v /path/to/data:/data:ro claude

# Worker 'alice' with the shared secrets (SECRET_*) plus its own, passed with exact names
karas run -n alice -s karas/shared -s karas/alice= claude

# Pass other flags to the engine and to the agent
KARAS_ENGINE_ARGS="--memory 4g" KARAS_HARNESS_ARGS="--model haiku" karas run claude
```

On Windows (`cmd`), set the variables first: `set "KARAS_HARNESS_ARGS=--model haiku"`.

## Credentials

Host credentials are used **only for amnesic runs**. In persistent runs, you log in interactively and credentials stay in the worker's named volume.

For amnesic runs, credentials are cached in `~/.karas/credentials/<harness>` (`%USERPROFILE%\.karas\credentials\<harness>` on Windows):

| Harness | Credential File | First Run | Container Mapping |
|---|---|---|---|
| **Claude** | `claude` | Log in interactively | `/home/worker/.claude/.credentials.json` |
| **Codex** | `codex` | Log in interactively | `/home/worker/.codex/auth.json` |
| **Copilot** | `copilot` | Paste GitHub token when prompted | `$COPILOT_GITHUB_TOKEN` |
| **Gemini** | `gemini` | Log in interactively | `/home/worker/.gemini/oauth_creds.json` |
| **Junie** | `junie` or `openrouter` | Paste key when prompted | `$JUNIE_API_KEY` or `$JUNIE_OPENROUTER_API_KEY` |
| **OpenCode** | `opencode` | Log in interactively | `/home/worker/.opencode/data/auth.json` |

Pasted tokens are hidden and saved with owner-only permissions. For Junie, press Enter at the Junie prompt to use an OpenRouter key instead. In non-interactive sessions, create the credential file yourself.

Since credential files are owner-only, the container's `worker` user (UID 1000) must map to your host user:

- **Rootless Podman on Linux**: Handled automatically with `--userns=keep-id:uid=1000,gid=1000` (Podman 4.3+).
- **Docker on Linux**: Works when your host UID is 1000.
- **Docker Desktop, Podman machine (macOS/Windows)**: Handled by the engine's file sharing.

## Secrets

Secrets such as API tokens are kept in an encrypted [KeePassXC](https://keepassxc.org) database on the host. They are passed to the agent as environment variables, for both amnesic and persistent runs. Manage them with the KeePassXC app. Karas reads them with `keepassxc-cli`, which ships with KeePassXC and must be on your `PATH`.

Each entry becomes one variable: its name is a prefix plus the entry's **Title**, and its value is the entry's **Password**. Use groups to organize entries into sets, for example:

```text
karas/
├── shared/    GITHUB_TOKEN, NPM_TOKEN
└── alice/     GITHUB_TOKEN, AWS_SECRET_ACCESS_KEY
```

Select groups with `-s`/`--secrets GROUP[=PREFIX]` (repeatable). Group paths are relative to the database root. Only entries placed directly in a group are included, not those in its subgroups.

The default prefix is `SECRET_`, so a secret can't accidentally override variables like `PATH` or the harness's own settings. Add `=PREFIX` to choose another prefix, or a bare `=` to use exact names:

| Option | Variable for `GITHUB_TOKEN` |
|---|---|
| `-s karas/shared` | `SECRET_GITHUB_TOKEN` |
| `-s karas/shared=CI_` | `CI_GITHUB_TOKEN` |
| `-s karas/shared=` | `GITHUB_TOKEN` |

If two groups produce the same variable name, the later group wins:

```bash
karas run -s karas/shared -s karas/alice= claude
```

`keepassxc-cli` asks for the database password on every run that uses `--secrets`. Decrypted values are kept only in memory and are never written to the host disk.

Use `--secrets-db PATH` to use a database other than the default `~/.karas/secrets.kdbx`.

To use a key file, set `KARAS_SECRETS_KEYFILE` to its path.

> [!NOTE]
> The container engine stores environment variables in the container's configuration. Anyone who can run `docker inspect` on the host can read them while the container exists.

## Workloads

Workloads provide the compilers and tools available to the agent. The included ones are starting points; add your own under `workloads/`.

- **`generic`**: Common CLI utilities (`git`, `python3`, `nodejs`, `npm`, `ripgrep`, `fd-find`, `jq`, `make`, `curl`, `wget`, `tree`).
- **`cpp`**: `g++`, `clang`, `lld`, `cmake`, `gdb`, `valgrind`, `clang-tidy`, `clang-format`, `cppcheck`, and Boost.
- **`android`**: JDK, Android SDK command-line tools, platform tools, API 36, and build tools.

### Adding your own workload

1. Create a directory with a lowercase name under `workloads/` (e.g., `workloads/rust/`).
2. Add a `Dockerfile` based on `karas/base`:

   ```dockerfile
   ARG base=karas/base
   FROM ${base}

   RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       cargo rustc \
   &&  rm -rf /var/lib/apt/lists/*

   USER worker
   ```

3. Run `karas run claude rust`.

Workloads can also live outside this repository; see [Build](#build).

## Build

```text
karas build [--rm] [harness] [workload[:PATH]]
```

- **`harness`**: Harness name or glob pattern. Default: `*` (all harnesses).
- **`workload`**: Workload name or glob pattern over built-in workloads. Default: `generic`. Use `name:PATH` to build a custom workload from the `Dockerfile` in `PATH`.
- **`--rm`**: Reinstall the selected harnesses (updates the agent CLI) and rebuild base, workload, and harness images without cache.

```bash
karas build                          # all harnesses for the generic workload
karas build '*' '*'                  # all harnesses x all built-in workloads
karas build claude cpp --rm          # update Claude Code and refresh the C++ toolchain
karas build '*' myworkload:.         # custom workload from ./Dockerfile
karas build '*' myworkload:/path/dir # custom workload from another folder
```

> [!NOTE]
> Quote `*` in POSIX shells so it isn't expanded to file names. In Windows `cmd`, write it bare: `karas build * *`.

## Inspect & Remove

```bash
karas ls                           # workload/harness images and harness install volumes
karas ps                           # workers: running or stopped
karas rm alice                     # remove worker 'alice' (its volumes)
karas rm --all                     # remove all workers
karas rmi --harness claude         # remove Claude images and its install volume
karas rmi --workload cpp           # remove the cpp workload and harness images built on it
karas rmi --harness claude --workload cpp  # remove only Claude images on cpp
karas rmi --all                    # remove all Karas images and harness install volumes
```

`--harness` and `--workload` accept glob patterns and may be repeated. `rm` and `rmi` refuse to remove anything in use by a running container.

## Architecture

Images combine a harness, a mode, and a workload:

```text
karas/harness-<harness>-<mode>-<workload>
```

| Component | Description |
|---|---|
| **Harness** | The CLI, installed into a named volume (`karas-harness-<name>`) and mounted read-only at `/opt/<name>`. |
| **Mode** | `amnesic` for throwaway runs, `generic` for persistent workers. |
| **Workload** | System packages and compilers built on Debian Stable (`karas/base`). |

Persistent workers keep their state in two kinds of named volumes:

- `karas-worker-<worker>-home`: The worker's home directory (`/home/worker`), shared by all harnesses.
- `karas-worker-<worker>-<harness>-data`: The harness config directory (`/home/worker/.<harness>`).
