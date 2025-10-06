import { ColumnDef } from "@tanstack/react-table";
import { z } from "zod";

import { dashboardConfig } from "./config";
import { tableSchema } from "./schema";
import { TableCellViewer } from "./table-cell-viewer";

function labelFor(key: string) {
  return (dashboardConfig.sections.table.labels as Record<string, string>)[key] ?? key;
}

export const tableColumns: ColumnDef<z.infer<typeof tableSchema>>[] = dashboardConfig.sections.table.displayKeys.map(
  (key) => ({
    accessorKey: key,
    header: labelFor(key),
    cell: ({ row }) =>
      key === dashboardConfig.sections.table.displayKeys[0] ? (
        <TableCellViewer item={row.original} />
      ) : (
        String(row.original[key as keyof typeof row.original] ?? "—")
      ),
  }),
);
