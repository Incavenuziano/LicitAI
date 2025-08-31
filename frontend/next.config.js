/** @type {import('next').NextConfig} */
const nextConfig = {
  i18n: { locales: ["pt-BR"], defaultLocale: "pt-BR" },
  transpilePackages: ["recharts"],
};

module.exports = nextConfig;
