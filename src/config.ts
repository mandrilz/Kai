import dotenv from 'dotenv';
import path from 'path';

// Load .env file explicitly (supports both development and production)
dotenv.config({ path: path.resolve(process.cwd(), '.env') });

export const config = {
  bot: {
    token: process.env.BOT_TOKEN || '',
    adminTgId: parseInt(process.env.ADMIN_TG_ID || '0'),
  },
  testMode: {
    enabled: (process.env.TESTMODE_ENABLED || '0') === '1',
  },
  database: {
    url: process.env.DATABASE_URL || '',
  },
  a2e: {
    baseUrl: process.env.A2E_BASE_URL || 'https://video.a2e.ai',
    bearerToken: process.env.A2E_BEARER_TOKEN || '',
  },
  polling: {
    intervalMs: 1500, // Poll every 1.5 seconds
    maxDurationMs: 240000, // 4 minutes timeout (NanoBanana can take 2-3 minutes)
  },
  session: {
    photoTtlMs: 10 * 60 * 1000, // 10 minutes
  },
  referral: {
    dailyLimitEnabled: (process.env.REFERRAL_DAILY_LIMIT_ENABLED || '0') === '1',
    dailyLimit: parseInt(process.env.REFERRAL_DAILY_LIMIT || '10', 10),
  },
  nowpayments: {
    apiKey: process.env.NOWPAYMENTS_API_KEY || '',
    email: process.env.NOWPAYMENTS_EMAIL || '',
    password: process.env.NOWPAYMENTS_PASSWORD || '',
    baseUrl: (() => {
      const url = process.env.NOWPAYMENTS_BASE_URL || 'https://api.nowpayments.io';
      // Remove trailing /v1 if present (to avoid double /v1/v1/invoice)
      return url.replace(/\/v1\/?$/, '');
    })(),
  },
};

// Validate required config
if (!config.bot.token) {
  throw new Error('BOT_TOKEN is required');
}
if (!config.database.url) {
  throw new Error('DATABASE_URL is required');
}
if (!config.a2e.bearerToken) {
  throw new Error('A2E_BEARER_TOKEN is required');
}

