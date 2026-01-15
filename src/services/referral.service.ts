import { prisma } from '../db/prisma';
import { logger } from '../utils/logger';
import { config } from '../config';

export class ReferralService {
  /**
   * Get referral relationship by invitee tgId
   * Returns referral with user IDs (UUIDs) if invitee was invited
   */
  async getReferralByInviteeTgId(inviteeTgId: number): Promise<{
    referralId: string;
    inviterUserId: string;
    inviteeUserId: string;
    inviterTgId: bigint;
  } | null> {
    const inviteeTgIdBig = BigInt(inviteeTgId);
    
    const referral = await prisma.referral.findFirst({
      where: {
        invitee: {
          tgId: inviteeTgIdBig,
        },
      },
      include: {
        inviter: true,
        invitee: true,
      },
    });

    if (!referral) {
      return null;
    }

    return {
      referralId: referral.id,
      inviterUserId: referral.inviterId,
      inviteeUserId: referral.inviteeId,
      inviterTgId: referral.inviter.tgId,
    };
  }

  /**
   * Create referral relationship when user starts with ref link
   * Returns true if created, false if already exists or self-ref
   */
  async createReferral(
    inviterTgId: number,
    inviteeTgId: number,
    options?: {
      createdFrom?: string;
      createdChatType?: string;
    }
  ): Promise<boolean> {
    // Prevent self-referral
    if (inviterTgId === inviteeTgId) {
      logger.warn(`Self-referral attempt blocked: ${inviterTgId}`);
      return false;
    }

    const inviterTgIdBig = BigInt(inviterTgId);
    const inviteeTgIdBig = BigInt(inviteeTgId);

    try {
      // Use transaction to ensure atomicity
      await prisma.$transaction(async (tx) => {
        // Get or create both users (by tgId)
        let inviter = await tx.user.findUnique({
          where: { tgId: inviterTgIdBig },
        });
        let invitee = await tx.user.findUnique({
          where: { tgId: inviteeTgIdBig },
        });

        if (!inviter) {
          inviter = await tx.user.create({
            data: { tgId: inviterTgIdBig, berries: 1 },
          });
        }

        if (!invitee) {
          invitee = await tx.user.create({
            data: { tgId: inviteeTgIdBig, berries: 1 },
          });
        }

        // Check if referral already exists (by invitee.id - UUID)
        const existing = await tx.referral.findUnique({
          where: { inviteeId: invitee.id },
        });

        if (existing) {
          logger.info(`Referral already exists for invitee ${inviteeTgId} (userId: ${invitee.id})`);
          return false;
        }

        // Create referral relationship (using user.id - UUID, not tgId)
        await tx.referral.create({
          data: {
            inviterId: inviter.id, // UUID
            inviteeId: invitee.id, // UUID
            createdFrom: options?.createdFrom || 'start_param',
            createdChatType: options?.createdChatType || null,
          },
        });

        logger.info(`Referral created: ${inviterTgId} (${inviter.id}) -> ${inviteeTgId} (${invitee.id})`);
      });

      return true;
    } catch (error: any) {
      // Handle unique constraint violation (invitee already has a referrer)
      if (error.code === 'P2002') {
        logger.warn(`Referral already exists for invitee ${inviteeTgId} (unique constraint)`);
        return false;
      }
      logger.error(`Error creating referral: ${error.message}`);
      throw error;
    }
  }

  /**
   * Check if invitee has already generated their first image
   * Returns true if first generation already happened (reward exists)
   */
  async hasInviteeGeneratedFirstImage(inviteeTgId: number): Promise<boolean> {
    const referral = await this.getReferralByInviteeTgId(inviteeTgId);
    if (!referral) {
      return false; // No referral relationship
    }

    // Check if reward already exists for this referral (UNIQUE constraint on referralId)
    const reward = await prisma.referralReward.findUnique({
      where: { referralId: referral.referralId },
    });

    return !!reward;
  }

