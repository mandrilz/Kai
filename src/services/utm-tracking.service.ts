import { prisma } from '../db/prisma';
import { logger } from '../utils/logger';
import { zonedTimeToUtc, utcToZonedTime } from 'date-fns-tz';
import { startOfDay, endOfDay } from 'date-fns';

/**
 * Validates UTM source payload
 * Only allows [a-zA-Z0-9_:-] and max length 32
 */
export function validateUtmSource(payload: string): string | null {
  if (!payload || payload.length === 0) {
    return null;
  }

  // Remove utm_ prefix if present (utm_ is 4 characters, so slice(4))
  const source = payload.startsWith('utm_') ? payload.slice(4) : payload;

  // Validate: only alphanumeric, underscore, colon, hyphen; max 32 chars
  if (source.length > 32) {
    logger.warn(`UTM source too long: ${source} (${source.length} chars)`);
    return null;
  }

  const validPattern = /^[a-zA-Z0-9_:-]+$/;
  if (!validPattern.test(source)) {
    logger.warn(`Invalid UTM source format: ${source}`);
    return null;
  }

  return source;
}

/**
 * Parse start payload and extract UTM source
 * Supports: utm_<source> or just <source>
 */
export function parseUtmSource(startPayload: string | undefined): string | null {
  if (!startPayload) {
    return null;
  }

  // Handle referral links (ref_*) - skip them for UTM tracking
  if (startPayload.startsWith('ref_')) {
    return null;
  }

  // Extract UTM source
  return validateUtmSource(startPayload);
}

export class UtmTrackingService {
  /**
   * Track user start with UTM source
   * - Creates UserTracking if user doesn't exist
   * - Records start_click event (only once per user) - ALWAYS, even for organic
   * - Sets firstSource (only on first start)
   */
  async trackStart(tgId: number, startPayload: string | undefined, chatType?: string): Promise<void> {
    const tgIdBig = BigInt(tgId);
    
    try {
      // Get or create user
      let user = await prisma.user.findUnique({
        where: { tgId: tgIdBig },
      });

      if (!user) {
        // User should exist by this point (created by creditsService.getOrCreateUser)
        // But if not, try to get it again after a short delay
        logger.warn(`User ${tgId} not found when tracking start, retrying...`);
        // Wait 100ms and retry
        await new Promise<void>((resolve) => {
          // @ts-ignore - setTimeout is available globally in Node.js
          setTimeout(() => resolve(), 100);
        });
        user = await prisma.user.findUnique({
          where: { tgId: tgIdBig },
        });
        if (!user) {
          logger.error(`User ${tgId} still not found after retry, skipping tracking`);
          return;
        }
      }

      // Parse UTM source (returns null if invalid/empty, or source string)
      const utmSource = parseUtmSource(startPayload);
      // Always set source - either utm_<source> or "organic"
      const source = utmSource ? `utm_${utmSource}` : 'organic';

      // Use transaction to ensure atomicity
      await prisma.$transaction(async (tx: any) => {
        // Check if tracking already exists
        let tracking = await tx.userTracking.findUnique({
          where: { userId: user.id },
        });

        if (!tracking) {
          // First start - create tracking record with firstSource
          tracking = await tx.userTracking.create({
            data: {
              userId: user.id,
              tgId: tgIdBig,
              firstSource: source,
            },
          });
          logger.info(`Created tracking for user ${tgId} with firstSource: ${source}`);
        } else {
          // Tracking exists - don't overwrite firstSource
          logger.debug(`Tracking already exists for user ${tgId}, firstSource: ${tracking.firstSource}`);
        }

        // Check if start_click event already exists
        const existingStartClick = await tx.trackingEvent.findUnique({
          where: {
            userId_eventType: {
              userId: user.id,
              eventType: 'start_click',
            },
          },
        });

        if (!existingStartClick) {
          // Record start_click event (only once) - ALWAYS, even for organic
          // Use firstSource from tracking (or source if tracking just created)
          await tx.trackingEvent.create({
            data: {
              userId: user.id,
              // Don't store tgId - it's redundant, can be retrieved via userId
              trackingId: tracking.id,
              eventType: 'start_click',
              source: tracking.firstSource, // Always use firstSource for attribution
              metadata: chatType ? JSON.stringify({ chatType }) : null,
            },
          });
          logger.info(`Recorded start_click event for user ${tgId} from source: ${tracking.firstSource}`);
        } else {
          logger.debug(`start_click event already exists for user ${tgId}`);
        }
      });
    } catch (error: any) {
      logger.error(`Error tracking start for user ${tgId}: ${error.message}`);
      // Don't throw - tracking errors shouldn't break user flow
    }
  }

