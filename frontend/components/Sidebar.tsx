'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'

interface Chat {
  id: string
  title: string | null
  updated_at: string
}

interface SidebarProps {
  selectedChatId?: string | null
  onChatSelect?: (chatId: string | null) => void
}

export default function Sidebar({ selectedChatId, onChatSelect }: SidebarProps) {
  const [chats, setChats] = useState<Chat[]>([])
  const [loading, setLoading] = useState(true)
  const [editingChatId, setEditingChatId] = useState<string | null>(null)
  const [draftTitle, setDraftTitle] = useState<string>('')
  const editInputRef = useRef<HTMLInputElement | null>(null)
  const router = useRouter()

  useEffect(() => {
    loadChats()
  }, [])

  useEffect(() => {
    if (editingChatId && editInputRef.current) {
      editInputRef.current.focus()
      editInputRef.current.select()
    }
  }, [editingChatId])

  const loadChats = async () => {
    try {
      const response = await fetch('/api/chats', {
        credentials: 'include',
      })

      if (response.status === 401) {
        // Не авторизован - перенаправляем на логин
        router.push('/login')
        return
      }

      if (!response.ok) {
        console.error('Ошибка загрузки чатов:', response.status, response.statusText)
        return
      }

      // Безопасно читаем JSON
      const contentType = response.headers.get('content-type') || ''
      if (!contentType.includes('application/json')) {
        console.error('Ожидался JSON, получен:', contentType)
        return
      }

      const responseText = await response.text()
      try {
        const data = JSON.parse(responseText)
        setChats(Array.isArray(data) ? data : [])
      } catch (e) {
        console.error('Ошибка парсинга JSON ответа чатов:', e)
        console.error('Ответ был:', responseText.substring(0, 200))
      }
    } catch (error) {
      console.error('Ошибка загрузки чатов:', error)
    } finally {
      setLoading(false)
    }
  }

  const selectChat = (chatId: string | null) => {
    if (onChatSelect) {
      onChatSelect(chatId)
    } else {
      if (chatId) router.push(`/chat/${chatId}`)
      else router.push('/')
    }
  }

  const handleNewChat = async () => {
    try {
      const response = await fetch('/api/chats', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({}),
      })

      if (response.status === 401) {
        router.push('/login')
        return
      }

      if (!response.ok) {
        console.error('Ошибка создания чата:', response.status, response.statusText)
        return
      }

      // Безопасно читаем JSON
      const contentType = response.headers.get('content-type') || ''
      if (!contentType.includes('application/json')) {
        console.error('Ожидался JSON при создании чата, получен:', contentType)
        return
      }

      const responseText = await response.text()
      try {
        const newChat = JSON.parse(responseText)
        if (newChat && newChat.id) {
          selectChat(newChat.id)
          // Обновляем список чатов
          loadChats()
        }
      } catch (e) {
        console.error('Ошибка парсинга JSON ответа создания чата:', e)
        console.error('Ответ был:', responseText.substring(0, 200))
      }
    } catch (error) {
      console.error('Ошибка создания чата:', error)
    }
  }

  const renameChat = async (chatId: string, newTitle: string) => {
    const trimmed = newTitle.trim()
    if (!trimmed) return

    // Оптимистично обновляем
    setChats(prev => prev.map(c => (c.id === chatId ? { ...c, title: trimmed } : c)))
    try {
      const res = await fetch(`/api/chats/${chatId}?title=${encodeURIComponent(trimmed)}`, {
        method: 'PATCH',
        credentials: 'include',
      })
      if (!res.ok) {
        // Откатываем через перезагрузку списка
        await loadChats()
      } else {
        await loadChats()
      }
    } catch (e) {
      console.error('Ошибка переименования чата:', e)
      await loadChats()
    }
  }

  const deleteChat = async (chatId: string) => {
    const ok = window.confirm('Удалить чат?')
    if (!ok) return

    // Находим соседа ДО удаления
    const idx = chats.findIndex(c => c.id === chatId)
    const nextChatId =
      idx >= 0
        ? (chats[idx + 1]?.id ?? chats[idx - 1]?.id ?? null)
        : null

    // Оптимистично убираем из списка
    setChats(prev => prev.filter(c => c.id !== chatId))

    try {
      const res = await fetch(`/api/chats/${chatId}`, {
        method: 'DELETE',
        credentials: 'include',
      })
      if (!res.ok) {
        await loadChats()
        return
      }

      if (selectedChatId === chatId) {
        if (nextChatId) {
          selectChat(nextChatId)
        } else {
          // Если чатов не осталось — создаём новый
          await handleNewChat()
        }
      }

      await loadChats()
    } catch (e) {
      console.error('Ошибка удаления чата:', e)
      await loadChats()
    }
  }

  const handleLogout = async () => {
    try {
      // Удаляем cookie с токеном
      document.cookie = 'auth_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT'
      // Перенаправляем на страницу логина
      router.push('/login')
    } catch (error) {
      console.error('Ошибка при выходе:', error)
      router.push('/login')
    }
  }

  const sidebarWidthClasses = useMemo(
    () => 'w-[280px] min-w-[260px] max-w-[300px]',
    []
  )

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'только что'
    if (diffMins < 60) return `${diffMins} мин назад`
    if (diffHours < 24) return `${diffHours} ч назад`
    if (diffDays < 7) return `${diffDays} дн назад`
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
  }

  return (
    <div className={`${sidebarWidthClasses} bg-[#2F2F2F] border-r border-[#3A3A3A] flex flex-col h-screen`}>
      {/* Кнопка "Новый чат" */}
      <div className="p-4 border-b border-[#3A3A3A]">
        <button
          onClick={handleNewChat}
          className="w-full bg-[#E49E00] text-white py-2 px-4 rounded-lg hover:bg-[#C88A00] transition-colors"
        >
          + Новый чат
        </button>
      </div>

      {/* Список чатов */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center text-[#B5B5B5]">Загрузка...</div>
        ) : chats.length === 0 ? (
          <div className="p-4 text-center text-[#B5B5B5]">
            Нет чатов. Создайте новый чат.
          </div>
        ) : (
          <div className="py-2">
            {chats.map((chat) => {
              const isActive = selectedChatId === chat.id
              const isEditing = editingChatId === chat.id
              return (
                <div key={chat.id} className="px-2">
                  <button
                    onClick={() => selectChat(chat.id)}
                    className={`group w-full text-left px-3 py-3 rounded-lg hover:bg-[#2F2F2F] transition-colors flex items-start gap-3 ${
                      isActive ? 'border-l-4 border-[#E49E00]' : ''
                    }`}
                    style={isActive ? { backgroundColor: 'rgba(228, 158, 0, 0.08)' } : {}}
                  >
                    <div className="flex-1 min-w-0">
                      {isEditing ? (
                        <input
                          ref={editInputRef}
                          value={draftTitle}
                          onChange={(e) => setDraftTitle(e.target.value)}
                          onKeyDown={async (e) => {
                            if (e.key === 'Escape') {
                              e.preventDefault()
                              setEditingChatId(null)
                              setDraftTitle('')
                              return
                            }
                            if (e.key === 'Enter') {
                              e.preventDefault()
                              const next = draftTitle
                              setEditingChatId(null)
                              setDraftTitle('')
                              await renameChat(chat.id, next)
                            }
                          }}
                          onBlur={async () => {
                            const next = draftTitle
                            setEditingChatId(null)
                            setDraftTitle('')
                            const currentTitle = (chat.title || 'Новый чат').trim()
                            if (next.trim() && next.trim() !== currentTitle) {
                              await renameChat(chat.id, next)
                            }
                          }}
                          className="w-full bg-[#282828] border border-[#3A3A3A] rounded-md px-2 py-1 text-[#EDEDED] text-sm focus:outline-none focus:ring-2 focus:ring-[#E49E00]"
                          placeholder="Название чата"
                        />
                      ) : (
                        <>
                          <div className="font-medium text-[#EDEDED] truncate">
                            {chat.title || 'Новый чат'}
                          </div>
                          <div className="text-xs text-[#B5B5B5] mt-1">
                            {formatDate(chat.updated_at)}
                          </div>
                        </>
                      )}
                    </div>

                    {/* Hover actions */}
                    {!isEditing && (
                      <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          type="button"
                          aria-label="Переименовать чат"
                          title="Переименовать чат"
                          onClick={(e) => {
                            e.stopPropagation()
                            e.preventDefault()
                            setEditingChatId(chat.id)
                            setDraftTitle((chat.title || 'Новый чат').toString())
                          }}
                          className="p-1 text-[#8A8A8A] hover:text-[#E49E00] transition-colors"
                        >
                          <svg
                            width="18"
                            height="18"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className="w-[18px] h-[18px]"
                          >
                            {/* pen-line */}
                            <path d="M12 20h9" />
                            <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
                          </svg>
                        </button>
                        <button
                          type="button"
                          aria-label="Удалить чат"
                          title="Удалить чат"
                          onClick={(e) => {
                            e.stopPropagation()
                            e.preventDefault()
                            deleteChat(chat.id)
                          }}
                          className="p-1 text-[#8A8A8A] hover:text-[#C94A3A] transition-colors"
                        >
                          <svg
                            width="18"
                            height="18"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className="w-[18px] h-[18px]"
                          >
                            {/* trash */}
                            <path d="M3 6h18" />
                            <path d="M8 6V4h8v2" />
                            <path d="M6 6l1 16h10l1-16" />
                            <path d="M10 11v6" />
                            <path d="M14 11v6" />
                          </svg>
                        </button>
                      </div>
                    )}
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Кнопка "Выйти" */}
      <div className="border-t border-[#3A3A3A] bg-[#2F2F2F] flex items-center min-h-[88px] px-4">
        <button
          onClick={handleLogout}
          className="w-full bg-[#282828] text-[#EDEDED] py-2 px-4 rounded-lg hover:bg-[#3A3A3A] transition-colors"
        >
          Выйти
        </button>
      </div>
    </div>
  )
}
