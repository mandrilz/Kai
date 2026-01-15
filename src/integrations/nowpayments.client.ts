import axios, { AxiosInstance } from 'axios';
import { logger } from '../utils/logger';
import { config } from '../config';

export interface NowPaymentsPayment {
  payment_id: string;
  payment_status: string;
  pay_address: string;
  price_amount: number;
  price_currency: string;
  pay_currency: string;
  order_id: string;
  order_description?: string;
  invoice_id?: string;
  payment_url?: string;
  purchase_id?: string;
  created_at?: string;
  updated_at?: string;
}

export interface NowPaymentsCreatePaymentRequest {
  price_amount: number;
  price_currency: string;
  pay_currency: string;
  order_id: string;
  order_description?: string;
}

export interface NowPaymentsEstimate {
  currency_from: string;
  currency_to: string;
  amount_from: number;
  amount_to: number;
  network?: string;
  network_from?: string;
  network_to?: string;
}

export interface NowPaymentsCreateInvoiceRequest {
  price_amount: number;
  price_currency: string;
  order_id: string;
  order_description: string;
  success_url?: string;
  cancel_url?: string;
  ipn_callback_url?: string;
}

export interface NowPaymentsInvoice {
  invoice_id: string;
  invoice_url: string;
  order_id: string;
  order_description: string;
  price_amount: number;
  price_currency: string;
  created_at: string;
  payment_id?: string; // Payment ID appears after invoice is paid
  payment_status?: string; // Payment status appears after invoice is paid (use this for status check)
}

export interface NowPaymentsPaymentListItem {
  payment_id: string;
  payment_status: string;
  pay_address: string;
  price_amount: number;
  price_currency: string;
  pay_currency: string;
  order_id: string;
  order_description?: string;
  created_at?: string;
  updated_at?: string;
}

export class NowPaymentsClient {
  private apiClient: AxiosInstance; // For x-api-key endpoints (invoice, estimate, etc.)
  private jwtClient: AxiosInstance; // For JWT endpoints (auth, list payments, payment status)
  private apiKey: string;
  private jwtToken: string | null = null;
  private jwtTokenExpiry: number = 0; // Timestamp when JWT expires

  constructor() {
    this.apiKey = config.nowpayments.apiKey;
    
    // Safety check: validate API key
    if (!this.apiKey || this.apiKey.trim().length < 10) {
      throw new Error('NOWPAYMENTS_API_KEY is empty/invalid (check .env and pm2 --update-env)');
    }
    
    const baseURL = config.nowpayments.baseUrl || 'https://api.nowpayments.io';
    
    // Log baseURL for debugging (especially to catch double /v1 issues)
    logger.info(`NOWPayments client initialized: baseURL=${baseURL}, apiKey length=${this.apiKey.length}`);

    // API client for x-api-key endpoints (invoice, estimate, etc.)
    this.apiClient = axios.create({
      baseURL,
      headers: {
        'x-api-key': this.apiKey,
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    });

    // JWT client WITHOUT x-api-key (for auth, list payments, payment status)
    this.jwtClient = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    });

