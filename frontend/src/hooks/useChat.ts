import { useCallback } from 'react'
import { useStore } from '../store'
import { streamChat, api } from '../api/client'
import { Message } from '../types'
import { isStandaloneMode, streamDirect } from '../api/directChat'
import { isMobile } from '../platform'

export function useChat() {
  const {
    activeConversationId,
    messages,
    isStreaming,
    streamingContent,
    setActiveConversation,
    addMessage,
    setStreaming,
    appendStreamToken,
    clearStreamBuffer,
    addProactiveMessage,
    setConversations,
    openMapOverlay,
    setPendingConfirmation,
    clearPendingConfirmation,
    setActivePlan,
    clearActivePlan,
  } = useStore()

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isStreaming) return

      const tempUserMsg: Message = {
        id: Date.now(),
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      }
      addMessage(tempUserMsg)
      setStreaming(true)
      clearStreamBuffer()

      let convId = activeConversationId
      let finalContent = ''
      let receivedMessageParts = false

      // ── Standalone mobile: stream directly to the AI provider ─────────────
      if (isMobile && isStandaloneMode()) {
        try {
          const history = messages
            .filter(m => m.role === 'user' || m.role === 'assistant')
            .slice(-20)
            .map(m => ({ role: m.role as 'user' | 'assistant', content: m.content }))

          for await (const token of streamDirect(history, content)) {
            finalContent += token
            appendStreamToken(token)
          }

          if (finalContent.trim()) {
            addMessage({
              id: Date.now() + 1,
              role: 'assistant',
              content: finalContent,
              created_at: new Date().toISOString(),
            })
          }
        } catch (err: any) {
          addMessage({
            id: Date.now() + 2,
            role: 'assistant',
            content: `Something went wrong: ${err?.message ?? 'unknown error'}`,
            created_at: new Date().toISOString(),
          })
        } finally {
          setStreaming(false)
          clearStreamBuffer()
        }
        return
      }

      // ── Backend mode ──────────────────────────────────────────────────────
      try {
        for await (const event of streamChat(content, convId ?? undefined)) {
          if (event.type === 'meta') {
            convId = event.conversation_id
            setActiveConversation(convId)
          } else if (event.type === 'token') {
            finalContent += event.token
            appendStreamToken(event.token)
          } else if (event.type === 'message_part') {
            receivedMessageParts = true
            clearStreamBuffer()
            const lunaMsg: Message = {
              id: Date.now() + Math.random(),
              role: 'assistant',
              content: event.content,
              created_at: new Date().toISOString(),
            }
            addMessage(lunaMsg)
          } else if (event.type === 'error') {
            finalContent = `Sorry, I ran into an issue: ${event.message}`
            appendStreamToken(finalContent)
          } else if (event.type === 'proactive') {
            addProactiveMessage(event.message)
          } else if (event.type === 'commands') {
            const awayCmds: any[] = event.commands?.filter((c: any) => c.type === 'away') ?? []
            if (awayCmds.some((c: any) => c.action === 'on')) useStore.getState().enterAwayMode()
            const widgetCmd = event.commands?.find((c: any) => c.type === 'widget')
            if (widgetCmd) {
              useStore.getState().openDynamicWidget({
                kind: widgetCmd.kind ?? 'summary',
                title: widgetCmd.title ?? 'Visual',
                body: widgetCmd.body ?? '',
              })
            }
            const mapCmds: any[] = event.commands?.filter((c: any) => c.type === 'map') ?? []
            if (mapCmds.some((c: any) => c.action === 'close')) {
              useStore.getState().closeMapOverlay()
            } else if (mapCmds.some((c: any) => c.action === 'search')) {
              const cmd = mapCmds.find((c: any) => c.action === 'search')
              openMapOverlay()
              useStore.getState().setMapPendingSearch(cmd.query ?? null)
            } else if (mapCmds.some((c: any) => c.action === 'route')) {
              const cmd = mapCmds.find((c: any) => c.action === 'route')
              openMapOverlay()
              useStore.getState().setMapPendingRoute(cmd.query ?? null)
            } else if (mapCmds.length > 0) {
              openMapOverlay()
            }
          } else if (event.type === 'confirmation_required') {
            setPendingConfirmation({
              confirm_id: event.confirm_id,
              message: event.message,
              tool: event.tool,
              args: event.args ?? {},
            })
          } else if (event.type === 'plan') {
            setActivePlan({ steps: event.steps, current: 0, total: event.total })
          } else if (event.type === 'plan_progress') {
            const cur = useStore.getState().activePlan
            if (cur) setActivePlan({ ...cur, current: event.step as number })
          } else if (event.type === 'plan_done') {
            clearActivePlan()
          } else if (event.type === 'done') {
            convId = event.conversation_id
            setActiveConversation(convId)
            clearPendingConfirmation()
          }
        }

        // Add completed Luna message (skip if empty)
        if (finalContent.trim() && !receivedMessageParts) {
          const lunaMsg: Message = {
            id: Date.now() + 1,
            role: 'assistant',
            content: finalContent,
            created_at: new Date().toISOString(),
          }
          addMessage(lunaMsg)
        }

        // Refresh conversation list
        const convs = await api.listConversations()
        setConversations(convs)
      } catch (err) {
        const isNetwork = err instanceof TypeError
        const errMsg: Message = {
          id: Date.now() + 2,
          role: 'assistant',
          content: isNetwork
            ? "Luna's backend isn't responding. Try restarting the app. If chat still fails, check Settings › Models to make sure a model is configured."
            : `Something went wrong: ${(err as any)?.message ?? 'unknown error'}`,
          created_at: new Date().toISOString(),
        }
        addMessage(errMsg)
      } finally {
        setStreaming(false)
        clearStreamBuffer()
      }
    },
    [activeConversationId, isStreaming, addMessage, setStreaming, appendStreamToken, clearStreamBuffer, addProactiveMessage, openMapOverlay, setActiveConversation, setConversations, setPendingConfirmation, clearPendingConfirmation, setActivePlan, clearActivePlan]
  )

  const loadConversation = useCallback(async (id: number) => {
    const conv = await api.getConversation(id)
    useStore.getState().setMessages(conv.messages ?? [])
    setActiveConversation(id)
    await api.setChatContext(id).catch(() => {})
  }, [setActiveConversation])

  const newConversation = useCallback(async () => {
    useStore.getState().setMessages([])
    setActiveConversation(null)
    await api.setChatContext(null).catch(() => {})
  }, [setActiveConversation])

  return { sendMessage, loadConversation, newConversation, messages, isStreaming, streamingContent }
}
