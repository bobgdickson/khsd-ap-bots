"use client";

import { useEffect, useMemo, useState } from "react";

import { InteractionStatus } from "@azure/msal-browser";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";

import { authFetchJson, getActiveAccount } from "@/auth/api-client";
import { getErrorMessage } from "@/auth/debug-log";

import { ChartAreaInteractive } from "./_components/chart-area-interactive";
import { dashboardConfig } from "./_components/config";
import { DataTable } from "./_components/data-table";
import { mapApiDataToTable } from "./_components/mapper";
import { SectionCards } from "./_components/section-cards";

export default function Page() {
  const { instance, accounts, inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (inProgress !== InteractionStatus.None) {
      return;
    }

    if (!isAuthenticated) {
      setLoading(false);
      setError("Not authenticated.");
      return;
    }

    const account = getActiveAccount(instance, accounts);
    if (!account) {
      setLoading(false);
      setError("No active Microsoft account found.");
      return;
    }

    let cancelled = false;
    const loadData = async () => {
      setLoading(true);
      setError(null);

      try {
        const payload = await authFetchJson<Record<string, unknown>[]>(instance, account, dashboardConfig.apiBase);
        if (!cancelled) {
          setData(Array.isArray(payload) ? payload : []);
        }
      } catch (fetchError) {
        if (!cancelled) {
          setError(getErrorMessage(fetchError));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadData();
    return () => {
      cancelled = true;
    };
  }, [accounts, inProgress, instance, isAuthenticated]);

  const tableData = useMemo(() => mapApiDataToTable(data), [data]);
  const { cards, chart, table } = dashboardConfig.sections;

  if (loading) {
    return <div className="p-4 text-sm">Loading dashboard...</div>;
  }

  if (error) {
    return <div className="p-4 text-sm text-red-600">Unable to load dashboard: {error}</div>;
  }

  return (
    <div className="@container/main flex flex-col gap-4 md:gap-6">
      <h1 className="mb-4 text-2xl font-semibold">{dashboardConfig.title}</h1>

      {cards.show && <SectionCards data={data} config={cards} />}
      {chart.show && <ChartAreaInteractive data={data} config={chart} />}
      {table.show && <DataTable data={tableData} />}
    </div>
  );
}
