"""Shared helpers for the industrial-icon-designer scripts.

Everything here is offline and deterministic: no timestamps in payloads,
no network, subprocesses always receive argument arrays.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_INPUT = 2
EXIT_DEPENDENCY = 3
EXIT_VALIDATION = 4
EXIT_RENDER = 5

PACKAGE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_GUARDRAILS = {
    "max_input_bytes": 10 * 1024 * 1024,
    "max_raster_px": 4096,
    "max_icons_per_run": 200,
}

KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ToolError(Exception):
    """A failure with an exit code and an actionable message."""

    def __init__(self, code: int, message: str, path: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def __str__(self) -> str:
        return f"{self.path}: {self.message}" if self.path else self.message


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


# ---------------------------------------------------------------- hashing / io

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def canonical_hash(obj: Any) -> str:
    return sha256_bytes(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def load_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ToolError(EXIT_INPUT, "file not found", str(path))
    except json.JSONDecodeError as exc:
        raise ToolError(EXIT_INPUT, f"invalid JSON: {exc}", str(path))


def atomic_write(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_json(path: Path, obj: Any) -> None:
    atomic_write(path, canonical_json(obj).encode("utf-8"))


def log_event(set_dir: Path, kind: str, ids: list[str], detail: str) -> None:
    """Append one JSON line to reports/invalidation-log.jsonl (history is never rewritten)."""
    import datetime
    path = Path(set_dir) / "reports" / "invalidation-log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
             "kind": kind, "ids": sorted(ids), "detail": detail}
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


@contextlib.contextmanager
def timed(set_dir: Path | str, name: str):
    """Log the elapsed seconds of a successful run to reports/timing-log.jsonl (never into an asset payload).

    Failed runs log nothing, so a refused or conflicting run leaves the set exactly as it was.
    """
    import time
    start = time.perf_counter()
    yield
    path = Path(set_dir) / "reports" / "timing-log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"name": name, "seconds": round(time.perf_counter() - start, 3)}) + "\n")


# --------------------------------------------------------------- schema checks

def schema_path(name: str) -> Path:
    return PACKAGE_DIR / "schemas" / f"{name}.schema.json"


def validate_schema(obj: Any, name: str, label: str = "") -> None:
    """Validate against a bundled schema; raise a field-specific ToolError."""
    from jsonschema import Draft202012Validator

    schema = load_json(schema_path(name))
    errors = sorted(Draft202012Validator(schema).iter_errors(obj), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        where = "/".join(str(p) for p in first.absolute_path) or "(root)"
        raise ToolError(EXIT_VALIDATION, f"{name}: {where}: {first.message}", label or None)


# ------------------------------------------------------------------ path safety

def is_within(path: Path, root: Path) -> bool:
    try:
        Path(os.path.realpath(path)).relative_to(Path(os.path.realpath(root)))
        return True
    except ValueError:
        return False


def ensure_inside(set_dir: Path, *names: str) -> None:
    """Refuse to read or write through set subdirectories (or files) that resolve outside the set."""
    for name in names:
        p = Path(set_dir) / name
        if (p.exists() or p.is_symlink()) and not is_within(p, set_dir):
            raise ToolError(EXIT_INPUT, f"{name} resolves outside the set directory (symlink?)", str(p))


def safe_join(root: Path, rel: str) -> Path:
    if os.path.isabs(rel) or ".." in Path(rel).parts:
        raise ToolError(EXIT_INPUT, "path escapes the configured root", rel)
    out = Path(root) / rel
    if not is_within(out, root):
        raise ToolError(EXIT_INPUT, "path resolves outside the configured root", rel)
    return out


def guardrails(set_dir: Path | None) -> dict:
    cfg = dict(DEFAULT_GUARDRAILS)
    if set_dir is not None:
        override = Path(set_dir) / "guardrails.json"
        if override.exists():
            cfg.update(load_json(override))
    return cfg


def guardrail_hint(set_dir: Path | None) -> str:
    base = Path(set_dir) if set_dir is not None else Path("<set>")
    return f"adjust limits in {base / 'guardrails.json'}"


def kebab_id(stem: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", stem)
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s


# ------------------------------------------------------------------- SVG safety

BANNED_TAGS = {"script", "foreignobject", "image", "iframe", "object", "embed", "audio", "video"}


_FORBIDDEN_MARKUP = re.compile(rb"<!--|<\?|<!\[CDATA\[")


def parse_svg(data: bytes, label: str | None = None, strict_markup: bool = True):
    """Parse SVG with a hardened parser (no DTD, entities or external refs).

    strict_markup also rejects comments, processing instructions and CDATA in the raw bytes. The parser
    drops them from the tree, so tree checks cannot see them, yet a browser ends `<!-->` and `<?...>` early
    and would run what follows. Masters (which are embedded in HTML and shipped as inline SVG) are strict;
    reference files are only ever rasterized by the renderer and may pass strict_markup=False.
    """
    try:
        import defusedxml.ElementTree as SafeET
        from defusedxml.common import DefusedXmlException
    except ImportError:
        raise ToolError(EXIT_DEPENDENCY, "defusedxml is not installed; install requirements.lock")
    if strict_markup:
        body = re.sub(rb"^\s*<\?xml[^>]*\?>", b"", data, count=1)
        if _FORBIDDEN_MARKUP.search(body):
            raise ToolError(EXIT_VALIDATION, "comments, processing instructions and CDATA are not allowed "
                            "(they can smuggle markup into inline use)", label)
    try:
        root = SafeET.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except DefusedXmlException as exc:
        raise ToolError(EXIT_VALIDATION, f"unsafe XML construct rejected: {type(exc).__name__}", label)
    except Exception as exc:  # malformed XML
        raise ToolError(EXIT_VALIDATION, f"not well-formed XML: {exc}", label)
    if _local(root.tag) != "svg":
        raise ToolError(EXIT_VALIDATION, "root element is not <svg>", label)
    return root


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def svg_findings(root) -> list[str]:
    """Return security/structure findings for a master SVG (empty list = clean)."""
    found: list[str] = []
    for el in root.iter():
        tag = _local(el.tag)
        if tag in BANNED_TAGS:
            found.append(f"forbidden element <{tag}>" + (" (embedded raster)" if tag == "image" else ""))
        if tag == "style" and (el.text or "") and re.search(r"@import|url\(", el.text, re.I):
            found.append("style block references external resources")
        for attr, value in el.attrib.items():
            name = _local(attr)
            if name.startswith("on"):
                found.append(f"event handler attribute {name}")
            if name == "href":
                if not value.startswith("#"):
                    found.append("external href reference")
            if isinstance(value, str) and re.search(r"(javascript:|data:image|https?://(?!www\.w3\.org))", value, re.I):
                found.append(f"suspicious value in attribute {name}")
    return sorted(set(found))


def svg_viewbox(root) -> tuple[float, float, float, float] | None:
    vb = root.attrib.get("viewBox")
    if not vb:
        return None
    parts = re.split(r"[ ,]+", vb.strip())
    if len(parts) != 4:
        return None
    try:
        return tuple(float(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        return None


def escape_html(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


# --------------------------------------------------------------------- renderer

def find_resvg() -> str:
    path = shutil.which("resvg")
    if not path:
        raise ToolError(
            EXIT_DEPENDENCY,
            "resvg not found; install with `cargo install resvg` or a release binary from "
            "github.com/linebender/resvg, then rerun",
        )
    return path


def resvg_version() -> str:
    out = subprocess.run([find_resvg(), "--version"], capture_output=True, text=True, check=False)
    return (out.stdout or out.stderr).strip().split()[-1]


def recolor_svg(svg_text: str, color: str) -> str:
    return svg_text.replace("currentColor", color)


def render_svg(svg_bytes: bytes, out_path: Path, width: int, height: int | None = None) -> None:
    """Render SVG bytes to PNG with the pinned renderer, directly at the requested size."""
    resvg = find_resvg()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.svg"
        dst = Path(tmp) / "out.png"
        src.write_bytes(svg_bytes)
        cmd = [resvg, "--width", str(width), "--height", str(height or width), str(src), str(dst)]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0 or not dst.exists():
            raise ToolError(EXIT_RENDER, f"render failed: {proc.stderr.strip() or 'unknown error'}", str(out_path))
        atomic_write(out_path, dst.read_bytes())


def render_many(jobs: list[tuple[bytes, Path, int]], workers: int = 8) -> None:
    """Render (svg_bytes, out_path, width) jobs concurrently; the first failure is raised after all finish.

    Each job writes its own file, so output bytes do not depend on scheduling order.
    """
    from concurrent.futures import ThreadPoolExecutor

    if not jobs:
        return
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(render_svg, svg, out, width) for svg, out, width in jobs]
    for f in futures:
        f.result()


# ------------------------------------------------------------------ cli helpers

def emit(result: dict, as_json: bool, text: str = "") -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif text:
        print(text)


def run_main(fn) -> None:
    """Run a script entry point mapping failures to the documented exit codes (diagnostics on stderr)."""
    try:
        sys.exit(fn() or 0)
    except ToolError as exc:
        eprint(f"error: {exc}")
        sys.exit(exc.code)
    except ImportError as exc:
        eprint(f"error: missing Python dependency: {exc}")
        sys.exit(EXIT_DEPENDENCY)
    except OSError as exc:
        eprint(f"error: file system failure: {exc}")
        sys.exit(EXIT_RENDER)
    except (ValueError, KeyError, TypeError) as exc:  # bad JSON shape, bad numbers, bad arguments
        eprint(f"error: invalid input: {type(exc).__name__}: {exc}")
        sys.exit(EXIT_INPUT)
