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
  const welcomeMessageShownRef = useRef<boolean>(false) // Флаг для отслеживания показа приветственного сообщения
  const printedMessageIdsRef = useRef<Set<string>>(new Set()) // Отслеживаем, какие сообщения уже были напечатаны

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Универсальная функция для эффекта печати сообщения от assistant
  const printMessageWithEffect = async (message: MessageData) => {
    // Проверяем, не было ли это сообщение уже напечатано
    if (printedMessageIdsRef.current.has(message.id)) {
      return
    }
    
    // Помечаем сразу, чтобы избежать повторной печати
    printedMessageIdsRef.current.add(message.id)
    
    const messageId = uuidv4()
    const tempMessage: MessageData = {
      id: messageId,
      role: message.role,
      content: '',
      attachments: message.attachments,
    }
    
    // Добавляем временное пустое сообщение
    setMessages(prev => [...prev, tempMessage])
    
    // Печатаем по символам
    const fullText = message.content
    let currentContent = ''
    
    for (let i = 0; i < fullText.length; i++) {
      await new Promise(resolve => setTimeout(resolve, 30)) // Задержка между символами (30ms)
      currentContent += fullText[i]
      setMessages(prev =>
        prev.map(msg =>
          msg.id === messageId
            ? { ...msg, content: currentContent }
            : msg
        )
      )
    }
    
    // После завершения печатания заменяем временное сообщение на реальное из БД
    setMessages(prev =>
      prev.map(msg =>
        msg.id === messageId
          ? message
          : msg
      )
    )
  }

  // Загружаем историю сообщений при монтировании
  useEffect(() => {
    // Сбрасываем флаги при смене чата
    welcomeMessageShownRef.current = false
    printedMessageIdsRef.current.clear()
    setMessages([]) // Очищаем сообщения при смене чата
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
        
        // Печатаем ВСЕ сообщения от assistant с эффектом печати
        // Разделяем сообщения на user и assistant
        const userMessages: MessageData[] = []
        const assistantMessages: MessageData[] = []
        
        for (const msg of loadedMessages) {
          if (msg.role === 'assistant') {
            // Все сообщения от assistant должны печататься с эффектом, если они еще не были напечатаны
            if (!printedMessageIdsRef.current.has(msg.id)) {
              assistantMessages.push(msg)
            } else {
              // Если сообщение уже было напечатано, добавляем его в userMessages для отображения
              userMessages.push(msg)
            }
          } else {
            userMessages.push(msg)
          }
        }
        
        // Сначала устанавливаем все сообщения пользователя (и уже напечатанные сообщения assistant)
        if (userMessages.length > 0) {
          setMessages(userMessages)
        } else {
          setMessages([])
        }
        
        // Затем печатаем все новые сообщения от assistant с эффектом
        if (assistantMessages.length > 0) {
          console.log('Найдено сообщений от assistant для печати:', assistantMessages.length)
          // Печатаем сообщения последовательно (одно за другим)
          const printAllAssistantMessages = async () => {
            for (let i = 0; i < assistantMessages.length; i++) {
              const msg = assistantMessages[i]
              console.log('Печатаем сообщение:', msg.id, msg.content.substring(0, 50))
              // Если это первое сообщение и это приветственное, помечаем
              if (i === 0 && isLoadingHistory) {
                welcomeMessageShownRef.current = true
              }
              // Ждем завершения печати предыдущего сообщения перед началом следующего
              await printMessageWithEffect(msg)
            }
          }
          // Запускаем печать асинхронно, не блокируя UI
          // Важно: не используем await, чтобы не блокировать выполнение
          printAllAssistantMessages().catch(error => {
            console.error('Ошибка при печати сообщений:', error)
          })
        } else {
          console.log('Нет новых сообщений от assistant для печати, загружаем все сообщения сразу')
          // Если нет новых сообщений от assistant, просто устанавливаем все сообщения
          setMessages(loadedMessages)
        }
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
                // Помечаем, что сообщение печатается через стриминг
                printedMessageIdsRef.current.add(assistantMessageId)
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
      // Добавляем небольшую задержку, чтобы дать время БД закоммитить транзакцию
      await new Promise(resolve => setTimeout(resolve, 500))
      
      // Загружаем историю - она заменит временные сообщения реальными из БД
      // Сохраняем содержимое временного сообщения ассистента
      const assistantContent = messages.find(m => m.id === assistantMessageId)?.content || ''
      
      // Загружаем историю
      const historyResponse = await fetch(`/api/chats/${chatId}`, {
        credentials: 'include',
      })
      
      if (historyResponse.ok) {
        const historyData = await historyResponse.json()
        const historyMessages: MessageData[] = historyData.messages.map((msg: any) => {
          let attachments = undefined
          if (msg.attachments) {
            try {
              attachments = typeof msg.attachments === 'string' 
                ? JSON.parse(msg.attachments) 
                : msg.attachments
            } catch (e) {
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
        
        // Обновляем сообщения: удаляем временные и добавляем реальные из БД
        setMessages(prev => {
          // Сохраняем временные сообщения на случай, если они еще не в истории
          const tempUserMessage = prev.find(msg => msg.id === userMessageId)
          const tempAssistantMessage = prev.find(msg => msg.id === assistantMessageId)
          
          // Проверяем, есть ли сообщения пользователя и ассистента в истории
          const userMessageFromHistory = historyMessages.find(msg => 
            msg.role === 'user' && 
            msg.content.trim() === message.trim()
          )
          const assistantMessageFromHistory = historyMessages.find(msg => 
            msg.role === 'assistant' && 
            msg.content.trim() === assistantContent.trim() &&
            assistantContent.length > 0
          )
          
          // Если оба сообщения есть в истории
          if (userMessageFromHistory && assistantMessageFromHistory) {
            // Если сообщение assistant уже было напечатано через стриминг, просто используем историю
            // В противном случае (если это загрузка истории), эффект печати уже применен в loadChatHistory
            return historyMessages
          }
          
          // Если только сообщение пользователя есть в истории
          if (userMessageFromHistory && !assistantMessageFromHistory) {
            // Заменяем временное сообщение пользователя на реальное, оставляем временное сообщение ассистента
            const otherMessages = historyMessages.filter(msg => msg.id !== userMessageFromHistory.id)
            return [
              ...otherMessages,
              userMessageFromHistory,
              tempAssistantMessage || assistantMessageFromHistory
            ].filter(Boolean) as MessageData[]
          }
          
          // Если только сообщение ассистента есть в истории
          if (!userMessageFromHistory && assistantMessageFromHistory) {
            // Оставляем временное сообщение пользователя, заменяем временное сообщение ассистента на реальное
            const otherMessages = historyMessages.filter(msg => msg.id !== assistantMessageFromHistory.id)
            return [
              ...otherMessages,
              tempUserMessage,
              assistantMessageFromHistory
            ].filter(Boolean) as MessageData[]
          }
          
          // Если ни одно сообщение не в истории, оставляем временные, но добавляем их к истории
          if (tempUserMessage && tempAssistantMessage) {
            // Объединяем: все сообщения из истории, временное сообщение пользователя, временное сообщение ассистента
            const existingMessages = prev.filter(msg => 
              msg.id !== userMessageId && msg.id !== assistantMessageId
            )
            return [
              ...existingMessages,
              tempUserMessage,
              tempAssistantMessage
            ]
          }
          
          // В крайнем случае возвращаем историю
          return historyMessages
        })
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
