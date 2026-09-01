"""CLI entrypoint: python -m elo_f1.ingestion.run_ingest --from 1980 --to 2026"""

import argparse

from elo_f1.ingestion.ergast_ingest import ingest_season
from elo_f1.storage.db import connect


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest F1 seasons from Jolpica-F1 into SQLite.")
    parser.add_argument("--from", dest="year_from", type=int, default=1980)
    parser.add_argument("--to", dest="year_to", type=int, default=2026)
    args = parser.parse_args()

    with connect() as conn:
        for year in range(args.year_from, args.year_to + 1):
            print(f"Ingesting season {year}...")
            try:
                ingest_season(conn, year)
            except Exception as exc:  # noqa: BLE001 - log and continue to next season
                print(f"  FAILED season {year}: {exc}")
    print("Done.")


if __name__ == "__main__":
    main()
