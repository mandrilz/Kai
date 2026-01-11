'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMessage('')

    try {
      // Используем относительный путь (nginx проксирует /api/ на backend)
      // ВЕРСИЯ КОДА: 2024-12-20-fix-api-url
      const endpoint = '/api/auth/magic-link'
      
      console.log('[LOGIN] Версия кода: 2024-12-20-fix-api-url')
      console.log('[LOGIN] Отправка запроса на:', endpoint)
      console.log('[LOGIN] Полный URL будет:', window.location.origin + endpoint)
      console.log('[LOGIN] Email:', email)
      
      // Проверяем, что email валиден перед отправкой
      if (!email || !email.includes('@')) {
        throw new Error('Невалидный email адрес')
      }
      
      const requestBody = { email }
      console.log('[LOGIN] Тело запроса:', requestBody)
      
      try {
        const requestBodyString = JSON.stringify(requestBody)
        console.log('[LOGIN] JSON.stringify успешно, длина:', requestBodyString.length)
      } catch (e) {
        console.error('[LOGIN] Ошибка JSON.stringify:', e)
        throw new Error('Ошибка подготовки данных для отправки')
      }
      
      console.log('[LOGIN] Вызываем fetch...')
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include', // Важно для cookie
        body: JSON.stringify(requestBody),
      })
      console.log('[LOGIN] fetch завершен, получен response объект')

      console.log('[LOGIN] Ответ получен:', response.status, response.statusText)
      
      const contentType = response.headers.get('content-type') || ''
      console.log('[LOGIN] Content-Type:', contentType)

      // ВАЖНО: читаем ответ ТОЛЬКО один раз
      // Сначала читаем как текст, чтобы не потерять данные
      const responseText = await response.text()
      console.log('[LOGIN] Получен ответ (первые 500 символов):', responseText.substring(0, 500))

      let responseData: any = null

      // Пытаемся распарсить как JSON только если Content-Type указывает на JSON
      if (contentType.includes('application/json') || responseText.trim().startsWith('{') || responseText.trim().startsWith('[')) {
        try {
          responseData = JSON.parse(responseText)
          console.log('[LOGIN] JSON успешно распарсен:', responseData)
        } catch (e) {
          console.error('[LOGIN] Ошибка парсинга JSON (ответ не является валидным JSON):', e)
          console.error('[LOGIN] Ответ был:', responseText.substring(0, 200))
          // Если это HTML (например, страница 404), не пытаемся парсить дальше
          if (responseText.trim().startsWith('<!DOCTYPE') || responseText.trim().startsWith('<html')) {
            console.error('[LOGIN] Сервер вернул HTML вместо JSON - возможно, неправильный URL или ошибка nginx')
          }
          responseData = null
        }
      }

      if (!response.ok) {
        // Ошибка от сервера
        let errorDetail = `Ошибка ${response.status}: ${response.statusText}`
        
        if (responseData) {
          errorDetail = responseData.detail || responseData.message || errorDetail
        } else if (responseText) {
          // Если ответ HTML, извлекаем только текст ошибки (не весь HTML)
          if (responseText.includes('<title>')) {
            const titleMatch = responseText.match(/<title>(.*?)<\/title>/i)
            errorDetail = titleMatch ? `Ошибка ${response.status}: ${titleMatch[1]}` : errorDetail
          } else {
            errorDetail = `Ошибка ${response.status}: ${responseText.substring(0, 200)}`
          }
        }
        
        console.error('[LOGIN] Ошибка API:', response.status, errorDetail)
        setMessage(errorDetail)
        return
      }

      // Успешный ответ
      if (responseData) {
        console.log('[LOGIN] Успешно:', responseData)
        setMessage(responseData.message || 'Ссылка для входа отправлена на ваш email. Проверьте почту.')
      } else {
        console.log('[LOGIN] Успешно (текст):', responseText.substring(0, 100))
        setMessage('Ссылка для входа отправлена на ваш email. Проверьте почту.')
      }
    } catch (error) {
      // Детальное логирование ошибки
      console.error('[LOGIN] ========== ОШИБКА ==========')
      console.error('[LOGIN] Тип ошибки:', error instanceof Error ? error.constructor.name : typeof error)
      console.error('[LOGIN] Сообщение ошибки:', error instanceof Error ? error.message : String(error))
      console.error('[LOGIN] Полный объект ошибки:', error)
      
      if (error instanceof TypeError && error.message.includes('fetch')) {
        console.error('[LOGIN] Ошибка сети или CORS. Проверьте:')
        console.error('[LOGIN] - Доступен ли сервер?')
        console.error('[LOGIN] - Правильно ли настроен nginx?')
        console.error('[LOGIN] - Нет ли блокировок в браузере?')
        setMessage('Ошибка сети. Проверьте консоль браузера (F12) для подробностей.')
      } else if (error instanceof SyntaxError) {
        console.error('[LOGIN] Ошибка парсинга (синтаксическая ошибка)')
        setMessage('Ошибка обработки ответа от сервера. Проверьте консоль браузера (F12).')
      } else {
        const errorMessage = error instanceof Error ? error.message : 'Неизвестная ошибка'
        setMessage(`Произошла ошибка: ${errorMessage}. Проверьте консоль браузера (F12) для подробностей.`)
      }
      
      console.error('[LOGIN] ============================')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-white">
      <div className="max-w-md w-full px-6 py-8 bg-white rounded-lg shadow-lg">
        <h1 className="text-2xl font-bold text-center mb-6 text-[#0066CC]">
          Вход в K.ai (Кометтик)
        </h1>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
              Email
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#0066CC] focus:border-transparent"
              placeholder="your@email.com"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#0066CC] text-white py-2 px-4 rounded-lg hover:bg-[#0052A3] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Отправка...' : 'Отправить ссылку для входа'}
          </button>
        </form>

        {message && (
          <div className={`mt-4 p-3 rounded-lg ${
            message.includes('ошибка') 
              ? 'bg-red-50 text-red-700' 
              : 'bg-green-50 text-green-700'
          }`}>
            {message}
          </div>
        )}
      </div>
    </div>
  )
}
