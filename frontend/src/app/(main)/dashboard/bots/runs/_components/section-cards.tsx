"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { dashboardConfig } from "../config";

interface CardsProps {
  data: any[];
  config?: typeof dashboardConfig.sections.cards;
}

/**
 * Config-driven metric cards (counts, sums, etc.)
 */
export function SectionCards({ data, config }: CardsProps) {
  const cardsCfg = config ?? dashboardConfig.sections.cards;
  if (!cardsCfg?.show) return null;

  const { metrics } = cardsCfg;

  function computeMetric(metric: (typeof metrics)[0]) {
    const { key, type } = metric;

    switch (type) {
      case "count":
        return data.length;
      case "countTrue":
        return data.filter((r) => r[key]).length;
      case "countFalse":
        return data.filter((r) => !r[key]).length;
      default:
        return 0;
    }
  }

  return (
    <div className="mb-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {metrics.map((metric) => (
        <Card key={metric.label} className="border border-gray-200 shadow-md">
          <CardHeader>
            <CardTitle className="text-sm font-medium">{metric.label}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold" style={{ color: metric.color ?? "var(--chart-1)" }}>
              {computeMetric(metric)}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
