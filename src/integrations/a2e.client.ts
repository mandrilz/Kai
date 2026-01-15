import axios, { AxiosInstance, AxiosError } from 'axios';
import { v4 as uuidv4 } from 'uuid';
import { config } from '../config';
import { logger } from '../utils/logger';
import { requestQueue } from '../utils/request-queue';

interface PresignedUrlResponse {
  data: {
    uploadUrl: string;
    key: string;
    expiresIn: number;
    bucket: string;
  };
}

interface StartTaskResponse {
  code: number;
  message?: string;
  data: {
    _id?: string;
    current_status?: string;
  } | Array<{
    _id: string;
    current_status: string;
  }> | {
    [key: string]: {
      _id: string;
      current_status: string;
    };
  };
}

interface TaskDetailResponse {
  code?: number;
  message?: string;
  data: {
    _id: string;
    current_status: string;
    image_urls?: string[];
    error_message?: string;
    error?: string;
    failed_message?: string;
  };
}

export class A2EClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: config.a2e.baseUrl,
      headers: {
        Authorization: `Bearer ${config.a2e.bearerToken}`,
        'Content-Type': 'application/json',
      },
      timeout: 300000, // 5 minutes timeout for all requests (longer than polling maxDuration)
    });

    // Add response interceptor for rate limit handling
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as any;

        // Handle rate limiting (429 Too Many Requests)
        if (error.response?.status === 429) {
          const retryAfter = error.response.headers['retry-after'];
          const delay = retryAfter ? parseInt(retryAfter) * 1000 : 2000; // Default 2 seconds

          logger.warn(`Rate limit hit (429), retrying after ${delay}ms`);

          // Wait and retry
          await new Promise(resolve => setTimeout(resolve, delay));
          return this.client(originalRequest);
        }

        // Handle 500 errors with retry
        if (error.response?.status === 500 && originalRequest && !originalRequest._retry) {
          originalRequest._retry = true;
          logger.warn(`Server error (500), retrying after 1 second`);
          await new Promise(resolve => setTimeout(resolve, 1000));
          return this.client(originalRequest);
        }

        return Promise.reject(error);
      }
    );
  }

  /**
   * Get presigned URL for file upload
   */
  async getPresignedUploadUrl(): Promise<{ uploadUrl: string; key: string; bucket: string }> {
    // Use request queue to limit concurrent requests
    return requestQueue.add(async () => {
      // Use correct key structure that CDN can serve
      // CDN serves paths like: adam2eve/stable/user/<user_id>/<model>/<date>/<file>
      // Use simple user/ prefix which is CDN-accessible
      const key = `user/${uuidv4()}.jpg`;
      const response = await this.client.post<PresignedUrlResponse>(
        '/api/v1/r2/get_upload_presigned_url',
        { key }
      );

      const responseData = response.data.data;
      logger.info(`Presigned URL response: key=${responseData.key}, bucket=${responseData.bucket}, expiresIn=${responseData.expiresIn}`);

      return {
        uploadUrl: responseData.uploadUrl,
        key: responseData.key,
        bucket: responseData.bucket,
      };
    }, `getPresignedUrl-${Date.now()}`);
  }

  /**
   * Probe URL to check if it's accessible
   */
  private async probeUrl(url: string): Promise<boolean> {
    try {
      // HEAD often faster, but some CDNs don't like HEAD - fallback to GET
      const head = await axios.head(url, {
        timeout: 8000,
        validateStatus: () => true,
        maxRedirects: 5,
      });

      if (head.status >= 200 && head.status < 300) return true;

      // fallback: small GET
      const get = await axios.get(url, {
        timeout: 8000,
        validateStatus: () => true,
        maxRedirects: 5,
        responseType: "arraybuffer",
        headers: { Range: "bytes=0-1023" }, // download 1KB
      });

      return get.status >= 200 && get.status < 300;
    } catch {
      return false;
    }
  }

  /**
   * Upload image to presigned URL
   */
  async uploadImage(
    uploadUrl: string,
    imageBuffer: Buffer,
    key: string,
    bucket: string
  ): Promise<string> {
    logger.info(`Uploading image, size: ${imageBuffer.length} bytes, key: ${key}, bucket: ${bucket}`);

    const uploadResponse = await axios.put(uploadUrl, imageBuffer, {
      headers: {
        "Content-Type": "image/jpeg",
        "Content-Length": String(imageBuffer.length),
      },
      maxRedirects: 5,
      validateStatus: (status) => status >= 200 && status < 400,
    });

    logger.info(`Upload response status: ${uploadResponse.status}`);

    // CDN used in NanoBanana examples (matches bucket name)
    const cdn1 = "https://a2e-prod-jumpy.ai2everyone.com";
    const cdn2 = "https://3days-apac.ai2everyone.com";

    const keyNoPrefix = key.startsWith("adam2eve/") ? key.replace(/^adam2eve\//, "") : key;

    const candidates = [
      `${cdn1}/${key}`,
      `${cdn1}/${keyNoPrefix}`,
      `${cdn2}/${key}`,
      `${cdn2}/${keyNoPrefix}`,
    ];

    for (const u of candidates) {
      const ok = await this.probeUrl(u);
      logger.info(`Probe ${u.substring(0, 90)}... => ${ok ? "OK" : "FAIL"}`);
      if (ok) {
        logger.info(`Public URL selected: ${u}`);
        return u;
      }
    }

    // If NO URL is accessible - this is a clear signal
    // that CDN doesn't publish uploaded objects in your tier/account.
    throw new Error(
      `Uploaded OK but no public CDN URL is reachable. key=${key}, keyNoPrefix=${keyNoPrefix}`
    );
  }

  /**
   * Start image editing task (NanoBanana)
   */
  async startTask(
    name: string,
    prompt: string,
    inputImages: string[],
    width: number,
    height: number
  ): Promise<string> {
    // Use request queue to limit concurrent requests
    return requestQueue.add(async () => {
      try {
      // According to A2E API documentation and working example:
      // Exact format from working example:
      // {
      //   "name": "12-20-2025 11:08:12",
      //   "prompt": "She is fully naked. Her breasts are small. Her nipples are small and delicate",
      //   "width": 768,
      //   "height": 1344,
      //   "model_type": "a2e",
      //   "input_images": ["https://3days-apac.ai2everyone.com/..."]
      // }
      const requestBody = {
        name,
        prompt,
        width,
        height,
        model_type: 'a2e',
        input_images: inputImages,
      };

      logger.info(`Starting A2E task: name=${name}, prompt length=${prompt.length}, images count=${inputImages.length}`);
      logger.info(`Request body: ${JSON.stringify({ ...requestBody, input_images: requestBody.input_images.map(url => url.substring(0, 80) + '...') })}`);

      // Use userText2image/start for image editing
      // This endpoint works with the detail/delete endpoints
      const response = await this.client.post<StartTaskResponse>(
        '/api/v1/userText2image/start',
        requestBody
      );

      // Check response code according to API documentation:
      // Success: { "code": 0, "message": "Task created successfully", "data": {...} }
      // Error: { "code": -1, "message": "Request failed" }
      if (response.data.code !== 0 && response.data.code !== 200) {
        const errorMsg = response.data.message || 'Request failed';
        logger.error(`A2E API returned error code: ${response.data.code}, message: ${errorMsg}`);
        throw new Error(`A2E API error: ${errorMsg} (code: ${response.data.code})`);
      }

      // According to API documentation, success response is:
      // { "code": 0, "message": "Task created successfully", "data": {} }
      // But in practice, data may contain task information
      // Check if data is empty object (as per documentation example)
      const responseData = response.data.data;
      
      // If data is empty object {}, we need to check response structure
      if (!responseData || (typeof responseData === 'object' && Object.keys(responseData).length === 0)) {
        logger.warn(`Response data is empty object, checking full response structure`);
        logger.warn(`Full response: ${JSON.stringify(response.data)}`);
        // Try to find task ID in response structure
        const fullResponse = response.data as any;
        if (fullResponse._id) {
          // Task ID might be at top level
          logger.info(`Task started: _id=${fullResponse._id}, status=${fullResponse.current_status || 'initialized'}`);
          return fullResponse._id;
        } else {
          logger.error(`Cannot extract task ID from response: ${JSON.stringify(response.data)}`);
          throw new Error('Failed to extract task ID from response: data is empty');
        }
      }

      // userText2image/start may return different structure
      // Response might be: { code: 0, data: { _id: "...", ... } } or { code: 0, data: [{ _id: "...", ... }] }
      // Or even: { code: 0, data: { "0": { _id: "...", ... } } } (object with numeric keys)
      let taskId: string;
      let initialStatus: string;
      let taskData: any;
      
      if (Array.isArray(responseData)) {
        // If data is an array, take the first task
        taskData = responseData[0];
        taskId = taskData._id;
        initialStatus = taskData.current_status || 'initialized';
      } else if (responseData._id) {
        // If data is an object with _id
        taskData = responseData;
        taskId = taskData._id;
        initialStatus = taskData.current_status || 'initialized';
      } else {
        // Try to find _id in nested structure (e.g., { "0": { _id: "..." } })
        const data = responseData as any;
        const firstKey = Object.keys(data)[0];
        if (firstKey && data[firstKey] && data[firstKey]._id) {
          taskData = data[firstKey];
          taskId = taskData._id;
          initialStatus = taskData.current_status || 'initialized';
        } else if (data[0] && data[0]._id) {
          taskData = data[0];
          taskId = taskData._id;
          initialStatus = taskData.current_status || 'initialized';
        } else {
          logger.error(`Unexpected response structure: ${JSON.stringify(response.data)}`);
          throw new Error('Failed to extract task ID from response');
        }
      }
      
      if (!taskId) {
        logger.error(`Task ID is undefined. Full response: ${JSON.stringify(response.data)}`);
        throw new Error('Task ID is undefined in response');
      }

        logger.info(`Task started: _id=${taskId}, status=${initialStatus}`);
        return taskId;
      } catch (error: any) {
        logger.error(`Failed to start A2E task: ${error.message}`);
        if (error.response?.data) {
          logger.error(`A2E API error response: ${JSON.stringify(error.response.data)}`);
        }
        if (error.response?.status) {
          logger.error(`A2E API HTTP status: ${error.response.status}`);
        }
        throw error;
      }
    }, `startTask-${name}`);
  }

  /**
   * Get task detail
   */
  async getTaskDetail(
    taskId: string,
    logOnlyOnStatusChange: boolean = false,
    lastStatus?: string | null
  ): Promise<{
    status: string;
    imageUrl?: string;
    error?: string;
    failed_message?: string;
  }> {
    try {
      // Use userText2image/{taskId} for getting task details (GET method)
      const response = await this.client.get<TaskDetailResponse>(
        `/api/v1/userText2image/${taskId}`
      );

      const data = response.data.data;
      
      // Handle case when data is null
      if (!data) {
        logger.warn(`Task ${taskId} detail: data is null`);
        return {
          status: 'unknown',
          imageUrl: undefined,
          error: 'Task data not found',
          failed_message: undefined,
        };
      }
      
      const statusChanged = !logOnlyOnStatusChange || data.current_status !== lastStatus;

      if (statusChanged) {
        logger.info(`Task ${taskId} status: ${data.current_status}`);

        // Log task details (sanitized)
        const logData: any = {
          _id: data._id,
          current_status: data.current_status,
          has_image_urls: !!data.image_urls?.length,
        };

        if (data.failed_message) {
          logData.failed_message = data.failed_message;
        }
        if (data.error_message) {
          logData.error_message = data.error_message;
        }
        if (data.error) {
          logData.error = data.error;
        }

        logger.info(`Task ${taskId} detail: ${JSON.stringify(logData)}`);
      }

      // Always log errors
      if (data.failed_message || data.error_message || data.error) {
        const errorMsg = data.failed_message || data.error_message || data.error;
        logger.error(`Task ${taskId} error: ${errorMsg}`);
      }

      return {
        status: data.current_status,
        imageUrl: data.image_urls?.[0],
        error: data.failed_message || data.error_message || data.error,
        failed_message: data.failed_message,
      };
    } catch (error: any) {
      logger.error(`Failed to get task detail for ${taskId}: ${error.message}`);
      if (error.response?.data) {
        logger.error(`A2E API error response: ${JSON.stringify(error.response.data)}`);
      }
      if (error.response?.status) {
        logger.error(`A2E API HTTP status: ${error.response.status}`);
        if (error.response.status === 404) {
          logger.error(`Task ${taskId} not found. This might mean:`);
          logger.error(`1. The task was created in a different system`);
          logger.error(`2. The task ID format is incorrect`);
          logger.error(`3. The endpoint /api/v1/userText2image/${taskId} is not correct for this task type`);
        }
      }
      throw error;
    }
  }

  /**
   * Poll task until completion
   * Returns the image URL if completed, or throws an error if failed/timeout
   * If timeout occurs, the task is still processing and should be tracked as pending
   */
  async pollTaskUntilComplete(
    taskId: string,
    onProgress?: (status: string) => void
  ): Promise<string> {
    const startTime = Date.now();
    const maxDuration = config.polling.maxDurationMs;
    const interval = config.polling.intervalMs;
    let lastStatus: string | null = null;
    
    logger.info(`Starting polling for task ${taskId}, maxDuration: ${maxDuration}ms (${maxDuration/1000}s), interval: ${interval}ms`);

    while (true) {
      const elapsed = Date.now() - startTime;
      if (elapsed > maxDuration) {
        // Don't delete task on timeout - it may still be processing
        // Throw a special error that indicates timeout but task may still complete
        const timeoutError: any = new Error('Task processing is taking longer than expected. Please try again later.');
        timeoutError.isTimeout = true;
        timeoutError.taskId = taskId;
        throw timeoutError;
      }

      const detail = await this.getTaskDetail(taskId, true, lastStatus);

      // Only call onProgress if status changed
      if (detail.status !== lastStatus) {
        onProgress?.(detail.status);
        lastStatus = detail.status;
      }

      if (detail.status === 'completed') {
        if (!detail.imageUrl) {
          throw new Error('Task completed but no image URL found');
        }
        return detail.imageUrl;
      }

      if (detail.status === 'failed' || detail.status === 'error') {
        let errorMsg = `Task failed with status: ${detail.status}`;
        if (detail.error) {
          errorMsg = `Task failed: ${detail.error}`;
        }

        logger.error(`A2E task failed: ${errorMsg}`);
        logger.error(`Task detail on failure: ${JSON.stringify({
          status: detail.status,
          error: detail.error,
          hasImageUrl: !!detail.imageUrl,
        })}`);

        throw new Error(errorMsg);
      }

      await new Promise((resolve) => setTimeout(resolve, interval));
    }
  }

  /**
   * Check if a task is completed (for pending task checking)
   * Returns the image URL if completed, null if still processing, or throws if failed
   */
  async checkTaskCompletion(taskId: string): Promise<string | null> {
    try {
      const detail = await this.getTaskDetail(taskId, false);
      
      if (detail.status === 'completed') {
        if (!detail.imageUrl) {
          logger.warn(`Task ${taskId} marked as completed but no image URL found`);
          return null;
        }
        return detail.imageUrl;
      }
      
      if (detail.status === 'failed' || detail.status === 'error') {
        let errorMsg = `Task failed with status: ${detail.status}`;
        if (detail.error) {
          errorMsg = `Task failed: ${detail.error}`;
        }
        throw new Error(errorMsg);
      }
      
      // Still processing
      return null;
    } catch (error: any) {
      // If 404, task might have been deleted or doesn't exist
      if (error.response?.status === 404) {
        logger.warn(`Task ${taskId} not found - may have been deleted`);
        throw new Error(`Task ${taskId} not found`);
      }
      throw error;
    }
  }

  /**
   * Delete task record
   */
  async deleteTask(taskId: string): Promise<void> {
    try {
      // Use userText2image/{taskId} for deleting tasks (DELETE method)
      await this.client.delete(`/api/v1/userText2image/${taskId}`);
      logger.debug(`Task ${taskId} deleted successfully`);
    } catch (error: any) {
      logger.error(`Failed to delete task ${taskId}: ${error.message}`);
      // Don't throw - deletion is best effort
    }
  }

  /**
   * Process image: full pipeline
   */
  async processImage(
    imageBuffer: Buffer,
    prompt: string,
    tgId: number,
    width: number,
    height: number,
    onProgress?: (status: string) => void
  ): Promise<Buffer> {
    let taskId: string | null = null;

    try {
      // Step 1: Get presigned URL
      onProgress?.('Getting upload URL...');
      const { uploadUrl, key, bucket } = await this.getPresignedUploadUrl();

      // Step 2: Upload image
      onProgress?.('Uploading image...');
      const publicUrl = await this.uploadImage(uploadUrl, imageBuffer, key, bucket);

      // Step 3: Start task with original image dimensions
      onProgress?.('Starting processing...');
      const taskName = `tg-${tgId}-${Date.now()}`;
      taskId = await this.startTask(taskName, prompt, [publicUrl], width, height);

      // Step 4: Poll until complete
      onProgress?.('Processing...');
      const resultImageUrl = await this.pollTaskUntilComplete(taskId, onProgress);

      // Step 5: Download result image
      onProgress?.('Downloading result...');
      const resultResponse = await axios.get(resultImageUrl, {
        responseType: 'arraybuffer',
      });
      const resultBuffer = Buffer.from(resultResponse.data);

      // Step 6: Cleanup - delete task
      if (taskId) {
        await this.deleteTask(taskId);
      }

      taskId = null;
      return resultBuffer;
    } catch (error: any) {
      // Cleanup on error
      // BUT: Don't delete task on timeout - it may still be processing
      if (taskId && !error.message.includes('taking longer than expected') && !error.message.includes('timeout')) {
        await this.deleteTask(taskId).catch(() => {});
      }
      taskId = null;
      throw error;
    }
  }
}

export const a2eClient = new A2EClient();
