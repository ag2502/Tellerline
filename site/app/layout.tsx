import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";

import { SITE_URL } from "@/lib/site";

import "./globals.css";

// Geist for words, Instrument Serif for the one italic phrase a headline leans on, Geist Mono
// for measured values. All three are SIL Open Font License.
const sans = Geist({ subsets: ["latin"], variable: "--font-sans-face", display: "swap" });
const serif = Instrument_Serif({ subsets: ["latin"], weight: "400", style: ["normal", "italic"], variable: "--font-serif-face", display: "swap" });
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
  themeColor: "#f6f5f1",
  colorScheme: "light",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB" className={`${sans.variable} ${serif.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
