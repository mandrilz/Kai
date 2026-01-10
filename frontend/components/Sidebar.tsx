'use client'

import { useState, useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'

interface Chat {
  id: string
  title: string | null
  updated_at: string
}

export default function Sidebar() {
  const [chats, setChats] = useState<Chat[]>([])
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    loadChats()
  }, [])

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

  const handleNewChat = async () => {
    try {
      const response = await fetch('/api/chats', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ title: null }),
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
          router.push(`/app/chat/${newChat.id}`)
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
    <div className="w-80 bg-gray-50 border-r border-gray-200 flex flex-col h-screen">
      {/* Кнопка "Новый чат" */}
      <div className="p-4 border-b border-gray-200">
        <button
          onClick={handleNewChat}
          className="w-full bg-[#0066CC] text-white py-2 px-4 rounded-lg hover:bg-[#0052A3] transition-colors"
        >
          + Новый чат
        </button>
      </div>

      {/* Список чатов */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center text-gray-500">Загрузка...</div>
        ) : chats.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            Нет чатов. Создайте новый чат.
          </div>
        ) : (
          <div className="py-2">
            {chats.map((chat) => {
              const isActive = pathname === `/app/chat/${chat.id}`
              return (
                <button
                  key={chat.id}
                  onClick={() => router.push(`/app/chat/${chat.id}`)}
                  className={`w-full text-left px-4 py-3 hover:bg-gray-100 transition-colors ${
                    isActive ? 'bg-blue-50 border-l-4 border-[#0066CC]' : ''
                  }`}
                >
                  <div className="font-medium text-gray-900 truncate">
                    {chat.title || 'Новый чат'}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {formatDate(chat.updated_at)}
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
