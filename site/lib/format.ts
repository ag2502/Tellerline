// How the page prints a measurement. Kept apart from data.ts so the browser can use it too.

export function seconds(value: number, digits = 2): string {
  return `${value.toFixed(digits)} s`;
}

export function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function ms(value: number): string {
  return `${Math.round(value)} ms`;
}
