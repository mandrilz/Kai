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

interface ChatProps {
  chatId: string
}

export default function Chat({ chatId }: ChatProps) {
  const [messages, setMessages] = useState<MessageData[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Загружаем историю сообщений при монтировании
  useEffect(() => {
    loadChatHistory()
  }, [chatId])

  const loadChatHistory = async () => {
    setIsLoadingHistory(true)
    try {
      const response = await fetch(`/api/chats/${chatId}`, {
        credentials: 'include',
      })

      if (response.ok) {
        const contentType = response.headers.get('content-type') || ''
        if (!contentType.includes('application/json')) {
          console.error('Ожидался JSON, получен:', contentType)
          const text = await response.text()
          console.error('Ответ был:', text.substring(0, 200))
          throw new Error('Некорректный формат ответа от сервера')
        }
        
        // Безопасно читаем JSON
        const responseText = await response.text()
        let data: any
        try {
          data = JSON.parse(responseText)
        } catch (e) {
          console.error('Ошибка парсинга JSON истории чата:', e)
          console.error('Ответ был:', responseText.substring(0, 200))
          throw new Error('Некорректный JSON ответ от сервера')
        }
        // Преобразуем сообщения из API в формат MessageData
        const loadedMessages: MessageData[] = data.messages.map((msg: any) => {
          let attachments = undefined
          if (msg.attachments) {
            try {
              // Если attachments уже объект, используем его; если строка - парсим
              attachments = typeof msg.attachments === 'string' 
                ? JSON.parse(msg.attachments) 
                : msg.attachments
            } catch (e) {
              console.error('Ошибка парсинга attachments:', e, msg.attachments)
              attachments = undefined
            }
          }
          
          return {
            id: msg.id,
            role: msg.role,
            content: msg.content,
            attachments,
          }
        })
        
        // Если нет сообщений, добавляем приветственное
        if (loadedMessages.length === 0) {
          loadedMessages.push({
            id: uuidv4(),
            role: 'assistant',
            content: 'Привет! Я Кометтик — инженер-помощник Кометта. Помогу с подбором насосов и поиском аналогов. Задайте вопрос!',
          })
        }
        
        setMessages(loadedMessages)
      } else if (response.status === 401) {
        // Не авторизован
        window.location.href = '/login'
      } else if (response.status === 403) {
        // Чат не принадлежит пользователю - создаем новый чат автоматически
        console.warn('Чат не принадлежит текущему пользователю, создаем новый чат')
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
    } catch (error) {
      console.error('Ошибка загрузки истории:', error)
    } finally {
      setIsLoadingHistory(false)
    }
  }

  const handleSend = async (message: string, attachments: Array<{ filename: string; content_type: string; base64: string }>) => {
    setIsLoading(true)

    // Добавляем сообщение пользователя сразу для правильного порядка отображения
    const userMessageId = uuidv4()
    const userMessage: MessageData = {
      id: userMessageId,
      role: 'user',
      content: message.trim(),
      attachments: attachments.length > 0 ? attachments : undefined,
    }
    setMessages(prev => [...prev, userMessage])

    // Создаём сообщение ассистента для потокового ответа
    const assistantMessageId = uuidv4()
    const assistantMessage: MessageData = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
    }
    setMessages(prev => [...prev, assistantMessage])

    try {
      const apiEndpoint = `/api/chats/${chatId}/messages`
      
      console.log('Отправка запроса на:', apiEndpoint)
      
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          message: message,
          attachments: attachments,
        }),
      })

      if (!response.ok) {
        if (response.status === 401) {
          window.location.href = '/login'
          return
        }
        if (response.status === 403) {
          // Чат не принадлежит пользователю - создаем новый чат автоматически
          console.warn('Чат не принадлежит текущему пользователю, создаем новый чат')
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
          return
        }
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
            const data = line.slice(6).trim()
            if (!data || data === '[DONE]') continue

            try {
              const parsed = JSON.parse(data)
              if (parsed.type === 'token' && parsed.content) {
                setMessages(prev =>
                  prev.map(msg =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: msg.content + parsed.content }
                      : msg
                  )
                )
              } else if (parsed.type === 'error') {
                console.error('[SSE] Ошибка от сервера:', parsed.message || parsed.error)
                setIsLoading(false)
              }
            } catch (e) {
              // Логируем ошибки парсинга для отладки, но продолжаем работу
              if (data && data.length > 0 && data !== '[DONE]') {
                console.warn('[SSE] Не удалось распарсить JSON:', data.substring(0, 100), e)
              }
            }
          }
        }
      }
      
      // После завершения потока перезагружаем историю, чтобы получить сохраненные сообщения с сервера
      // Удаляем временные сообщения (пользователя и ассистента) перед загрузкой, чтобы избежать дублирования
      setMessages(prev => prev.filter(msg => msg.id !== userMessageId && msg.id !== assistantMessageId))
      await loadChatHistory()
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

  if (isLoadingHistory) {
    return (
      <div className="h-full w-full flex items-center justify-center bg-[#1D1D1D]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#E49E00] mx-auto mb-4"></div>
          <p className="text-[#B5B5B5]">Загрузка чата...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full w-full flex flex-col bg-[#1D1D1D]">
      {/* Зона сообщений - единое окно без границ */}
      <div className="flex-1 overflow-y-auto" style={{ minHeight: 0 }}>
        <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
          {messages.length > 0 ? (
            messages.map((message) => (
              <Message key={message.id} message={message} />
            ))
          ) : (
            <div className="text-center text-[#B5B5B5] py-8">
              Нет сообщений
            </div>
          )}
          {isLoading && (
            <div className="flex items-center space-x-2 text-[#B5B5B5]">
              <div className="w-2 h-2 bg-[#E49E00] rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-[#E49E00] rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              <div className="w-2 h-2 bg-[#E49E00] rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>
      
      {/* Поле ввода внизу */}
      <div className="flex-shrink-0 border-t border-[#3A3A3A] bg-[#1D1D1D] min-h-[88px]">
        <div className="max-w-3xl mx-auto">
          <Composer onSend={handleSend} isLoading={isLoading} />
        </div>
      </div>
    </div>
  )
}
