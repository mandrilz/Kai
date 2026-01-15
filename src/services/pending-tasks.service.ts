import { logger } from '../utils/logger';
import { creditsService } from './credits.service';

interface PendingTask {
  taskId: string;
  tgId: number;
  chatId: number;
  messageId: number;
  reservedBerries: number;
  createdAt: number;
  lastChecked: number;
}

/**
 * Service to track pending tasks that timed out but may still complete
 */
class PendingTasksService {
  private pendingTasks: Map<string, PendingTask> = new Map();
  private checkInterval: NodeJS.Timeout | null = null;
  private readonly CHECK_INTERVAL_MS = 20 * 1000; // Check every 20 seconds (more frequent for better recovery)
  private readonly MAX_AGE_MS = 60 * 60 * 1000; // Remove tasks older than 60 minutes (increased to allow more recovery time)

  /**
   * Add a pending task
   */
  addPendingTask(
    taskId: string,
    tgId: number,
    chatId: number,
    messageId: number,
    reservedBerries: number
  ): void {
    this.pendingTasks.set(taskId, {
      taskId,
      tgId,
      chatId,
      messageId,
      reservedBerries,
      createdAt: Date.now(),
      lastChecked: Date.now(),
    });
    logger.info(`Added pending task ${taskId} for user ${tgId}`);
    
    // Start checking if not already started
    if (!this.checkInterval) {
      this.startChecking();
    }
  }

  /**
   * Remove a pending task (when completed or failed)
   */
  removePendingTask(taskId: string): void {
    const task = this.pendingTasks.get(taskId);
    if (task) {
      this.pendingTasks.delete(taskId);
      logger.info(`Removed pending task ${taskId} for user ${task.tgId}`);
    }
  }

  /**
   * Get all pending tasks
   */
  getAllPendingTasks(): PendingTask[] {
    return Array.from(this.pendingTasks.values());
  }

  /**
   * Get pending task by ID
   */
  getPendingTask(taskId: string): PendingTask | undefined {
    return this.pendingTasks.get(taskId);
  }

  /**
   * Update last checked time for a task
   */
  updateLastChecked(taskId: string): void {
    const task = this.pendingTasks.get(taskId);
    if (task) {
      task.lastChecked = Date.now();
    }
  }

  /**
   * Clean up old tasks
   */
  async cleanupOldTasks(): Promise<void> {
    const now = Date.now();
    let cleaned = 0;
    
    for (const [taskId, task] of this.pendingTasks.entries()) {
      if (now - task.createdAt > this.MAX_AGE_MS) {
        this.pendingTasks.delete(taskId);
        cleaned++;

        // Refund reserved berries because we won't deliver this task anymore
        try {
          await creditsService.refundBerries(task.tgId, task.reservedBerries);
        } catch (error: any) {
          logger.error(`Failed to refund berries for expired pending task ${taskId}: ${error.message}`);
        }

        logger.info(`Cleaned up old pending task ${taskId} (age: ${Math.round((now - task.createdAt) / 1000)}s)`);
      }
    }
    
    if (cleaned > 0) {
      logger.info(`Cleaned up ${cleaned} old pending tasks`);
    }
    
    // Stop checking if no tasks left
    if (this.pendingTasks.size === 0 && this.checkInterval) {
      this.stopChecking();
    }
  }

  /**
   * Start periodic checking of pending tasks
   */
  private startChecking(): void {
    if (this.checkInterval) {
      return; // Already started
    }
    
    logger.info('Started periodic checking of pending tasks');
    this.checkInterval = setInterval(() => {
      this.cleanupOldTasks().catch((error: any) => {
        logger.error(`Error cleaning up old pending tasks: ${error.message}`);
      });
    }, this.CHECK_INTERVAL_MS);
  }

  /**
   * Stop periodic checking
   */
  private stopChecking(): void {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
      logger.info('Stopped periodic checking of pending tasks');
    }
  }

  /**
   * Get status
   */
  getStatus() {
    return {
      pendingCount: this.pendingTasks.size,
      isChecking: this.checkInterval !== null,
    };
  }
}

export const pendingTasksService = new PendingTasksService();

