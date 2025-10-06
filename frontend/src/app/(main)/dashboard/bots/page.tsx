import { apiClient } from "@/lib/api/client";

import { ChartAreaInteractive } from "./_components/chart-area-interactive";
import { dashboardConfig } from "./_components/config";
import { DataTable } from "./_components/data-table";
import { mapApiDataToTable } from "./_components/mapper";
import { SectionCards } from "./_components/section-cards";

export default async function Page() {
  const res = await apiClient.get(dashboardConfig.apiBase);
  const data = Array.isArray(res.data) ? res.data : [];
  const tableData = mapApiDataToTable(data);

  const { cards, chart, table } = dashboardConfig.sections;

  return (
    <div className="@container/main flex flex-col gap-4 md:gap-6">
      <h1 className="mb-4 text-2xl font-semibold">{dashboardConfig.title}</h1>

      {cards.show && <SectionCards data={data} config={cards} />}
      {chart.show && <ChartAreaInteractive data={data} config={chart} />}
      {table.show && <DataTable data={tableData} />}
    </div>
  );
}
