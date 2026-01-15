import { Telegraf, Context } from 'telegraf';
import axios from 'axios';
import sizeOf from 'image-size';
import { config } from './config';
import { prisma } from './db/prisma';
import { creditsService } from './services/credits.service';
import { paymentsService, PAYMENT_PACKAGES, CRYPTO_PAYMENT_PRICES } from './services/payments.service';
import { cryptoPaymentTracker } from './services/crypto-payment-tracker.service';
import { sessionService } from './services/session.service';
import { referralService } from './services/referral.service';
import { utmTrackingService } from './services/utm-tracking.service';
import { a2eClient } from './integrations/a2e.client';
import { nowPaymentsClient, NowPaymentsInvoice } from './integrations/nowpayments.client';
import { requestQueue } from './utils/request-queue';
import { pendingTasksService } from './services/pending-tasks.service';
import { getProcessingOptionById } from './prompts/photo';
import {
  getMainMenuKeyboard,
  getProcessingOptionsKeyboard,
  getProcessingTypesKeyboard,
  getPaymentPackagesKeyboard,
  getBackToMenuKeyboard,
  getLanguageSelectionKeyboard,
  getTermsAgreementKeyboard,
  getProceedPaymentKeyboard,
  getReferralKeyboard,
  getPaymentMethodKeyboard,
  getCryptoPaymentKeyboard,
} from './ui/keyboards';
import { logger } from './utils/logger';
import { formatBerriesCount, getTranslation, Language } from './i18n/translations';
import { zonedTimeToUtc, utcToZonedTime } from 'date-fns-tz';
import { startOfDay, endOfDay } from 'date-fns';

// Helper function to safely answer callback queries (ignore expired queries)
async function safeEditMessageText(
  chatId: number,
  messageId: number,
  text: string,
  options?: any
) {
  try {
    await bot.telegram.editMessageText(chatId, messageId, undefined, text, options);
  } catch (error: any) {
    // Ignore "message is not modified" error (expected when content is the same)
    if (error.response?.error_code === 400 && 
        error.message?.includes('message is not modified')) {
      // This is expected when trying to edit a message to the same content
      return;
    }
    // Log other errors but don't throw
    logger.error(`Error editing message ${messageId}: ${error.message}`);
  }
}

async function safeAnswerCbQuery(ctx: any, text?: string) {
  try {
    if (text) {
      await ctx.answerCbQuery(text);
    } else {
      await ctx.answerCbQuery();
    }
  } catch (error: any) {
    // Ignore errors for expired callback queries
    if (error.response?.error_code === 400 && 
        (error.response?.description?.includes('query is too old') || 
         error.response?.description?.includes('query ID is invalid'))) {
      logger.debug(`Ignoring expired callback query: ${error.response?.description}`);
    } else {
      // Re-throw other errors
      throw error;
    }
  }
}

// Increase handler timeout to 5 minutes (300000ms) to allow long-running image processing
const bot = new Telegraf(config.bot.token, {
  handlerTimeout: 300000, // 5 minutes - longer than maxDurationMs (4 minutes)
});

// Helper to get user ID from context
function getUserId(ctx: Context): number {
  if (!ctx.from) {
    throw new Error('User not found in context');
  }
  return ctx.from.id;
}

// Helper to get user language
async function getUserLanguage(tgId: number): Promise<Language | null> {
  const user = await creditsService.getOrCreateUser(tgId);
  return (user.language as Language) || null;
}

// Helper to check if user completed onboarding
async function checkOnboarding(ctx: Context): Promise<boolean> {
  const tgId = getUserId(ctx);
  const user = await creditsService.getOrCreateUser(tgId);
  const lang = (user.language as Language) || null;
  const t = getTranslation(lang);

  if (!user.language) {
    await ctx.reply(t.languageSelection, {
      reply_markup: getLanguageSelectionKeyboard(),
    });
    return false;
  }

  if (!user.termsAccepted) {
    await ctx.reply(t.termsText, {
      reply_markup: getTermsAgreementKeyboard(lang),
      parse_mode: 'Markdown',
    });
    return false;
  }

  return true;
}

// Helper to send main menu
async function sendMainMenu(ctx: Context, lang: Language | null = null) {
  const tgId = getUserId(ctx);
  const userLang = lang || await getUserLanguage(tgId);
  const t = getTranslation(userLang);
  await ctx.reply(t.welcome, {
    reply_markup: getMainMenuKeyboard(userLang),
  });
}

// Start command
bot.command('start', async (ctx) => {
  const tgId = getUserId(ctx);
  const user = await creditsService.getOrCreateUser(tgId);
  const lang = (user.language as Language) || null;
  const t = getTranslation(lang);

  // Get parameter after /start
  const startPayload = ctx.message?.text?.split(' ')[1];
  const chatType = ctx.chat?.type || 'private';

  // Handle payment success redirect: /start pay_ok_<orderId>[?payment_id=...]
  // NOWPayments may pass payment_id as URL parameter after successful payment
  if (startPayload && startPayload.startsWith('pay_ok_')) {
    let orderId = startPayload.replace('pay_ok_', '');
    let paymentIdFromUrl: string | undefined;
    
    // Check if payment_id is passed as URL parameter
    // Format: pay_ok_<orderId>?payment_id=<paymentId>
    // Telegram deep link: https://t.me/bot?start=pay_ok_<orderId>_<paymentId>
    // OR check ctx.startParam or URL params if available
    
    // Try to extract payment_id from startPayload if it's in format: pay_ok_<orderId>_<paymentId>
    const parts = orderId.split('_');
    if (parts.length > 3) {
      // Format: tg_<userId>_<timestamp>_<paymentId>
      // OR: <orderId>_<paymentId>
      // Try last part as potential payment_id (numeric ID)
      const lastPart = parts[parts.length - 1];
      if (lastPart && /^\d+$/.test(lastPart) && lastPart.length > 5) {
        // Looks like a payment_id (long numeric ID)
        paymentIdFromUrl = lastPart;
        orderId = parts.slice(0, -1).join('_');
        logger.info(`Extracted payment_id from URL: ${paymentIdFromUrl}, order_id: ${orderId}`);
      }
    }
    
    logger.info(`User ${tgId} returned from successful payment, order_id=${orderId}, payment_id_from_url=${paymentIdFromUrl || 'none'}`);
    
    // Find tracker by orderId to get invoice_id
    const tracker = cryptoPaymentTracker.getPaymentByOrderId(orderId, tgId);
    
    if (tracker) {
      // Try to check payment status directly if payment_id is available from URL
      // Or try to find payment via NOWPayments API by order_id
      // This happens when payment exists in NOWPayments but not yet in our DB
      try {
        let foundPayment: any = null;
        
        // If payment_id is available from URL, check it directly
        if (paymentIdFromUrl) {
          try {
            logger.info(`Checking payment status directly via payment_id from URL: ${paymentIdFromUrl}`);
            const paymentDetails = await nowPaymentsClient.getPaymentStatus(paymentIdFromUrl);
            
            // Verify order_id matches
            if (paymentDetails.order_id === orderId) {
              foundPayment = paymentDetails;
              logger.info(`Payment found via payment_id from URL: payment_id=${paymentIdFromUrl}, order_id=${orderId}, status=${paymentDetails.payment_status}`);
            } else {
              logger.warn(`Payment_id ${paymentIdFromUrl} exists but order_id mismatch: expected ${orderId}, got ${paymentDetails.order_id}`);
            }
          } catch (paymentError: any) {
            logger.warn(`Failed to check payment via payment_id from URL ${paymentIdFromUrl}: ${paymentError.message}`);
          }
        }
        
        // If payment not found via payment_id, try to find via order_id (may not work without JWT)
        if (!foundPayment) {
          logger.debug(`Trying to find payment via order_id (may require JWT)...`);
          foundPayment = await nowPaymentsClient.findPaymentByOrderId(orderId);
        }
        
        if (foundPayment && foundPayment.payment_id && foundPayment.payment_status) {
          // Payment found via NOWPayments API - check if already processed
          // CRITICAL: Convert payment_id to string (NOWPayments returns it as number)
          const paymentIdStr = String(foundPayment.payment_id);
          const payment = await prisma.payment.findFirst({
            where: {
              telegramPaymentChargeId: paymentIdStr,
              provider: 'nowpayments',
            },
          });
          
          if (payment) {
            // Payment already processed
            const lang = await getUserLanguage(tgId);
            const t = getTranslation(lang);
            await ctx.reply(t.paymentSuccess);
            await showWallet(tgId);
            return;
          }
          
          // Payment exists in NOWPayments but not in our DB - process it
          if (nowPaymentsClient.isPaymentPaid(foundPayment.payment_status)) {
            const sku = tracker.sku;
            const pkg = paymentsService.getPackageBySku(sku);
            
            if (pkg) {
              // CRITICAL: Convert payment_id to string (NOWPayments returns it as number)
              const paymentIdStr = String(foundPayment.payment_id);
              const success = await paymentsService.handleCryptoPayment(
                tgId,
                sku,
                paymentIdStr,
                foundPayment.price_amount,
                JSON.stringify(foundPayment)
              );
              
              if (success) {
                const lang = await getUserLanguage(tgId);
                const t = getTranslation(lang);
                await ctx.reply(t.paymentSuccess);
                await showWallet(tgId);
                
                // Remove from tracker
                cryptoPaymentTracker.removePayment(tracker.invoiceId);
                
                // Track payment event for UTM
                utmTrackingService.trackPayment(tgId, foundPayment.price_amount).catch((error) => {
                  logger.error(`Error tracking payment for user ${tgId}: ${error.message}`);
                });
                
                return;
              }
            }
          }
        }
      } catch (error: any) {
        logger.warn(`Failed to check payment status for order_id ${orderId}: ${error.message}`);
      }
    }
    
    // Payment not found or not completed yet, show wallet anyway
    const lang = await getUserLanguage(tgId);
    const t = getTranslation(lang);
    await ctx.reply(t.paymentSuccess || 'Payment processing...');
    await showWallet(tgId);
    return;
  }

  // Handle payment cancel redirect: /start pay_cancel_<orderId>
  if (startPayload && startPayload.startsWith('pay_cancel_')) {
    const orderId = startPayload.replace('pay_cancel_', '');
    logger.info(`User ${tgId} cancelled payment, order_id=${orderId}`);
    
    // Find invoice_id by order_id from tracker
    const tracker = cryptoPaymentTracker.getPaymentByOrderId(orderId, tgId);
    
    if (tracker) {
      cryptoPaymentTracker.cancelPayment(tracker.invoiceId, tgId);
    }

    const lang = await getUserLanguage(tgId);
    const t = getTranslation(lang);
    await ctx.reply(t.paymentFailed || 'Payment was cancelled.');
    return;
  }

  // Handle referral link: /start ref_<inviterTgId>
  if (startPayload && startPayload.startsWith('ref_')) {
    const inviterTgIdStr = startPayload.replace('ref_', '');
    const inviterTgId = parseInt(inviterTgIdStr, 10);
    
    if (!isNaN(inviterTgId) && inviterTgId !== tgId) {
      // Create referral relationship (async, don't block onboarding)
      // Pass metadata about source and chat type
      referralService.createReferral(inviterTgId, tgId, {
        createdFrom: 'start_param',
        createdChatType: chatType,
      }).catch((error) => {
        logger.error(`Error creating referral ${inviterTgId} -> ${tgId}: ${error.message}`);
      });
    }
  }

  // Track UTM source (async, don't block onboarding)
  // This handles utm_<source> links and records start_click event
  utmTrackingService.trackStart(tgId, startPayload, chatType).catch((error) => {
    logger.error(`Error tracking UTM start for user ${tgId}: ${error.message}`);
  });

  // Step 1: Check if language is selected
  if (!user.language) {
    await ctx.reply(t.languageSelection, {
      reply_markup: getLanguageSelectionKeyboard(),
    });
    return;
  }

  // Step 2: Check if terms are accepted
  if (!user.termsAccepted) {
    await ctx.reply(t.termsText, {
      reply_markup: getTermsAgreementKeyboard(lang),
      parse_mode: 'Markdown',
    });
    return;
  }

  // Step 3: Show main menu
  await sendMainMenu(ctx, lang);
});

