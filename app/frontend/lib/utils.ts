type ClassValue = string | number | null | false | undefined | ClassValue[] | Record<string, boolean | null | undefined>;

export function cn(...inputs: ClassValue[]) {
  const classes: string[] = [];
  const visit = (value: ClassValue) => {
    if (!value) return;
    if (typeof value === "string" || typeof value === "number") classes.push(String(value));
    else if (Array.isArray(value)) value.forEach(visit);
    else Object.entries(value).forEach(([name, enabled]) => enabled && classes.push(name));
  };
  inputs.forEach(visit);
  return classes.join(" ");
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Missing";
  return new Intl.NumberFormat("en-US", { notation: value >= 100_000 ? "compact" : "standard" }).format(value);
}

export function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Missing";
  return new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 2 }).format(value);
}

export function titleCase(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
