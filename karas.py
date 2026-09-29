#!/usr/bin/env python3
"""Karas: run AI coding assistants in isolated containers"""

import argparse
import csv
import fnmatch
import importlib.util
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
HARNESSES_DIR = ROOT / "harnesses"
WORKLOADS_DIR = ROOT / "workloads"
BASE_DIR = WORKLOADS_DIR / ".base"
SHARED_DIR = HARNESSES_DIR / ".shared"
CREDENTIALS_DIR = Path.home() / ".karas" / "credentials"
DEFAULT_SECRETS_DB = Path.home() / ".karas" / "secrets.kdbx"
DEFAULT_SECRETS_PREFIX = "SECRET_"
ENV_VAR_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

MODES = ("generic", "amnesic")
DEFAULT_HARNESS = "opencode"
DEFAULT_WORKLOAD = "generic"
WORKER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
WORKLOAD_NAME = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
HARNESS_NAME = re.compile(r"^[a-z0-9]+(?:[._][a-z0-9]+)*$")
GLOB_CHARS = set("*?[")
FORWARDED_RUN_OPTIONS = (
    (("-e", "--env"), "VAR[=VALUE]", "set an environment variable"),
    (("--env-file",), "FILE", "read environment variables from a file"),
    (("-v", "--volume"), "SRC:DST[:OPTS]", "bind mount a host path or volume"),
    (("--mount",), "type=TYPE,src=SRC,dst=DST[,...]", "attach a filesystem mount (bind, volume, tmpfs, ...)"),
    (("--tmpfs",), "DST[:OPTS]", "mount a tmpfs directory"),
    (("-p", "--publish"), "[IP:]HOST:CONTAINER", "publish a container port to the host"),
    (("--network",), "NETWORK", "connect the container to a network"),
    (("--add-host",), "HOST:IP", "add a custom host-to-IP mapping"),
    (("--device",), "DEVICE", "add a host device"),
    (("--gpus",), "GPUS", "GPU devices to add (docker only)"),
)

BASE_IMAGE = "karas/base"
WORKLOAD_IMAGE_PREFIX = "karas/workload-"
HARNESS_IMAGE_PREFIX = "karas/harness-"
HARNESS_VOLUME_PREFIX = "karas-harness-"
WORKER_PREFIX = "karas-worker-"
WORKER_HOME = "home"
WORKER_HARNESS_SUFFIX = "-data"
WORKER_UID = 1000


class KarasError(Exception):
    pass


def buildable_dirs(root, pattern):
    return sorted(p.name for p in root.iterdir() if pattern.match(p.name) and (p / "Dockerfile").is_file())


def harnesses():
    return buildable_dirs(HARNESSES_DIR, HARNESS_NAME)


def workloads():
    return buildable_dirs(WORKLOADS_DIR, WORKLOAD_NAME)


def workload_image(workload):
    return f"{WORKLOAD_IMAGE_PREFIX}{workload}"


def harness_image(harness, mode, workload):
    return f"{HARNESS_IMAGE_PREFIX}{harness}-{mode}-{workload}"


def harness_volume(harness):
    return f"{HARNESS_VOLUME_PREFIX}{harness}"


def harness_secrets_group(harness):
    return f"karas/{harness}"


def worker_prefix(worker):
    return f"{WORKER_PREFIX}{worker}-"


def worker_home_volume(worker):
    return worker_prefix(worker) + WORKER_HOME


def worker_harness_volume(worker, harness):
    return worker_prefix(worker) + harness + WORKER_HARNESS_SUFFIX


def owned_by_worker(name, worker):
    prefix = worker_prefix(worker)
    if not name.startswith(prefix):
        return False
    rest = name[len(prefix):]
    return rest == WORKER_HOME or bool(HARNESS_NAME.match(rest.removesuffix(WORKER_HARNESS_SUFFIX)))


def parse_worker_harness_volume(name, worker):
    prefix = worker_prefix(worker)
    if name.startswith(prefix) and name.endswith(WORKER_HARNESS_SUFFIX):
        harness = name[len(prefix):-len(WORKER_HARNESS_SUFFIX)]
        return harness if HARNESS_NAME.match(harness) else None


