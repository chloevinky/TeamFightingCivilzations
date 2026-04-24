"""Entry point: ``python -m src.gui [--seed=N]``."""

from __future__ import annotations

import sys

from .app import run


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    seed: int | None = None
    for a in argv:
        if a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
    return run(seed=seed)


if __name__ == "__main__":
    raise SystemExit(main())