    // Add request interceptor to jwtClient for debugging Authorization header
    this.jwtClient.interceptors.request.use((cfg) => {
      const auth = (cfg.headers as any)?.Authorization || (cfg.headers as any)?.authorization;
      const apiKey = (cfg.headers as any)?.['x-api-key'] || (cfg.headers as any)?.['X-Api-Key'];
      
      // CRITICAL: Log at INFO level to see in production logs
      logger.info(`[JWT REQ] ${cfg.method?.toUpperCase()} ${cfg.baseURL}${cfg.url}`);
      logger.info(`[JWT REQ] Authorization header: ${auth ? auth.toString().slice(0, 40) + '...' : 'MISSING/NONE'}`);
      logger.info(`[JWT REQ] x-api-key header: ${apiKey ? 'PRESENT (SHOULD NOT BE!)' : 'NOT PRESENT (correct)'}`);
      
      // CRITICAL: Ensure x-api-key is NOT present in JWT requests
      if (apiKey) {
        logger.error(`[JWT REQ] ERROR: x-api-key header found in JWT request! This will cause conflicts.`);
        delete (cfg.headers as any)['x-api-key'];
        delete (cfg.headers as any)['X-Api-Key'];
      }
      
      return cfg;
    });
  }

  /**
   * Get JWT token for authenticated requests
   * JWT token expires in 5 minutes, so we cache it and refresh when needed
   * Requires NOWPAYMENTS_EMAIL and NOWPAYMENTS_PASSWORD from .env
   */
  private async getJwtToken(): Promise<string> {
    // Check if we have a valid cached token
    const now = Date.now();
    if (this.jwtToken && this.jwtTokenExpiry > now + 60000) { // Refresh 1 minute before expiry
      return this.jwtToken;
    }

    const email = config.nowpayments.email;
    const password = config.nowpayments.password;

    if (!email || !password) {
      throw new Error('NOWPAYMENTS_EMAIL and NOWPAYMENTS_PASSWORD are required for JWT authentication. Check your .env file.');
    }

    try {
      // POST /v1/auth - get JWT token using email + password
      // Use jwtClient (NO x-api-key header)
      const response = await this.jwtClient.post<{ token: string }>('/v1/auth', {
        email,
        password,
      });

      if (!response.data?.token) {
        throw new Error('JWT token not received from NOWPayments API');
      }

      this.jwtToken = response.data.token;
      // JWT expires in 5 minutes, set expiry to 4.5 minutes to be safe
      this.jwtTokenExpiry = now + (4.5 * 60 * 1000);

      logger.debug(`Obtained JWT token from NOWPayments (expires in ~4.5 minutes)`);
      return this.jwtToken;
    } catch (error: any) {
      logger.error(`Failed to get JWT token: ${error.message}`);
      if (error.response?.data) {
        logger.error(`NOWPayments API error: ${JSON.stringify(error.response.data)}`);
      }
      throw error;
    }
  }

  /**
   * Create a payment
   */
  async createPayment(request: NowPaymentsCreatePaymentRequest): Promise<NowPaymentsPayment> {
    try {
      const response = await this.apiClient.post<NowPaymentsPayment>('/v1/payment', request);
      logger.info(`NOWPayments payment created: payment_id=${response.data.payment_id}, order_id=${request.order_id}`);
      return response.data;
    } catch (error: any) {
      logger.error(`Failed to create NOWPayments payment: ${error.message}`);
      if (error.response?.data) {
        logger.error(`NOWPayments API error: ${JSON.stringify(error.response.data)}`);
      }
      throw error;
    }
  }

  /**
   * Get estimate for currency conversion
   */
  async getEstimate(amount: number, currencyFrom: string, currencyTo: string): Promise<NowPaymentsEstimate> {
    try {
      const response = await this.apiClient.get<NowPaymentsEstimate>('/v1/estimate', {
        params: {
          amount: amount,
          currency_from: currencyFrom,
          currency_to: currencyTo,
        },
      });
      logger.info(`NOWPayments estimate: ${amount} ${currencyFrom} = ${response.data.amount_to} ${currencyTo}`);
      return response.data;
    } catch (error: any) {
      logger.error(`Failed to get NOWPayments estimate: ${error.message}`);
      if (error.response?.data) {
        logger.error(`NOWPayments API error: ${JSON.stringify(error.response.data)}`);
      }
      throw error;
    }
  }

  /**
   * Get payment status by payment_id
   * According to NOWPayments docs, this endpoint also requires JWT authentication
   */
  async getPaymentStatus(paymentId: string): Promise<NowPaymentsPayment> {
    try {
      // Get JWT token for authenticated request
      const jwtToken = await this.getJwtToken();
      
      // CRITICAL: Validate JWT token before making request
      if (!jwtToken || jwtToken.trim().length === 0) {
        throw new Error(`JWT token is empty! Cannot get payment status.`);
      }
      
      const authHeader = `Bearer ${jwtToken}`;
      logger.info(`[CRITICAL] Making GET /v1/payment/${paymentId} request with JWT, token length=${jwtToken.length}`);
      
      // IMPORTANT: GET /v1/payment/{id} may require BOTH x-api-key AND Authorization header
      // Try with both headers
      const requestHeaders: any = {
        'Authorization': authHeader,
        'x-api-key': this.apiKey,  // API key may also be required
      };
      
      logger.info(`[CRITICAL] About to make getPaymentStatus request with headers: Authorization=${authHeader.substring(0, 30)}..., x-api-key=${this.apiKey.substring(0, 10)}...`);
      
      // Use apiClient (which has x-api-key) but add Authorization header
      const response = await this.apiClient.get<NowPaymentsPayment>(`/v1/payment/${paymentId}`, {
        headers: requestHeaders,
      });
      
      logger.debug(`NOWPayments payment status: payment_id=${paymentId}, status=${response.data.payment_status}`);
      return response.data;
    } catch (error: any) {
      logger.error(`Failed to get NOWPayments payment status: ${error.message}`);
      if (error.response?.data) {
        logger.error(`NOWPayments API error: ${JSON.stringify(error.response.data)}`);
      }
      if (error.response?.status === 401 || error.response?.status === 403) {
        // JWT might have expired, clear cache and retry once
        logger.warn(`JWT token expired for getPaymentStatus, clearing cache`);
        this.jwtToken = null;
        this.jwtTokenExpiry = 0;
        
        // Retry once with fresh token
        const newJwtToken = await this.getJwtToken();
        const retryAuthHeader = `Bearer ${newJwtToken}`;
        logger.info(`Retrying GET /v1/payment/${paymentId} with fresh JWT token`);
        
        // CRITICAL: Use both x-api-key AND Authorization
        const retryHeaders: any = {
          'Authorization': retryAuthHeader,
          'x-api-key': this.apiKey,
        };
        
        const retryResponse = await this.apiClient.get<NowPaymentsPayment>(`/v1/payment/${paymentId}`, {
          headers: retryHeaders,
        });
        
        logger.debug(`NOWPayments payment status (retry): payment_id=${paymentId}, status=${retryResponse.data.payment_status}`);
        return retryResponse.data;
      }
      throw error;
    }
  }

  /**
   * Find payment by order_id using GET /v1/payment endpoint
   * Requires JWT token authentication
   */
  async findPaymentByOrderId(orderId: string): Promise<NowPaymentsPayment | null> {
    try {
      // Get JWT token for authenticated request
      const jwtToken = await this.getJwtToken();

      // GET /v1/payment with pagination to find payment by order_id
      // According to NOWPayments docs, we need to paginate through results
      // Page may be 0-based, so start from 0
      let page = 0;
      const limit = 100; // Increased limit for better coverage
      const maxPages = 30; // Increased max pages (payment might be on later pages)

      // Helper function to try list payments with different auth header formats
      const tryListPayments = async (authHeader: string, pageNum: number): Promise<any> => {
        // CRITICAL: Validate authHeader before making request
        if (!authHeader || authHeader.trim().length === 0) {
          throw new Error(`Authorization header is empty! Cannot make request.`);
        }
        
        // CRITICAL: Log exactly what we're sending
        const authHeaderPrefix = authHeader.substring(0, Math.min(30, authHeader.length));
        const willSendAuthHeader = Boolean(authHeader && authHeader.length > 0);
        const hasBearerPrefix = authHeader.startsWith('Bearer ');
        logger.debug(`[CRITICAL] Making GET /v1/payment request: page=${pageNum}, limit=${limit}`);
        logger.debug(`[CRITICAL] willSendAuthHeader=${willSendAuthHeader}, authHeader length=${authHeader.length}, hasBearerPrefix=${hasBearerPrefix}, authHeader starts with="${authHeaderPrefix}..."`);
        
        // IMPORTANT: GET /v1/payment may require BOTH x-api-key AND Authorization header
        // Try with both headers first
        const requestHeaders: any = {
          'Authorization': authHeader,  // Bearer token or plain token
          'x-api-key': this.apiKey,     // API key may also be required
        };
        
        logger.debug(`[CRITICAL] About to make request with headers: Authorization=${authHeader.substring(0, 30)}..., x-api-key=${this.apiKey.substring(0, 10)}...`);
        
        // Use apiClient (which has x-api-key) but add Authorization header
        const response = await this.apiClient.get<any>('/v1/payment', {
          params: {
            limit,
            page: pageNum,
            sortBy: 'created_at',  // Field to sort by (as per NOWPayments docs)
            orderBy: 'desc',       // Sort direction: 'asc' or 'desc' (lowercase, as per NOWPayments docs)
          },
          headers: requestHeaders,
        });
        
        logger.debug(`[CRITICAL] Request completed successfully for page ${pageNum}`);
        return response;
      };

      while (page < maxPages) {
        try {
          let response: any;
          
          // Try with Bearer token first
          try {
            response = await tryListPayments(`Bearer ${jwtToken}`, page);
          } catch (bearerError: any) {
            // Log detailed error for debugging
            if (bearerError.response?.data) {
              logger.debug(`Bearer format error for page ${page}: ${JSON.stringify(bearerError.response.data)}`);
            }
            if (bearerError.response?.status) {
              logger.debug(`Bearer format status for page ${page}: ${bearerError.response.status}`);
            }
            
            // If 400/401 with Bearer, try without Bearer prefix
            if (bearerError.response?.status === 400 || bearerError.response?.status === 401) {
              logger.debug(`Bearer format failed, trying token without Bearer prefix for page ${page}`);
              try {
                response = await tryListPayments(jwtToken, page);
              } catch (noBearerError: any) {
                // If still 401, JWT might be invalid or expired
                if (noBearerError.response?.status === 401 || noBearerError.response?.status === 403) {
                  logger.warn(`Both Bearer and non-Bearer formats failed with 401/403, JWT token may be invalid`);
                  throw noBearerError; // Will be caught by outer catch and trigger JWT refresh
                }
                throw noBearerError;
              }
            } else {
              throw bearerError;
            }
          }

          // Response can be array directly or object with data property
          let payments: NowPaymentsPayment[] = [];
          if (Array.isArray(response.data)) {
            payments = response.data;
          } else if (response.data?.data && Array.isArray(response.data.data)) {
            payments = response.data.data;
          } else if (response.data?.payments && Array.isArray(response.data.payments)) {
            payments = response.data.payments;
          }
          
          logger.debug(`Page ${page}: found ${payments.length} payments`);
          
          // Search for payment with matching order_id
          const foundPayment = payments.find((p) => p.order_id === orderId);
          
          if (foundPayment) {
            logger.info(`Found payment by order_id: payment_id=${foundPayment.payment_id}, order_id=${orderId}, status=${foundPayment.payment_status}`);
            return foundPayment;
          }

          // If no more pages, stop searching
          if (!payments || payments.length === 0) {
            logger.debug(`No more payments on page ${page}, stopping search`);
            break;
          }

          page++;
        } catch (pageError: any) {
          // Log detailed error before retry
          logger.debug(`Page ${page} error: ${pageError.message}`);
          if (pageError.response?.data) {
            logger.debug(`Page ${page} error data: ${JSON.stringify(pageError.response.data)}`);
          }
          if (pageError.response?.status) {
            logger.debug(`Page ${page} error status: ${pageError.response.status}`);
          }
          
          // If 401/403, JWT might have expired, try to refresh
          if (pageError.response?.status === 401 || pageError.response?.status === 403) {
            logger.warn(`JWT token expired or invalid (status ${pageError.response?.status}), refreshing...`);
            this.jwtToken = null; // Clear cached token
            this.jwtTokenExpiry = 0; // Clear expiry
            
            try {
              const newJwtToken = await this.getJwtToken();
              logger.info(`JWT token refreshed successfully, token length=${newJwtToken.length}`);
              
              // Retry current page with new token (try both formats)
              let retryResponse: any;
              try {
                logger.debug(`Retrying page ${page} with Bearer token format`);
                retryResponse = await tryListPayments(`Bearer ${newJwtToken}`, page);
              } catch (bearerRetryError: any) {
                logger.debug(`Bearer format failed on retry for page ${page}, status=${bearerRetryError.response?.status}`);
                if (bearerRetryError.response?.data) {
                  logger.debug(`Bearer retry error data: ${JSON.stringify(bearerRetryError.response.data)}`);
                }
                
                if (bearerRetryError.response?.status === 400 || bearerRetryError.response?.status === 401) {
                  logger.debug(`Trying token without Bearer prefix for page ${page}`);
                  retryResponse = await tryListPayments(newJwtToken, page);
                } else {
                  throw bearerRetryError;
                }
              }

              // Response can be array directly or object with data property
              let payments: NowPaymentsPayment[] = [];
              if (Array.isArray(retryResponse.data)) {
                payments = retryResponse.data;
              } else if (retryResponse.data?.data && Array.isArray(retryResponse.data.data)) {
                payments = retryResponse.data.data;
              } else if (retryResponse.data?.payments && Array.isArray(retryResponse.data.payments)) {
                payments = retryResponse.data.payments;
              }
              
              const foundPayment = payments.find((p) => p.order_id === orderId);
              
              if (foundPayment) {
                logger.info(`Found payment by order_id (after JWT refresh): payment_id=${foundPayment.payment_id}, order_id=${orderId}, status=${foundPayment.payment_status}`);
                return foundPayment;
              }

              if (!payments || payments.length === 0) {
                break;
              }
              
              // Continue to next page after successful retry
              page++;
            } catch (retryError: any) {
              logger.error(`Failed to retry payment search after JWT refresh: ${retryError.message}`);
              if (retryError.response?.data) {
                logger.error(`NOWPayments API error (retry): ${JSON.stringify(retryError.response.data)}`);
              }
              if (retryError.response?.status) {
                logger.error(`NOWPayments status (retry): ${retryError.response.status}`);
              }
              break;
            }
          } else {
            // Detailed error logging
            logger.error(`Failed to search payments page ${page}: ${pageError.message}`);
            if (pageError.response?.data) {
              logger.error(`NOWPayments API error (list payments): ${JSON.stringify(pageError.response.data)}`);
            }
            if (pageError.response?.status) {
              logger.error(`NOWPayments status: ${pageError.response.status}`);
            }
            break;
          }
        }
      }

      logger.debug(`Payment not found by order_id ${orderId} after searching ${page} pages`);
      return null;
    } catch (error: any) {
      logger.error(`Failed to find payment by order_id ${orderId}: ${error.message}`);
      if (error.response?.data) {
        logger.error(`NOWPayments API error: ${JSON.stringify(error.response.data)}`);
      }
      if (error.response?.status) {
        logger.error(`NOWPayments status: ${error.response.status}`);
      }
      return null;
    }
  }

  /**
   * Check if payment status indicates success
   */
  isPaymentSuccessful(status: string): boolean {
    // According to NOWPayments docs, these statuses indicate successful payment
    // Some integrations also mention 'paid' as a success status
    const successStatuses = ['paid', 'finished', 'confirmed', 'sending'];
    return successStatuses.includes(status.toLowerCase());
  }

  /**
   * Check if payment is still pending
   */
  isPaymentPending(status: string): boolean {
    const pendingStatuses = ['waiting', 'confirming', 'partially_paid'];
    return pendingStatuses.includes(status.toLowerCase());
  }

  /**
   * Check if payment failed
   */
  isPaymentFailed(status: string): boolean {
    const failedStatuses = ['failed', 'expired', 'refunded'];
    return failedStatuses.includes(status.toLowerCase());
  }

  /**
   * Normalize invoice response - NOWPayments may return id, iid, or invoice_id
   * According to NOWPayments docs, invoice_id may be in different fields
   */
  private normalizeInvoiceResponse(data: any): NowPaymentsInvoice {
    // NOWPayments API may return:
    // - invoice_id (standard)
    // - id (alternative)
    // - iid (in payment URL: https://nowpayments.io/payment?iid=...)
    // Check all possible fields
    const invoice_id = data.invoice_id ?? data.id ?? data.iid ?? data.invoiceId;
    
    if (!invoice_id) {
      logger.error(`NOWPayments invoice response missing invoice_id. Full response: ${JSON.stringify(data)}`);
      logger.error(`Available fields: ${Object.keys(data).join(', ')}`);
      throw new Error('Failed to normalize invoice: invoice_id missing in response');
    }

    return {
      ...data,
      invoice_id, // Ensure invoice_id is always present with correct value
    };
  }

  /**
   * Create an invoice
   */
  async createInvoice(request: NowPaymentsCreateInvoiceRequest): Promise<NowPaymentsInvoice> {
    try {
      const response = await this.apiClient.post<any>('/v1/invoice', request);
      
      // Log full response for debugging
      logger.info(`NOWPayments createInvoice raw response: ${JSON.stringify(response.data)}`);
      
      // Normalize response to ensure invoice_id is present
      const normalized = this.normalizeInvoiceResponse(response.data);
      
      logger.info(`NOWPayments invoice created: invoice_id=${normalized.invoice_id}, order_id=${request.order_id}`);
      return normalized;
    } catch (error: any) {
      logger.error(`Failed to create NOWPayments invoice: ${error.message}`);
      if (error.response?.data) {
        logger.error(`NOWPayments API error: ${JSON.stringify(error.response.data)}`);
      }
      throw error;
    }
  }

  /**
   * Get invoice status by invoice_id
   * Makes real API request to GET /v1/invoice/{invoice_id}
   * Returns invoice with payment_status and payment_id (if payment was created)
   * 
   * NOTE: This endpoint may return 404 if it's not available in NOWPayments API.
   * In that case, throws an error - caller should use fallback approach (check payment via payment_id).
   */
  async getInvoiceStatus(invoiceId: string): Promise<NowPaymentsInvoice> {
    // CRITICAL: Validate invoiceId before making request
    if (!invoiceId || invoiceId === 'undefined' || invoiceId.trim().length === 0) {
      logger.error(`Invalid invoice_id provided: "${invoiceId}" (type: ${typeof invoiceId})`);
      throw new Error(`Invalid invoice_id: ${invoiceId}`);
    }

    try {
      const fullUrl = `${this.apiClient.defaults.baseURL}/v1/invoice/${invoiceId}`;
      logger.debug(`Getting invoice status: ${fullUrl}`);
      
      const response = await this.apiClient.get<any>(`/v1/invoice/${invoiceId}`);
      
      // Normalize response to ensure invoice_id is present
      const normalized = this.normalizeInvoiceResponse(response.data);
      
      logger.info(`NOWPayments invoice status: invoice_id=${normalized.invoice_id}, payment_id=${normalized.payment_id || 'not yet'}, payment_status=${normalized.payment_status || 'not paid'}`);
      
      return normalized;
    } catch (error: any) {
      // If endpoint returns 404, this endpoint is not available in NOWPayments API
      // We throw a specific error that caller can catch and use fallback
      if (error.response?.status === 404) {
        logger.warn(`Invoice GET endpoint returns 404: invoice_id=${invoiceId} (endpoint not available in NOWPayments API)`);
        const notFoundError: any = new Error(`Invoice endpoint not available (404)`);
        notFoundError.is404 = true;
        notFoundError.invoiceId = invoiceId;
        throw notFoundError;
      }
      
      logger.error(`Failed to get NOWPayments invoice status: ${error.message}`);
      if (error.response?.data) {
        logger.error(`NOWPayments API error: ${JSON.stringify(error.response.data)}`);
      }
      
      throw error;
    }
  }

  /**
   * Check if invoice payment status indicates success
   * Uses invoice.payment_status field
   */
  isPaymentPaid(status: string | undefined): boolean {
    if (!status) return false;
    // According to NOWPayments docs, these statuses indicate successful payment
    // Some integrations also mention 'paid' as a success status
    const successStatuses = ['paid', 'finished', 'confirmed', 'sending'];
    return successStatuses.includes(status.toLowerCase());
  }
}

export const nowPaymentsClient = new NowPaymentsClient();

