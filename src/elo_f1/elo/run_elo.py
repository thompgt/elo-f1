"""CLI entrypoint: python -m elo_f1.elo.run_elo (full recompute)."""

from elo_f1.elo.engine import run
from elo_f1.storage.db import connect


def main() -> None:
    with connect() as conn:
        run(conn)
    print("Elo recompute done.")


if __name__ == "__main__":
    main()
