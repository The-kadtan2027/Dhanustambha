export function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(digits);
}

export function formatCurrency(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2
  }).format(value);
}

export function verdictClass(verdict: string | undefined): string {
  const normalized = (verdict ?? "").toUpperCase();
  if (normalized === "OFFENSIVE") {
    return "good";
  }
  if (normalized === "DEFENSIVE") {
    return "warn";
  }
  return "bad";
}

export function setupLabel(setupType: string, notes: string | null | undefined): string {
  const marker = notes?.includes("A+") ? "A+ " : notes?.includes("HIGH") ? "HIGH " : "";
  return `${marker}${labelFromToken(setupType)}`;
}

export function labelFromToken(value: string | null | undefined): string {
  return value ? value.replaceAll("_", " ") : "-";
}
