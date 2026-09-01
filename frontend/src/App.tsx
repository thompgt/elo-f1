import { useEffect, useState } from "react";
import { fetchSeasons, fetchStandings } from "./api/client";
import { SeasonPicker } from "./components/SeasonPicker";
import { StandingsTable } from "./components/StandingsTable";
import type { StandingsRow } from "./types";
import "./app.css";

export default function App() {
  const [seasons, setSeasons] = useState<number[]>([]);
  const [year, setYear] = useState<number | null>(null);
  const [rows, setRows] = useState<StandingsRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSeasons()
      .then((s) => {
        setSeasons(s);
        if (s.length) setYear(s[s.length - 1]);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (year == null) return;
    fetchStandings(year)
      .then(setRows)
      .catch((e) => setError(String(e)));
  }, [year]);

  return (
    <div className="app">
      <h1>elo-f1 standings</h1>
      <p className="subtitle">
        Driving-quality Elo ratings, controlling for car and teammate strength.
      </p>
      {error && <p className="error">{error}</p>}
      {year != null && (
        <SeasonPicker seasons={seasons} selected={year} onChange={setYear} />
      )}
      <StandingsTable rows={rows} />
    </div>
  );
}