def parse_harness_image(name):
    modes = "|".join(MODES)
    match = re.match(rf"^{re.escape(HARNESS_IMAGE_PREFIX)}([^-]+)-({modes})-(.+)$", name)
    return match.groups() if match else None


def parse_workload_image(name):
    return name.removeprefix(WORKLOAD_IMAGE_PREFIX) if name.startswith(WORKLOAD_IMAGE_PREFIX) else None


def parse_harness_volume(name):
    return name.removeprefix(HARNESS_VOLUME_PREFIX) if name.startswith(HARNESS_VOLUME_PREFIX) else None


def parse_worker_home_volume(name):
    suffix = "-" + WORKER_HOME
    if name.startswith(WORKER_PREFIX) and name.endswith(suffix):
        return name[len(WORKER_PREFIX):-len(suffix)]
    return None


def validate_name(kind, name, pattern):
    if not pattern.match(name):
        raise KarasError(f"invalid {kind} name '{name}'")


_harness_cache = {}


def load_harness(name):
    if name in _harness_cache:
        return _harness_cache[name]
    path = HARNESSES_DIR / name / "harness.py"
    module = None
    if path.exists():
        spec = importlib.util.spec_from_file_location(f"karas_harness_{name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    _harness_cache[name] = module
    return module


def print_table(headers, rows):
    rows = [[str(cell) for cell in row] for row in rows]
    widths = [max(len(r[i]) for r in [headers] + rows) for i in range(len(headers))]
    for row in [headers] + rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip())


class Engine:
    def __init__(self, name, dry_run):
        self.name = name or os.environ.get("KARAS_ENGINE") or ("docker" if shutil.which("docker") else "podman")
        self.dry_run = dry_run
        self.available = shutil.which(self.name) is not None
        if not self.available and not dry_run:
            raise KarasError(f"container engine '{self.name}' not found")

    def run(self, *args, env=None, check=True):
        command = [self.name, *args]
        if self.dry_run:
            print(shlex.join(command), flush=True)
            return 0
        code = subprocess.run(command, env={**os.environ, **(env or {})}).returncode
        if check and code != 0:
            raise KarasError(f"'{shlex.join(command[:3])} ...' failed with exit code {code}")
        return code

    def userns_args(self):
        rootless_podman = Path(self.name).stem == "podman" and sys.platform == "linux" and os.geteuid() != 0
        return [f"--userns=keep-id:uid={WORKER_UID},gid={WORKER_UID}"] if rootless_podman else []

    def query(self, *args):
        if not self.available:
            return []
        result = subprocess.run([self.name, *args], capture_output=True, text=True)
        if result.returncode != 0:
            raise KarasError(result.stderr.strip() or f"'{self.name} {args[0]}' failed")
        return [line for line in result.stdout.splitlines() if line.strip()]

    def exists(self, kind, name):
        if not self.available:
            return False
        return subprocess.run([self.name, kind, "inspect", name], capture_output=True).returncode == 0

    def images(self):
        images = []
        for line in self.query("images", "--filter", "reference=*karas/*:latest",
                               "--format", "{{.Repository}}\t{{.Size}}\t{{.CreatedSince}}"):
            reference, size, created = line.split("\t")
            images.append((reference.removeprefix("localhost/"), size, created))
        return images

    def volumes(self):
        return self.query("volume", "ls", "--filter", "name=karas-", "--format", "{{.Name}}")

    def containers(self):
        containers = []
        for line in self.query("ps", "--filter", "label=karas", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}"):
            name, image, status = line.split("\t")
            containers.append((name, image.removeprefix("localhost/").removesuffix(":latest"), status))
        return containers