// Upload command
bot.command('upload', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  await ctx.reply(t.uploadPhotoPrompt, {
    reply_markup: getBackToMenuKeyboard(lang),
  });
});

// Buy command
bot.command('buy', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  await ctx.reply(t.selectPaymentMethod, {
    reply_markup: getPaymentMethodKeyboard(lang),
  });
});

// Helper function to show wallet for a user (used after successful payment)
async function showWallet(tgId: number) {
  try {
    const lang = await getUserLanguage(tgId);
    const t = getTranslation(lang);
    const remaining = await creditsService.getTotalCredits(tgId);
    const message = t.walletBerriesMessage.replace('{count}', String(remaining));
    await bot.telegram.sendMessage(tgId, message, {
      reply_markup: getBackToMenuKeyboard(lang),
    });
  } catch (error: any) {
    logger.error(`Failed to show wallet for user ${tgId}: ${error.message}`);
  }
}

// Wallet command
bot.command('wallet', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  const remaining = await creditsService.getTotalCredits(tgId);
  const message = t.walletBerriesMessage.replace('{count}', String(remaining));
  await ctx.reply(message, {
    reply_markup: getBackToMenuKeyboard(lang),
  });
});

bot.command('invite', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);

  // Get bot username
  const botInfo = await bot.telegram.getMe();
  const referralLink = referralService.generateReferralLink(botInfo.username, tgId);

  // Use only referralTitle in the message - referralDescription is used in the share button
  const message = t.referralTitle;
  await ctx.reply(message, {
    reply_markup: getReferralKeyboard(lang, referralLink),
  });
});

// Language command
bot.command('language', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  await ctx.reply(t.languageSelection, {
    reply_markup: getLanguageSelectionKeyboard(),
  });
});

// Terms command - opens link in new tab
bot.command('terms', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  await ctx.reply(t.commandTermsDescription, {
    reply_markup: {
      inline_keyboard: [
        [{ text: t.commandTermsDescription, url: 'https://titsberry.github.io/terms.html' }],
      ],
    },
  });
});

// Privacy command - opens link in new tab
bot.command('privacy', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  await ctx.reply(t.commandPrivacyDescription, {
    reply_markup: {
      inline_keyboard: [
        [{ text: t.commandPrivacyDescription, url: 'https://titsberry.github.io/privacy.html' }],
      ],
    },
  });
});

// Admin stats command
bot.command('stats', async (ctx) => {
  const tgId = getUserId(ctx);

  if (!config.bot.adminTgId || tgId !== config.bot.adminTgId) {
    return;
  }

  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);

  const [totalUsers, totalPayments, paymentsAgg] = await Promise.all([
    prisma.user.count(),
    prisma.payment.count({ where: { provider: 'telegram_stars' } }),
    prisma.payment.aggregate({
      where: { provider: 'telegram_stars' },
      _sum: { amountRub: true },
    }),
  ]);

  const totalStars = paymentsAgg._sum.amountRub || 0;
  const avgCheck = totalPayments > 0 ? totalStars / totalPayments : 0;

  await ctx.reply(
    `${t.statsTitle}\n\n` +
      `${t.statsTotalUsers} ${totalUsers}\n` +
      `${t.statsTotalPayments} ${totalPayments}\n` +
      `${t.statsTotalStars} ⭐ ${totalStars}\n` +
      `${t.statsAvgCheck} ⭐ ${avgCheck.toFixed(2)}`,
    {
      reply_markup: getBackToMenuKeyboard(lang),
    }
  );
});

// Helper to check if user is admin
function isAdmin(tgId: number): boolean {
  return config.bot.adminTgId > 0 && tgId === config.bot.adminTgId;
}

// UTM Statistics commands (admin only)
bot.command('statsutm', async (ctx) => {
  const tgId = getUserId(ctx);
  
  if (!isAdmin(tgId)) {
    return;
  }

  try {
    const args = ctx.message?.text?.split(' ') || [];
    
    // /statsutm_today
    // "today" считается по Europe/Moscow (UTC+3)
    if (args[1] === '_today') {
      const MOSCOW_TIMEZONE = 'Europe/Moscow';
      
      // Получить текущее время в UTC
      const nowUtc = new Date();
      
      // Конвертировать текущее время в Moscow timezone
      const nowInMoscow = utcToZonedTime(nowUtc, MOSCOW_TIMEZONE);
      
      // Начало дня по Moscow time (00:00:00)
      const startOfTodayMoscow = startOfDay(nowInMoscow);
      
      // Конец дня по Moscow time (23:59:59.999)
      const endOfTodayMoscow = endOfDay(nowInMoscow);
      
      // Конвертировать границы дня из Moscow time в UTC для запроса к БД
      const startUtc = zonedTimeToUtc(startOfTodayMoscow, MOSCOW_TIMEZONE);
      const endUtc = zonedTimeToUtc(endOfTodayMoscow, MOSCOW_TIMEZONE);
      
      const stats = await utmTrackingService.getUtmStats(startUtc, endUtc);
      
      let message = '📊 UTM Statistics (Today - Moscow Time)\n\n';
      if (stats.length === 0) {
        message += 'No data for today.';
      } else {
        message += 'Source | Users | Generations | Payments | Conv %\n';
        message += '─'.repeat(60) + '\n';
        
        for (const stat of stats) {
          message += `${stat.source} | ${stat.uniqueUsers} | ${stat.firstGenerations} | ${stat.payments} | ${stat.conversionRate.toFixed(2)}%\n`;
        }
      }
      
      await ctx.reply(message);
      return;
    }
    
    // /statsutm <source> - detailed stats for specific source
    if (args[1] && args[1] !== '_today') {
      const source = args[1];
      const stats = await utmTrackingService.getSourceStats(source);
      
      let message = `📊 UTM Statistics: ${source}\n\n`;
      message += `👥 Unique Users: ${stats.uniqueUsers}\n`;
      message += `🎨 First Generations: ${stats.firstGenerations}\n`;
      message += `💳 Payments: ${stats.payments}\n`;
      message += `📈 Conversion Rate: ${stats.conversionRate.toFixed(2)}%\n`;
      message += `💰 Payment Conversion: ${stats.paymentConversionRate.toFixed(2)}%\n`;
      message += `📊 Total Users: ${stats.totalUsers}\n`;
      
      await ctx.reply(message);
      return;
    }
    
    // /statsutm - top sources (all time)
    const stats = await utmTrackingService.getUtmStats();
    
    let message = '📊 UTM Статистика (All Time)\n\n';
    if (stats.length === 0) {
      message += 'No data available.';
    } else {
      for (const stat of stats) {
        message += `Source: ${stat.source}\n`;
        message += `Users: ${stat.uniqueUsers}\n`;
        message += `Generations: ${stat.firstGenerations}\n`;
        message += `Payments: ${stat.payments}\n`;
        message += `Convertion: ${stat.conversionRate.toFixed(2)} %\n`;
        message += `Pay Convertions: ${stat.paymentConversionRate.toFixed(2)} %\n\n`;
      }
    }
    
    await ctx.reply(message);
  } catch (error: any) {
    logger.error(`Error getting UTM stats: ${error.message}`);
    await ctx.reply(`❌ Error: ${error.message}`);
  }
});

// Language selection handler
bot.action(/^lang_(.+)$/, async (ctx) => {
  const tgId = getUserId(ctx);
  const match = ctx.match;
  const language = match[1] as Language; // 'en', 'ru', 'id', 'pt', 'hi'

  await creditsService.updateLanguage(tgId, language);
  const t = getTranslation(language);
    await safeAnswerCbQuery(ctx, `${t.languageSet} ${language}`);

  // Show terms after language selection
  await ctx.editMessageText(t.termsText, {
    reply_markup: getTermsAgreementKeyboard(language),
    parse_mode: 'Markdown',
  });
});

// Terms agreement handler
bot.action('terms_agree', async (ctx) => {
  const tgId = getUserId(ctx);

  // Acknowledge immediately to avoid users needing to tap twice
  await safeAnswerCbQuery(ctx);

  await creditsService.acceptTerms(tgId);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);

  // Try to edit the terms message into the main menu; fallback to sending a new message
  try {
    await ctx.editMessageText(t.welcome, {
      reply_markup: getMainMenuKeyboard(lang),
    });
  } catch (error: any) {
    logger.warn(`Failed to edit terms message for user ${tgId}, sending main menu as a new message: ${error?.message || error}`);
    await ctx.reply(t.welcome, {
      reply_markup: getMainMenuKeyboard(lang),
    });
  }
});

