'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'

export default function Home() {
  const router = useRouter()
  const [checkingAuth, setCheckingAuth] = useState(true)

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
          if (chats && Array.isArray(chats) && chats.length > 0) {
            // Перенаправляем на первый чат
            console.log('[AUTH CHECK] Чаты найдены, перенаправление на первый чат')
            router.push(`/chat/${chats[0].id}`)
          } else {
            // Нет чатов - показываем приветствие
            console.log('[AUTH CHECK] Чаты не найдены, показываем приветствие')
            setCheckingAuth(false)
          }
        } catch (e) {
          console.error('[AUTH CHECK] Ошибка парсинга списка чатов:', e)
          setCheckingAuth(false)
        }
      } catch (error) {
        console.error('Ошибка проверки авторизации:', error)
        router.push('/login')
      } finally {
        setCheckingAuth(false)
      }
    }

    checkAuth()
  }, [router])

  if (checkingAuth) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-white">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#0066CC] mx-auto mb-4"></div>
          <p className="text-gray-600">Загрузка...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen w-screen flex bg-white">
      <Sidebar />
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md px-6">
          <h1 className="text-3xl font-bold text-[#0066CC] mb-4">
            Добро пожаловать в K.ai (Кометтик)
          </h1>
          <p className="text-gray-600 mb-6">
            Я помогу вам с подбором насосов и поиском аналогов.
          </p>
          <p className="text-sm text-gray-500">
            Создайте новый чат, чтобы начать работу.
          </p>
        </div>
      </div>
    </div>
  )
}
