import { Inter } from "next/font/google";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export const metadata = {
  title: "GeoMemo — Geopolitical Intelligence",
  description: "Daily geopolitical intelligence for investment bankers, asset managers, and policymakers. Covering conflicts, trade, markets, and policy worldwide.",
  keywords: "geopolitics, intelligence, news, investment, policy, trade, sanctions, conflicts",
  openGraph: {
    title: "GeoMemo — Geopolitical Intelligence",
    description: "Daily geopolitical intelligence for global decision makers.",
    siteName: "GeoMemo",
    type: "website",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} antialiased`}>
        <Header />
        <main style={{ minHeight: 'calc(100vh - var(--header-height) - 200px)' }}>
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
