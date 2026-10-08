import type { Metadata, Viewport } from "next";
import { Martian_Mono, Mona_Sans } from "next/font/google";

import { SITE_URL } from "@/lib/site";

import "./globals.css";

// Mona Sans for words, pulled condensed for what a strip prints in capitals; Martian Mono for
// measured values. Both are variable in width, and both are SIL Open Font License.
const mona = Mona_Sans({
  subsets: ["latin"],
  axes: ["wdth"],
  variable: "--font-mona",
  display: "swap",
});
const martian = Martian_Mono({
  subsets: ["latin"],
  axes: ["wdth"],
  variable: "--font-martian",
  display: "swap",
});

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
  themeColor: "#e7eaed",
  colorScheme: "light",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB" className={`${mona.variable} ${martian.variable}`}>
      <body>{children}</body>
    </html>
  );
}
