import packageJson from "../../package.json";

const currentYear = new Date().getFullYear();

export const APP_CONFIG = {
  name: "Epoch Admin",
  version: packageJson.version,
  copyright: `© ${currentYear}, Epoch Forge.`,
  meta: {
    title: "Epoch Admin - Modern Next.js Dashboard Starter Template",
    description:
      "Epoch Admin is a modern, open-source dashboard starter template built with Next.js 15, Tailwind CSS v4, and shadcn/ui. Perfect for SaaS apps, admin panels, and internal tools—fully customizable and production-ready.",
  },
};
