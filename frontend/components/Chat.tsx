'use client'

import { useState, useRef, useEffect } from 'react'
import Message from './Message'
import Composer from './Composer'
import { v4 as uuidv4 } from 'uuid'

export interface MessageData {
  id: string
  role: 'user' | 'assistant'
  content: string
  attachments?: Array<{
    filename: string
    content_type: string
  }>
}

export default function Chat() {
  const [messages, setMessages] = useState<MessageData[]>([
    {
      id: uuidv4(),
      role: 'assistant',
      content: 'Привет! Я Кометтик — инженер-помощник Кометта. Помогу с подбором насосов и поиском аналогов. Задайте вопрос!',
    },
  ])
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async (message: string, attachments: Array<{ filename: string; content_type: string; base64: string }>) => {
    // Добавляем сообщение пользователя
    const userMessage: MessageData = {
      id: uuidv4(),
      role: 'user',
      content: message,
      attachments: attachments.map(att => ({
        filename: att.filename,
        content_type: att.content_type,
      })),
    }

    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)

    // Создаём сообщение ассистента для потокового ответа
    const assistantMessageId = uuidv4()
    const assistantMessage: MessageData = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
    }
    setMessages(prev => [...prev, assistantMessage])

    try {
      const sessionId = localStorage.getItem('session_id') || uuidv4()
      localStorage.setItem('session_id', sessionId)

      // Используем относительный путь для production (nginx проксирует /api/ на backend)
      // Для локальной разработки можно использовать NEXT_PUBLIC_API_URL
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
      const apiEndpoint = `${apiUrl}/api/chat`
      
      console.log('Отправка запроса на:', apiEndpoint)
      
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: message,
          attachments: attachments,
        }),
      })

      if (!response.ok) {
        const errorText = await response.text()
        console.error('Ошибка API:', response.status, errorText)
        throw new Error(`Ошибка при отправке сообщения: ${response.status} ${errorText}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('Не удалось получить поток данных')
      }

      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()

        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') continue

            try {
              const parsed = JSON.parse(data)
              if (parsed.type === 'token') {
                setMessages(prev =>
                  prev.map(msg =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: msg.content + parsed.content }
                      : msg
                  )
                )
              }
            } catch (e) {
              // Игнорируем ошибки парсинга
            }
          }
        }
      }
    } catch (error) {
      console.error('Ошибка при отправке сообщения:', error)
      const errorMessage = error instanceof Error ? error.message : 'Неизвестная ошибка'
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessageId
            ? { ...msg, content: `Произошла ошибка при обработке запроса: ${errorMessage}. Проверьте консоль браузера (F12) для подробностей.` }
            : msg
        )
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="h-full w-full flex flex-col bg-white" style={{ height: '100vh', width: '100vw' }}>
      {/* Зона сообщений - единое окно без границ */}
      <div className="flex-1 overflow-y-auto" style={{ minHeight: 0 }}>
        <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
          {messages.length > 0 ? (
            messages.map((message) => (
              <Message key={message.id} message={message} />
            ))
          ) : (
            <div className="text-center text-[#666666] py-8">
              Нет сообщений
            </div>
          )}
          {isLoading && (
            <div className="flex items-center space-x-2 text-[#666666]">
              <div className="w-2 h-2 bg-[#0066CC] rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-[#0066CC] rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              <div className="w-2 h-2 bg-[#0066CC] rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>
      
      {/* Поле ввода внизу */}
      <div className="flex-shrink-0 border-t border-[#E0E0E0] bg-white">
        <div className="max-w-3xl mx-auto">
          <Composer onSend={handleSend} isLoading={isLoading} />
        </div>
      </div>
    </div>
  )
}

