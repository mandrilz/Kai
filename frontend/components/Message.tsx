'use client'

import { MessageData } from './Chat'
import { useMemo } from 'react'
import React from 'react'

interface MessageProps {
  message: MessageData
}

export default function Message({ message }: MessageProps) {
  const isUser = message.role === 'user'

  // Парсим markdown ссылки [текст](url) с поддержкой многострочного текста
  const parseContent = (content: string): React.ReactNode[] => {
    if (!content) return []
    
    const parts: React.ReactNode[] = []
    // Регулярное выражение для поиска ссылок [текст](url)
    // Используем флаг 'g' для глобального поиска и 'm' для многострочного режима
    const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g
    let lastIndex = 0
    let match
    let keyCounter = 0

    // Сбрасываем lastIndex для нового поиска
    linkRegex.lastIndex = 0
    
    while ((match = linkRegex.exec(content)) !== null) {
      // Добавляем текст до ссылки
      if (match.index > lastIndex) {
        const textBefore = content.substring(lastIndex, match.index)
        if (textBefore) {
          // Сохраняем переносы строк
          parts.push(<span key={`text-${keyCounter++}`}>{textBefore}</span>)
        }
      }
      // Добавляем ссылку
      parts.push(
        <a
          key={`link-${keyCounter++}`}
          href={match[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[#0066CC] hover:underline"
        >
          {match[1]}
        </a>
      )
      lastIndex = match.index + match[0].length
    }
    // Добавляем оставшийся текст
    if (lastIndex < content.length) {
      const remainingText = content.substring(lastIndex)
      if (remainingText) {
        parts.push(<span key={`text-${keyCounter++}`}>{remainingText}</span>)
      }
    }

    // Если не было ссылок, возвращаем весь текст
    if (parts.length === 0) {
      return [<span key="text-0">{content}</span>]
    }

    return parts
  }

  const parsedContent = useMemo(() => parseContent(message.content || ''), [message.content])

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} w-full`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-[#0066CC] text-white'
            : 'bg-[#F5F5F5] text-[#333333]'
        }`}
      >
        {message.attachments && message.attachments.length > 0 && (
          <div className="mb-2 space-y-1">
            {message.attachments.map((att, idx) => (
              <div
                key={idx}
                className="text-xs opacity-80 flex items-center space-x-1"
              >
                <span>📎</span>
                <span>{att.filename}</span>
              </div>
            ))}
          </div>
        )}
        <div className="whitespace-pre-wrap break-words">
          {parsedContent.length > 0 ? parsedContent : <span>...</span>}
        </div>
      </div>
    </div>
  )
}

