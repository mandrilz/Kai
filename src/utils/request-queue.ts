import { logger } from './logger';

/**
 * Request queue with concurrency limit to prevent overwhelming the API
 * This ensures that only a limited number of requests are processed simultaneously
 */
class RequestQueue {
  private queue: Array<{
    id: string;
    fn: () => Promise<any>;
    resolve: (value: any) => void;
    reject: (error: any) => void;
  }> = [];
  private running = 0;
  private maxConcurrent: number;
  private delayBetweenRequests: number;

  constructor(maxConcurrent: number = 2, delayBetweenRequests: number = 500) {
    this.maxConcurrent = maxConcurrent;
    this.delayBetweenRequests = delayBetweenRequests;
  }

  /**
   * Add a request to the queue
   */
  async add<T>(fn: () => Promise<T>, requestId?: string): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      const id = requestId || `req-${Date.now()}-${Math.random()}`;
      this.queue.push({ id, fn, resolve, reject });
      this.process();
    });
  }

  /**
   * Process the queue
   */
  private async process() {
    if (this.running >= this.maxConcurrent || this.queue.length === 0) {
      return;
    }

    const item = this.queue.shift();
    if (!item) {
      return;
    }

    this.running++;
    logger.debug(`[RequestQueue] Processing request ${item.id}, running: ${this.running}/${this.maxConcurrent}, queue: ${this.queue.length}`);

    try {
      // Add delay between requests to avoid rate limiting
      if (this.running > 1) {
        await new Promise(resolve => setTimeout(resolve, this.delayBetweenRequests));
      }

      const result = await item.fn();
      item.resolve(result);
    } catch (error) {
      item.reject(error);
    } finally {
      this.running--;
      logger.debug(`[RequestQueue] Completed request ${item.id}, running: ${this.running}/${this.maxConcurrent}, queue: ${this.queue.length}`);
      // Process next item in queue
      this.process();
    }
  }

  /**
   * Get current queue status
   */
  getStatus() {
    return {
      queueLength: this.queue.length,
      running: this.running,
      maxConcurrent: this.maxConcurrent,
    };
  }
}

export const requestQueue = new RequestQueue(2, 500); // Max 2 concurrent requests, 500ms delay between requests

