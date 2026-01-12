'use client'

import { useRef, ChangeEvent } from 'react'

interface FileUploadProps {
  onFileSelect: (files: Array<{ filename: string; content_type: string; base64: string }>) => void
  disabled?: boolean
}

export default function FileUpload({ onFileSelect, disabled }: FileUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    const processedFiles: Array<{ filename: string; content_type: string; base64: string }> = []

    for (const file of Array.from(files)) {
      // Проверяем тип файла
      if (!file.type.startsWith('image/') && file.type !== 'application/pdf') {
        alert(`Файл ${file.name} не поддерживается. Используйте PDF или изображение.`)
        continue
      }

      try {
        const base64 = await fileToBase64(file)
        processedFiles.push({
          filename: file.name,
          content_type: file.type,
          base64: base64,
        })
      } catch (error) {
        console.error(`Ошибка обработки файла ${file.name}:`, error)
        alert(`Не удалось обработать файл ${file.name}`)
      }
    }

    if (processedFiles.length > 0) {
      onFileSelect(processedFiles)
    }

    // Сбрасываем input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const result = reader.result as string
        // Убираем префикс data:...;base64,
        const base64 = result.split(',')[1]
        resolve(base64)
      }
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
  }

  return (
    <button
      type="button"
      onClick={() => fileInputRef.current?.click()}
      disabled={disabled}
      className="p-3 text-[#E49E00] hover:text-[#C88A00] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      style={{ color: '#E49E00' }}
      title="Прикрепить файл"
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
        <line x1="12" y1="5" x2="12" y2="19"></line>
        <line x1="5" y1="12" x2="19" y2="12"></line>
      </svg>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,image/*"
        multiple
        onChange={handleFileChange}
        className="hidden"
        disabled={disabled}
      />
    </button>
  )
}

