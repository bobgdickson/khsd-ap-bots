import { ColumnDef } from "@tanstack/react-table";
import { z } from "zod";

import { dashboardConfig } from "../config";
import { tableSchema } from "./schema";
import { TableCellViewer } from "./table-cell-viewer";

function labelFor(key: string) {
  return (dashboardConfig.sections.table.labels as Record<string, string>)[key] ?? key;
}

export type TableRow = z.infer<typeof tableSchema>;

export function createTableColumns(extra?: ColumnDef<TableRow>): ColumnDef<TableRow>[] {
  const base = dashboardConfig.sections.table.displayKeys.map((key) => ({
    accessorKey: key,
    header: labelFor(key),
    cell: ({ row }: { row: { original: TableRow } }) =>
      key === dashboardConfig.sections.table.displayKeys[0] ? (
        <TableCellViewer item={row.original} />
      ) : (
        String(row.original[key as keyof TableRow] ?? "–")
      ),
  })) as ColumnDef<TableRow>[];

  return extra ? [...base, extra] : base;
}