  /**
   * Process referral reward after first successful generation
   * 
   * Надежный паттерн:
   * 1. Сначала пытаемся создать reward (UNIQUE constraint на referralId)
   * 2. Если получили ошибку уникальности → уже начисляли → выходим
   * 3. Только если create успешен → инкрементим ягоды inviter
   * 
   * Это предотвращает race conditions даже без Serializable isolation
   */
  async processReferralReward(inviteeTgId: number): Promise<{
    success: boolean;
    inviterTgId?: number;
    berriesRewarded?: number;
    reason?: string;
  }> {
    try {
      // Step 1: Get referral relationship (by tgId, then use user.id)
      const referral = await this.getReferralByInviteeTgId(inviteeTgId);
      if (!referral) {
        return { success: false, reason: 'No referral relationship' };
      }

      // Step 2: Check daily limit if enabled (by calendar day in UTC)
      const dailyLimitEnabled = (process.env.REFERRAL_DAILY_LIMIT_ENABLED || '0') === '1';
      const dailyLimit = parseInt(process.env.REFERRAL_DAILY_LIMIT || '10', 10);

      if (dailyLimitEnabled) {
        // Calendar day in UTC (00:00:00 UTC to 23:59:59 UTC)
        const now = new Date();
        const todayStart = new Date(Date.UTC(
          now.getUTCFullYear(),
          now.getUTCMonth(),
          now.getUTCDate(),
          0, 0, 0, 0
        ));
        const tomorrowStart = new Date(todayStart);
        tomorrowStart.setUTCDate(tomorrowStart.getUTCDate() + 1);

        const todayRewardsCount = await prisma.referralReward.count({
          where: {
            inviterId: referral.inviterUserId, // Use UUID
            createdAt: {
              gte: todayStart,
              lt: tomorrowStart,
            },
          },
        });

        if (todayRewardsCount >= dailyLimit) {
          logger.warn(`Daily referral limit reached for inviter ${Number(referral.inviterTgId)}: ${todayRewardsCount}/${dailyLimit} (UTC day)`);
          return { success: false, reason: 'Daily limit reached' };
        }
      }

      // Step 3: Try to create reward record first (UNIQUE constraint on referralId)
      // If this succeeds, we know this is the first time
      let reward;
      try {
        reward = await prisma.referralReward.create({
          data: {
            referralId: referral.referralId, // UNIQUE constraint
            inviterId: referral.inviterUserId, // UUID
            berriesRewarded: 1,
          },
        });
        logger.info(`Referral reward record created for referral ${referral.referralId}`);
      } catch (createError: any) {
        // Handle unique constraint violation (reward already exists)
        if (createError.code === 'P2002' && createError.meta?.target?.includes('referralId')) {
          logger.info(`Referral reward already exists for invitee ${inviteeTgId} (referralId: ${referral.referralId})`);
          return { success: false, reason: 'Reward already given' };
        }
        // Re-throw other errors
        throw createError;
      }

      // Step 4: Only if reward creation succeeded, increment berries
      // Use transaction to ensure atomicity
      await prisma.$transaction(async (tx) => {
        await tx.user.update({
          where: { id: referral.inviterUserId }, // Use UUID
          data: {
            berries: {
              increment: 1,
            },
          },
        });
      });

      logger.info(`Referral reward given: ${Number(referral.inviterTgId)} received 1 berry for invitee ${inviteeTgId}`);

      return {
        success: true,
        inviterTgId: Number(referral.inviterTgId),
        berriesRewarded: 1,
      };
    } catch (error: any) {
      logger.error(`Error processing referral reward for invitee ${inviteeTgId}: ${error.message}`);
      // If reward was created but berries increment failed, we have inconsistent state
      // In production, you might want to add a cleanup job or manual fix
      throw error;
    }
  }

  /**
   * Get referral statistics for a user (by tgId)
   */
  async getReferralStats(inviterTgId: number): Promise<{
    totalReferrals: number;
    totalRewards: number;
    totalBerriesEarned: number;
  }> {
    const inviterTgIdBig = BigInt(inviterTgId);

    const inviter = await prisma.user.findUnique({
      where: { tgId: inviterTgIdBig },
    });

    if (!inviter) {
      return { totalReferrals: 0, totalRewards: 0, totalBerriesEarned: 0 };
    }

    // Use inviter.id (UUID) for queries
    const [totalReferrals, rewards] = await Promise.all([
      prisma.referral.count({
        where: { inviterId: inviter.id },
      }),
      prisma.referralReward.findMany({
        where: { inviterId: inviter.id },
      }),
    ]);

    const totalRewards = rewards.length;
    const totalBerriesEarned = rewards.reduce((sum, r) => sum + r.berriesRewarded, 0);

    return {
      totalReferrals,
      totalRewards,
      totalBerriesEarned,
    };
  }

  /**
   * Generate referral link for a user
   */
  generateReferralLink(botUsername: string, inviterTgId: number): string {
    return `https://t.me/${botUsername}?start=ref_${inviterTgId}`;
  }
}

export const referralService = new ReferralService();

