import { logger } from '../utils/logger';

interface PaymentTracker {
  paymentId: string; // payment_id when available, otherwise invoice_id
  tgId: number;
  sku: string;
  orderId: string;
  invoiceId: string; // Store invoice_id to get payment_id when payment is created
  actualPaymentId: string | null; // Actual payment_id (set when payment is created from invoice)
  cancelled: boolean;
  lastCheckAt: number;
  checkCount: number;
  autoCheckTimer?: NodeJS.Timeout;
}

  /**
   * Tracks crypto payments for auto-checking and rate limiting
   */
export class CryptoPaymentTrackerService {
  private payments: Map<string, PaymentTracker> = new Map();
  private readonly RATE_LIMIT_MS = 15 * 1000; // 15 seconds between checks
  private readonly MAX_AUTO_CHECKS = 3; // Maximum auto-checks
  private readonly AUTO_CHECK_DELAYS = [120 * 1000, 300 * 1000, 600 * 1000]; // 120s (2min), 300s (5min), 600s (10min)

  /**
   * Register a new payment for tracking
   * CRITICAL: For invoice-based payments, paymentId should be invoice_id
   */
  registerPayment(
    paymentId: string,
    tgId: number,
    sku: string,
    orderId: string,
    autoCheckCallback: (invoiceId: string) => Promise<void>,
    invoiceId?: string
  ): void {
    // CRITICAL: For invoice-based payments, paymentId IS invoice_id
    // If invoiceId is explicitly provided, use it; otherwise assume paymentId is invoice_id
    const finalInvoiceId = invoiceId || paymentId;
    
    // Validate invoiceId
    if (!finalInvoiceId || finalInvoiceId === 'undefined' || finalInvoiceId.trim().length === 0) {
      logger.error(`Cannot register payment: invoiceId is invalid (${finalInvoiceId})`);
      return;
    }

    const tracker: PaymentTracker = {
      paymentId, // This is the key in Map, should be invoice_id for invoice-based payments
      tgId,
      sku,
      orderId,
      invoiceId: finalInvoiceId, // Always use explicit invoiceId
      actualPaymentId: null, // Will be set when payment is created from invoice
      cancelled: false,
      lastCheckAt: 0,
      checkCount: 0,
    };

    // Use invoiceId as the key in Map for invoice-based payments
    this.payments.set(finalInvoiceId, tracker);

    // Schedule auto-checks (will use invoiceId from tracker)
    this.scheduleAutoChecks(finalInvoiceId, autoCheckCallback);

    logger.info(`Registered payment for tracking: invoice_id=${finalInvoiceId}, order_id=${orderId}, user=${tgId}, sku=${sku}`);
  }

  /**
   * Schedule automatic payment checks
   * CRITICAL: Uses invoiceId from tracker, not paymentId parameter (to avoid order_id confusion)
   */
  private scheduleAutoChecks(
    paymentId: string,
    callback: (invoiceId: string) => Promise<void>
  ): void {
    const tracker = this.payments.get(paymentId);
    if (!tracker) {
      logger.warn(`Tracker not found for paymentId ${paymentId}, cannot schedule auto-checks`);
      return;
    }

    // CRITICAL: Use invoiceId from tracker, not paymentId parameter
    // This ensures we always use invoice_id for invoice-based payments
    const invoiceId = tracker.invoiceId;
    if (!invoiceId || invoiceId === 'undefined' || invoiceId.trim().length === 0) {
      logger.error(`Cannot schedule auto-checks: invoiceId is invalid (${invoiceId}) for paymentId ${paymentId}`);
      return;
    }

    let checkIndex = 0;

    const scheduleNext = () => {
      if (checkIndex >= this.MAX_AUTO_CHECKS) {
        logger.info(`Auto-checks completed for invoice ${invoiceId}`);
        return;
      }

      if (tracker.cancelled) {
        logger.info(`Invoice ${invoiceId} was cancelled, stopping auto-checks`);
        return;
      }

      const delay = this.AUTO_CHECK_DELAYS[checkIndex];
      tracker.autoCheckTimer = setTimeout(async () => {
        try {
          // CRITICAL: Pass invoiceId, not paymentId
          await callback(invoiceId);
          checkIndex++;
          scheduleNext();
        } catch (error: any) {
          logger.error(`Auto-check failed for invoice_id ${invoiceId}: ${error.message}`);
          checkIndex++;
          scheduleNext();
        }
      }, delay);

      logger.info(`Scheduled auto-check ${checkIndex + 1}/${this.MAX_AUTO_CHECKS} for invoice ${invoiceId} in ${delay}ms`);
    };

    scheduleNext();
  }

