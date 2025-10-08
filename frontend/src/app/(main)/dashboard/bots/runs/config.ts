export const dashboardConfig = {
  title: "Bot Runs",
  apiBase: "/bot-runs",
  sections: {
    cards: {
      show: false,
      metrics: [
        { label: "Successful Runs", key: "status", type: "countSuccess", color: "green" },
        { label: "Cancelled Runs", key: "status", type: "countcancelled", color: "red" },
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
      displayKeys: ["bot_name", "runid", "status", "cancel_requested", "updated_at"],
      labels: {
        bot_name: "Bot",
        runid: "Run ID",
        status: "Status",
        cancel_requested: "Cancel Requested",
        updated_at: "Updated",
      },
      keepFullRecord: true,
    },
  },
};

export const runLaunchers = [
  {
    id: "voucher-entry",
    label: "Voucher Entry Bot",
    endpoint: "/bots/voucher-entry",
    allowRentLine: true,
    vendorOptions: [
      {
        value: "cdw",
        label: "CDW",
        defaultAttachOnly: true,
        defaultRentLineEnabled: false,
        defaultInstructionId: "cdw",
      },
      {
        value: "royal",
        label: "Royal Industrial",
        defaultAttachOnly: false,
        defaultRentLineEnabled: false,
        defaultInstructionId: "none",
        defaultApoOverride: "KERNH-APO950043J",
      },
      {
        value: "class",
        label: "Class Leasing",
        defaultAttachOnly: false,
        defaultRentLineEnabled: true,
        defaultInstructionId: "class",
      },
      {
        value: "mobile",
        label: "Mobile Modular",
        defaultAttachOnly: false,
        defaultRentLineEnabled: true,
        defaultInstructionId: "mobile",
      },
      {
        value: "floyds",
        label: "Floyd's",
        defaultAttachOnly: false,
        defaultRentLineEnabled: false,
        defaultInstructionId: "none",
        defaultApoOverride: "KERNH-APO962523J",
      },
    ],
    instructionOptions: [
      { id: "none", label: "None", prompt: "" },
      {
        id: "cdw",
        label: "CDW Prompt",
        prompt: `INVOICE NUMBER RULES (CDW):
- The invoice number is ALPHANUMERIC (contains at least one letter and one digit).
- Typical length 6 characters, uppercase, no spaces. Examples: AF66R7Y, AB123C45.`,
      },
      {
        id: "class",
        label: "Class Leasing Prompt",
        prompt: `PO NUMBER RULES (Class Leasing):
- The PO number will often have the form of LN1234 or KERNH-LN5678
- Typically the Lease# XXXX will match the PO as LNXXXX.  Don't include trailing zero like _0`,
      },
      {
        id: "mobile",
        label: "Mobile Modular Prompt",
        prompt: `PO NUMBER RULES (Mobile Modular):
- The PO number will often have the form of KERNH-CON12345`,
      },
    ],
    defaults: {
      rent_line: "FY26",
      attach_only: false,
      test_mode: true,
    },
  },
];