class HarnessContext:
    def __init__(self, engine, harness):
        self.engine = engine
        self.harness = harness
        self.volume = harness_volume(harness)
        self.run_args = []

    def npm_install(self, package, args=()):
        self.engine.run(
            "run", "--rm", "--pull", "never",
            "-v", f"{self.volume}:/opt/{self.harness}",
            "-e", f"NPM_CONFIG_PREFIX=/opt/{self.harness}",
            "-e", "npm_config_cache=/tmp/npm-cache",
            *args,
            BASE_IMAGE, "npm", "i", "-g", package,
        )

    def mount_credential(self, name, container_path):
        path = CREDENTIALS_DIR / name
        if not self.engine.dry_run:
            try:
                CREDENTIALS_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
                os.close(os.open(path, os.O_WRONLY | os.O_CREAT, 0o600))
            except OSError as error:
                print(f"karas: cannot create credential file {path}: {error.strerror}", file=sys.stderr)
                return False
        self.run_args += ["-v", f"{path}:{container_path}:z"]
        return True


class Builder:
    def __init__(self, engine, reinstall=False, refresh=False, no_cache=False):
        self.engine = engine
        self.reinstall = reinstall
        self.refresh = refresh
        self.no_cache = no_cache
        self.built_images = set()
        self.installed_harnesses = set()

    def _build_image(self, tag, args):
        if tag in self.built_images:
            return
        self.built_images.add(tag)
        if not self.refresh and self.engine.exists("image", tag):
            return
        print(f"karas: building {tag}", file=sys.stderr)
        cache_args = ["--no-cache"] if self.no_cache else []
        self.engine.run("build", *cache_args, "-t", tag, *args)

    def build_base(self):
        self._build_image(BASE_IMAGE, [str(BASE_DIR)])

    def build_workload(self, workload, context):
        self.build_base()
        args = ["--build-arg", f"base={BASE_IMAGE}", str(context)]
        self._build_image(workload_image(workload), args)

    def install_harness(self, harness):
        if harness in self.installed_harnesses:
            return
        self.installed_harnesses.add(harness)
        volume = harness_volume(harness)
        module = load_harness(harness)
        if not hasattr(module, "install"):
            return
        if self.engine.exists("volume", volume):
            if not self.reinstall:
                return
            self.engine.run("volume", "rm", volume)
        self.build_base()
        print(f"karas: installing {harness} into {volume}", file=sys.stderr)
        module.install(HarnessContext(self.engine, harness))

    def build_harness_image(self, harness, mode, workload, context):
        self.build_workload(workload, context)
        self.install_harness(harness)
        args = [
            "--target", mode,
            "--build-arg", f"base={workload_image(workload)}",
            "--build-context", f"shared={SHARED_DIR}",
            str(HARNESSES_DIR / harness),
        ]
        self._build_image(harness_image(harness, mode, workload), args)


def read_secrets_db(database):
    key_file = os.environ.get("KARAS_SECRETS_KEYFILE")
    command = ["keepassxc-cli", "export", "--format", "csv"]
    if key_file:
        command += ["--key-file", key_file]
    command.append(str(database))
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, text=True, encoding="utf-8")
    except FileNotFoundError:
        raise KarasError("keepassxc-cli not found in PATH")
    if result.returncode != 0:
        raise KarasError(f"cannot open {database}")
    return list(csv.DictReader(result.stdout.splitlines()))


def group_secrets(entries, group, prefix):
    wanted = "/".join(part for part in group.replace("\\", "/").split("/") if part)
    values = {}
    for entry in entries:
        if wanted not in (entry["Group"], entry["Group"].partition("/")[2]):
            continue
        name = prefix + entry["Title"]
        if not ENV_VAR_NAME.match(name):
            raise KarasError(f"secret '{group}/{entry['Title']}' gives an invalid environment variable name '{name}'")
        values[name] = entry["Password"]
    return values


def selected_secrets(entries, groups):
    values = {}
    for spec in groups:
        group, separator, prefix = spec.rpartition("=")
        if not separator:
            group, prefix = spec, DEFAULT_SECRETS_PREFIX
        matched = group_secrets(entries, group, prefix)
        if not matched:
            raise KarasError(f"secrets group '{group}' is empty or not found")
        values.update(matched)
    return values


def validate(kind, names, known):
    unknown = [name for name in names if name not in known]
    if unknown:
        raise KarasError(f"unknown {kind}: {', '.join(unknown)} (available: {', '.join(known)})")


