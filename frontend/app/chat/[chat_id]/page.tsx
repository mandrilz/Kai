import Chat from '@/components/Chat'

interface ChatPageProps {
  params: {
    chat_id: string
  }
}

export default function ChatPage({ params }: ChatPageProps) {
  return (
    <main className="h-screen w-screen overflow-hidden bg-white">
      <Chat chatId={params.chat_id} />
    </main>
  )
}
