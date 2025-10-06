import { dashboardConfig } from "./config";
import { tableSchema } from "./schema";

export function mapApiDataToTable<T extends Record<string, any>>(records: T[]) {
  const keys = dashboardConfig.sections.table.displayKeys;
  const mapped = records.map((r, i) => {
    const row: Record<string, any> = { id: i + 1 };
    for (const key of keys) row[key] = r[key] ?? "—";
    if (dashboardConfig.sections.table.keepFullRecord) row.full = r;
    return row;
  });
  return tableSchema.array().parse(mapped);
}
