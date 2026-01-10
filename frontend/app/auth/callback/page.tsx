import { Suspense } from 'react'
import CallbackClient from './CallbackClient'

// Важно: страница должна быть динамической, т.к. использует useSearchParams
export const dynamic = 'force-dynamic'

export default function Page() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="max-w-md w-full px-6 py-8 bg-white rounded-lg shadow-lg text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#0066CC] mx-auto mb-4"></div>
          <p className="text-gray-700">Загрузка...</p>
        </div>
      </div>
    }>
      <CallbackClient />
    </Suspense>
  )
}
