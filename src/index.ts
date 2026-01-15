import { bot, registerBotCommands } from './bot';
import { logger } from './utils/logger';
import { config } from './config';

async function main() {
  try {
    logger.info('Starting Telegram bot...');
    logger.info(`Bot token: ${config.bot.token.substring(0, 10)}...`);
    logger.info(`A2E Base URL: ${config.a2e.baseUrl}`);
    logger.info(`Admin Telegram ID: ${config.bot.adminTgId}`);
    logger.info(`Test mode (no berry spending): ${config.testMode.enabled ? `ENABLED (only for admin ${config.bot.adminTgId})` : 'disabled'}`);
    logger.info(`NOWP baseURL=${config.nowpayments.baseUrl} apiKeyLen=${(config.nowpayments.apiKey || '').length}`);

    // Register bot commands with descriptions in all languages
    await registerBotCommands();

    // Start bot
    await bot.launch();

    logger.info('Bot started successfully');

    // Graceful shutdown
    process.once('SIGINT', () => {
      logger.info('SIGINT received, shutting down...');
      bot.stop('SIGINT');
      process.exit(0);
    });

    process.once('SIGTERM', () => {
      logger.info('SIGTERM received, shutting down...');
      bot.stop('SIGTERM');
      process.exit(0);
    });
  } catch (error: any) {
    logger.error(`Failed to start bot: ${error.message}`, error);
    process.exit(1);
  }
}

main();

