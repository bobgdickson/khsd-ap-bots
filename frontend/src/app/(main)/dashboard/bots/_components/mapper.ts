import { dashboardConfig } from "./config";
import { tableSchema } from "./schema";

export function mapApiDataToTable<T extends Record<string, any>>(records: T[]) {
  const keys = dashboardConfig.sections.table.displayKeys;
  const mapped = records.map((r, i) => {
    const row: Record<string, any> = { id: i + 1 };

    // Coerce everything into display-safe strings
    for (const key of keys) {
      const val = r[key];
      if (val === null || val === undefined) {
        row[key] = "—";
      } else if (typeof val === "object") {
        row[key] = JSON.stringify(val);
      } else {
        row[key] = String(val);
      }
    }

    if (dashboardConfig.sections.table.keepFullRecord) row.full = r;
    return row;
  });

  return tableSchema.array().parse(mapped);
}
