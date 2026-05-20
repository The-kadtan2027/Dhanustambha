export default function Metric({ 
  label, value, highlight = false 
}: { 
  label: string; value: string; highlight?: boolean 
}) {
  return (
    <div className={`metric ${highlight ? 'highlight' : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
