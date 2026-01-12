'use client'

import { useEffect, useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import Chat from '@/components/Chat'

function HomeContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null)

  useEffect(() => {
    // Получаем chatId из query параметров
    const chatId = searchParams.get('chat')
    if (chatId) {
      setSelectedChatId(chatId)
    }
  }, [searchParams])

  useEffect(() => {
    // Проверяем авторизацию, пытаясь загрузить чаты
    const checkAuth = async () => {
      try {
        const response = await fetch('/api/chats', {
          credentials: 'include',
        })

        // Проверяем статус перед чтением body
        if (response.status === 401) {
          // Не авторизован - перенаправляем на логин
          console.log('[AUTH CHECK] 401 - перенаправление на /login')
          router.push('/login')
          return
        }

        if (!response.ok) {
          // Другая ошибка
          console.error('[AUTH CHECK] Ошибка:', response.status, response.statusText)
          setCheckingAuth(false)
          return
        }

        // Авторизован - проверяем, есть ли чаты
        const contentType = response.headers.get('content-type') || ''
        if (!contentType.includes('application/json')) {
          console.error('[AUTH CHECK] Некорректный формат ответа:', contentType)
          setCheckingAuth(false)
          return
        }

        try {
          const chats = await response.json()
          // Если есть чаты и нет выбранного чата в URL, выбираем первый
          if (chats && Array.isArray(chats) && chats.length > 0) {
            const chatIdFromUrl = searchParams.get('chat')
            if (!chatIdFromUrl && !selectedChatId) {
              // Устанавливаем первый чат как выбранный
              setSelectedChatId(chats[0].id)
              router.replace(`/?chat=${chats[0].id}`, { scroll: false })
            }
          }
        } catch (e) {
          console.error('[AUTH CHECK] Ошибка парсинга списка чатов:', e)
        }
      } catch (error) {
        console.error('Ошибка проверки авторизации:', error)
        router.push('/login')
      } finally {
        setCheckingAuth(false)
      }
    }

    checkAuth()
  }, [router, searchParams, selectedChatId])

  const handleChatSelect = (chatId: string | null) => {
    setSelectedChatId(chatId)
    if (chatId) {
      router.replace(`/?chat=${chatId}`, { scroll: false })
    } else {
      router.replace('/', { scroll: false })
    }
  }

  if (checkingAuth) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-[#1D1D1D]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#E49E00] mx-auto mb-4"></div>
          <p className="text-[#B5B5B5]">Загрузка...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen w-screen flex bg-[#1D1D1D]">
      <Sidebar selectedChatId={selectedChatId} onChatSelect={handleChatSelect} />
      <div className="flex-1 flex flex-col">
        {selectedChatId ? (
          <Chat chatId={selectedChatId} />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center max-w-md px-6">
              <h1 className="text-3xl font-bold text-[#E49E00] mb-4">
                Добро пожаловать в K.ai (Кометтик)
              </h1>
              <p className="text-[#B5B5B5] mb-6">
                Я помогу вам с подбором насосов и поиском аналогов.
              </p>
              <p className="text-sm text-[#B5B5B5]">
                Создайте новый чат, чтобы начать работу.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function Home() {
  return (
    <Suspense fallback={
      <div className="h-screen w-screen flex items-center justify-center bg-[#1D1D1D]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#E49E00] mx-auto mb-4"></div>
          <p className="text-[#B5B5B5]">Загрузка...</p>
        </div>
      </div>
    }>
      <HomeContent />
    </Suspense>
  )
}