  /**
   * Track first generation event (only once per user)
   * Always uses firstSource from user_tracking for attribution
   */
  async trackFirstGeneration(tgId: number): Promise<void> {
    const tgIdBig = BigInt(tgId);
    
    try {
      const user = await prisma.user.findUnique({
        where: { tgId: tgIdBig },
      });

      if (!user) {
        logger.warn(`User ${tgId} not found when tracking first generation`);
        return;
      }

      // Check if event already exists
      const existing = await prisma.trackingEvent.findUnique({
        where: {
          userId_eventType: {
            userId: user.id,
            eventType: 'first_generation',
          },
        },
      });

      if (existing) {
        logger.debug(`first_generation event already exists for user ${tgId}`);
        return;
      }

      // Get user's tracking to get firstSource (the only source for attribution)
      const tracking = await prisma.userTracking.findUnique({
        where: { userId: user.id },
      });

      // Always use firstSource for attribution (not "source at the time of event")
      const attributionSource = tracking?.firstSource || 'organic';

      // Record first_generation event
      await prisma.trackingEvent.create({
        data: {
          userId: user.id,
          // Don't store tgId - it's redundant, can be retrieved via userId
          trackingId: tracking?.id || null,
          eventType: 'first_generation',
          source: attributionSource, // Always use firstSource
        },
      });

      logger.info(`Recorded first_generation event for user ${tgId} with source: ${attributionSource}`);
    } catch (error: any) {
      logger.error(`Error tracking first generation for user ${tgId}: ${error.message}`);
      // Don't throw - tracking errors shouldn't break user flow
    }
  }

  /**
   * Track payment event (only once per user)
   * Always uses firstSource from user_tracking for attribution
   */
  async trackPayment(tgId: number, amount?: number): Promise<void> {
    const tgIdBig = BigInt(tgId);
    
    try {
      const user = await prisma.user.findUnique({
        where: { tgId: tgIdBig },
      });

      if (!user) {
        logger.warn(`User ${tgId} not found when tracking payment`);
        return;
      }

      // Check if event already exists
      const existing = await prisma.trackingEvent.findUnique({
        where: {
          userId_eventType: {
            userId: user.id,
            eventType: 'payment',
          },
        },
      });

      if (existing) {
        logger.debug(`payment event already exists for user ${tgId}`);
        return;
      }

      // Get user's tracking to get firstSource (the only source for attribution)
      const tracking = await prisma.userTracking.findUnique({
        where: { userId: user.id },
      });

      // Always use firstSource for attribution (not "source at the time of event")
      const attributionSource = tracking?.firstSource || 'organic';

      // Record payment event
      await prisma.trackingEvent.create({
        data: {
          userId: user.id,
          // Don't store tgId - it's redundant, can be retrieved via userId
          trackingId: tracking?.id || null,
          eventType: 'payment',
          source: attributionSource, // Always use firstSource
          metadata: amount ? JSON.stringify({ amount }) : null,
        },
      });

      logger.info(`Recorded payment event for user ${tgId} with source: ${attributionSource}`);
    } catch (error: any) {
      logger.error(`Error tracking payment for user ${tgId}: ${error.message}`);
      // Don't throw - tracking errors shouldn't break user flow
    }
  }

