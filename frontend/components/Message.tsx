'use client'

import { MessageData } from './Chat'
import { useMemo } from 'react'
import React from 'react'
import Plot from './Plot'

interface MessageProps {
  message: MessageData
}

export default function Message({ message }: MessageProps) {
  const isUser = message.role === 'user'

  // Парсим markdown ссылки [текст](url) с поддержкой многострочного текста
  // Также распознаем ссылки на графики /api/plot/compare
  const parseContent = (content: string): React.ReactNode[] => {
    if (!content) return []
    
    const parts: React.ReactNode[] = []
    let keyCounter = 0
    
    // Сначала ищем ссылки на графики
    const plotRegex = /\/api\/plot\/compare\?[^\s\)]+/g
    const plotMatches: Array<{ index: number; url: string }> = []
    let plotMatch
    plotRegex.lastIndex = 0
    
    while ((plotMatch = plotRegex.exec(content)) !== null) {
      plotMatches.push({
        index: plotMatch.index,
        url: plotMatch[0]
      })
    }
    
    // Регулярное выражение для поиска ссылок [текст](url)
    const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g
    const linkMatches: Array<{ index: number; length: number; text: string; url: string }> = []
    let linkMatch
    linkRegex.lastIndex = 0
    
    while ((linkMatch = linkRegex.exec(content)) !== null) {
      linkMatches.push({
        index: linkMatch.index,
        length: linkMatch[0].length,
        text: linkMatch[1],
        url: linkMatch[2]
      })
    }
    
    // Объединяем все совпадения и сортируем по индексу
    const allMatches: Array<{ index: number; length: number; type: 'plot' | 'link'; url: string; text?: string }> = []
    
    plotMatches.forEach(m => {
      allMatches.push({
        index: m.index,
        length: m.url.length,
        type: 'plot',
        url: m.url
      })
    })
    
    linkMatches.forEach(m => {
      allMatches.push({
        index: m.index,
        length: m.length,
        type: 'link',
        url: m.url,
        text: m.text
      })
    })
    
    allMatches.sort((a, b) => a.index - b.index)
    
    let lastIndex = 0
    
    allMatches.forEach(match => {
      // Добавляем текст до совпадения
      if (match.index > lastIndex) {
        const textBefore = content.substring(lastIndex, match.index)
        if (textBefore) {
          parts.push(<span key={`text-${keyCounter++}`}>{textBefore}</span>)
        }
      }
      
      // Добавляем совпадение
      if (match.type === 'plot') {
        // Это график - встраиваем компонент Plot
        parts.push(<Plot key={`plot-${keyCounter++}`} url={match.url} />)
      } else {
        // Это обычная ссылка
        parts.push(
          <a
            key={`link-${keyCounter++}`}
            href={match.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#E49E00] hover:underline"
          >
            {match.text || match.url}
          </a>
        )
      }
      
      lastIndex = match.index + match.length
    })
    
    // Добавляем оставшийся текст
    if (lastIndex < content.length) {
      const remainingText = content.substring(lastIndex)
      if (remainingText) {
        parts.push(<span key={`text-${keyCounter++}`}>{remainingText}</span>)
      }
    }

    // Если не было совпадений, возвращаем весь текст
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
            ? 'bg-[#E49E00] text-white'
            : 'bg-[#282828] text-[#EDEDED]'
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

