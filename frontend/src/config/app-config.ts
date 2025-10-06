import packageJson from "../../package.json";

const currentYear = new Date().getFullYear();

export const APP_CONFIG = {
  name: "KHSD Bot Admin",
  version: packageJson.version,
  copyright: `© ${currentYear}, Bob Dickson.`,
  meta: {
    title: "KHSD Bot Admin",
    description:
      "KHSD Bot Admin is a modern, open-source dashboard for controlling KHSD Bot activity.",
  },
};
