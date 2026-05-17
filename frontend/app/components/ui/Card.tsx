export default function Card({
  title,
  icon,
  children,
  className = ""
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panelHeader">
        <span className="panelIcon">{icon}</span>
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}
