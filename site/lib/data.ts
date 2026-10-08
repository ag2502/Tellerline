import { readFile } from "node:fs/promises";
import path from "node:path";

import siteData from "@/data/site.json";

import type { Call, SiteData } from "./types";

// Everything here is read at build time from files scripts/export_site_data.py writes from real
// runs on the MacBook Air M5. The page never states a number that isn't in them.

export const data = siteData as unknown as SiteData;

export async function loadCall(slug: string): Promise<Call> {
  const file = path.join(process.cwd(), "public", "calls", `${slug}.json`);
  return JSON.parse(await readFile(file, "utf8")) as Call;
}

export type Commit = { sha: string; message: string; date: string; url: string };

/** The repository's latest commits, refreshed hourly; empty if GitHub can't be reached. */
export async function recentCommits(limit = 6): Promise<Commit[]> {
  try {
    const response = await fetch(
      `https://api.github.com/repos/ag2502/Tellerline/commits?per_page=${limit}`,
      {
        headers: { Accept: "application/vnd.github+json", "User-Agent": "tellerline-site" },
        next: { revalidate: 3600 },
      },
    );
    if (!response.ok) return [];
    const body = (await response.json()) as {
      sha: string;
      html_url: string;
      commit: { message: string; author: { date: string } };
    }[];
    return body.map((item) => ({
      sha: item.sha.slice(0, 7),
      message: item.commit.message.split("\n")[0].replace(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2} - /, ""),
      date: item.commit.author.date,
      url: item.html_url,
    }));
  } catch {
    return [];
  }
}

export { ms, percent, seconds } from "./format";
