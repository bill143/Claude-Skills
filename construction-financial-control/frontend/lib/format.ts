const usd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const usdCents = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
});

export const money = (value: number | null | undefined): string =>
  value === null || value === undefined ? "—" : usd.format(value);

export const moneyExact = (value: number | null | undefined): string =>
  value === null || value === undefined ? "—" : usdCents.format(value);

export const pct = (fraction: number): string => `${(fraction * 100).toFixed(1)}%`;

export const dateShort = (iso: string | null | undefined): string =>
  iso
    ? new Date(iso).toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" })
    : "—";

export const dateTime = (iso: string): string =>
  new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "numeric",
    minute: "2-digit",
  });

/** Signed VAC coloring helper: positive = savings, negative = overrun. */
export const vacTone = (value: number): "success" | "danger" | "muted" =>
  value > 0.005 ? "success" : value < -0.005 ? "danger" : "muted";
