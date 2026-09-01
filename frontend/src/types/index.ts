export interface StandingsRow {
  driver_id: string;
  driver_name: string;
  constructor_id: string;
  constructor_name: string;
  points: number | null;
  elo_season_end: number;
  elo_season_average: number;
  final_points_position: number | null;
  races_started: number;
}
