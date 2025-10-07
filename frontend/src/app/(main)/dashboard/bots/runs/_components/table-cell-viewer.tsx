"use client";

import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerTrigger,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
} from "@/components/ui/drawer";
import { useIsMobile } from "@/hooks/use-mobile";

import { dashboardConfig } from "../config";

/**
 * Generic cell viewer / detail drawer.
 * Displays all key-value pairs from the backend record.
 */
export function TableCellViewer({ item }: { item: any }) {
  const isMobile = useIsMobile();
  const full = item.full ?? item;
  const titleField = dashboardConfig.sections.table.displayKeys[0] ?? "Record";

  // optional custom label for title
  const title = full[titleField] ?? full.name ?? full.id ?? dashboardConfig.title ?? "Details";

  return (
    <Drawer direction={isMobile ? "bottom" : "right"}>
      <DrawerTrigger asChild>
        <Button variant="link" className="p-0 font-medium text-blue-600 hover:underline">
          {title}
        </Button>
      </DrawerTrigger>

      <DrawerContent className="max-h-[85vh] overflow-y-auto">
        <DrawerHeader>
          <DrawerTitle>{title}</DrawerTitle>
          <DrawerDescription>Full record details</DrawerDescription>
        </DrawerHeader>

        <div className="space-y-2 p-6 text-sm">
          {Object.entries(full).map(([key, value]) => (
            <div key={key} className="break-all">
              <span className="text-muted-foreground font-medium">{key}</span>: {String(value ?? "—")}
            </div>
          ))}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