// Change language handler
bot.action('change_language', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  await safeAnswerCbQuery(ctx);
  await ctx.reply(t.languageSelection, {
    reply_markup: getLanguageSelectionKeyboard(),
  });
});

// Main menu callback
bot.action('main_menu', async (ctx) => {
  const tgId = getUserId(ctx);
  const user = await creditsService.getOrCreateUser(tgId);
  const lang = (user.language as Language) || null;
  const t = getTranslation(lang);

  // Check if user has completed onboarding
  if (!user.language || !user.termsAccepted) {
      await safeAnswerCbQuery(ctx, t.pleaseCompleteSetup);
    if (!user.language) {
      await ctx.reply(t.languageSelection, {
        reply_markup: getLanguageSelectionKeyboard(),
      });
    } else if (!user.termsAccepted) {
      await ctx.reply(t.termsText, {
        reply_markup: getTermsAgreementKeyboard(lang),
        parse_mode: 'Markdown',
      });
    }
    return;
  }

  await safeAnswerCbQuery(ctx);
  await sendMainMenu(ctx, lang);
});

// Upload photo callback
bot.action('upload_photo', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  await safeAnswerCbQuery(ctx);
  await ctx.reply(t.uploadPhotoPrompt, {
    reply_markup: getBackToMenuKeyboard(lang),
  });
});

// Handle photo upload
bot.on('photo', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);

  try {
    // Get largest photo
    const photos = ctx.message.photo;
    if (!photos || photos.length === 0) {
      await ctx.reply(t.noPhotoFound);
      return;
    }

    const largestPhoto = photos[photos.length - 1];
    const fileId = largestPhoto.file_id;

    // Download photo to buffer (in memory only)
    const file = await ctx.telegram.getFile(fileId);
    const fileUrl = `https://api.telegram.org/file/bot${config.bot.token}/${file.file_path}`;
    
    // Download image buffer
    const response = await axios.get(fileUrl, {
      responseType: 'arraybuffer',
    });
    const imageBuffer = Buffer.from(response.data);

    // Determine MIME type
    const mime = file.file_path?.endsWith('.png') ? 'image/png' : 'image/jpeg';

    // Get image dimensions - try Telegram API first, then from buffer
    let width: number;
    let height: number;
    
    if (largestPhoto.width && largestPhoto.height) {
      // Use dimensions from Telegram API
      width = largestPhoto.width;
      height = largestPhoto.height;
      logger.info(`Photo dimensions from Telegram API: ${width}x${height}`);
    } else {
      // Determine dimensions from image buffer
      const dimensions = sizeOf(imageBuffer);
      width = dimensions.width || 960; // Fallback to default if not available
      height = dimensions.height || 1280; // Fallback to default if not available
      logger.info(`Photo dimensions from buffer: ${width}x${height}`);
    }

    // Store in session (in memory, TTL 10 minutes) with dimensions
    sessionService.storePhoto(tgId, imageBuffer, mime, width, height);

    // Note: fileId is not stored anywhere - only buffer in memory

    await ctx.reply(t.photoReceived, {
      reply_markup: getProcessingTypesKeyboard(lang),
    });
  } catch (error: any) {
    logger.error(`Error handling photo: ${error.message}`);
    await ctx.reply(t.errorReceivingPhoto);
  }
});

// Processing type selection (level 1)
bot.action('processing_types', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);

  const photo = sessionService.getPhoto(tgId);
  if (!photo) {
    await safeAnswerCbQuery(ctx, t.photoExpiredOrNotFound);
    await ctx.reply(t.photoExpired, {
      reply_markup: getBackToMenuKeyboard(lang),
    });
    return;
  }

  await safeAnswerCbQuery(ctx);

  try {
    await ctx.editMessageText(t.selectProcessing, {
      reply_markup: getProcessingTypesKeyboard(lang),
    });
  } catch {
    await ctx.reply(t.selectProcessing, {
      reply_markup: getProcessingTypesKeyboard(lang),
    });
  }
});

// Processing type selection handler (level 1 -> level 2)
bot.action(/^processing_type_(.+)$/, async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);

  const match = ctx.match;
  const typeId = match?.[1] || '';

  const photo = sessionService.getPhoto(tgId);
  if (!photo) {
    await safeAnswerCbQuery(ctx, t.photoExpiredOrNotFound);
    await ctx.reply(t.photoExpired, {
      reply_markup: getBackToMenuKeyboard(lang),
    });
    return;
  }

  await safeAnswerCbQuery(ctx);

  const keyboard = getProcessingOptionsKeyboard(lang, typeId);
  try {
    await ctx.editMessageText(t.selectProcessing, {
      reply_markup: keyboard,
    });
  } catch {
    await ctx.reply(t.selectProcessing, {
      reply_markup: keyboard,
    });
  }
});

// Handle processing option selection
bot.action(/^process_(.+)$/, async (ctx) => {
  const tgId = getUserId(ctx);
  const match = ctx.match;
  if (!match || !match[1]) {
    const lang = await getUserLanguage(tgId);
    const t = getTranslation(lang);
    await safeAnswerCbQuery(ctx, t.invalidProcessingOption);
    return;
  }

  const optionId = match[1];
  const option = getProcessingOptionById(optionId);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);

  if (!option) {
    await safeAnswerCbQuery(ctx, t.processingOptionNotFound);
    return;
  }

  // Check if user has photo in session
  const photo = sessionService.getPhoto(tgId);
  if (!photo) {
    await safeAnswerCbQuery(ctx, t.photoExpiredOrNotFound);
    await ctx.reply(t.photoExpired, {
      reply_markup: getBackToMenuKeyboard(lang),
    });
    return;
  }

  // Check processing lock
  if (!sessionService.acquireLock(tgId)) {
    await safeAnswerCbQuery(ctx, t.processingInProgress);
    return;
  }

  const berriesCost = option.berriesCost || 1;

  // TESTMODE_ENABLED=1 -> do not spend berries (only for admin)
  const isTestModeForUser = config.testMode.enabled && isAdmin(tgId);
  const reservedBerries = isTestModeForUser ? 0 : berriesCost;
  if (!isTestModeForUser) {
    const reservedOk = await creditsService.consumeBerries(tgId, berriesCost);
    if (!reservedOk) {
      sessionService.releaseLock(tgId);
      await safeAnswerCbQuery(ctx, t.noCredits);
      await ctx.reply(t.selectPaymentMethod, {
        reply_markup: getPaymentMethodKeyboard(lang),
      });
      return;
    }
  }

  await safeAnswerCbQuery(ctx);
  
  // Check queue status and inform user if needed
  const queueStatus = requestQueue.getStatus();
  if (queueStatus.queueLength > 0 || queueStatus.running >= queueStatus.maxConcurrent) {
    await ctx.reply(t.queueWaiting);
  }
  
  const processingMsg = await ctx.reply(t.processing);

  // Process image asynchronously - don't block the handler
  // This allows other users to upload photos and get responses immediately
  // Use setImmediate to ensure the handler returns immediately
  setImmediate(() => {
    processImageAsync(
      tgId,
      photo,
      option,
      berriesCost,
      reservedBerries,
      ctx.chat!.id,
      processingMsg.message_id,
      lang
    ).catch((error: any) => {
      logger.error(`Error in async image processing for user ${tgId}: ${error.message}`);
    });
  });
});

