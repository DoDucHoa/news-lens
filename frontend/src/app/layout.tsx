import type { Metadata } from "next";
import { Geist_Mono, IBM_Plex_Sans, Source_Serif_4 } from "next/font/google";
import "./globals.css";

const newsSans = IBM_Plex_Sans({
  variable: "--font-news-sans",
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

const newsSerif = Source_Serif_4({
  variable: "--font-news-serif",
  weight: ["400", "600", "700"],
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "News Lens",
  description: "Professional newsroom style interface for querying recent news with local RAG.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${newsSans.variable} ${newsSerif.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
