"""Sphinx configuration. Build with ``uv run --group docs sphinx-build -W docs docs/_build/html``."""

import os
from importlib import metadata
from pathlib import Path

# autodoc imports the app; point it at an in-memory database so building the docs never touches real data.
os.environ.setdefault("DATABASE_URL", "sqlite://")

project = "Bookplate (Python port)"
author = "The Bookplate authors"
copyright = f"2026, {author}"
release = version = metadata.version("bookplate")

extensions = ["sphinx.ext.autodoc", "sphinx.ext.viewcode"]
autodoc_member_order = "bysource"
# SQLModel tables have generated keyword signatures that autodoc can't render; their fields are listed instead.
autodoc_class_signature = "separated"
autodoc_default_options = {"members": True, "undoc-members": True}
exclude_patterns = ["_build"]
html_theme = "alabaster"
html_theme_options = {"description": "A self-hosted reading tracker", "fixed_sidebar": True}


ROUTE_TABLE = """.. list-table::
   :header-rows: 1
   :widths: 8 32 60

   * - Method
     - Path
     - What it does
"""


def write_route_tables(here: Path) -> None:
    """Writes the HTTP route tables from the app's OpenAPI schema, so they never drift from the code."""
    from bookplate.main import app

    rows = {"api": [], "pages": []}
    for path, operations in app.openapi()["paths"].items():
        for method, op in operations.items():
            summary = (op.get("description") or "").split("\n")[0]
            row = f"   * - ``{method.upper()}``\n     - ``{path}``\n     - {summary}\n"
            rows["api" if path.startswith("/api/") else "pages"].append(row)
    out = here / "_generated"
    out.mkdir(exist_ok=True)
    for name, body in rows.items():
        (out / f"routes-{name}.rst").write_text(ROUTE_TABLE + "".join(body))


write_route_tables(Path(__file__).parent)