def resolve_workload(spec):
    name, has_path, path = spec.partition(":")
    validate_name("workload", name, WORKLOAD_NAME)
    if has_path:
        context = Path(path)
    elif name in workloads():
        context = WORKLOADS_DIR / name
    else:
        raise KarasError(f"unknown workload '{name}' (available: {', '.join(workloads())}; "
                         f"use NAME:PATH for a custom one)")
    context = context.resolve()
    if not (context / "Dockerfile").is_file():
        raise KarasError(f"no Dockerfile for workload '{name}' in {context}")
    return name, context


def cmd_build(engine, args):
    selected_harnesses = fnmatch.filter(harnesses(), args.harness)
    if not selected_harnesses:
        raise KarasError(f"no harness matches '{args.harness}' (available: {', '.join(harnesses())})")
    if ":" not in args.workload and GLOB_CHARS & set(args.workload):
        matched = fnmatch.filter(workloads(), args.workload)
        if not matched:
            raise KarasError(f"no workload matches '{args.workload}' (available: {', '.join(workloads())})")
        selected_workloads = [(name, WORKLOADS_DIR / name) for name in matched]
    else:
        selected_workloads = [resolve_workload(args.workload)]
    builder = Builder(engine, args.reinstall, refresh=True, no_cache=args.rebuild)
    for harness in selected_harnesses:
        for workload, context in selected_workloads:
            for mode in MODES:
                builder.build_harness_image(harness, mode, workload, context)


def forwarded_option_dest(flags):
    return flags[-1].lstrip("-").replace("-", "_")


def forwarded_run_args(args):
    forwarded = []
    for flags, _, _ in FORWARDED_RUN_OPTIONS:
        for value in getattr(args, forwarded_option_dest(flags)):
            forwarded += [flags[-1], value]
    return forwarded


def cmd_run(engine, args):
    harness, workload, worker = args.harness, args.workload, args.worker
    validate("harness", [harness], harnesses())
    validate_name("workload", workload, WORKLOAD_NAME)
    if worker is not None:
        validate_name("worker", worker, WORKER_NAME)

    mode = "amnesic" if worker is None else "generic"
    image = harness_image(harness, mode, workload)
    module = load_harness(harness)
    installable = hasattr(module, "install")

    builder = Builder(engine)
    if not engine.exists("image", image):
        if workload not in workloads():
            raise KarasError(f"workload '{workload}' not found")
        builder.build_harness_image(harness, mode, workload, WORKLOADS_DIR / workload)
    else:
        builder.install_harness(harness)

    secrets_db = Path(args.secrets_db).expanduser()
    context = HarnessContext(engine, harness)
    auth = getattr(module, "auth", None)
    needs_harness_secrets = not auth or (worker is None and not auth(context))
    use_harness_secrets = needs_harness_secrets and secrets_db.is_file()
    entries = read_secrets_db(secrets_db) if args.secrets or use_harness_secrets else []
    harness_secrets = group_secrets(entries, harness_secrets_group(harness), "") if use_harness_secrets else {}
    secret_values = {**harness_secrets, **selected_secrets(entries, args.secrets)}
    secret_args = [arg for name in secret_values for arg in ("-e", name)]

    workspace = Path(args.workspace or Path.cwd()).resolve()
    tty_args = ["-it"] if sys.stdin.isatty() and sys.stdout.isatty() else ["-i"]
    labels = ["--label", "karas", "--label", f"karas.harness={harness}", "--label", f"karas.workload={workload}"]
    volume_args = ["-v", f"{harness_volume(harness)}:/opt/{harness}:ro"] if installable else []
    if worker is not None:
        volume_args += ["-v", f"{worker_home_volume(worker)}:/home/worker"]
    volume_args += ["-v", f"{workspace}:/home/worker/workspace"]

    if worker is None:
        name = f"karas-{harness}-{secrets.token_hex(2)}"
        volume_args += context.run_args
    else:
        name = worker_prefix(worker) + harness
        labels += ["--label", f"karas.worker={worker}"]
        volume_args += ["-v", f"{worker_harness_volume(worker, harness)}:/home/worker/.{harness}"]

    def env_args(var):
        return shlex.split(os.environ.get(var, ""))

    return engine.run(
        "run", "--rm", "--pull", "never", *engine.userns_args(), *tty_args, "--name", name, *labels, *volume_args,
        *secret_args, *forwarded_run_args(args), *env_args("KARAS_ENGINE_ARGS"),
        image, *env_args("KARAS_HARNESS_ARGS"),
        env=secret_values, check=False,
    )


