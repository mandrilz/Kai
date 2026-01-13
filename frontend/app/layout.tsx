import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'K.ai (Кометтик)',
  description: 'Инженер-помощник Кометта для подбора насосов',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  )
}
