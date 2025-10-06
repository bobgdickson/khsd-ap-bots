export const dashboardConfig = {
  title: "School Directory",
  apiBase: "/api/v2/directory/schools",
  sections: {
    cards: {
      show: true,
      metrics: [
        { label: "Active Schools", key: "is_current", type: "countTrue", color: "green" },
        { label: "Inactive Schools", key: "is_current", type: "countFalse", color: "red" },
      ],
    },
    chart: {
      show: true,
      xKey: "county",
      yKey: "district",
      label: "Schools by District",
      color: "var(--chart-1)",
    },
    table: {
      show: true,
      displayKeys: ["name", "district", "county", "phone", "status_type"],
      labels: {
        name: "School",
        district: "District",
        county: "County",
        phone: "Phone",
        status_type: "Status",
      },
      keepFullRecord: true,
    },
  },
};
