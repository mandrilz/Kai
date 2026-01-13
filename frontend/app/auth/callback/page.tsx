import { Suspense } from 'react'
import CallbackClient from './CallbackClient'

// Важно: страница должна быть динамической, т.к. использует useSearchParams
export const dynamic = 'force-dynamic'

export default function Page() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-[#1D1D1D]">
        <div className="max-w-md w-full px-6 py-8 bg-[#282828] rounded-lg shadow-lg text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#E49E00] mx-auto mb-4"></div>
          <p className="text-[#EDEDED]">Загрузка...</p>
        </div>
      </div>
    }>
      <CallbackClient />
    </Suspense>
  )
}
