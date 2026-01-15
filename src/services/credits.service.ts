import { prisma } from '../db/prisma';
import { logger } from '../utils/logger';

export class CreditsService {
  /**
   * Get or create user
   */
  async getOrCreateUser(tgId: number) {
    const tgIdBig = BigInt(tgId);

    let user = await prisma.user.findUnique({
      where: { tgId: tgIdBig },
    });

    if (!user) {
user = await prisma.user.create({
  data: {
    tgId: tgIdBig,
    berries: 1,
    // language: 'en', // ����� ���, �� ����� ������ �� ����������, ����� ������� DEFAULT
  },
});
      logger.info(`Created new user with tgId: ${tgId}`);
    }

    return user;
  }

  /**
   * Update user language
   */
  async updateLanguage(tgId: number, language: string) {
    const user = await this.getOrCreateUser(tgId);
    await prisma.user.update({
      where: { id: user.id },
      data: { language },
    });
    logger.info(`Updated language for user ${tgId} to ${language}`);
  }

  /**
   * Accept terms
   */
  async acceptTerms(tgId: number) {
    const user = await this.getOrCreateUser(tgId);
    await prisma.user.update({
      where: { id: user.id },
      data: { termsAccepted: true },
    });
    logger.info(`User ${tgId} accepted terms`);
  }

  /**
   * Check if user has berries available
   */
  async hasCredits(tgId: number): Promise<boolean> {
    const user = await this.getOrCreateUser(tgId);
    return user.berries > 0;
  }

  /**
   * Check if user has at least N berries
   */
  async hasCreditsAmount(tgId: number, required: number): Promise<boolean> {
    if (!Number.isFinite(required) || required <= 0) {
      return true;
    }
    const user = await this.getOrCreateUser(tgId);
    return user.berries >= required;
  }

  /**
   * Get total berries remaining
   */
  async getTotalCredits(tgId: number): Promise<number> {
    const user = await this.getOrCreateUser(tgId);
    return user.berries;
  }

  /**
   * Get berries breakdown (single balance)
   */
  async getCreditsBreakdown(tgId: number) {
    const user = await this.getOrCreateUser(tgId);
    return {
      berries: user.berries,
      total: user.berries,
    };
  }

  /**
   * Consume one berry
   */
  async consumeCredit(tgId: number): Promise<boolean> {
    const user = await this.getOrCreateUser(tgId);

    if (user.berries > 0) {
      await prisma.user.update({
        where: { id: user.id },
        data: {
          berries: {
            decrement: 1,
          },
        },
      });
      logger.info(`Consumed 1 berry for user ${tgId}`);
      return true;
    }

    return false;
  }

  /**
   * Reserve/consume N berries.
   * Returns true if consumed, false if insufficient balance.
   */
  async consumeBerries(tgId: number, amount: number): Promise<boolean> {
    const safeAmount = Math.floor(amount);
    if (!Number.isFinite(safeAmount) || safeAmount <= 0) {
      return true;
    }

    const user = await this.getOrCreateUser(tgId);
    if (user.berries < safeAmount) {
      return false;
    }

    await prisma.user.update({
      where: { id: user.id },
      data: {
        berries: { decrement: safeAmount },
      },
    });

    logger.info(`Consumed ${safeAmount} berries for user ${tgId}`);
    return true;
  }

  /**
   * Refund previously consumed berries.
   */
  async refundBerries(tgId: number, amount: number): Promise<void> {
    const safeAmount = Math.max(0, Math.floor(amount));
    if (!Number.isFinite(safeAmount) || safeAmount <= 0) {
      return;
    }

    const user = await this.getOrCreateUser(tgId);
    await prisma.user.update({
      where: { id: user.id },
      data: {
        berries: { increment: safeAmount },
      },
    });

    logger.info(`Refunded ${safeAmount} berries for user ${tgId}`);
  }

  /**
   * Add berries (top up)
   */
  async addBerries(tgId: number, amount: number) {
    const safeAmount = Math.max(0, Math.floor(amount));
    if (!Number.isFinite(safeAmount) || safeAmount <= 0) {
      return;
    }

    const user = await this.getOrCreateUser(tgId);
    await prisma.user.update({
      where: { id: user.id },
      data: {
        berries: { increment: safeAmount },
      },
    });
    logger.info(`Added ${safeAmount} berries for user ${tgId}`);
  }
}

export const creditsService = new CreditsService();

