import { Buffer } from 'buffer';
import { config } from '../config';
import { logger } from '../utils/logger';

interface PhotoSession {
  buffer: Buffer;
  mime: string;
  width: number;
  height: number;
  expiresAt: number;
}

/**
 * In-memory session storage for photos
 * Stores only the last photo per user with TTL
 */
class SessionService {
  private sessions: Map<number, PhotoSession> = new Map();
  private processingLocks: Set<number> = new Set();

  /**
   * Store photo in memory (overwrites previous if exists)
   */
  storePhoto(tgId: number, buffer: Buffer, mime: string, width: number, height: number): void {
    const expiresAt = Date.now() + config.session.photoTtlMs;
    this.sessions.set(tgId, {
      buffer,
      mime,
      width,
      height,
      expiresAt,
    });
    logger.debug(`Stored photo in session for user ${tgId}, size: ${width}x${height}, expires at ${new Date(expiresAt).toISOString()}`);
  }

  /**
   * Get photo from memory (returns null if expired or not found)
   */
  getPhoto(tgId: number): { buffer: Buffer; mime: string; width: number; height: number } | null {
    const session = this.sessions.get(tgId);
    if (!session) {
      return null;
    }

    if (Date.now() > session.expiresAt) {
      this.sessions.delete(tgId);
      logger.debug(`Photo session expired for user ${tgId}`);
      return null;
    }

    return {
      buffer: session.buffer,
      mime: session.mime,
      width: session.width,
      height: session.height,
    };
  }

  /**
   * Remove photo from memory
   */
  removePhoto(tgId: number): void {
    const session = this.sessions.get(tgId);
    if (session) {
      // Clear buffer reference
      session.buffer = Buffer.alloc(0);
      this.sessions.delete(tgId);
      logger.debug(`Removed photo from session for user ${tgId}`);
    }
  }

  /**
   * Acquire processing lock (one job per user)
   */
  acquireLock(tgId: number): boolean {
    if (this.processingLocks.has(tgId)) {
      return false;
    }
    this.processingLocks.add(tgId);
    logger.debug(`Acquired processing lock for user ${tgId}`);
    return true;
  }

  /**
   * Release processing lock
   */
  releaseLock(tgId: number): void {
    this.processingLocks.delete(tgId);
    logger.debug(`Released processing lock for user ${tgId}`);
  }

  /**
   * Check if user has active processing
   */
  isProcessing(tgId: number): boolean {
    return this.processingLocks.has(tgId);
  }

  /**
   * Cleanup expired sessions (should be called periodically)
   */
  cleanupExpired(): void {
    const now = Date.now();
    let cleaned = 0;
    for (const [tgId, session] of this.sessions.entries()) {
      if (now > session.expiresAt) {
        session.buffer = Buffer.alloc(0);
        this.sessions.delete(tgId);
        cleaned++;
      }
    }
    if (cleaned > 0) {
      logger.debug(`Cleaned up ${cleaned} expired photo sessions`);
    }
  }
}

export const sessionService = new SessionService();

// Periodic cleanup every 5 minutes
setInterval(() => {
  sessionService.cleanupExpired();
}, 5 * 60 * 1000);