def cmd_ls(engine, args):
    images = engine.images()
    volumes = set(engine.volumes())

    workload_rows = []
    for ref, size, created in images:
        workload = parse_workload_image(ref)
        if workload:
            workload_rows.append((workload, size, created))
    print_table(["WORKLOAD", "SIZE", "CREATED"], sorted(workload_rows))
    print()

    harness_rows = []
    seen = set()
    for ref, size, created in images:
        parsed = parse_harness_image(ref)
        if parsed:
            harness, mode, workload = parsed
            seen.add(harness)
            installed = "yes" if harness_volume(harness) in volumes else "no"
            harness_rows.append((harness, mode, workload, installed, size, created))
    for volume in volumes:
        harness = parse_harness_volume(volume)
        if harness and harness not in seen:
            harness_rows.append((harness, "-", "-", "yes", "-", "-"))
    print_table(["HARNESS", "MODE", "WORKLOAD", "INSTALLED", "SIZE", "CREATED"], sorted(harness_rows))


def list_workers(volumes):
    return sorted(filter(None, map(parse_worker_home_volume, volumes)))


def cmd_ps(engine, args):
    volumes = engine.volumes()
    containers = engine.containers()
    rows = []
    for worker in list_workers(volumes):
        worker_harnesses = sorted(filter(None, (parse_worker_harness_volume(v, worker) for v in volumes)))
        harness_list = ",".join(worker_harnesses) or "-"
        running = [c for c in containers if owned_by_worker(c[0], worker)]
        for name, image, status in running:
            rows.append((worker, harness_list, name, image, status))
        if not running:
            rows.append((worker, harness_list, "-", "-", "Stopped"))
    print_table(["WORKER", "HARNESSES", "CONTAINER", "IMAGE", "STATUS"], rows)


def refuse_if_running(containers):
    if containers:
        raise KarasError(f"refusing: running containers: {', '.join(containers)}")


def cmd_rm(engine, args):
    if not args.all and not args.workers:
        raise KarasError("specify worker names or --all")
    volumes = engine.volumes()
    known = list_workers(volumes)
    targets = known if args.all else args.workers
    validate("worker", targets, known)

    containers = engine.containers()
    refuse_if_running([c[0] for c in containers if any(owned_by_worker(c[0], w) for w in targets)])

    to_remove = [v for v in volumes if any(owned_by_worker(v, w) for w in targets)]
    if to_remove:
        engine.run("volume", "rm", *to_remove)


def cmd_rmi(engine, args):
    if not (args.all or args.harness or args.workload):
        raise KarasError("specify --harness, --workload or --all")

    def matches(name, patterns):
        return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)

    images = [ref for ref, _, _ in engine.images()]
    volumes = engine.volumes()
    both = bool(args.harness and args.workload)
    remove_images, remove_volumes = [], []

    for ref in images:
        harness_parts = parse_harness_image(ref)
        workload = parse_workload_image(ref)
        if args.all:
            remove_images.append(ref)
        elif harness_parts:
            harness, _, image_workload = harness_parts
            by_harness = matches(harness, args.harness)
            by_workload = matches(image_workload, args.workload)
            if (by_harness and by_workload) if both else (by_harness or by_workload):
                remove_images.append(ref)
        elif workload and not both and matches(workload, args.workload):
            remove_images.append(ref)

    for volume in volumes:
        harness = parse_harness_volume(volume)
        if harness and (args.all or (not both and matches(harness, args.harness))):
            remove_volumes.append(volume)

    blocking = []
    for name, image, _ in engine.containers():
        harness_parts = parse_harness_image(image)
        if image in remove_images or (harness_parts and harness_volume(harness_parts[0]) in remove_volumes):
            blocking.append(name)
    refuse_if_running(blocking)

    remove_images.sort(key=lambda ref: (ref == BASE_IMAGE, ref.startswith(WORKLOAD_IMAGE_PREFIX)))
    if remove_images:
        engine.run("rmi", *remove_images)
    if remove_volumes:
        engine.run("volume", "rm", *remove_volumes)
    if not remove_images and not remove_volumes:
        print("karas: nothing to remove", file=sys.stderr)


