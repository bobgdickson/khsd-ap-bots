"use client";

import * as React from "react";

import { Plus } from "lucide-react";
import { z } from "zod";

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

import { tableColumns } from "./columns";
import { dashboardConfig } from "./config";
import { tableSchema } from "./schema";

/**
 * Config-aware wrapper around your legacy DataTable layout.
 */
export function DataTable({ data: initialData }: { data: z.infer<typeof tableSchema>[] }) {
  const [data, setData] = React.useState(() => initialData);

  // Apply your DnD and table instance logic
  const columns = withDndColumn(tableColumns);
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
          <Button variant="outline" size="sm">
            <Plus />
            <span className="hidden lg:inline">Add</span>
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
