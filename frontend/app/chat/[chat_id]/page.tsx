'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

interface ChatPageProps {
  params: {
    chat_id: string
  }
}

export default function ChatPage({ params }: ChatPageProps) {
  const router = useRouter()

  useEffect(() => {
    // Редиректим на главную страницу с параметром chat
    router.replace(`/?chat=${params.chat_id}`)
  }, [params.chat_id, router])

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-[#1D1D1D]">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#E49E00] mx-auto mb-4"></div>
        <p className="text-[#B5B5B5]">Перенаправление...</p>
      </div>
    </div>
  )
}
