export default function Badge({
  label,
  variant = "default"
}: {
  label: string;
  variant?: "default" | "good" | "warn" | "bad";
}) {
  const colorMap: Record<string, string> = {
    default: "background: var(--panel-muted); color: var(--muted)",
    good: "background: #e7f6ef; color: var(--green)",
    warn: "background: #fff4d6; color: var(--amber)",
    bad: "background: #fde8e7; color: var(--red)"
  };

  return (
    <span
      style={{
        ...Object.fromEntries(
          colorMap[variant].split("; ").map((s) => s.split(": "))
        ),
        display: "inline-flex",
        alignItems: "center",
        borderRadius: "4px",
        fontSize: "11px",
        fontWeight: 700,
        padding: "2px 6px",
        letterSpacing: "0.3px",
        textTransform: "uppercase"
      }}
    >
      {label}
    </span>
  );
}
