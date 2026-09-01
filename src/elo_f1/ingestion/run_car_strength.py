"""CLI entrypoint: python -m elo_f1.ingestion.run_car_strength [--fastf1-from 2018] [--fastf1-to 2025]

Always computes the Tier A (Ergast-derived) proxy for every ingested season, since
it's pure local derivation with no network cost. FastF1 Tier B telemetry ingestion
is slow/heavy (one download+parse per race weekend) so it's opt-in via
--fastf1-from/--fastf1-to; omit both to skip it.
"""

import argparse

from elo_f1.ingestion import car_strength_ergast, car_strength_fastf1, fastf1_ingest
from elo_f1.storage.db import connect


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute car-strength-relative-to-field signals.")
    parser.add_argument("--fastf1-from", dest="fastf1_from", type=int, default=None)
    parser.add_argument("--fastf1-to", dest="fastf1_to", type=int, default=None)
    args = parser.parse_args()

    with connect() as conn:
        print("Computing Tier A (ergast_proxy) car strength for all seasons...")
        car_strength_ergast.compute_all(conn)

        if args.fastf1_from is not None:
            year_to = args.fastf1_to or args.fastf1_from
            print(f"Ingesting FastF1 telemetry for {args.fastf1_from}-{year_to}...")
            fastf1_ingest.ingest_seasons(conn, args.fastf1_from, year_to)
            print("Computing Tier B (fastf1_telemetry) car strength...")
            car_strength_fastf1.compute_all(conn, args.fastf1_from, year_to)

    print("Done.")


if __name__ == "__main__":
    main()
