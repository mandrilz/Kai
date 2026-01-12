'use client'

import { useState, useRef, KeyboardEvent } from 'react'
import FileUpload from './FileUpload'

interface ComposerProps {
  onSend: (message: string, attachments: Array<{ filename: string; content_type: string; base64: string }>) => void
  isLoading: boolean
}

export default function Composer({ onSend, isLoading }: ComposerProps) {
  const [message, setMessage] = useState('')
  const [attachments, setAttachments] = useState<Array<{ filename: string; content_type: string; base64: string }>>([])
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = () => {
    console.log('handleSend вызван', { message: message.trim(), attachments: attachments.length, isLoading })
    
    if ((!message.trim() && attachments.length === 0) || isLoading) {
      console.log('Отправка заблокирована:', { hasMessage: !!message.trim(), hasAttachments: attachments.length > 0, isLoading })
      return
    }

    console.log('Вызываю onSend с:', { message: message.trim(), attachments: attachments.length })
    onSend(message.trim(), attachments)
    setMessage('')
    setAttachments([])
    
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
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

