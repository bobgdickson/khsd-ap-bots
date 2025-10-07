import { z } from "zod";

import { dashboardConfig } from "../config";

const shape: Record<string, z.ZodTypeAny> = { id: z.number() };
for (const key of dashboardConfig.sections.table.displayKeys) shape[key] = z.string();

export const tableSchema = z
  .object({
    ...shape,
    full: z.any().optional(),
  })
  .passthrough();

export type TableRow = z.infer<typeof tableSchema>;
