"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAccountSize } from "../../../hooks/useAccountSize";

export default function Sidebar() {
  const pathname = usePathname();
  const [accountSize, setAccountSize] = useAccountSize();

  return (
    <aside className="sidebar">
      <h2>Dhanustambha</h2>
      <div className="sidebarNav">
        <Link href="/" className={`sidebarNavItem ${pathname === "/" ? "active" : ""}`}>Dashboard</Link>
        <Link href="/scanners" className={`sidebarNavItem ${pathname === "/scanners" ? "active" : ""}`}>Scanners</Link>
        <Link href="/trades" className={`sidebarNavItem ${pathname === "/trades" ? "active" : ""}`}>Trade Book</Link>
        <Link href="/journal" className={`sidebarNavItem ${pathname === "/journal" ? "active" : ""}`}>Journal</Link>
      </div>
      <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: "8px" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
          <span>Account Size (₹)</span>
          <input
            type="number"
            value={accountSize}
            onChange={(e) => setAccountSize(Number(e.target.value))}
            step="10000"
            style={{ padding: "4px", background: "var(--bg-base)", color: "var(--text-main)", border: "1px solid var(--border-subtle)", borderRadius: "4px" }}
          />
        </label>
      </div>
    </aside>
  );
}