def build_parser():
    engine_options = argparse.ArgumentParser(add_help=False)
    engine_options.add_argument("--engine", default=argparse.SUPPRESS,
                                help="container engine (default: $KARAS_ENGINE, docker, podman)")
    engine_options.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS,
                                help="print engine commands instead of executing them")

    parser = argparse.ArgumentParser(prog="karas", description="Run AI coding assistants in isolated containers.",
                                     parents=[engine_options])
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    run = commands.add_parser("run", parents=[engine_options], help="run a harness",
                              epilog="Extra engine/agent arguments: $KARAS_ENGINE_ARGS / $KARAS_HARNESS_ARGS.")
    run.add_argument("harness", nargs="?", default=DEFAULT_HARNESS, help=f"harness (default: {DEFAULT_HARNESS})")
    run.add_argument("workload", nargs="?", default=DEFAULT_WORKLOAD, help=f"workload (default: {DEFAULT_WORKLOAD})")
    run.add_argument("-n", "--name", "--worker", dest="worker", help="persistent worker name (default: amnesic)")
    run.add_argument("--workspace", help="host folder mounted as the workspace (default: cwd)")
    run.add_argument("-s", "--secrets", action="append", default=[], metavar="GROUP[=PREFIX]",
                     help=f"KeePassXC group whose entries become environment variables named PREFIX+title "
                          f"(default prefix: {DEFAULT_SECRETS_PREFIX}; empty for exact names; repeatable)")
    run.add_argument("--secrets-db", default=str(DEFAULT_SECRETS_DB), metavar="PATH",
                     help=f"KeePassXC database for --secrets (default: {DEFAULT_SECRETS_DB})")
    forwarded = run.add_argument_group("engine options", "forwarded to the engine's run command (repeatable)")
    for flags, metavar, help_text in FORWARDED_RUN_OPTIONS:
        forwarded.add_argument(*flags, dest=forwarded_option_dest(flags), action="append", default=[],
                               metavar=metavar, help=help_text)

    build = commands.add_parser("build", parents=[engine_options],
                                help="build or refresh workload/harness images and install harnesses")
    build.add_argument("harness", nargs="?", default="*", help="harness name or glob (default: *)")
    build.add_argument("workload", nargs="?", default=DEFAULT_WORKLOAD,
                       help=f"workload, NAME:PATH for a custom one, or * for all built-in (default: {DEFAULT_WORKLOAD})")
    build.add_argument("--rm", dest="reinstall", action="store_true", help="reinstall selected harnesses")
    build.add_argument("--rmi", dest="rebuild", action="store_true",
                       help="rebuild all selected images without cache")

    commands.add_parser("ls", parents=[engine_options], help="list images and harness install volumes")
    commands.add_parser("ps", parents=[engine_options], help="list workers and their status")

    rm = commands.add_parser("rm", parents=[engine_options], help="remove workers (their volumes)")
    rm.add_argument("workers", nargs="*", metavar="worker")
    rm.add_argument("--all", action="store_true", help="remove all workers")

    rmi = commands.add_parser("rmi", parents=[engine_options], help="remove images and harness install volumes")
    rmi.add_argument("--harness", action="append", default=[], metavar="PAT", help="harness name or glob (repeatable)")
    rmi.add_argument("--workload", action="append", default=[], metavar="PAT", help="workload name or glob (repeatable)")
    rmi.add_argument("--all", action="store_true", help="remove all Karas images and harness volumes")
    return parser


COMMANDS = {"run": cmd_run, "build": cmd_build, "ls": cmd_ls, "ps": cmd_ps, "rm": cmd_rm, "rmi": cmd_rmi}


def main(argv):
    args = build_parser().parse_args(argv)
    try:
        engine = Engine(getattr(args, "engine", None), getattr(args, "dry_run", False))
        return COMMANDS[args.command](engine, args) or 0
    except KarasError as error:
        print(f"karas: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
