/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Отключаем Server Actions для избежания ошибок в production
  experimental: {
    serverActions: {
      bodySizeLimit: '2mb',
    },
  },
  // Отключаем кэширование для production (если проблемы продолжаются)
  // onDemandEntries: {
  //   maxInactiveAge: 25 * 1000,
  //   pagesBufferLength: 2,
  // },
}

module.exports = nextConfig

