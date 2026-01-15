import { prisma } from '../db/prisma';
import { creditsService } from './credits.service';
import { logger } from '../utils/logger';

export interface PaymentPackage {
  sku: string;
  amountStars: number; // Amount in Telegram Stars
  berries: number;
  title: string;
}

/**
 * Payment packages in Telegram Stars (XTR)
 * Prices are in Stars - minimum 1 Star
 */
export const PAYMENT_PACKAGES: PaymentPackage[] = [
  { sku: 'berries_1', amountStars: 15, berries: 1, title: '1 berry' },
  { sku: 'berries_2', amountStars: 29, berries: 2, title: '2 berries' },
  { sku: 'berries_10', amountStars: 140, berries: 10, title: '10 berries' },
  { sku: 'berries_20', amountStars: 270, berries: 20, title: '20 berries' },
  { sku: 'berries_50', amountStars: 650, berries: 50, title: '50 berries' },
  { sku: 'berries_100', amountStars: 1250, berries: 100, title: '100 berries' },
];

/**
 * Crypto payment prices in USD (fixed prices)
 */
export const CRYPTO_PAYMENT_PRICES: Record<string, number> = {
  'berries_1': 0.6,
  'berries_2': 1.15,
  'berries_10': 5.5,
  'berries_20': 10.5,
  'berries_50': 25,
  'berries_100': 47.5,
};

export class PaymentsService {
  /**
   * Get payment package by SKU
   */
  getPackageBySku(sku: string): PaymentPackage | undefined {
    return PAYMENT_PACKAGES.find((pkg) => pkg.sku === sku);
  }

  /**
   * Get all payment packages
   */
  getAllPackages(): PaymentPackage[] {
    return PAYMENT_PACKAGES;
  }

  /**
   * Handle successful payment (Telegram Stars)
   */
  async handleSuccessfulPayment(
    tgId: number,
    sku: string,
    amountStars: number,
    telegramPaymentChargeId: string,
    payloadJson?: string
  ) {
    const pkg = this.getPackageBySku(sku);
    if (!pkg) {
      logger.error(`Unknown SKU: ${sku}`);
      return false;
    }

    if (pkg.amountStars !== amountStars) {
      logger.error(`Amount mismatch for SKU ${sku}: expected ${pkg.amountStars} Stars, got ${amountStars}`);
      return false;
    }

    const user = await creditsService.getOrCreateUser(tgId);

    // Record payment
    await prisma.payment.create({
      data: {
        userId: user.id,
        tgId: BigInt(tgId),
        telegramPaymentChargeId: telegramPaymentChargeId || null,
        provider: 'telegram_stars',
        sku,
        amountRub: amountStars, // Store Stars amount in amountRub field for compatibility
        creditsAdded: pkg.berries,
        payloadJson: payloadJson || JSON.stringify({ telegramPaymentChargeId }),
      },
    });

    // Add berries
    await creditsService.addBerries(tgId, pkg.berries);

    logger.info(`Payment processed: user ${tgId}, SKU ${sku}, ${pkg.berries} berries added, ${amountStars} Stars, charge_id: ${telegramPaymentChargeId}`);
    return true;
  }

  /**
   * Handle successful crypto payment (NOWPayments)
   * Idempotent: if payment_id already processed, returns true without duplicate processing
   */
  async handleCryptoPayment(
    tgId: number,
    sku: string,
    paymentId: string,
    amountUsd: number,
    payloadJson?: string
  ): Promise<boolean> {
    const pkg = this.getPackageBySku(sku);
    if (!pkg) {
      logger.error(`Unknown SKU: ${sku}`);
      return false;
    }

    const user = await creditsService.getOrCreateUser(tgId);

    // Check if this payment_id was already processed (idempotency)
    // CRITICAL: Ensure paymentId is a string (NOWPayments may return it as number)
    const paymentIdStr = String(paymentId);
    const existingPayment = await prisma.payment.findFirst({
      where: {
        telegramPaymentChargeId: paymentIdStr, // Reusing this field for NOWPayments payment_id
        provider: 'nowpayments',
      },
    });

    if (existingPayment) {
      logger.info(`Payment ${paymentId} already processed for user ${tgId}, skipping duplicate`);
      return true; // Already processed, return success
    }

    // Record payment
    await prisma.payment.create({
      data: {
        userId: user.id,
        tgId: BigInt(tgId),
        telegramPaymentChargeId: paymentIdStr, // Store NOWPayments payment_id here (already converted to string)
        provider: 'nowpayments',
        sku,
        amountRub: Math.round(amountUsd * 100), // Store USD amount in cents in amountRub field
        creditsAdded: pkg.berries,
        payloadJson: payloadJson || JSON.stringify({ paymentId, amountUsd }),
      },
    });

    // Add berries (reuse existing mechanism)
    await creditsService.addBerries(tgId, pkg.berries);

    logger.info(`Crypto payment processed: user ${tgId}, SKU ${sku}, ${pkg.berries} berries added, payment_id: ${paymentId}, amount: $${amountUsd}`);
    return true;
  }

  /**
   * Refund a payment (Telegram Stars)
   * Note: This requires the telegram_payment_charge_id from the successful payment
   */
  async refundPayment(telegramPaymentChargeId: string, reason?: string): Promise<boolean> {
    try {
      // This will be implemented when we add refund functionality
      // For now, we just log it
      logger.info(`Refund requested for charge_id: ${telegramPaymentChargeId}, reason: ${reason || 'N/A'}`);
      return true;
    } catch (error: any) {
      logger.error(`Failed to refund payment: ${error.message}`);
      return false;
    }
  }
}

export const paymentsService = new PaymentsService();