// Async function to process image without blocking the handler
async function processImageAsync(
  tgId: number,
  photo: { buffer: Buffer; mime: string; width: number; height: number },
  option: { id: string; prompt: string },
  berriesCost: number,
  reservedBerries: number,
  chatId: number,
  messageId: number,
  lang: Language | null
) {
  const t = getTranslation(lang);
  let refunded = false;
  let taskId: string | null = null;
  let pollingSucceeded = false; // Declare at function level so it's accessible in catch block
  
  try {
    // Process image with original dimensions
    logger.info(`Starting image processing for user ${tgId}, option: ${option.id}, prompt length: ${option.prompt.length}, image size: ${photo.width}x${photo.height}`);
    
    // We need to track taskId for pending tasks, so we'll call the methods separately
    // Step 1: Get presigned URL
    const { uploadUrl, key, bucket } = await a2eClient.getPresignedUploadUrl();
    
    // Step 2: Upload image
    const publicUrl = await a2eClient.uploadImage(uploadUrl, photo.buffer, key, bucket);
    
    // Step 3: Start task
    const taskName = `tg-${tgId}-${Date.now()}`;
    taskId = await a2eClient.startTask(taskName, option.prompt, [publicUrl], photo.width, photo.height);
    
    // Step 4: Poll until complete
    let resultImageUrl: string;
    try {
      resultImageUrl = await a2eClient.pollTaskUntilComplete(taskId, (status) => {
        logger.info(`Processing status: ${status}`);
      });
      pollingSucceeded = true;
      
      // Polling succeeded - we got the result
      // Remove from pending IMMEDIATELY to prevent background checker from delivering it again
      // We'll deliver the result in this flow, so no need to keep it in pending
      logger.info(`Task ${taskId} completed successfully via polling, removing from pending to prevent duplicate delivery`);
    } catch (pollError: any) {
      // Check if this is a timeout error
      if (pollError.isTimeout && pollError.taskId) {
        // Task timed out but may still complete - add to pending for background recovery
        logger.info(`Task ${taskId} timed out, adding to pending tasks for user ${tgId}`);
        pendingTasksService.addPendingTask(taskId, tgId, chatId, messageId, reservedBerries);
        
        // Update message to inform user
        await safeEditMessageText(
          chatId,
          messageId,
          t.timeoutStillRunningMessage,
          {
            reply_markup: getBackToMenuKeyboard(lang),
          }
        );
        
        // Immediately check if task is already completed (it might have finished during timeout)
        // This helps catch tasks that completed just before timeout
        setImmediate(() => {
          checkPendingTasks().catch((error) => {
            logger.error(`Error checking pending tasks immediately after timeout: ${error.message}`);
          });
        });
        
        // Don't throw - we'll check later via pending tasks
        return;
      }
      
      // For other errors (e.g., cooldown, network issues), add to pending for recovery
      logger.warn(`Task ${taskId} polling failed (not timeout), adding to pending tasks: ${pollError.message}`);
      pendingTasksService.addPendingTask(taskId, tgId, chatId, messageId, reservedBerries);
      
      // Update message to inform user that processing is ongoing
      try {
        await safeEditMessageText(
          chatId,
          messageId,
          t.timeoutStillRunningMessage,
          {
            reply_markup: getBackToMenuKeyboard(lang),
          }
        );
      } catch (editError: any) {
        logger.warn(`Failed to update message for task ${taskId}: ${editError.message}`);
      }
      
      // Don't throw - task is in pending, will be checked later
      return;
    }
    
    // IMPORTANT: Remove from pending IMMEDIATELY after successful polling
    // This prevents the background checker from delivering the same result
    // We only add to pending on errors/timeouts, so if we're here, task was never in pending
    // But just in case, check and remove if present
    if (taskId && pendingTasksService.getPendingTask(taskId)) {
      pendingTasksService.removePendingTask(taskId);
      logger.info(`Task ${taskId} was in pending, removed to prevent duplicate delivery`);
    }
    
    // Step 5: Download result image
    const resultResponse = await axios.get(resultImageUrl, {
      responseType: 'arraybuffer',
    });
    const resultBuffer = Buffer.from(resultResponse.data);
    
    // Step 6: Cleanup - delete task from A2E
    if (taskId) {
      try {
        await a2eClient.deleteTask(taskId);
      } catch (deleteError: any) {
        logger.warn(`Failed to delete task ${taskId} from A2E: ${deleteError.message}`);
        // Don't fail the whole process if deletion fails
      }
    }

    // Send result
    await bot.telegram.sendPhoto(chatId, {
      source: resultBuffer,
    });

    // Track first generation event (only once per user)
    utmTrackingService.trackFirstGeneration(tgId).catch((error) => {
      logger.error(`Error tracking first generation for user ${tgId}: ${error.message}`);
    });

    // Process referral reward (after successful generation)
    // This is the first successful generation for this user
    referralService.processReferralReward(tgId).then((result) => {
      if (result.success && result.inviterTgId) {
        // Notify inviter about the reward
        getUserLanguage(result.inviterTgId).then((inviterLang) => {
          const inviterT = getTranslation(inviterLang);
          bot.telegram.sendMessage(
            result.inviterTgId!,
            inviterT.referralRewardNotification
          ).catch((error) => {
            logger.error(`Failed to send referral notification to ${result.inviterTgId}: ${error.message}`);
          });
        }).catch(() => {});
      }
    }).catch((error) => {
      logger.error(`Error processing referral reward for user ${tgId}: ${error.message}`);
    });

    // Get remaining credits
    const remaining = await creditsService.getTotalCredits(tgId);

    await safeEditMessageText(
      chatId,
      messageId,
      `${t.done} ${t.remains} 🍓 ${remaining}`,
      {
        reply_markup: getBackToMenuKeyboard(lang),
      }
    );

    logger.info(`Task ${taskId} successfully delivered to user ${tgId}`);

    // Clear result buffer
    resultBuffer.fill(0);
    taskId = null;
  } catch (error: any) {
    logger.error(`Processing error: ${error.message}`);
    if (error.response) {
      logger.error(`API response error: ${JSON.stringify(error.response.data)}`);
    }

    // Check for minor detection error (code 1003)
    const apiError = error.response?.data;
    if (apiError && (apiError.code === 1003 || apiError.msg?.includes('Minor detected'))) {
      await safeEditMessageText(
        chatId,
        messageId,
        t.minorDetected,
        {
          reply_markup: getBackToMenuKeyboard(lang),
        }
      );

      // Remove from pending if task failed due to minor detection (permanent error)
      if (taskId) {
        pendingTasksService.removePendingTask(taskId);
        logger.info(`Task ${taskId} removed from pending due to minor detection error (permanent failure)`);
      }

      // Refund berries on error
      if (!refunded) {
        refunded = true;
        await creditsService.refundBerries(tgId, reservedBerries);
      }
    } else {
      // For other errors, check if task exists and might still complete
      // But if pollingSucceeded, we already got the result, so don't add to pending
      let errorMessage = t.errorProcessingPhoto + ' ';
      let isPermanentError = false;
      
      if (error.message.includes('timeout') || error.message.includes('taking longer than expected')) {
        errorMessage += t.timeoutMessage;
        // Timeout is not permanent - task might still complete
      } else if (error.message.includes('failed')) {
        // Extract error details if available
        const errorDetail = error.message.includes('Task failed:') 
          ? error.message.split('Task failed:')[1]?.trim()
          : null;
        if (errorDetail) {
          // Check for specific A2E error messages
          if (errorDetail.includes('media file is unavailable')) {
            errorMessage += t.fileUnavailable;
            isPermanentError = true; // Permanent - file is gone
          } else if (errorDetail.includes('500') || errorDetail.includes('Internal Server Error') || errorDetail.includes('External API call failed')) {
            errorMessage += t.serviceUnavailable;
            // Temporary error - task might still complete
          } else {
            errorMessage += `${t.processingFailed} ${errorDetail}.`;
            // Check if it's a permanent failure
            if (errorDetail.toLowerCase().includes('not found') || errorDetail.toLowerCase().includes('invalid')) {
              isPermanentError = true;
            }
          }
        } else {
          errorMessage += t.processingFailed;
        }
      } else if (error.message.includes('Failed to start')) {
        errorMessage += t.failedToStart;
        isPermanentError = true; // Can't start = permanent
      } else {
        errorMessage += t.tryAgainLater;
        // Unknown error - assume temporary
      }

      await safeEditMessageText(
        chatId,
        messageId,
        errorMessage,
        {
          reply_markup: getBackToMenuKeyboard(lang),
        }
      );

      // If polling succeeded, we already got the result and removed from pending
      // Don't add to pending again to avoid duplicate delivery
      if (pollingSucceeded) {
        logger.warn(`Error after successful polling for task ${taskId}: ${error.message}. Task was already removed from pending, won't add again.`);
        // Refund berries since delivery failed
        if (!refunded) {
          refunded = true;
          await creditsService.refundBerries(tgId, reservedBerries);
        }
      } else if (taskId && !isPermanentError) {
        // Polling failed but not permanent error - add to pending for recovery
        pendingTasksService.addPendingTask(taskId, tgId, chatId, messageId, reservedBerries);
        logger.info(`Task ${taskId} added to pending for recovery (temporary error: ${error.message})`);
        // Don't refund yet - task might still complete
      } else if (taskId && isPermanentError) {
        // Permanent error - don't add to pending, refund immediately
        pendingTasksService.removePendingTask(taskId);
        logger.info(`Task ${taskId} removed from pending due to permanent error: ${error.message}`);
        
        // Refund berries for permanent errors
        if (!refunded) {
          refunded = true;
          await creditsService.refundBerries(tgId, reservedBerries);
        }
      } else if (!refunded) {
        // No taskId means task wasn't created - refund immediately
        refunded = true;
        await creditsService.refundBerries(tgId, reservedBerries);
      }
    }

  } finally {
    // Cleanup
    sessionService.removePhoto(tgId);
    sessionService.releaseLock(tgId);
  }
}

// Wallet callback
bot.action('wallet', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  await safeAnswerCbQuery(ctx);

  const remaining = await creditsService.getTotalCredits(tgId);
  const message = t.walletBerriesMessage.replace('{count}', String(remaining));

  await ctx.reply(message, {
    reply_markup: getBackToMenuKeyboard(lang),
  });
});

// Free berries (referral) callback
bot.action('free_berries', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  await safeAnswerCbQuery(ctx);

  // Get bot username
  const botInfo = await bot.telegram.getMe();
  const referralLink = referralService.generateReferralLink(botInfo.username, tgId);

  // Use only referralTitle in the message - referralDescription is used in the share button
  const message = t.referralTitle;
  await ctx.reply(message, {
    reply_markup: getReferralKeyboard(lang, referralLink),
  });
});

// Buy berries callback - show payment method selection
bot.action('buy_generation', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  await safeAnswerCbQuery(ctx);
  await ctx.reply(t.selectPaymentMethod, {
    reply_markup: getPaymentMethodKeyboard(lang),
  });
});

// Payment method selection: Telegram Stars
bot.action('payment_method_stars', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  await safeAnswerCbQuery(ctx);
  await ctx.reply(`💳 ${t.buyPackage}`, {
    reply_markup: getPaymentPackagesKeyboard(lang),
  });
});

// Payment method selection: Crypto
bot.action('payment_method_crypto', async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  await safeAnswerCbQuery(ctx);
  
  // Check if NOWPayments is configured
  if (!config.nowpayments.apiKey) {
    logger.error('NOWPayments API key not configured');
    await ctx.reply(t.errorOccurred);
    return;
  }
  
  // Show crypto payment packages with fixed prices (all packages)
  const buttons = PAYMENT_PACKAGES
    .map((pkg) => {
      const localizedTitle = formatBerriesCount(lang, pkg.berries);
      const priceUsd = CRYPTO_PAYMENT_PRICES[pkg.sku];
      
      if (!priceUsd) {
        logger.warn(`No crypto price defined for SKU: ${pkg.sku}`);
        return null;
      }

      // Show berries count and price in USD (use 2 decimal places for accuracy)
      return [{
        text: `🍓 ${localizedTitle} | 💎 ${priceUsd.toFixed(2)} USD`,
        callback_data: `crypto_buy_${pkg.sku}`,
      }];
    })
    .filter((btn): btn is Array<{ text: string; callback_data: string }> => btn !== null);

  await ctx.reply(`💳 ${t.buyPackage}`, {
    reply_markup: {
      inline_keyboard: [
        ...buttons,
        [{ text: t.back, callback_data: 'buy_generation' }],
      ],
    },
  });
});

