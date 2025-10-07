"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { dashboardConfig } from "../config";

interface ChartProps {
  data: any[];
  config?: typeof dashboardConfig.sections.chart;
}

/**
 * Generic interactive area chart
 * Reads axis keys, colors, and labels from config.
 */
export function ChartAreaInteractive({ data, config }: ChartProps) {
  const chartCfg = config ?? dashboardConfig.sections.chart;
  if (!chartCfg?.show) return null;

  const { xKey, yKey, color, label } = chartCfg;

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>{label ?? "Chart"}</CardTitle>
      </CardHeader>
      <CardContent className="h-[400px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="color" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color ?? "#3b82f6"} stopOpacity={0.8} />
                <stop offset="95%" stopColor={color ?? "#3b82f6"} stopOpacity={0.1} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey={xKey} stroke="#9ca3af" />
            <YAxis stroke="#9ca3af" />
            <Tooltip />
            <Area type="monotone" dataKey={yKey} stroke={color ?? "#3b82f6"} fillOpacity={1} fill="url(#color)" />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
