"""Ad hoc read-only sanity checks: row counts per season, known-storyline Elo spot checks."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elo_f1.storage.db import connect  # noqa: E402


def row_counts_per_season() -> None:
    with connect() as conn:
        print(f"{'year':>6} {'races':>6} {'results':>8} {'quali':>6} {'elo_rows':>9}")
        for row in conn.execute("SELECT year FROM seasons ORDER BY year"):
            year = row["year"]
            races = conn.execute("SELECT COUNT(*) FROM races WHERE year=?", (year,)).fetchone()[0]
            results = conn.execute(
                "SELECT COUNT(*) FROM race_results rr JOIN races r ON r.race_id=rr.race_id WHERE r.year=?",
                (year,),
            ).fetchone()[0]
            quali = conn.execute(
                "SELECT COUNT(*) FROM qualifying_results qr JOIN races r ON r.race_id=qr.race_id WHERE r.year=?",
                (year,),
            ).fetchone()[0]
            elo_rows = conn.execute("SELECT COUNT(*) FROM driver_elo_season_summary WHERE year=?", (year,)).fetchone()[0]
            print(f"{year:>6} {races:>6} {results:>8} {quali:>6} {elo_rows:>9}")


def storyline_spot_check() -> None:
    storylines = [
        ("max_verstappen", 2016), ("max_verstappen", 2017), ("max_verstappen", 2023),
        ("ricciardo", 2017),  # should now be close to / above 2017 Verstappen (avg), not far below
        ("perez", 2023), ("alonso", 2023), ("stroll", 2023),
        ("hamilton", 2014), ("rosberg", 2014), ("hamilton", 2018),
        ("hamilton", 2016), ("button", 2011),
        ("alonso", 2012), ("senna", 1991), ("michael_schumacher", 2004),  # should rank #1 or near it in-season
        ("max_verstappen", 2024), ("perez", 2024),  # long-tenured pairing: growth should be flattening, not compounding
        ("antonelli", 2025), ("antonelli", 2026), ("russell", 2026),  # 2026 Antonelli should rate above 2026 Russell despite a bad 2025 (seasons are independent)
    ]
    with connect() as conn:
        print(f"\n{'driver':>16} {'year':>6} {'elo_end':>9} {'elo_avg':>9} {'points':>8}")
        for driver_id, year in storylines:
            row = conn.execute(
                "SELECT elo_season_end, elo_season_average, points FROM driver_elo_season_summary WHERE year=? AND driver_id=?",
                (year, driver_id),
            ).fetchone()
            if row is None:
                print(f"{driver_id:>16} {year:>6} {'(no data)':>9}")
                continue
            print(f"{driver_id:>16} {year:>6} {row['elo_season_end']:>9.1f} {row['elo_season_average']:>9.1f} {row['points'] or 0:>8.0f}")


if __name__ == "__main__":
    row_counts_per_season()
    storyline_spot_check()