// Handle crypto payment package selection - show agreement
bot.action(/^crypto_buy_(.+)$/, async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  const match = ctx.match;
  
  if (!match || !match[1]) {
    await safeAnswerCbQuery(ctx, t.invalidPackage);
    return;
  }

  const sku = match[1];
  const pkg = paymentsService.getPackageBySku(sku);

  if (!pkg) {
    await safeAnswerCbQuery(ctx, t.packageNotFound);
    return;
  }

  await safeAnswerCbQuery(ctx);

  // Show agreement message with proceed button
  await ctx.reply(t.paymentAgreement, {
    reply_markup: {
      inline_keyboard: [
        [{ text: t.proceedButton, callback_data: `crypto_proceed_${sku}` }],
        [{ text: t.back, callback_data: 'payment_method_crypto' }],
      ],
    },
    parse_mode: 'Markdown',
  });
});

// Proceed to crypto payment handler
bot.action(/^crypto_proceed_(.+)$/, async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  const match = ctx.match;
  
  if (!match || !match[1]) {
    await safeAnswerCbQuery(ctx, t.invalidPackage);
    return;
  }

  const sku = match[1];
  const pkg = paymentsService.getPackageBySku(sku);

  if (!pkg) {
    await safeAnswerCbQuery(ctx, t.packageNotFound);
    return;
  }

  await safeAnswerCbQuery(ctx);

  try {
    // Get fixed price from CRYPTO_PAYMENT_PRICES (price in USD)
    const priceUsd = CRYPTO_PAYMENT_PRICES[sku];
    if (!priceUsd) {
      logger.error(`No crypto price defined for SKU: ${sku}`);
      await ctx.reply(t.errorOccurred);
      return;
    }
    
    // Generate unique order ID (format: tg_<userId>_<timestamp>)
    const orderId = `tg_${tgId}_${Date.now()}`;
    
    // Get bot username for redirect URLs
    const botInfo = await bot.telegram.getMe();
    const botUsername = botInfo.username || 'TitsBerryBot';
    
    // Create NOWPayments invoice
    // CRITICAL: If this fails, do NOT register payment or start auto-check
    const invoice = await nowPaymentsClient.createInvoice({
      price_amount: priceUsd,
      price_currency: 'usd',
      order_id: orderId,
      order_description: `${pkg.berries} berries`,
      success_url: `https://t.me/${botUsername}?start=pay_ok_${orderId}`,
      cancel_url: `https://t.me/${botUsername}?start=pay_cancel_${orderId}`,
    });

    // Validate invoice was created successfully
    if (!invoice || !invoice.invoice_id) {
      logger.error(`Failed to create invoice: invoice response is invalid`);
      await ctx.reply(t.errorOccurred);
      return;
    }

    logger.info(`Created NOWPayments invoice: invoice_id=${invoice.invoice_id}, order_id=${orderId}, user=${tgId}, amount=${priceUsd} USD`);
    logger.info(`Invoice URL: ${invoice.invoice_url}`);

    // Register payment for tracking and auto-checking (using invoice_id for reliable lookup)
    // Only register if invoice was successfully created
    cryptoPaymentTracker.registerPayment(
      invoice.invoice_id, // Use invoice_id as identifier
      tgId,
      sku,
      orderId,
      async (invoiceIdForCheck: string) => {
        await autoCheckPaymentByInvoiceId(invoiceIdForCheck, tgId);
      },
      invoice.invoice_id // Pass invoice_id explicitly
    );

    // Build payment message
    let messageText = `**${t.cryptoPaymentDetails}**\n`;
    messageText += `${t.cryptoPaymentTransactionId} ${orderId}\n`;
    messageText += `${t.cryptoPaymentAmount} ${priceUsd.toFixed(2)} USD\n`;
    messageText += `${t.cryptoPaymentBerries} ${pkg.berries}`;
    
    // Show instructions
    messageText += `\n\n**${t.cryptoPaymentImportant}**\n`;
    messageText += `${t.cryptoPaymentImportant1}\n`;
    messageText += `${t.cryptoPaymentImportant2}\n`;
    messageText += `${t.cryptoPaymentImportant3}`;

    // Send payment instructions and buttons (use invoice_id for check button)
    await ctx.reply(messageText, {
      reply_markup: getCryptoPaymentKeyboard(lang, invoice.invoice_url, invoice.invoice_id),
      parse_mode: 'Markdown',
    });
  } catch (error: any) {
    logger.error(`Error creating crypto payment: ${error.message}`);
    logger.error(`Error stack: ${error.stack}`);
    
    // Check for specific NOWPayments errors
    const apiError = error.response?.data;
    if (apiError) {
      logger.error(`NOWPayments API error details: ${JSON.stringify(apiError)}`);
      if (apiError.code === 'CURRENCY_UNAVAILABLE') {
        await ctx.reply(t.cryptoPaymentUnavailable);
      } else if (apiError.code === 'INTERNAL_ERROR' && apiError.message?.includes('estimate')) {
        await ctx.reply(t.cryptoPaymentConversionError);
      } else if (apiError.code === 'AMOUNT_MINIMAL_ERROR') {
        await ctx.reply(t.cryptoPaymentMinimalAmountError);
      } else if (apiError.code === 'INVALID_API_KEY') {
        logger.error(`NOWPayments API key is invalid. Check .env NOWPAYMENTS_API_KEY and ensure baseUrl is correct (should be https://api.nowpayments.io without /v1)`);
        await ctx.reply(t.errorOccurred);
      } else {
        await ctx.reply(t.errorOccurred);
      }
    } else {
      // Try to send error message, but catch if it fails
      try {
        await ctx.reply(t.errorOccurred);
      } catch (replyError: any) {
        logger.error(`Failed to send error message to user: ${replyError.message}`);
      }
    }
  }
});

// Auto-check payment function by invoice_id (called by tracker for invoice-based payments)
async function autoCheckPaymentByInvoiceId(invoiceId: string, tgId: number): Promise<void> {
  try {
    // CRITICAL: Validate invoice_id before attempting to check
    if (!invoiceId || invoiceId === 'undefined' || invoiceId.trim().length === 0) {
      logger.error(`Auto-check failed: invoice_id is invalid (${invoiceId})`);
      return;
    }

    const tracker = cryptoPaymentTracker.getPayment(invoiceId);

    if (!tracker) {
      logger.warn(`Invoice ${invoiceId} not found in tracker during auto-check`);
      return;
    }

    // Check if cancelled
    if (tracker.cancelled) {
      logger.info(`Invoice ${invoiceId} was cancelled, skipping auto-check`);
      return;
    }

    // IMPORTANT: GET /v1/invoice/{invoice_id} returns 404 - this is expected behavior
    // We need to find payment by order_id using GET /v1/payment (list payments with JWT)
    // Then check payment status using GET /v1/payment/{payment_id}
    
    const orderId = tracker.orderId;
    if (!orderId) {
      logger.warn(`No order_id in tracker for invoice ${invoiceId}, cannot check payment status`);
      return;
    }
    
    let invoice: NowPaymentsInvoice;
    let paymentStatus: string | undefined;
    let paymentId: string | undefined;
    
    // Step 1: Check if payment exists in database first (fast path)
    const recentPayment = await prisma.payment.findFirst({
      where: {
        tgId: BigInt(tgId),
        provider: 'nowpayments',
        payloadJson: {
          contains: orderId,
        },
      },
      orderBy: {
        createdAt: 'desc',
      },
    });
    
    if (recentPayment?.telegramPaymentChargeId) {
      // Payment found in database - check status via payment endpoint
      paymentId = recentPayment.telegramPaymentChargeId;
      
      if (!paymentId) {
        logger.error(`Payment ID is undefined after finding in database`);
        return;
      }
      
      logger.info(`Payment found in database: payment_id=${paymentId}, checking status via NOWPayments API`);
      
      try {
        const paymentDetails = await nowPaymentsClient.getPaymentStatus(paymentId);
        paymentStatus = paymentDetails.payment_status;
        const pkg = paymentsService.getPackageBySku(tracker.sku);
        invoice = {
          invoice_id: invoiceId,
          payment_id: paymentId,
          payment_status: paymentStatus,
          price_amount: paymentDetails.price_amount || (pkg ? CRYPTO_PAYMENT_PRICES[tracker.sku] : 0),
          invoice_url: `https://nowpayments.io/payment?iid=${invoiceId}`,
          order_id: orderId,
          order_description: paymentDetails.order_description || '',
          price_currency: paymentDetails.price_currency || 'usd',
          created_at: paymentDetails.created_at || new Date().toISOString(),
        };
        logger.info(`Got payment status via payment_id ${paymentId}: status=${paymentStatus}`);
      } catch (paymentError: any) {
        logger.error(`Failed to get payment status for payment_id ${paymentId}: ${paymentError.message}`);
        return;
      }
    } else {
      // Step 2: Payment not in database - find via NOWPayments API using JWT
      logger.info(`Payment not found in database, searching via NOWPayments API with JWT for order_id ${orderId}`);
      
      try {
        const foundPayment = await nowPaymentsClient.findPaymentByOrderId(orderId);
        
        if (foundPayment && foundPayment.payment_id) {
          // CRITICAL: Convert payment_id to string (NOWPayments returns it as number)
          paymentId = String(foundPayment.payment_id);
          paymentStatus = foundPayment.payment_status;
          const pkg = paymentsService.getPackageBySku(tracker.sku);
          invoice = {
            invoice_id: invoiceId,
            payment_id: paymentId,
            payment_status: paymentStatus,
            price_amount: foundPayment.price_amount || (pkg ? CRYPTO_PAYMENT_PRICES[tracker.sku] : 0),
            invoice_url: `https://nowpayments.io/payment?iid=${invoiceId}`,
            order_id: orderId,
            order_description: foundPayment.order_description || '',
            price_currency: foundPayment.price_currency || 'usd',
            created_at: foundPayment.created_at || new Date().toISOString(),
          };
          logger.info(`Found payment via NOWPayments API: payment_id=${paymentId}, order_id=${orderId}, status=${paymentStatus}`);
        } else {
          // Payment not found - invoice may not be paid yet
          logger.debug(`Payment not found via NOWPayments API for order_id ${orderId}. Invoice may not be paid yet.`);
          return;
        }
      } catch (apiError: any) {
        logger.error(`Failed to find payment via NOWPayments API for order_id ${orderId}: ${apiError.message}`);
        if (apiError.response?.data) {
          logger.error(`NOWPayments API error: ${JSON.stringify(apiError.response.data)}`);
        }
        return;
      }
    }
    
    // Step 2: Check payment_status
    if (!paymentStatus) {
      logger.debug(`Invoice ${invoiceId} not paid yet (no payment_status)`);
      return;
    }

    // Step 3: If payment_id appeared, get detailed payment status via getPaymentStatus
    // This endpoint works with x-api-key (no JWT needed)
    let finalPaymentStatus = paymentStatus;
    let paymentDetails: any = null;
    
    if (paymentId && (!invoice?.price_amount || paymentId !== invoice.payment_id)) {
      try {
        paymentDetails = await nowPaymentsClient.getPaymentStatus(paymentId);
        finalPaymentStatus = paymentDetails.payment_status;
        logger.info(`Got payment details for invoice ${invoiceId}: payment_id=${invoice.payment_id}, status=${finalPaymentStatus}`);
      } catch (error: any) {
        logger.warn(`Failed to get payment status for payment_id ${invoice.payment_id}, using invoice status: ${error.message}`);
        // Continue with invoice.payment_status if getPaymentStatus fails
      }

      // Check if already processed (idempotency check) - use payment_id from invoice
      if (paymentId) {
        // CRITICAL: Ensure paymentId is a string (NOWPayments may return it as number)
        const paymentIdStr = String(paymentId);
        const existingPayment = await prisma.payment.findFirst({
          where: {
            telegramPaymentChargeId: paymentIdStr,
            provider: 'nowpayments',
          },
        });

        if (existingPayment) {
          logger.info(`Payment ${paymentId} (invoice_id: ${invoiceId}) already processed, stopping auto-checks`);
          cryptoPaymentTracker.removePayment(invoiceId);
          return;
        }
      }
    }

    // Step 4: Process if successful - check final payment status
    if (nowPaymentsClient.isPaymentPaid(finalPaymentStatus)) {
      const sku = tracker.sku;
      const pkg = paymentsService.getPackageBySku(sku);
      
      if (!pkg) {
        logger.error(`Package not found for SKU: ${sku}`);
        return;
      }

      // Use payment_id from invoice if available, otherwise use invoice_id
      // CRITICAL: Convert payment_id to string (NOWPayments may return it as number)
      const paymentIdForRecord = paymentId ? String(paymentId) : (invoice.payment_id ? String(invoice.payment_id) : invoiceId);
      
      const success = await paymentsService.handleCryptoPayment(
        tgId,
        sku,
        paymentIdForRecord,
        invoice.price_amount,
        JSON.stringify(invoice)
      );

      if (success) {
        logger.info(`Auto-check: Invoice ${invoiceId} (payment_id: ${invoice.payment_id || 'N/A'}) processed successfully for user ${tgId}`);
        
        // Notify user
        try {
          const lang = await getUserLanguage(tgId);
          const t = getTranslation(lang);
          await bot.telegram.sendMessage(tgId, t.paymentSuccess);
          
          // Show wallet after successful payment
          await showWallet(tgId);
          
          // Track payment event for UTM
          utmTrackingService.trackPayment(tgId, invoice.price_amount).catch((error) => {
            logger.error(`Error tracking payment for user ${tgId}: ${error.message}`);
          });
        } catch (notifyError: any) {
          logger.error(`Failed to notify user ${tgId} about successful payment: ${notifyError.message}`);
        }

        // Remove from tracker
        cryptoPaymentTracker.removePayment(invoiceId);
      }
    }
  } catch (error: any) {
    logger.error(`Auto-check failed for invoice_id ${invoiceId}: ${error.message}`);
  }
}

