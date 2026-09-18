"""M1: dependency direction is enforced, not merely documented.

docs/06 §3 requires dependencies to point strictly downward, and AD-03 makes
that a decision rather than a convention. This test reads the import graph with
``ast`` so it keeps working as code arrives at later milestones — it does not
depend on any module being non-empty today.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "rescuenet"

#: Layers a package may NOT import, per docs/06 §3 and §10.
FORBIDDEN: dict[str, set[str]] = {
    # Rule 1: domain deals in events and projections only — no transport, no
    # protocol, no broker, no persistence, no wire format.
    "domain": {"api", "store", "projections", "auth", "mqtt"},
    # The store is written to by ingestion; it must never reach up into the API,
    # and it must never depend on the broker.
    "store": {"api", "mqtt"},
    # AD-15: MQTT is a downstream notifier. It must not be able to write truth,
    # so it must not import the store at all.
    "mqtt": {"api", "store", "projections"},
    # Projections derive from the store; they never serve HTTP or publish.
    "projections": {"api", "mqtt"},
    # Configuration is a leaf.
    "config": {"api", "store", "projections", "auth", "mqtt", "domain"},
}

#: Third-party libraries the domain layer must never touch.
DOMAIN_FORBIDDEN_LIBS = {
    "fastapi", "starlette", "uvicorn",          # web
    "sqlalchemy", "alembic", "psycopg",         # persistence
    "aiomqtt", "paho",                          # broker
    "httpx", "requests",                        # transport
}


def _modules(package: str) -> list[Path]:
    directory = PACKAGE_ROOT / package
    return sorted(directory.rglob("*.py")) if directory.is_dir() else []


def _imported_names(path: Path) -> set[str]:
    """Every module name imported by a file, absolute and relative."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import — resolve against the package
                base = path.relative_to(PACKAGE_ROOT).parts[0]
                names.add(f"rescuenet.{base}.{node.module or ''}".rstrip("."))
            elif node.module:
                names.add(node.module)
    return names


@pytest.mark.parametrize("package", sorted(FORBIDDEN))
def test_package_does_not_import_forbidden_layers(package: str) -> None:
    forbidden = FORBIDDEN[package]
    violations: list[str] = []
    for module in _modules(package):
        for imported in _imported_names(module):
            for layer in forbidden:
                if imported == f"rescuenet.{layer}" or imported.startswith(
                    f"rescuenet.{layer}."
                ):
                    violations.append(f"{module.name} imports {imported}")
    assert not violations, (
        f"docs/06 §3 / AD-03 violated — '{package}' must not import "
        f"{sorted(forbidden)}: {violations}"
    )


def test_domain_imports_no_web_db_or_broker_library() -> None:
    """docs/06 §3 rule 1: the domain knows no protocol, broker or wire format."""
    violations: list[str] = []
    for module in _modules("domain"):
        for imported in _imported_names(module):
            root = imported.split(".")[0]
            if root in DOMAIN_FORBIDDEN_LIBS:
                violations.append(f"{module.name} imports {imported}")
    assert not violations, f"domain layer must stay pure: {violations}"


def test_mqtt_cannot_reach_the_store() -> None:
    """AD-15: MQTT is never a write path to authoritative state.

    Enforced structurally: if the publisher cannot import the store, it cannot
    write to it by accident.
    """
    violations = [
        f"{module.name} imports {imported}"
        for module in _modules("mqtt")
        for imported in _imported_names(module)
        if imported.startswith("rescuenet.store")
    ]
    assert not violations, f"AD-15 violated: {violations}"


def test_no_backend_module_imports_a_spike() -> None:
    """spikes/ is evidence, never source (docs/12 §3)."""
    violations = [
        f"{module.relative_to(PACKAGE_ROOT)} imports {imported}"
        for module in PACKAGE_ROOT.rglob("*.py")
        for imported in _imported_names(module)
        if imported.split(".")[0] in {"spikes", "sp01a_codec_budget",
                                      "sp05_merge_convergence"}
    ]
    assert not violations, f"spike code must never be imported: {violations}"


def test_every_declared_layer_exists() -> None:
    """The package layout from docs/12 §3 is present."""
    expected = {"domain", "store", "projections", "api", "auth", "mqtt", "config"}
    actual = {p.name for p in PACKAGE_ROOT.iterdir() if p.is_dir()
              and not p.name.startswith("__")}
    assert expected <= actual, f"missing layers: {expected - actual}"
