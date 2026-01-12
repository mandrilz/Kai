'use client'

import { useState, useEffect } from 'react'

interface PlotProps {
  url: string
}

export default function Plot({ url }: PlotProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Если URL уже полный путь, используем его напрямую
    let plotUrl = url
    
    // Если URL не начинается с /api/, пытаемся извлечь параметры
    if (!url.startsWith('/api/')) {
      try {
        // Пытаемся распарсить как полный URL или относительный путь
        const urlObj = url.startsWith('http') 
          ? new URL(url) 
          : new URL(url, window.location.origin)
        const komettaArticul = urlObj.searchParams.get('kometta_articul')
        const competitorArticul = urlObj.searchParams.get('competitor_articul')

        if (!komettaArticul) {
          setError('Не указан артикул насоса')
          setLoading(false)
          return
        }

        // Формируем URL для получения графика
        plotUrl = `/api/plot/compare?kometta_articul=${komettaArticul}${competitorArticul ? `&competitor_articul=${competitorArticul}` : ''}`
      } catch (e) {
        // Если не удалось распарсить, используем URL как есть
        plotUrl = url.startsWith('/') ? url : `/api/plot/compare?${url}`
      }
    }

    // Загружаем график
    fetch(plotUrl, {
      credentials: 'include',
    })
      .then(response => {
        if (!response.ok) {
          throw new Error(`Ошибка загрузки графика: ${response.status}`)
        }
        return response.blob()
      })
      .then(blob => {
        const imageUrl = URL.createObjectURL(blob)
        setImageUrl(imageUrl)
        setLoading(false)
      })
      .catch(err => {
        console.error('Ошибка загрузки графика:', err)
        setError(err.message || 'Не удалось загрузить график')
        setLoading(false)
      })
  }, [url])

  if (loading) {
    return (
      <div className="my-4 p-4 bg-[#282828] rounded-lg border border-[#3A3A3A]">
        <div className="text-center text-[#B5B5B5]">Загрузка графика...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="my-4 p-4 bg-[#282828] rounded-lg border border-[#3A3A3A]">
        <div className="text-center text-[#C94A3A]">{error}</div>
      </div>
    )
  }

  if (!imageUrl) {
    return null
  }

  return (
    <div className="my-4 p-4 bg-[#282828] rounded-lg border border-[#3A3A3A]">
      <img
        src={imageUrl}
        alt="График кривой насоса"
        className="w-full h-auto rounded"
        onError={() => {
          setError('Ошибка отображения графика')
          setImageUrl(null)
        }}
      />
    </div>
  )
}