  /**
   * Get UTM statistics - top sources with aggregated data
   * @param dateFilter - Start date (inclusive) - events with createdAt >= dateFilter
   * @param dateFilterEnd - End date (inclusive) - events with createdAt <= dateFilterEnd
   */
  async getUtmStats(dateFilter?: Date, dateFilterEnd?: Date): Promise<any[]> {
    // Get events filtered by date range if provided
    const eventDateCondition: any = {};
    if (dateFilter) {
      eventDateCondition.createdAt = { gte: dateFilter };
    }
    if (dateFilterEnd) {
      if (eventDateCondition.createdAt) {
        eventDateCondition.createdAt.lte = dateFilterEnd;
      } else {
        eventDateCondition.createdAt = { lte: dateFilterEnd };
      }
    }

    // Get all start_click events (unique users per source)
    const startClickEvents = await prisma.trackingEvent.findMany({
      where: {
        eventType: 'start_click',
        ...eventDateCondition,
      },
      include: {
        tracking: true,
      },
    });

    // Get all first_generation events
    const firstGenEvents = await prisma.trackingEvent.findMany({
      where: {
        eventType: 'first_generation',
        ...eventDateCondition,
      },
      include: {
        tracking: true,
      },
    });

    // Get all payment events
    const paymentEvents = await prisma.trackingEvent.findMany({
      where: {
        eventType: 'payment',
        ...eventDateCondition,
      },
      include: {
        tracking: true,
      },
    });

    // Aggregate by source
    const sourceMap = new Map<string, {
      source: string;
      uniqueUsers: Set<string>; // Use Set to track unique user IDs
      firstGenerations: Set<string>;
      payments: Set<string>;
    }>();

    // Process start_click events (unique users)
    // source field always contains firstSource (attribution source)
    for (const event of startClickEvents) {
      const source = event.source; // Always firstSource, never null
      
      if (!sourceMap.has(source)) {
        sourceMap.set(source, {
          source,
          uniqueUsers: new Set(),
          firstGenerations: new Set(),
          payments: new Set(),
        });
      }

      sourceMap.get(source)!.uniqueUsers.add(event.userId);
    }

    // Process first_generation events
    // source field always contains firstSource (attribution source)
    for (const event of firstGenEvents) {
      const source = event.source; // Always firstSource, never null
      
      if (!sourceMap.has(source)) {
        sourceMap.set(source, {
          source,
          uniqueUsers: new Set(),
          firstGenerations: new Set(),
          payments: new Set(),
        });
      }

      sourceMap.get(source)!.firstGenerations.add(event.userId);
    }

    // Process payment events
    // source field always contains firstSource (attribution source)
    for (const event of paymentEvents) {
      const source = event.source; // Always firstSource, never null
      
      if (!sourceMap.has(source)) {
        sourceMap.set(source, {
          source,
          uniqueUsers: new Set(),
          firstGenerations: new Set(),
          payments: new Set(),
        });
      }

      sourceMap.get(source)!.payments.add(event.userId);
    }

    // Convert to array and calculate conversion rates
    return Array.from(sourceMap.values())
      .map(stat => {
        const uniqueUsers = stat.uniqueUsers.size;
        const firstGenerations = stat.firstGenerations.size;
        const payments = stat.payments.size;

        return {
          source: stat.source,
          uniqueUsers,
          firstGenerations,
          payments,
          conversionRate: uniqueUsers > 0
            ? (firstGenerations / uniqueUsers) * 100
            : 0,
          paymentConversionRate: uniqueUsers > 0
            ? (payments / uniqueUsers) * 100
            : 0,
        };
      })
      .sort((a, b) => b.uniqueUsers - a.uniqueUsers);
  }

  /**
   * Get detailed stats for a specific source
   * @param source - UTM source to get stats for
   * @param dateFilter - Start date (inclusive) - events with createdAt >= dateFilter
   * @param dateFilterEnd - End date (inclusive) - events with createdAt <= dateFilterEnd
   */
  async getSourceStats(source: string, dateFilter?: Date, dateFilterEnd?: Date): Promise<any> {
    // Get events filtered by date range if provided
    const eventDateCondition: any = {};
    if (dateFilter) {
      eventDateCondition.createdAt = { gte: dateFilter };
    }
    if (dateFilterEnd) {
      if (eventDateCondition.createdAt) {
        eventDateCondition.createdAt.lte = dateFilterEnd;
      } else {
        eventDateCondition.createdAt = { lte: dateFilterEnd };
      }
    }

    // Get events for this source
    const startClickEvents = await prisma.trackingEvent.findMany({
      where: {
        eventType: 'start_click',
        source: source,
        ...eventDateCondition,
      },
    });

    const firstGenEvents = await prisma.trackingEvent.findMany({
      where: {
        eventType: 'first_generation',
        source: source,
        ...eventDateCondition,
      },
    });

    const paymentEvents = await prisma.trackingEvent.findMany({
      where: {
        eventType: 'payment',
        source: source,
        ...eventDateCondition,
      },
    });

    // Count unique users
    const uniqueUsers = new Set(startClickEvents.map((e: { userId: string }) => e.userId)).size;
    const firstGenerations = new Set(firstGenEvents.map((e: { userId: string }) => e.userId)).size;
    const payments = new Set(paymentEvents.map((e: { userId: string }) => e.userId)).size;

    // Get total users with this source (filtered by date range if provided)
    const trackingDateCondition: any = {};
    if (dateFilter) {
      trackingDateCondition.createdAt = { gte: dateFilter };
    }
    if (dateFilterEnd) {
      if (trackingDateCondition.createdAt) {
        trackingDateCondition.createdAt.lte = dateFilterEnd;
      } else {
        trackingDateCondition.createdAt = { lte: dateFilterEnd };
      }
    }
    
    const totalUsers = await prisma.userTracking.count({
      where: {
        firstSource: source,
        ...trackingDateCondition,
      },
    });

    return {
      source,
      uniqueUsers,
      firstGenerations,
      payments,
      conversionRate: uniqueUsers > 0
        ? (firstGenerations / uniqueUsers) * 100
        : 0,
      paymentConversionRate: uniqueUsers > 0
        ? (payments / uniqueUsers) * 100
        : 0,
      totalUsers,
    };
  }
}

export const utmTrackingService = new UtmTrackingService();