  /**
   * Check if payment can be checked (rate limiting)
   */
  canCheckPayment(paymentId: string, tgId: number): { allowed: boolean; reason?: string } {
    const tracker = this.payments.get(paymentId);
    
    if (!tracker) {
      return { allowed: false, reason: 'Payment not found' };
    }

    // Verify user owns this payment
    if (tracker.tgId !== tgId) {
      logger.warn(`User ${tgId} attempted to check payment ${paymentId} owned by ${tracker.tgId}`);
      return { allowed: false, reason: 'Payment ownership mismatch' };
    }

    // Check if cancelled
    if (tracker.cancelled) {
      return { allowed: false, reason: 'Payment was cancelled' };
    }

    // Rate limiting
    const now = Date.now();
    const timeSinceLastCheck = now - tracker.lastCheckAt;
    
    if (tracker.lastCheckAt > 0 && timeSinceLastCheck < this.RATE_LIMIT_MS) {
      const waitSeconds = Math.ceil((this.RATE_LIMIT_MS - timeSinceLastCheck) / 1000);
      return { allowed: false, reason: `Please wait ${waitSeconds} seconds before checking again` };
    }

    tracker.lastCheckAt = now;
    tracker.checkCount++;
    
    return { allowed: true };
  }

  /**
   * Mark payment as cancelled
   */
  cancelPayment(paymentId: string, tgId: number): boolean {
    const tracker = this.payments.get(paymentId);
    
    if (!tracker) {
      return false;
    }

    // Verify user owns this payment
    if (tracker.tgId !== tgId) {
      logger.warn(`User ${tgId} attempted to cancel payment ${paymentId} owned by ${tracker.tgId}`);
      return false;
    }

    tracker.cancelled = true;
    
    // Clear auto-check timer
    if (tracker.autoCheckTimer) {
      clearTimeout(tracker.autoCheckTimer);
      tracker.autoCheckTimer = undefined;
    }

    logger.info(`Payment ${paymentId} cancelled by user ${tgId}`);
    return true;
  }

  /**
   * Get payment tracker
   */
  getPayment(paymentId: string): PaymentTracker | undefined {
    return this.payments.get(paymentId);
  }

  /**
   * Get payment tracker by orderId
   */
  getPaymentByOrderId(orderId: string, tgId: number): PaymentTracker | undefined {
    for (const tracker of this.payments.values()) {
      if (tracker.orderId === orderId && tracker.tgId === tgId) {
        return tracker;
      }
    }
    return undefined;
  }

  /**
   * Update payment_id when payment is created from invoice
   */
  updatePaymentId(invoiceId: string, paymentId: string): void {
    const tracker = this.payments.get(invoiceId);
    if (tracker) {
      tracker.actualPaymentId = paymentId;
      logger.info(`Updated payment_id for invoice ${invoiceId}: ${paymentId}`);
    }
  }

  /**
   * Get actual payment_id (either from tracker or by getting it from invoice)
   */
  getActualPaymentId(trackerId: string): string | null {
    const tracker = this.payments.get(trackerId);
    return tracker?.actualPaymentId || null;
  }

  /**
   * Remove payment from tracking (after successful processing)
   */
  removePayment(paymentId: string): void {
    const tracker = this.payments.get(paymentId);
    if (tracker?.autoCheckTimer) {
      clearTimeout(tracker.autoCheckTimer);
    }
    this.payments.delete(paymentId);
    logger.info(`Removed payment ${paymentId} from tracking`);
  }

  /**
   * Cleanup old payments (older than 1 hour)
   */
  cleanupOldPayments(): void {
    const oneHourAgo = Date.now() - 60 * 60 * 1000;
    let cleaned = 0;

    for (const [paymentId, tracker] of this.payments.entries()) {
      if (tracker.lastCheckAt > 0 && tracker.lastCheckAt < oneHourAgo) {
        if (tracker.autoCheckTimer) {
          clearTimeout(tracker.autoCheckTimer);
        }
        this.payments.delete(paymentId);
        cleaned++;
      }
    }

    if (cleaned > 0) {
      logger.info(`Cleaned up ${cleaned} old payment trackers`);
    }
  }
}

export const cryptoPaymentTracker = new CryptoPaymentTrackerService();

// Cleanup old payments every 30 minutes
setInterval(() => {
  cryptoPaymentTracker.cleanupOldPayments();
}, 30 * 60 * 1000);

