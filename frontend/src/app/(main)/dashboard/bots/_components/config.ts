export const dashboardConfig = {
  title: "Bot Run IDs",
  apiBase: "/process-logs",
  sections: {
    cards: {
      show: false,
      metrics: [
        { label: "Active Schools", key: "is_current", type: "countTrue", color: "green" },
        { label: "Inactive Schools", key: "is_current", type: "countFalse", color: "red" },
      ],
    },
    chart: {
      show: false,
      xKey: "county",
      yKey: "district",
      label: "Schools by District",
      color: "var(--chart-1)",
    },
    table: {
      show: true,
      displayKeys: ["runid", "voucher_id", "invoice", "amount", "status"],
      labels: {
        runid: "Run ID",
        voucher_id: "Voucher",
        invoice: "Invoice",
        amount: "Amount",
        status: "Status",
      },
      keepFullRecord: true,
    },
  },
};
