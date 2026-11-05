import { useParams, useSearchParams } from 'react-router-dom'
import ChatPanel from '../components/ChatPanel'

/** Public assistant page. Works standalone and inside an iframe (?embed=1). No login required. */
export default function ChatPage() {
  const { token } = useParams()
  const [sp] = useSearchParams()
  const embedded = sp.get('embed') === '1'
  return embedded ? (
    <main className="flex h-[100dvh] flex-col"><ChatPanel token={token} embedded className="h-full" /></main>
  ) : (
    <main className="grid min-h-[100dvh] place-items-center bg-bg p-0 sm:p-6">
      <div className="flex h-[100dvh] w-full max-w-[560px] flex-col sm:h-[min(820px,92dvh)]"><ChatPanel token={token} className="h-full" /></div>
    </main>
  )
}
