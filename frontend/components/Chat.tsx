'use client'

import { useState, useRef, useEffect } from 'react'
import Message from './Message'
import Composer, { ComposerHandle } from './Composer'
import { v4 as uuidv4 } from 'uuid'
import { handleApiError, fetchWithRetry } from '../utils/api'

export interface MessageData {
  id: string
  role: 'user' | 'assistant'
  content: string
  attachments?: Array<{
    filename: string
    content_type: string
  }>
  printed_at?: string | null  // ISO timestamp из БД, если сообщение уже было напечатано
}

interface ChatProps {
  chatId: string
}

export default function Chat({ chatId }: ChatProps) {
  const [messages, setMessages] = useState<MessageData[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(true)
  const [messageSent, setMessageSent] = useState(false) // Флаг успешной отправки для очистки полей в Composer
  const [messageError, setMessageError] = useState(false) // Флаг ошибки для восстановления текста в Composer
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null) // Ref для скролл-контейнера
  const welcomeMessageShownRef = useRef<boolean>(false) // Флаг для отслеживания показа приветственного сообщения
  const printedMessageIdsRef = useRef<Set<string>>(new Set()) // Отслеживаем, какие сообщения уже были напечатаны
  const streamingMessageIdsRef = useRef<Set<string>>(new Set()) // Отслеживаем временные ID сообщений во время стриминга
  const abortControllerRef = useRef<AbortController | null>(null) // AbortController для отмены запросов
  const composerRef = useRef<ComposerHandle>(null) // Ref для доступа к методу focusInput компонента Composer
  const hasFocusedForChatRef = useRef<string | null>(null) // Отслеживаем, был ли установлен фокус для текущего чата

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const isUserAtBottomRef = useRef(true) // Отслеживаем, находится ли пользователь внизу

  // Проверяем, находится ли пользователь внизу
  const checkIfUserAtBottom = () => {
    const container = scrollContainerRef.current
    if (!container) return true
    
    const threshold = 100 // пикселей от низа
    const isAtBottom = 
      container.scrollHeight - container.scrollTop - container.clientHeight < threshold
    
    isUserAtBottomRef.current = isAtBottom
    return isAtBottom
  }

  // Слушаем скролл для отслеживания позиции пользователя
  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return
    
    // Проверяем начальную позицию
    checkIfUserAtBottom()
    
    // Throttle для обработчика скролла
    let scrollTimeout: NodeJS.Timeout | null = null
    const throttledHandleScroll = () => {
      if (scrollTimeout) return
      scrollTimeout = setTimeout(() => {
        checkIfUserAtBottom()
        scrollTimeout = null
      }, 100)
    }
    
    container.addEventListener('scroll', throttledHandleScroll, { passive: true })
    return () => {
      container.removeEventListener('scroll', throttledHandleScroll)
      if (scrollTimeout) clearTimeout(scrollTimeout)
    }
  }, [])

  // Throttle для scrollToBottom
  const lastScrollTimeRef = useRef(0)
  const throttledScrollToBottom = () => {
    const now = Date.now()
    if (now - lastScrollTimeRef.current < 100) { // Максимум раз в 100ms
      return
    }
    lastScrollTimeRef.current = now
    scrollToBottom()
  }

  // Автоскролл только если пользователь внизу
  useEffect(() => {
    // Небольшая задержка для корректного расчета высоты контейнера
    const timeoutId = setTimeout(() => {
      if (isUserAtBottomRef.current) {
        throttledScrollToBottom()
      }
    }, 50)
    
    return () => clearTimeout(timeoutId)
  }, [messages])

  const printingLockRef = useRef<Set<string>>(new Set()) // Блокировка для предотвращения параллельной печати

  // Универсальная функция для эффекта печати сообщения от assistant
  const printMessageWithEffect = async (message: MessageData) => {
    // Проверяем и блокируем атомарно (используем printed_at из БД как основной источник истины)
    if (message.printed_at || printingLockRef.current.has(message.id)) {
      return
    }
    
    // Блокируем сразу
    printingLockRef.current.add(message.id)
    
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
    
    // Отмечаем сообщение как напечатанное в БД через API
    try {
      const response = await fetch(`/api/chats/${chatId}/messages/${message.id}/printed`, {
        method: 'POST',
        credentials: 'include',
      })
      if (!response.ok) {
        console.error('Ошибка при отметке сообщения как напечатанного:', response.statusText)
      }
    } catch (error) {
      console.error('Ошибка при вызове API для отметки сообщения:', error)
    }
    
    // Разблокируем после завершения
    printingLockRef.current.delete(message.id)
  }

  // Загружаем историю сообщений при монтировании
  useEffect(() => {
    // Сбрасываем флаги при смене чата
    welcomeMessageShownRef.current = false
    printedMessageIdsRef.current.clear()
    streamingMessageIdsRef.current.clear()
    setMessages([]) // Очищаем сообщения при смене чата
    hasFocusedForChatRef.current = null // Сбрасываем флаг фокуса при смене чата
    
    // Отменяем предыдущий запрос, если есть
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    
    loadChatHistory()
    
    // Cleanup при размонтировании или смене чата
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [chatId])
  
  // Фокусим поле ввода после загрузки истории (при переключении чата или монтировании)
  useEffect(() => {
    if (!isLoadingHistory && hasFocusedForChatRef.current !== chatId) {
      // Небольшая задержка для гарантии, что DOM обновлен и Composer отрендерен
      const focusTimeout = setTimeout(() => {
        // Определяем reason: если это первый фокус для этого чата, то initialMount, иначе afterSwitchChat
        const isFirstFocus = hasFocusedForChatRef.current === null
        const reason = isFirstFocus ? 'initialMount' : 'afterSwitchChat'
        composerRef.current?.focusInput(reason)
        hasFocusedForChatRef.current = chatId // Отмечаем, что фокус был установлен для этого чата
      }, 150)
      return () => clearTimeout(focusTimeout)
    }
  }, [isLoadingHistory, chatId])

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
        
        // Определяем, какие сообщения нужно показать сразу, а какие - с эффектом печати
        // Печатаем эффектом только последнее assistant сообщение (или первое приветственное)
        const userMessages: MessageData[] = []
        const messagesToPrint: MessageData[] = []

        // Находим последнее assistant сообщение
        let lastAssistantMessage: MessageData | null = null
        for (let i = loadedMessages.length - 1; i >= 0; i--) {
          if (loadedMessages[i].role === 'assistant') {
            lastAssistantMessage = loadedMessages[i]
            break
          }
        }

        for (const msg of loadedMessages) {
          if (msg.role === 'assistant') {
            // Печатаем эффектом только последнее assistant сообщение, если оно еще не было напечатано в БД
            // Проверяем printed_at из БД вместо локального ref
            if (msg.id === lastAssistantMessage?.id && !msg.printed_at) {
              messagesToPrint.push(msg)
            } else {
              // Остальные assistant сообщения (или уже напечатанные) показываем сразу
              userMessages.push(msg)
            }
          } else {
            userMessages.push(msg)
          }
        }

        // Сначала устанавливаем все сообщения (кроме последнего assistant, если его нужно печатать)
        if (messagesToPrint.length > 0) {
          // Удаляем последнее assistant сообщение из списка, т.к. его будем печатать
          const messagesWithoutLastAssistant = userMessages.filter(m => 
            !messagesToPrint.some(toPrint => toPrint.id === m.id)
          )
          setMessages(messagesWithoutLastAssistant)
          
          // Печатаем последнее assistant сообщение с эффектом
          printMessageWithEffect(messagesToPrint[0]).catch(error => {
            console.error('Ошибка при печати сообщения:', error)
          })
        } else {
          // Все сообщения показываем сразу
          setMessages(loadedMessages)
        }
      } else {
        handleApiError(response)
      }
    } catch (error) {
      console.error('Ошибка загрузки истории:', error)
    } finally {
      setIsLoadingHistory(false)
    }
  }

  const handleSend = async (message: string, attachments: Array<{ filename: string; content_type: string; base64: string }>) => {
    // Сбрасываем флаги
    setMessageSent(false)
    setMessageError(false)
    
    // Отменяем предыдущий запрос, если есть
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    
    // Создаем новый AbortController
    const abortController = new AbortController()
    abortControllerRef.current = abortController
    
    setIsLoading(true)

    // Добавляем сообщение пользователя и ассистента сразу для правильного порядка отображения
    const userMessageId = uuidv4()
    const userMessage: MessageData = {
      id: userMessageId,
      role: 'user',
      content: message.trim(),
      attachments: attachments.length > 0 ? attachments : undefined,
    }

    // Создаём сообщение ассистента для потокового ответа
    const assistantMessageId = uuidv4()
    const assistantMessage: MessageData = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
    }
    
    // Объединяем в один setMessages для атомарности и уменьшения ререндеров
    setMessages(prev => [...prev, userMessage, assistantMessage])

    try {
      const apiEndpoint = `/api/chats/${chatId}/messages`
      
      console.log('Отправка запроса на:', apiEndpoint)
      
      // Генерируем idempotency key для предотвращения дубликатов
      const idempotencyKey = uuidv4()
      
      // Выполняем запрос с повторными попытками
      const response = await fetchWithRetry(
        apiEndpoint,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
          signal: abortController.signal, // Добавляем signal для отмены
          body: JSON.stringify({
            message: message,
            attachments: attachments,
            idempotency_key: idempotencyKey,
          }),
        },
        3, // Максимум 3 попытки
        1000 // Задержка между попытками: 1s, 2s, 3s
      )
      
      // Проверяем, не был ли запрос отменен
      if (abortController.signal.aborted) {
        return
      }

      if (!response.ok) {
        handleApiError(response)
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
        // Проверяем, не был ли запрос отменен перед каждым чтением
        if (abortController.signal.aborted) {
          reader.cancel()
          return
        }
        
        const { done, value } = await reader.read()
        
        // Проверяем после чтения
        if (abortController.signal.aborted) {
          return
        }

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
                // Помечаем временный ID стриминга (не добавляем в printedMessageIdsRef, т.к. это временный ID)
                streamingMessageIdsRef.current.add(assistantMessageId)
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
            printed_at: msg.printed_at || null,  // Сохраняем printed_at из БД
          }
        })
        
        // Сообщения, полученные через стриминг, уже показаны полностью
        // Если у них нет printed_at, можно сразу отметить (опционально, для консистентности)
        // Но обычно стриминг-сообщения не нужно печатать эффектом, так что printed_at остается null
        
        // Обновляем сообщения: используем ID из БД как источник истины
        // Убираем сложную логику merge по content - просто заменяем временные сообщения реальными из БД
        setMessages(prev => {
          // Удаляем все временные сообщения по их ID
          const filteredPrev = prev.filter(msg => 
            msg.id !== userMessageId && msg.id !== assistantMessageId
          )
          
          // Объединяем: существующие (не временные) + все из истории
          const merged = [...filteredPrev, ...historyMessages]
          
          // Удаляем дубликаты по ID (если есть)
          const uniqueMap = new Map<string, MessageData>()
          for (const msg of merged) {
            // Если сообщение с таким ID уже есть, оставляем то, что из истории (более свежее)
            if (!uniqueMap.has(msg.id) || historyMessages.some(m => m.id === msg.id)) {
              uniqueMap.set(msg.id, msg)
            }
          }
          
          const unique = Array.from(uniqueMap.values())
          
          // Сортируем по порядку из истории (история уже отсортирована по created_at)
          const historyIds = new Set(historyMessages.map(m => m.id))
          const sorted = unique.sort((a, b) => {
            const aInHistory = historyIds.has(a.id)
            const bInHistory = historyIds.has(b.id)
            
            if (aInHistory && bInHistory) {
              // Оба в истории - сортируем по порядку в истории
              const aIndex = historyMessages.findIndex(m => m.id === a.id)
              const bIndex = historyMessages.findIndex(m => m.id === b.id)
              return aIndex - bIndex
            }
            
            if (aInHistory) return -1
            if (bInHistory) return 1
            return 0
          })
          
          return sorted
        })
        
        // Успешная отправка - очищаем поля в Composer
        setMessageSent(true)
      }
    } catch (error) {
      // Проверяем, не была ли ошибка из-за отмены запроса
      if (error instanceof Error && error.name === 'AbortError') {
        // Запрос был отменен - это нормально, просто выходим
        return
      }
      
      // Проверяем, не был ли запрос отменен
      if (abortController.signal.aborted) {
        return
      }
      
      console.error('Ошибка при отправке сообщения:', error)
      const errorMessage = error instanceof Error ? error.message : 'Неизвестная ошибка'
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessageId
            ? { ...msg, content: `Произошла ошибка при обработке запроса: ${errorMessage}. Проверьте консоль браузера (F12) для подробностей.` }
            : msg
        )
      )
      
      // Ошибка - восстанавливаем текст в Composer
      setMessageError(true)
    } finally {
      // Сбрасываем isLoading только если запрос не был отменен
      if (!abortController.signal.aborted) {
        setIsLoading(false)
      }
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
      {/* На мобильных устройствах добавляем padding-top чтобы не перекрывать mobile header */}
      <div 
        ref={scrollContainerRef} 
        className="flex-1 overflow-y-auto" 
        style={{ 
          minHeight: 0
        }}
      >
        <div 
          className="max-w-3xl mx-auto px-4 space-y-6 mobile-messages-padding pb-8"
        >
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
          <Composer 
            ref={composerRef}
            onSend={handleSend} 
            isLoading={isLoading}
            onMessageSent={messageSent ? () => setMessageSent(false) : undefined}
            onError={messageError ? () => setMessageError(false) : undefined}
          />
        </div>
      </div>
    </div>
  )
}
