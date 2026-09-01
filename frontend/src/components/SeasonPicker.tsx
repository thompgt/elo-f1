export function SeasonPicker({
  seasons,
  selected,
  onChange,
}: {
  seasons: number[];
  selected: number | null;
  onChange: (year: number) => void;
}) {
  return (
    <select
      value={selected ?? ""}
      onChange={(e) => onChange(Number(e.target.value))}
      className="season-picker"
    >
      {seasons
        .slice()
        .sort((a, b) => b - a)
        .map((year) => (
          <option key={year} value={year}>
            {year}
          </option>
        ))}
    </select>
  );
}
