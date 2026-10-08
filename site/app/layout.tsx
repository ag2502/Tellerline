import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Geist, Geist_Mono } from "next/font/google";

import { SITE_URL } from "@/lib/site";

import "./globals.css";

// Bricolage Grotesque for the big type, Geist for reading, Geist Mono for measured values. All
// three are SIL Open Font License.
const display = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-display-face", display: "swap" });
const sans = Geist({ subsets: ["latin"], variable: "--font-sans-face", display: "swap" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono-face", display: "swap" });

const description =
  "Tellerline is a voice banking agent that verifies callers and handles their banking in " +
  "British English, with speech recognition, the language model and the voice all running on " +
  "one MacBook Air. Hear real recorded calls and the measurements behind them.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "Tellerline: bank calls, answered on one MacBook Air",
  description,
  applicationName: "Tellerline",
  authors: [{ name: "Amogh Gaikwad", url: "https://github.com/ag2502" }],
  keywords: [
    "voice agent",
    "on-device AI",
    "Apple Silicon",
    "MLX",
    "Pipecat",
    "Gemma 4",
    "Parakeet",
    "Kokoro",
    "banking",
  ],
  openGraph: {
    type: "website",
    title: "Tellerline: bank calls, answered on one MacBook Air",
    description,
    siteName: "Tellerline",
    locale: "en_GB",
  },
  twitter: { card: "summary_large_image", title: "Tellerline", description },
};

export const viewport: Viewport = {
  themeColor: "#07060d",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
