/**
 * Logger utility with URL sanitization
 * Prevents logging sensitive URLs (uploadUrl, publicUrl, image_urls)
 */

const SENSITIVE_PATTERNS = [
  /uploadUrl/gi,
  /publicUrl/gi,
  /image_urls/gi,
  /https?:\/\/[^\s]+/g,
];

function sanitizeMessage(message: string): string {
  let sanitized = message;
  SENSITIVE_PATTERNS.forEach((pattern) => {
    sanitized = sanitized.replace(pattern, '[REDACTED]');
  });
  return sanitized;
}

function sanitizeObject(obj: any): any {
  if (obj === null || obj === undefined) {
    return obj;
  }
  if (typeof obj === 'string') {
    return sanitizeMessage(obj);
  }
  if (Array.isArray(obj)) {
    return obj.map(sanitizeObject);
  }
  if (typeof obj === 'object') {
    const sanitized: any = {};
    for (const [key, value] of Object.entries(obj)) {
      const lowerKey = key.toLowerCase();
      if (
        lowerKey.includes('url') ||
        lowerKey.includes('image') ||
        lowerKey.includes('file')
      ) {
        sanitized[key] = '[REDACTED]';
      } else {
        sanitized[key] = sanitizeObject(value);
      }
    }
    return sanitized;
  }
  return obj;
}

export const logger = {
  info: (message: string, ...args: any[]) => {
    console.log(`[INFO] ${sanitizeMessage(message)}`, ...args.map(sanitizeObject));
  },
  error: (message: string, ...args: any[]) => {
    console.error(`[ERROR] ${sanitizeMessage(message)}`, ...args.map(sanitizeObject));
  },
  warn: (message: string, ...args: any[]) => {
    console.warn(`[WARN] ${sanitizeMessage(message)}`, ...args.map(sanitizeObject));
  },
  debug: (message: string, ...args: any[]) => {
    if (process.env.DEBUG) {
      console.debug(`[DEBUG] ${sanitizeMessage(message)}`, ...args.map(sanitizeObject));
    }
  },
};