// Check crypto payment status (manual check by user)
bot.action(/^check_crypto_payment_(.+)$/, async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  const match = ctx.match;
  
  if (!match || !match[1]) {
    await safeAnswerCbQuery(ctx, t.errorOccurred);
    return;
  }

  const invoiceId = match[1];
  
  // CRITICAL: Validate invoice_id before attempting to check
  if (!invoiceId || invoiceId === 'undefined' || invoiceId.trim().length === 0) {
    logger.error(`Check payment failed: invoice_id is invalid (${invoiceId})`);
    await safeAnswerCbQuery(ctx, t.errorOccurred);
    await ctx.reply(t.errorOccurred);
    return;
  }
  
  // Check rate limiting and ownership
  const canCheck = cryptoPaymentTracker.canCheckPayment(invoiceId, tgId);
  if (!canCheck.allowed) {
    await safeAnswerCbQuery(ctx, canCheck.reason || t.paymentRateLimited);
    if (canCheck.reason?.includes('wait')) {
      await ctx.reply(t.paymentRateLimited);
    }
    return;
  }

  await safeAnswerCbQuery(ctx, t.paymentChecking);

  try {
    const tracker = cryptoPaymentTracker.getPayment(invoiceId);
    
    // Verify ownership (early check)
    if (!tracker || tracker.tgId !== tgId) {
      logger.warn(`User ${tgId} attempted to check invoice ${invoiceId} without ownership`);
      await ctx.reply(t.errorOccurred);
      return;
    }

    // Step 1: Get invoice status directly from NOWPayments API
    // This is the primary way to check payment status - invoice contains payment_status and payment_id
    logger.info(`User ${tgId} checking payment for invoice_id: ${invoiceId}`);
    
    let invoice: NowPaymentsInvoice;
    let paymentStatus: string | undefined;
    let paymentId: string | undefined;
    
    try {
      invoice = await nowPaymentsClient.getInvoiceStatus(invoiceId);
      paymentStatus = invoice.payment_status;
      paymentId = invoice.payment_id;
      
      // Log full invoice response for debugging (as requested)
      logger.info(`Invoice status check result:`);
      logger.info(`  invoice_id: ${invoice.invoice_id}`);
      logger.info(`  payment_id: ${paymentId || 'not yet'}`);
      logger.info(`  payment_status: ${paymentStatus || 'not paid'}`);
      logger.info(`  order_id: ${invoice.order_id}`);
      logger.info(`  price_amount: ${invoice.price_amount}`);
      
    } catch (invoiceError: any) {
      // If GET /v1/invoice/{invoice_id} returns 404, endpoint is not available
      // Use fallback: Check if payment exists in database by order_id
      if (invoiceError.is404) {
        logger.info(`Invoice GET endpoint not available (404), using fallback: check payment in database`);
      } else {
        logger.warn(`Failed to get invoice status via GET /v1/invoice/${invoiceId}: ${invoiceError.message}`);
      }
      
      // Fallback: Check if payment exists in database
      const orderId = tracker.orderId;
      if (!orderId) {
        logger.warn(`No order_id in tracker for invoice ${invoiceId}`);
        await ctx.reply(t.paymentNotConfirmed);
        return;
      }
      
      const recentPayment = await prisma.payment.findFirst({
        where: {
          tgId: BigInt(tgId),
          provider: 'nowpayments',
          payloadJson: {
            contains: orderId,
          },
        },
        orderBy: {
          createdAt: 'desc',
        },
      });
      
      if (recentPayment?.telegramPaymentChargeId) {
        // Payment found in database - check status via payment endpoint
        paymentId = recentPayment.telegramPaymentChargeId;
        if (!paymentId) {
          logger.error(`Payment ID is undefined after finding in database`);
          await ctx.reply(t.paymentNotConfirmed);
          return;
        }
        logger.info(`Found payment_id ${paymentId} in database for order_id ${orderId}`);
        
        try {
          if (!paymentId) {
            logger.error(`Payment ID is undefined after finding in database`);
            return;
          }
          const paymentDetails = await nowPaymentsClient.getPaymentStatus(paymentId);
          paymentStatus = paymentDetails.payment_status;
          const pkg = paymentsService.getPackageBySku(tracker.sku);
          invoice = {
            invoice_id: invoiceId,
            payment_id: paymentId,
            payment_status: paymentStatus,
            price_amount: paymentDetails.price_amount || (pkg ? CRYPTO_PAYMENT_PRICES[tracker.sku] : 0),
            invoice_url: `https://nowpayments.io/payment?iid=${invoiceId}`,
            order_id: orderId,
            order_description: '',
            price_currency: 'usd',
            created_at: new Date().toISOString(),
          };
          logger.info(`Got payment status via payment_id ${paymentId}: status=${paymentStatus}`);
        } catch (paymentError: any) {
          logger.error(`Failed to get payment status for payment_id ${paymentId}: ${paymentError.message}`);
          await ctx.reply(t.paymentNotConfirmed);
          return;
        }
      } else {
        // Step 2: Payment not in database - find via NOWPayments API using JWT
        logger.info(`Payment not found in database, searching via NOWPayments API with JWT for order_id ${orderId}`);
        
        try {
          const foundPayment = await nowPaymentsClient.findPaymentByOrderId(orderId);
          
          if (foundPayment && foundPayment.payment_id) {
            // CRITICAL: Convert payment_id to string (NOWPayments returns it as number)
            paymentId = String(foundPayment.payment_id);
            paymentStatus = foundPayment.payment_status;
            const pkg = paymentsService.getPackageBySku(tracker.sku);
            invoice = {
              invoice_id: invoiceId,
              payment_id: paymentId,
              payment_status: paymentStatus,
              price_amount: foundPayment.price_amount || (pkg ? CRYPTO_PAYMENT_PRICES[tracker.sku] : 0),
              invoice_url: `https://nowpayments.io/payment?iid=${invoiceId}`,
              order_id: orderId,
              order_description: foundPayment.order_description || '',
              price_currency: foundPayment.price_currency || 'usd',
              created_at: foundPayment.created_at || new Date().toISOString(),
            };
            logger.info(`Found payment via NOWPayments API: payment_id=${paymentId}, order_id=${orderId}, status=${paymentStatus}`);
          } else {
            // Payment not found - invoice may not be paid yet
            logger.info(`Payment not found via NOWPayments API for order_id ${orderId}. Invoice may not be paid yet.`);
            await ctx.reply(t.paymentNotConfirmed);
            return;
          }
        } catch (apiError: any) {
          logger.error(`Failed to find payment via NOWPayments API for order_id ${orderId}: ${apiError.message}`);
          await ctx.reply(t.paymentNotConfirmed);
          return;
        }
      }
    }

    // Step 2: If payment_id appeared, get detailed payment status via getPaymentStatus
    // This endpoint works with x-api-key (no JWT needed)
    let finalPaymentStatus = paymentStatus || invoice.payment_status;
    let paymentDetails: any = null;
    
    if (!finalPaymentStatus) {
      logger.warn(`No payment_status found for invoice ${invoiceId}`);
      await ctx.reply(t.paymentNotConfirmed);
      return;
    }
    
    if (invoice.payment_id) {
      try {
        paymentDetails = await nowPaymentsClient.getPaymentStatus(invoice.payment_id);
        finalPaymentStatus = paymentDetails.payment_status || finalPaymentStatus;
        logger.info(`Got payment details for invoice ${invoiceId}: payment_id=${invoice.payment_id}, status=${finalPaymentStatus}`);
      } catch (error: any) {
        logger.warn(`Failed to get payment status for payment_id ${invoice.payment_id}, using invoice status: ${error.message}`);
        // Continue with invoice.payment_status if getPaymentStatus fails
      }
    }

    logger.info(`Invoice ${invoiceId} status: payment_status=${finalPaymentStatus}, payment_id=${invoice.payment_id || 'N/A'}`);

    // Check if cancelled - if cancelled, don't process even if payment succeeded
    if (tracker.cancelled) {
      logger.info(`Invoice ${invoiceId} was cancelled by user ${tgId}, not processing even though status is ${finalPaymentStatus}`);
      await ctx.reply(t.paymentFailed + ' (Payment was cancelled)');
      return;
    }

    // Handle partially paid
    if (finalPaymentStatus && finalPaymentStatus.toLowerCase() === 'partially_paid') {
      logger.info(`Invoice ${invoiceId} is partially paid`);
      await ctx.reply(t.paymentPartiallyPaid);
      return;
    }

    const isPaid = finalPaymentStatus ? nowPaymentsClient.isPaymentPaid(finalPaymentStatus) : false;
    const isPending = finalPaymentStatus ? nowPaymentsClient.isPaymentPending(finalPaymentStatus) : false;
    const isFailed = finalPaymentStatus ? nowPaymentsClient.isPaymentFailed(finalPaymentStatus) : false;
    
    logger.info(`Invoice ${invoiceId} status check: payment_status="${finalPaymentStatus}", isPaid=${isPaid}, isPending=${isPending}, isFailed=${isFailed}`);

    if (isPaid) {
      // Payment successful - process it
      const sku = tracker.sku;
      const pkg = paymentsService.getPackageBySku(sku);
      
      if (!pkg) {
        logger.error(`Package not found for SKU: ${sku}`);
        await ctx.reply(t.errorOccurred);
        return;
      }

      // Use payment_id from invoice if available, otherwise use invoice_id
      // CRITICAL: Convert payment_id to string (NOWPayments may return it as number)
      const paymentIdForRecord = paymentId ? String(paymentId) : (invoice.payment_id ? String(invoice.payment_id) : invoiceId);
      
      // Use payment details if available, otherwise use invoice
      const paymentData = paymentDetails || invoice;
      
      // Process payment (idempotent - reuses existing mechanism)
      const success = await paymentsService.handleCryptoPayment(
        tgId,
        sku,
        paymentIdForRecord,
        invoice.price_amount,
        JSON.stringify(paymentData)
      );

      if (success) {
        await ctx.reply(t.paymentSuccess);
        
        // Show wallet after successful payment
        await showWallet(tgId);
        
        // Track payment event for UTM
        utmTrackingService.trackPayment(tgId, invoice.price_amount).catch((error) => {
          logger.error(`Error tracking payment for user ${tgId}: ${error.message}`);
        });

        // Remove from tracker (stop auto-checks)
        cryptoPaymentTracker.removePayment(invoiceId);
      } else {
        await ctx.reply(t.errorOccurred);
      }
    } else if (isPending) {
      logger.info(`Invoice ${invoiceId} is still pending with status: ${finalPaymentStatus}`);
      await ctx.reply(t.paymentNotConfirmed);
    } else if (isFailed) {
      logger.info(`Invoice ${invoiceId} failed with status: ${finalPaymentStatus}`);
      await ctx.reply(t.paymentFailed);
      // Remove from tracker if failed
      cryptoPaymentTracker.removePayment(invoiceId);
    } else {
      logger.warn(`Invoice ${invoiceId} has unknown status: ${finalPaymentStatus}`);
      await ctx.reply(t.paymentNotConfirmed);
    }
  } catch (error: any) {
    logger.error(`Error checking crypto payment: ${error.message}`);
    await ctx.reply(t.paymentNotConfirmed);
  }
});

