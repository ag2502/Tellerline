export const REPO = "https://github.com/ag2502/Tellerline";

/** A file in the repository on GitHub, for linking a number to the run it came from. */
export function source(path: string): string {
  return `${REPO}/blob/main/${path}`;
}
