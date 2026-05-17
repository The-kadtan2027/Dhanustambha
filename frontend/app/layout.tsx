import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import Sidebar from "./components/navigation/Sidebar";

export const metadata: Metadata = {
  title: "Dhanustambha Dashboard",
  description: "Operational dashboard for NSE momentum scans and trade status"
};

export default function RootLayout({
  children
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="appLayout">
          <Sidebar />
          <div className="mainContent">{children}</div>
        </div>
      </body>
    </html>
  );
}
