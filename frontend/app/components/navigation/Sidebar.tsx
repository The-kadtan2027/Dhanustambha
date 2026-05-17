"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";

export default function Sidebar() {
  const pathname = usePathname();
  const [accountSize, setAccountSize] = useState(500000);

  useEffect(() => {
    const saved = localStorage.getItem("dhanustambha_account_size");
    if (saved) setAccountSize(Number(saved));
  }, []);

  const handleAccountSizeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    setAccountSize(val);
    localStorage.setItem("dhanustambha_account_size", val.toString());
  };

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
          <input type="number" value={accountSize} onChange={handleAccountSizeChange} step="10000" style={{ padding: "4px", background: "var(--bg-base)", color: "var(--text-main)", border: "1px solid var(--border-subtle)", borderRadius: "4px" }} />
        </label>
      </div>
    </aside>
  );
}
