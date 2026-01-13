'use client'

import { useState, useRef, KeyboardEvent, useEffect } from 'react'
import FileUpload from './FileUpload'

interface ComposerProps {
  onSend: (message: string, attachments: Array<{ filename: string; content_type: string; base64: string }>) => void
  isLoading: boolean
  onMessageSent?: () => void // Callback для очистки полей после успешной отправки
  onError?: () => void // Callback для восстановления текста при ошибке
}

export default function Composer({ onSend, isLoading, onMessageSent, onError }: ComposerProps) {
  const [message, setMessage] = useState('')
  const [attachments, setAttachments] = useState<Array<{ filename: string; content_type: string; base64: string }>>([])
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const isSendingRef = useRef(false) // Защита от двойной отправки (микрозадержка)
  const savedMessageRef = useRef<{ message: string; attachments: Array<{ filename: string; content_type: string; base64: string }> } | null>(null) // Сохраняем текст на случай ошибки

  // Сбрасываем блокировку когда isLoading становится false (запрос завершен)
  useEffect(() => {
    if (!isLoading) {
      // Микрозадержка для защиты от мгновенных повторных кликов
      const timeoutId = setTimeout(() => {
        isSendingRef.current = false
      }, 200)
      return () => clearTimeout(timeoutId)
    } else {
      // Когда isLoading становится true, блокируем повторные вызовы
      isSendingRef.current = true
    }
  }, [isLoading])

  // Очистка полей после успешной отправки
  useEffect(() => {
    if (onMessageSent) {
      savedMessageRef.current = null
      setMessage('')
      setAttachments([])
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }
  }, [onMessageSent])

  // Восстановление текста при ошибке
  useEffect(() => {
    if (onError && savedMessageRef.current) {
      setMessage(savedMessageRef.current.message)
      setAttachments(savedMessageRef.current.attachments)
      savedMessageRef.current = null
    }
  }, [onError])

  const handleSend = () => {
    // Защита от повторных вызовов - используем isLoading как основную защиту
    if (isLoading || (!message.trim() && attachments.length === 0)) {
      return
    }
    
    // Дополнительная микрозащита от мгновенных повторных кликов
    if (isSendingRef.current) {
      return
    }
    isSendingRef.current = true
    
    const messageToSend = message.trim()
    const attachmentsToSend = [...attachments]
    
    // Сохраняем текст на случай ошибки (НЕ очищаем сразу)
    savedMessageRef.current = {
      message: messageToSend,
      attachments: attachmentsToSend
    }
    
    // Вызываем onSend (очистка полей будет после успешной отправки через onMessageSent)
    onSend(messageToSend, attachmentsToSend)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      // Проверяем isLoading перед вызовом
      if (!isLoading && (message.trim() || attachments.length > 0)) {
        handleSend()
      }
    }
  }

  const handleFileSelect = (files: Array<{ filename: string; content_type: string; base64: string }>) => {
    setAttachments(prev => [...prev, ...files])
  }

  const removeAttachment = (index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index))
  }

  const adjustTextareaHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`
    }
  }

  return (
    <div className="p-4 bg-[#1D1D1D]">
      {attachments.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {attachments.map((att, idx) => (
            <div
              key={idx}
              className="flex items-center space-x-2 bg-[#282828] rounded px-2 py-1 text-sm text-[#EDEDED]"
            >
              <span>📎 {att.filename}</span>
              <button
                onClick={() => removeAttachment(idx)}
                className="text-[#C94A3A] hover:text-[#C94A3A]"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="flex items-end space-x-2">
        <FileUpload onFileSelect={handleFileSelect} disabled={isLoading} />
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => {
            setMessage(e.target.value)
            adjustTextareaHeight()
          }}
          onKeyDown={handleKeyDown}
          placeholder="Введите сообщение..."
          className="flex-1 resize-none border border-[#3A3A3A] rounded-lg px-4 py-2 bg-[#282828] text-[#EDEDED] placeholder:text-[#8A8A8A] focus:outline-none focus:ring-2 focus:ring-[#E49E00] min-h-[44px] max-h-[200px]"
          rows={1}
          disabled={isLoading}
        />
        <button
          onClick={handleSend}
          disabled={isLoading || (!message.trim() && attachments.length === 0)}
          className="p-3 text-[#E49E00] hover:text-[#C88A00] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          style={{ color: '#E49E00' }}
        >
          <svg 
            width="24" 
            height="24" 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="3" 
            strokeLinecap="round" 
            strokeLinejoin="round"
            className="w-8 h-8"
          >
            <line x1="12" y1="19" x2="12" y2="5"></line>
            <polyline points="5 12 12 5 19 12"></polyline>
          </svg>
        </button>
      </div>
    </div>
  )
}

