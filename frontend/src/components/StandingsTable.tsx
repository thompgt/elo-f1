import { useMemo, useState } from "react";
import type { StandingsRow } from "../types";

type SortKey = "driver_name" | "constructor_name" | "points" | "elo_season_end" | "elo_season_average";
type SortDir = "asc" | "desc";

interface Column {
  key: SortKey;
  label: string;
}

const COLUMNS: Column[] = [
  { key: "driver_name", label: "Driver" },
  { key: "constructor_name", label: "Team" },
  { key: "points", label: "Points" },
  { key: "elo_season_end", label: "Elo (season-end)" },
  { key: "elo_season_average", label: "Elo (season-avg)" },
];

export function StandingsTable({ rows }: { rows: StandingsRow[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("elo_season_end");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      const an = av as number;
      const bn = bv as number;
      return sortDir === "asc" ? an - bn : bn - an;
    });
    return copy;
  }, [rows, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "driver_name" || key === "constructor_name" ? "asc" : "desc");
    }
  }

  return (
    <table className="standings-table">
      <thead>
        <tr>
          {COLUMNS.map((col) => (
            <th key={col.key} onClick={() => handleSort(col.key)} className="sortable">
              {col.label}
              {sortKey === col.key ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr key={row.driver_id}>
            <td>{row.driver_name}</td>
            <td>{row.constructor_name}</td>
            <td>{row.points ?? "-"}</td>
            <td>{row.elo_season_end.toFixed(0)}</td>
            <td>{row.elo_season_average.toFixed(0)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
