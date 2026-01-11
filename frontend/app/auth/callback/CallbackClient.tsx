'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

export default function CallbackClient() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    const token = searchParams.get('token')

    if (!token) {
      setStatus('error')
      setMessage('Токен не найден в ссылке.')
      return
    }

    const verifyToken = async () => {
      try {
        // Используем относительный путь (nginx проксирует /api/ на backend)
        const endpoint = `/api/auth/verify?token=${encodeURIComponent(token)}`
        
        console.log('[CALLBACK] Проверка токена на:', endpoint)
        
        const response = await fetch(endpoint, {
          method: 'GET',
          credentials: 'include', // Важно для cookie
        })

        console.log('[CALLBACK] Ответ получен:', response.status, response.statusText)
        
        const contentType = response.headers.get('content-type') || ''
        console.log('[CALLBACK] Content-Type:', contentType)

        // ВАЖНО: читаем ответ ТОЛЬКО один раз
        // Сначала читаем как текст, чтобы не потерять данные
        const responseText = await response.text()
        console.log('[CALLBACK] Получен ответ (первые 500 символов):', responseText.substring(0, 500))

        let responseData: any = null

        // Пытаемся распарсить как JSON только если Content-Type указывает на JSON
        if (contentType.includes('application/json') || responseText.trim().startsWith('{') || responseText.trim().startsWith('[')) {
          try {
            responseData = JSON.parse(responseText)
            console.log('[CALLBACK] JSON успешно распарсен:', responseData)
          } catch (e) {
            console.error('[CALLBACK] Ошибка парсинга JSON (ответ не является валидным JSON):', e)
            console.error('[CALLBACK] Ответ был:', responseText.substring(0, 200))
            // Если это HTML (например, страница 404), не пытаемся парсить дальше
            if (responseText.trim().startsWith('<!DOCTYPE') || responseText.trim().startsWith('<html')) {
              console.error('[CALLBACK] Сервер вернул HTML вместо JSON - возможно, неправильный URL или ошибка nginx')
            }
            responseData = null
          }
        }

        if (!response.ok) {
          // Ошибка от сервера
          let errorDetail = 'Невалидный или истекший токен.'
          
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
          } else {
            errorDetail = `Ошибка ${response.status}: ${response.statusText}`
          }
          
          console.error('[CALLBACK] Ошибка проверки токена:', response.status, errorDetail)
          setStatus('error')
          setMessage(errorDetail)
          return
        }

        // Успешный ответ
        if (!responseData) {
          console.error('[CALLBACK] Не удалось распарсить ответ как JSON')
          console.error('[CALLBACK] Ответ был:', responseText.substring(0, 200))
          setStatus('error')
          setMessage('Получен некорректный ответ от сервера. Проверьте консоль для подробностей.')
          return
        }

        console.log('[CALLBACK] Токен проверен успешно, user_id:', responseData.user_id)
        // JWT уже установлен в cookie сервером
        setStatus('success')
        setMessage('Вход выполнен успешно. Перенаправление...')
        
        // Перенаправляем на главную страницу (корень '/')
        // В старой версии код перенаправлял на '/app', но в проекте
        // отсутствует соответствующая страница, что вызывало 404.
        // Теперь перенаправляем на '/': приложение само проверит
        // авторизацию и загрузит чаты.
        setTimeout(() => {
          router.push('/')
        }, 1500)
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Неизвестная ошибка'
        console.error('Ошибка при проверке токена:', error)
        setStatus('error')
        setMessage(`Произошла ошибка при проверке токена: ${errorMessage}. Проверьте консоль браузера (F12) для подробностей.`)
      }
    }

    verifyToken()
  }, [searchParams, router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-white">
      <div className="max-w-md w-full px-6 py-8 bg-white rounded-lg shadow-lg text-center">
        {status === 'loading' && (
          <>
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#0066CC] mx-auto mb-4"></div>
            <p className="text-gray-700">Проверка токена...</p>
          </>
        )}
        
        {status === 'success' && (
          <>
            <div className="text-green-500 text-4xl mb-4">✓</div>
            <p className="text-green-700">{message}</p>
          </>
        )}
        
        {status === 'error' && (
          <>
            <div className="text-red-500 text-4xl mb-4">✗</div>
            <p className="text-red-700 mb-4">{message}</p>
            <button
              onClick={() => router.push('/login')}
              className="text-[#0066CC] hover:underline"
            >
              Вернуться на страницу входа
            </button>
          </>
        )}
      </div>
    </div>
  )
}
