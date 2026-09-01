import type { StandingsRow } from "../types";

const API_BASE = "http://127.0.0.1:8000";

export async function fetchSeasons(): Promise<number[]> {
  const res = await fetch(`${API_BASE}/api/seasons`);
  if (!res.ok) throw new Error(`Failed to fetch seasons: ${res.status}`);
  return res.json();
}

export async function fetchStandings(year: number): Promise<StandingsRow[]> {
  const res = await fetch(`${API_BASE}/api/seasons/${year}/standings`);
  if (!res.ok) throw new Error(`Failed to fetch standings for ${year}: ${res.status}`);
  return res.json();
}
