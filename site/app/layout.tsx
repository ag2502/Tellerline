import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";

import { SITE_URL } from "@/lib/site";

import "./globals.css";

// IBM 3270: the lettering of the green-screen terminals bank tellers worked at for decades.
// BSD-3-Clause, Ricardo Banffy and the 3270font authors (public/fonts/LICENSE-3270.txt).
const wide = localFont({
  src: "./fonts/3270-Regular.woff2",
  variable: "--font-3270",
  display: "swap",
});
const semi = localFont({
  src: "./fonts/3270-SemiCondensed.woff2",
  variable: "--font-3270-semi",
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
  themeColor: "#020805",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB" className={`${wide.variable} ${semi.variable}`}>
      <body>
        {children}
        <div className="crt" aria-hidden="true">
          <i />
        </div>
      </body>
    </html>
  );
}
