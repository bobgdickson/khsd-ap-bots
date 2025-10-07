"use client";

import * as React from "react";

import type { ColumnDef } from "@tanstack/react-table";
import { z } from "zod";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api/client";
import { toast } from "sonner";

import { DataTable as DataTableNew } from "@/components/data-table/data-table";
import { DataTablePagination } from "@/components/data-table/data-table-pagination";
import { DataTableViewOptions } from "@/components/data-table/data-table-view-options";
import { withDndColumn } from "@/components/data-table/table-utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDataTableInstance } from "@/hooks/use-data-table-instance";

import { createTableColumns, TableRow } from "./columns";
import { dashboardConfig } from "../config";
import { tableSchema } from "./schema";

/**
 * Config-aware wrapper around your legacy DataTable layout.
 */
export function DataTable({ data: initialData }: { data: z.infer<typeof tableSchema>[] }) {
  const router = useRouter();
  const [data, setData] = React.useState(() => initialData);
  const [cancellingRunId, setCancellingRunId] = React.useState<string | null>(null);

  React.useEffect(() => {
    setData(initialData);
  }, [initialData]);

  const handleCancel = React.useCallback(
    async (row: TableRow) => {
      const full = (row as any).full ?? {};
      const runid: string | undefined = full.runid ?? row.runid;
      if (!runid) {
        toast.error("Missing run id", { description: "Unable to cancel without a run identifier." });
        return;
      }

      setCancellingRunId(runid);
      try {
        await apiClient.post(`/bot-runs/${encodeURIComponent(runid)}/cancel`, { reason: "Cancelled from dashboard" });

        setData((prev) =>
          prev.map((item) => {
            const itemFull = (item as any).full ?? {};
            const itemRunid = itemFull.runid ?? item.runid;
            if (itemRunid !== runid) return item;
            const updatedFull = {
              ...itemFull,
              status: "cancel_requested",
              cancel_requested: true,
            };
            return {
              ...item,
              status: "cancel_requested",
              cancel_requested: "true",
              full: updatedFull,
            } as TableRow;
          }),
        );

        toast.success(`Cancel requested for ${runid}`);
        router.refresh();
      } catch (error: any) {
        toast.error("Unable to cancel run", {
          description: error?.message ?? "Something went wrong while cancelling.",
        });
      } finally {
        setCancellingRunId(null);
      }
    },
    [router],
  );

  const actionColumn = React.useMemo(() => {
    return {
      id: "actions",
      header: "Actions",
      cell: ({ row }: { row: { original: TableRow } }) => {
        const full: any = row.original.full ?? {};
        const runid: string | undefined = full.runid ?? row.original.runid;
        const status = String(full.status ?? row.original.status ?? "").toLowerCase();
        const rawCancel = full.cancel_requested ?? row.original.cancel_requested;
        const cancelRequested = String(rawCancel).toLowerCase() === 'true';
        const isTerminal = ["completed", "failed", "cancelled"].includes(status);
        const canCancel = Boolean(runid) && !isTerminal && !cancelRequested;

        if (canCancel) {
          const isBusy = cancellingRunId === runid;
          return (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => handleCancel(row.original)}
              disabled={isBusy}
              className="flex items-center gap-1"
            >
              {isBusy ? "Cancelling" : "Cancel"}
            </Button>
          );
        }

        if (cancelRequested) {
          return <Badge variant="secondary">Cancel Requested</Badge>;
        }

        return null;
      },
    } satisfies ColumnDef<TableRow>;
  }, [cancellingRunId, handleCancel]);

  const baseColumns = React.useMemo(() => createTableColumns(actionColumn), [actionColumn]);
  const columns = React.useMemo(() => withDndColumn(baseColumns), [baseColumns]);

  const table = useDataTableInstance({
    data,
    columns,
    getRowId: (row) => String((row as any).id ?? Math.random()),
  });

  const { title } = dashboardConfig;

  return (
    <Tabs defaultValue="outline" className="w-full flex-col justify-start gap-6">
      <div className="flex items-center justify-between">
        <Label htmlFor="view-selector" className="sr-only">
          View
        </Label>

        {/* Mobile View Selector */}
        <Select defaultValue="outline">
          <SelectTrigger className="flex w-fit @4xl/main:hidden" size="sm" id="view-selector">
            <SelectValue placeholder="Select a view" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="outline">Outline</SelectItem>
            <SelectItem value="analytics">Analytics</SelectItem>
          </SelectContent>
        </Select>

        {/* Desktop Tabs */}
        <TabsList className="**:data-[slot=badge]:bg-muted-foreground/30 hidden **:data-[slot=badge]:size-5 **:data-[slot=badge]:rounded-full **:data-[slot=badge]:px-1 @4xl/main:flex">
          <TabsTrigger value="outline">{title}</TabsTrigger>
          <TabsTrigger value="analytics">
            Analytics <Badge variant="secondary">1</Badge>
          </TabsTrigger>
        </TabsList>

        <div className="flex items-center gap-2">
          <DataTableViewOptions table={table} />
          <Button variant="outline" size="sm" onClick={() => router.refresh()} className="flex items-center gap-1">
            <span className="hidden lg:inline">Refresh</span>
          </Button>
        </div>
      </div>

      {/* TABLE TAB */}
      <TabsContent value="outline" className="relative flex flex-col gap-4 overflow-auto">
        <div className="overflow-hidden rounded-lg border">
          <DataTableNew dndEnabled table={table} columns={columns} onReorder={setData} />
        </div>
        <DataTablePagination table={table} />
      </TabsContent>

      {/* SECOND TAB (optional future charts) */}
      <TabsContent value="analytics" className="flex flex-col">
        <div className="aspect-video w-full flex-1 rounded-lg border border-dashed" />
      </TabsContent>
    </Tabs>
  );
}
