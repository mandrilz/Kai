/**
 * Утилиты для работы с API
 */

/**
 * Обрабатывает ошибки HTTP запросов
 */
export function handleApiError(response: Response): void {
  if (response.status === 401) {
    // Не авторизован - редирект на логин
    window.location.href = '/login'
    return
  }
  
  if (response.status === 403) {
    // Чат не принадлежит пользователю - создаем новый чат автоматически
    console.warn('Чат не принадлежит текущему пользователю, создаем новый чат')
    createNewChatAndRedirect()
    return
  }
}

/**
 * Создает новый чат и перенаправляет на него
 */
export async function createNewChatAndRedirect(): Promise<void> {
  try {
    const createResponse = await fetch('/api/chats', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({}),
    })
    
    if (createResponse.ok) {
      const newChat = await createResponse.json()
      window.location.href = `/?chat=${newChat.id}`
    } else {
      window.location.href = '/'
    }
  } catch (e) {
    console.error('Ошибка при создании нового чата:', e)
    window.location.href = '/'
  }
}

/**
 * Выполняет запрос с повторными попытками
 * @param url URL для запроса
 * @param options Опции запроса (включая signal для AbortController)
 * @param maxRetries Максимальное количество попыток (по умолчанию 3)
 * @param retryDelay Базовая задержка между попытками в мс (по умолчанию 1000)
 * @returns Promise с Response
 */
export async function fetchWithRetry(
  url: string,
  options: RequestInit,
  maxRetries: number = 3,
  retryDelay: number = 1000
): Promise<Response> {
  let lastError: Error | null = null
  
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      // Проверяем, не был ли запрос отменен перед попыткой
      if (options.signal && (options.signal as AbortSignal).aborted) {
        throw new DOMException('Request aborted', 'AbortError')
      }
      
      const response = await fetch(url, options)
      
      // Если успешный ответ или ошибка, которую не нужно повторять
      if (response.ok || response.status === 401 || response.status === 403) {
        return response
      }
      
      // Для других ошибок пробуем повторить
      if (attempt < maxRetries - 1) {
        // Экспоненциальная задержка: 1s, 2s, 3s...
        const delay = retryDelay * (attempt + 1)
        await new Promise(resolve => setTimeout(resolve, delay))
        continue
      }
      
      return response
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error))
      
      // Если это AbortError, не повторяем
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw error
      }
      
      // Проверяем, не был ли запрос отменен во время задержки
      if (options.signal && (options.signal as AbortSignal).aborted) {
        throw new DOMException('Request aborted', 'AbortError')
      }
      
      // Для сетевых ошибок пробуем повторить
      if (attempt < maxRetries - 1) {
        // Экспоненциальная задержка: 1s, 2s, 3s...
        const delay = retryDelay * (attempt + 1)
        await new Promise(resolve => setTimeout(resolve, delay))
        continue
      }
    }
  }
  
  throw lastError || new Error('Failed to fetch after retries')
}