// Cancel crypto payment
bot.action(/^cancel_crypto_payment_(.+)$/, async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  const match = ctx.match;
  
  if (!match || !match[1]) {
    await safeAnswerCbQuery(ctx);
    return;
  }

  const invoiceId = match[1];
  await safeAnswerCbQuery(ctx);

  // Cancel payment in tracker
  const cancelled = cryptoPaymentTracker.cancelPayment(invoiceId, tgId);
  
  if (cancelled) {
    await ctx.reply(t.cancelButton + ' ✅');
    logger.info(`Invoice ${invoiceId} cancelled by user ${tgId}`);
  } else {
    await ctx.reply(t.errorOccurred);
  }
});

// Handle payment package selection (Telegram Stars)
bot.action(/^buy_(.+)$/, async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  const match = ctx.match;
  if (!match || !match[1]) {
    await safeAnswerCbQuery(ctx, t.invalidPackage);
    return;
  }

  const sku = match[1];
  const pkg = paymentsService.getPackageBySku(sku);

  if (!pkg) {
    await safeAnswerCbQuery(ctx, t.packageNotFound);
    return;
  }

  await safeAnswerCbQuery(ctx);

  // Show agreement message with proceed button
  await ctx.reply(t.paymentAgreement, {
    reply_markup: {
      inline_keyboard: [
        [{ text: t.proceedButton, callback_data: `proceed_${sku}` }],
        [{ text: t.back, callback_data: 'payment_method_stars' }],
      ],
    },
    parse_mode: 'Markdown',
  });
});

// Proceed to payment handler
bot.action(/^proceed_(.+)$/, async (ctx) => {
  const tgId = getUserId(ctx);
  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);
  const match = ctx.match;
  if (!match || !match[1]) {
    await safeAnswerCbQuery(ctx, t.invalidPackage);
    return;
  }

  const sku = match[1];
  const pkg = paymentsService.getPackageBySku(sku);

  if (!pkg) {
    await safeAnswerCbQuery(ctx, t.packageNotFound);
    return;
  }

  await safeAnswerCbQuery(ctx);

  try {
    // Create invoice with Telegram Stars (XTR)
    // provider_token is empty string for digital goods/services
    // Localize the package title based on berries count
    const localizedTitle = formatBerriesCount(lang, pkg.berries);
    
    await ctx.replyWithInvoice({
      title: `${t.invoiceTitle} - ${localizedTitle}`,
      description: `${pkg.berries} ${t.invoiceDescription}`,
      payload: JSON.stringify({ sku, tgId }),
      provider_token: '', // Empty for digital goods/services with Telegram Stars
      currency: 'XTR', // Telegram Stars currency code
      prices: [
        {
          label: `${localizedTitle} - ⭐ ${pkg.amountStars} ${t.stars}`,
          amount: pkg.amountStars, // Amount in Stars (integer)
        },
      ],
    });
  } catch (error: any) {
    logger.error(`Error creating invoice: ${error.message}`);
    const lang = await getUserLanguage(tgId);
    const t = getTranslation(lang);
    await ctx.reply(t.errorOccurred);
  }
});

// Pre-checkout query handler (Telegram Stars)
bot.on('pre_checkout_query', async (ctx) => {
  const query = ctx.preCheckoutQuery;
  const tgId = query.from.id;
  
  try {
    const lang = await getUserLanguage(tgId);
    const t = getTranslation(lang);

    // Parse payload to get SKU
    let payload: any = {};
    try {
      payload = JSON.parse(query.invoice_payload || '{}');
    } catch (e) {
      logger.error('Failed to parse invoice payload in pre-checkout');
      await ctx.answerPreCheckoutQuery(false, t.paymentInvalidData);
      return;
    }

    const sku = payload.sku;
    if (!sku) {
      logger.error('SKU not found in pre-checkout payload');
      await ctx.answerPreCheckoutQuery(false, t.paymentPackageNotFound);
      return;
    }

    const pkg = paymentsService.getPackageBySku(sku);
    if (!pkg) {
      logger.error(`Unknown SKU in pre-checkout: ${sku}`);
      await ctx.answerPreCheckoutQuery(false, t.paymentPackageNotFound);
      return;
    }

    // Verify amount matches
    if (query.total_amount !== pkg.amountStars) {
      logger.error(`Amount mismatch in pre-checkout: expected ${pkg.amountStars}, got ${query.total_amount}`);
      await ctx.answerPreCheckoutQuery(false, t.paymentAmountMismatch);
      return;
    }

    // Verify currency is XTR (Telegram Stars)
    if (query.currency !== 'XTR') {
      logger.error(`Invalid currency in pre-checkout: ${query.currency}`);
      await ctx.answerPreCheckoutQuery(false, t.paymentInvalidCurrency);
      return;
    }

    // All checks passed - approve the payment
    await ctx.answerPreCheckoutQuery(true);
    logger.info(`Pre-checkout approved: user ${tgId}, SKU ${sku}, ${pkg.amountStars} Stars`);
  } catch (error: any) {
    logger.error(`Error in pre-checkout query: ${error.message}`);
    // Fallback to English if we can't resolve user's language in time
    const t = getTranslation('en');
    await ctx.answerPreCheckoutQuery(false, t.paymentProcessingError);
  }
});

// Successful payment handler (Telegram Stars)
bot.on('successful_payment', async (ctx) => {
  const tgId = getUserId(ctx);
  const payment = ctx.message.successful_payment;

  if (!payment) {
    return;
  }

  const lang = await getUserLanguage(tgId);
  const t = getTranslation(lang);

  try {
    // Useful to confirm whether you are in Telegram's test environment
    const isTest = Boolean((payment as any).is_test);
    logger.info(`Successful payment received (Stars): user ${tgId}, is_test=${isTest}`);

    // Verify currency is XTR (Telegram Stars)
    if (payment.currency !== 'XTR') {
      logger.error(`Invalid currency in successful payment: ${payment.currency}`);
      await ctx.reply(t.errorOccurred);
      return;
    }

    // Parse payload
    let payload: any = {};
    
    try {
      payload = JSON.parse(payment.invoice_payload || '{}');
    } catch (e) {
      logger.error('Failed to parse invoice payload in successful payment');
      await ctx.reply(t.errorOccurred);
      return;
    }

    // Get SKU from payload
    const sku = payload.sku;
    if (!sku) {
      logger.error('SKU not found in payment', { 
        invoice_payload: payment.invoice_payload
      });
      await ctx.reply(t.errorOccurred);
      return;
    }

    // Amount is already in Stars (integer)
    const amountStars = payment.total_amount;

    // Get telegram_payment_charge_id for potential refunds
    const telegramPaymentChargeId = payment.telegram_payment_charge_id || '';

    const success = await paymentsService.handleSuccessfulPayment(
      tgId,
      sku,
      amountStars,
      telegramPaymentChargeId,
      JSON.stringify(payment)
    );

    if (success) {
      // Track payment event (only once per user)
      utmTrackingService.trackPayment(tgId, amountStars).catch((error) => {
        logger.error(`Error tracking payment for user ${tgId}: ${error.message}`);
      });

      const pkg = paymentsService.getPackageBySku(sku);
      const berriesText = formatBerriesCount(lang, pkg?.berries || 0);
      await ctx.reply(
        `${t.paymentSuccessful} ${berriesText} ${t.creditsAdded}`,
        {
          reply_markup: getBackToMenuKeyboard(lang),
        }
      );
      
      // Show wallet after successful payment
      await showWallet(tgId);
    } else {
      await ctx.reply(t.errorOccurred);
    }
  } catch (error: any) {
    logger.error(`Error handling payment: ${error.message}`);
    await ctx.reply(t.errorOccurred);
  }
});

// Error handler
bot.catch(async (err: unknown, ctx) => {
  const errorMessage = err instanceof Error ? err.message : 'Unknown error';
  logger.error(`Error in bot: ${errorMessage}`, err);
  
  // Get user language for error message
  try {
    const tgId = ctx.from?.id;
    if (tgId) {
      const lang = await getUserLanguage(tgId);
      const t = getTranslation(lang);
      await ctx.reply(t.errorOccurred);
      return;
    }
  } catch {
    // Fallback if can't get user language
  }
  
  // Fallback to English
  const t = getTranslation('en');
  await ctx.reply(t.errorOccurred);
});

// Background task to check pending tasks and deliver results
async function checkPendingTasks() {
  const pendingTasks = pendingTasksService.getAllPendingTasks();
  
  if (pendingTasks.length === 0) {
    return;
  }
  
  logger.info(`Checking ${pendingTasks.length} pending tasks`);
  
  for (const task of pendingTasks) {
    try {
      pendingTasksService.updateLastChecked(task.taskId);
      
      // Check if task is completed
      const imageUrl = await a2eClient.checkTaskCompletion(task.taskId);
      
      if (imageUrl) {
        // Task completed! Download and send the result
        logger.info(`✅ Pending task ${task.taskId} completed! Delivering result to user ${task.tgId} (chatId: ${task.chatId})`);
        
        // IMPORTANT: Remove from pending FIRST to prevent double delivery
        // This is safe because if delivery fails, task will be checked again on next interval
        // But we want to avoid delivering the same result twice if checkPendingTasks runs in parallel
        pendingTasksService.removePendingTask(task.taskId);
        
        try {
          // Download result image
          const resultResponse = await axios.get(imageUrl, {
            responseType: 'arraybuffer',
          });
          const resultBuffer = Buffer.from(resultResponse.data);
          
          // Send result to user
          await bot.telegram.sendPhoto(task.chatId, {
            source: resultBuffer,
          });
          
          // Process referral reward (after successful generation)
          referralService.processReferralReward(task.tgId).then((result) => {
            if (result.success && result.inviterTgId) {
              // Notify inviter about the reward
              getUserLanguage(result.inviterTgId).then((inviterLang) => {
                const inviterT = getTranslation(inviterLang);
                bot.telegram.sendMessage(
                  result.inviterTgId!,
                  inviterT.referralRewardNotification
                ).catch((error) => {
                  logger.error(`Failed to send referral notification to ${result.inviterTgId}: ${error.message}`);
                });
              }).catch(() => {});
            }
          }).catch((error) => {
            logger.error(`Error processing referral reward for user ${task.tgId}: ${error.message}`);
          });
          
          // Update the processing message
          const lang = await getUserLanguage(task.tgId);
          const t = getTranslation(lang);
          const remaining = await creditsService.getTotalCredits(task.tgId);

          await safeEditMessageText(
            task.chatId,
            task.messageId,
            `${t.done} ${t.remains} 🍓 ${remaining}`,
            {
              reply_markup: getBackToMenuKeyboard(lang),
            }
          );
          
          // Delete task from A2E (cleanup)
          try {
            await a2eClient.deleteTask(task.taskId);
          } catch (deleteError: any) {
            logger.warn(`Failed to delete task ${task.taskId} from A2E after delivery: ${deleteError.message}`);
            // Don't fail - result is already delivered
          }

          logger.info(`✅ Successfully delivered result for pending task ${task.taskId} to user ${task.tgId}`);
          
          // Clear result buffer
          resultBuffer.fill(0);
        } catch (sendError: any) {
          logger.error(`❌ Failed to send result for pending task ${task.taskId} to user ${task.tgId}: ${sendError.message}`);
          logger.error(`Error details: ${JSON.stringify({
            taskId: task.taskId,
            tgId: task.tgId,
            chatId: task.chatId,
            messageId: task.messageId,
            error: sendError.message,
          })}`);
          // Don't remove from pending - we'll try again later
        }
      } else {
        // Task is still processing
        logger.debug(`Pending task ${task.taskId} still processing (last checked: ${new Date(task.lastChecked).toISOString()})`);
      }
    } catch (error: any) {
      // If task failed or not found, remove it from pending
      if (error.message.includes('failed') || error.message.includes('not found')) {
        logger.warn(`Pending task ${task.taskId} failed or not found, removing from pending: ${error.message}`);

        // Refund berries because we won't deliver this task
        try {
          await creditsService.refundBerries(task.tgId, task.reservedBerries);
        } catch (refundError: any) {
          logger.error(`Failed to refund berries for failed pending task ${task.taskId}: ${refundError.message}`);
        }

        pendingTasksService.removePendingTask(task.taskId);
        
        // Try to notify user (but don't fail if message can't be sent)
        try {
          const lang = await getUserLanguage(task.tgId);
          const t = getTranslation(lang);
          await safeEditMessageText(
            task.chatId,
            task.messageId,
            t.errorProcessingPhoto + ' ' + t.processingFailed,
            {
              reply_markup: getBackToMenuKeyboard(lang),
            }
          );
        } catch (notifyError: any) {
          logger.error(`Failed to notify user about failed pending task: ${notifyError.message}`);
        }
      } else {
        logger.error(`Error checking pending task ${task.taskId}: ${error.message}`);
        // Don't remove - might be a temporary error
      }
    }
  }
}

// Start background task to check pending tasks every 15 seconds (more frequent for better responsiveness)
setInterval(() => {
  checkPendingTasks().catch((error) => {
    logger.error(`Error in pending tasks checker: ${error.message}`);
  });
}, 15 * 1000); // Check every 15 seconds

// Also check immediately on startup (in case there are tasks from previous session)
// Note: pending tasks are stored in memory, so they won't persist across restarts,
// but this ensures we check as soon as possible
setTimeout(() => {
  checkPendingTasks().catch((error) => {
    logger.error(`Error in initial pending tasks check: ${error.message}`);
  });
}, 5000); // Check after 5 seconds on startup

/**
 * Register bot commands with descriptions in all supported languages
 * According to Telegram Bot API: https://core.telegram.org/bots/api#setmycommands
 */
export async function registerBotCommands(): Promise<void> {
  const languages: Language[] = ['en', 'hi', 'id', 'pt', 'ru'];
  
  for (const lang of languages) {
    const t = getTranslation(lang);
    
    const commands = [
      { command: 'upload', description: t.commandUploadDescription },
      { command: 'buy', description: t.commandBuyDescription },
      { command: 'wallet', description: t.commandWalletDescription },
      { command: 'invite', description: t.commandInviteDescription },
      { command: 'language', description: t.commandLanguageDescription },
      { command: 'terms', description: t.commandTermsDescription },
      { command: 'privacy', description: t.commandPrivacyDescription },
    ];
    
    try {
      // Set commands for specific language
      // Telegram language codes: 'en', 'ru', 'id', 'pt', 'hi' (Hindi uses 'hi')
      // According to Telegram Bot API, language_code is optional and uses ISO 639-1 codes
      const languageCode = lang === 'hi' ? 'hi' : lang === 'id' ? 'id' : lang === 'pt' ? 'pt' : lang === 'ru' ? 'ru' : 'en';
      
      // Only set language-specific commands if not default (en)
      if (languageCode !== 'en') {
        await bot.telegram.setMyCommands(commands, {
          scope: { type: 'default' },
          language_code: languageCode,
        });
        logger.info(`Registered bot commands for language: ${lang} (code: ${languageCode})`);
      }
    } catch (error: any) {
      logger.error(`Failed to register commands for language ${lang}: ${error.message}`);
    }
  }
  
  // Set default commands (English, used as fallback)
  const t = getTranslation('en');
  const defaultCommands = [
    { command: 'upload', description: t.commandUploadDescription },
    { command: 'buy', description: t.commandBuyDescription },
    { command: 'wallet', description: t.commandWalletDescription },
    { command: 'invite', description: t.commandInviteDescription },
    { command: 'language', description: t.commandLanguageDescription },
    { command: 'terms', description: t.commandTermsDescription },
    { command: 'privacy', description: t.commandPrivacyDescription },
  ];
  
  try {
    await bot.telegram.setMyCommands(defaultCommands, {
      scope: { type: 'default' },
    });
    logger.info('Registered default bot commands (English)');
  } catch (error: any) {
    logger.error(`Failed to register default commands: ${error.message}`);
  }
}

export { bot };

