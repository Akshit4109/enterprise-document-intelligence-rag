import React, { useEffect, useState, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Bot,
  Send,
  Sparkles,
  Plus,
  ShieldCheck,
  Cpu,
  Layers,
  FileText,
  AlertCircle,
  SlidersHorizontal,
} from 'lucide-react'
import { conversationsApi, ragApi } from '../api'
import {
  Conversation,
  ConversationDetail,
  Message,
  CitationSource,
  ConversationalRAGResponse,
} from '../types'
import { Card } from '../components/common/Card'
import { Button } from '../components/common/Button'
import { Badge } from '../components/common/Badge'
import { ConversationList } from '../components/chat/ConversationList'
import { ChatMessage } from '../components/chat/ChatMessage'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { ErrorBanner } from '../components/common/ErrorBanner'

export interface AssistantPageProps {
  currentUserId: string
}

export const AssistantPage: React.FC<AssistantPageProps> = ({ currentUserId }) => {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversation, setActiveConversation] = useState<ConversationDetail | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [messageCitations, setMessageCitations] = useState<Record<string, CitationSource[]>>({})
  const [messageTelemetry, setMessageTelemetry] = useState<Record<string, Record<string, unknown>>>({})
  const [messageGrounded, setMessageGrounded] = useState<Record<string, boolean>>({})

  const [inputQuestion, setInputQuestion] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Retrieval hyperparameters
  const [topK, setTopK] = useState(5)
  const [similarityThreshold, setSimilarityThreshold] = useState(0.25)
  const [showOptions, setShowOptions] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isSending])

  // Load user conversations
  const loadConversations = async (preferredConvId?: string) => {
    setIsLoadingHistory(true)
    try {
      const list = await conversationsApi.listConversations({ user_id: currentUserId, limit: 30 })
      setConversations(list)

      const targetId = preferredConvId || searchParams.get('c') || (list.length > 0 ? list[0].id : null)

      if (targetId) {
        await selectConversation(targetId)
      } else {
        setActiveConversation(null)
        setMessages([])
      }
    } catch (err: any) {
      console.error('Error loading conversations', err)
    } finally {
      setIsLoadingHistory(false)
    }
  }

  useEffect(() => {
    loadConversations()
  }, [currentUserId])

  const selectConversation = async (convId: string) => {
    try {
      const detail = await conversationsApi.getConversation(convId)
      setActiveConversation(detail)
      setMessages(detail.messages || [])
      setSearchParams({ c: convId })
    } catch (err: any) {
      console.error('Error loading conversation details', err)
    }
  }

  const handleNewConversation = async () => {
    try {
      const newConv = await conversationsApi.createConversation({
        user_id: currentUserId,
        title: 'New Conversation',
      })
      setConversations((prev) => [newConv, ...prev])
      await selectConversation(newConv.id)
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to create new conversation.')
    }
  }

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!inputQuestion.trim() || isSending) return

    const questionText = inputQuestion.trim()
    setInputQuestion('')
    setIsSending(true)
    setErrorMessage(null)

    // Ensure we have an active conversation
    let currentConvId = activeConversation?.id
    if (!currentConvId) {
      try {
        const newConv = await conversationsApi.createConversation({
          user_id: currentUserId,
          title: questionText.slice(0, 40),
        })
        setConversations((prev) => [newConv, ...prev])
        setActiveConversation({
          id: newConv.id,
          user_id: newConv.user_id,
          title: newConv.title,
          created_at: newConv.created_at,
          updated_at: newConv.updated_at,
          messages: [],
        })
        currentConvId = newConv.id
        setSearchParams({ c: newConv.id })
      } catch (err: any) {
        setErrorMessage(err.message || 'Failed to initialize conversation session.')
        setIsSending(false)
        return
      }
    }

    // Optimistically add user message
    const tempUserMsg: Message = {
      id: `temp-${Date.now()}`,
      conversation_id: currentConvId,
      role: 'user',
      content: questionText,
      message_metadata: {},
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, tempUserMsg])

    try {
      const response: ConversationalRAGResponse = await conversationsApi.sendMessage(
        currentConvId,
        {
          content: questionText,
          top_k: topK,
          similarity_threshold: similarityThreshold,
        }
      )

      // Replace messages with confirmed server records
      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== tempUserMsg.id)
        return [...filtered, response.user_message, response.assistant_message]
      })

      // Store citations and telemetry
      if (response.assistant_message) {
        const msgId = response.assistant_message.id
        setMessageCitations((prev) => ({ ...prev, [msgId]: response.sources }))
        setMessageTelemetry((prev) => ({ ...prev, [msgId]: response.retrieval_metadata }))
        setMessageGrounded((prev) => ({ ...prev, [msgId]: response.is_grounded }))
      }

      // Refresh conversation list to update title and message count
      const updatedList = await conversationsApi.listConversations({ user_id: currentUserId, limit: 30 })
      setConversations(updatedList)
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to generate RAG response.')
    } finally {
      setIsSending(false)
    }
  }

  const handleCitationClick = (citation: CitationSource) => {
    const pageParam = citation.page_number
      ? `?page=${citation.page_number}&chunk=${citation.chunk_id}`
      : `?chunk=${citation.chunk_id}`
    navigate(`/documents/${citation.document_id}${pageParam}`)
  }

  const suggestedPrompts = [
    'What does the compliance guideline say about cryptographic key rotation?',
    'Which database extension is used for high-dimensional vector embeddings?',
    'What is our access control policy for multi-department document isolation?',
    'Explain the distributed consensus protocols documented in our architecture.',
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '20px', height: 'calc(100vh - 110px)' }}>
      {/* Left Conversations Sidebar */}
      <ConversationList
        conversations={conversations}
        selectedConversationId={activeConversation?.id}
        onSelectConversation={(conv) => selectConversation(conv.id)}
        onNewConversation={handleNewConversation}
        isLoading={isLoadingHistory}
      />

      {/* Main Chat Interface */}
      <div
        className="card"
        style={{
          padding: 0,
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflow: 'hidden',
          backgroundColor: 'var(--bg-surface)',
        }}
      >
        {/* Chat Header */}
        <div
          className="flex items-center justify-between p-4"
          style={{
            borderBottom: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-sidebar)',
          }}
        >
          <div className="flex items-center gap-2">
            <Bot size={20} style={{ color: 'var(--primary)' }} />
            <div>
              <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)' }}>
                {activeConversation?.title || 'Enterprise RAG Assistant'}
              </div>
              <div className="text-muted text-xs">
                Stateful LangGraph • Verified Provenance • Citations
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant={showOptions ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setShowOptions(!showOptions)}
              icon={<SlidersHorizontal size={14} />}
            >
              RAG Parameters
            </Button>
          </div>
        </div>

        {/* Hyperparameter Settings Drawer */}
        {showOptions && (
          <div
            style={{
              padding: '12px 20px',
              backgroundColor: 'var(--bg-input)',
              borderBottom: '1px solid var(--border-strong)',
              display: 'flex',
              alignItems: 'center',
              gap: '24px',
              fontSize: '13px',
            }}
          >
            <div className="flex items-center gap-2">
              <span className="text-secondary text-xs">Top K Context:</span>
              <select
                className="select"
                style={{ padding: '4px 8px', fontSize: '12px', width: 'auto' }}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
              >
                <option value={3}>3 Chunks</option>
                <option value={5}>5 Chunks</option>
                <option value={10}>10 Chunks</option>
              </select>
            </div>

            <div className="flex items-center gap-2" style={{ flex: 1, maxWidth: '280px' }}>
              <span className="text-secondary text-xs">Relevance Cutoff ({similarityThreshold.toFixed(2)}):</span>
              <input
                type="range"
                min="0.0"
                max="0.8"
                step="0.05"
                value={similarityThreshold}
                onChange={(e) => setSimilarityThreshold(Number(e.target.value))}
                style={{ flex: 1, accentColor: 'var(--primary)' }}
              />
            </div>
          </div>
        )}

        {/* Error Alert */}
        {errorMessage && (
          <div style={{ padding: '12px 16px' }}>
            <ErrorBanner message="Assistant Error" details={errorMessage} />
          </div>
        )}

        {/* Messages Stream Container */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {messages.length === 0 && !isSending ? (
            <div className="flex flex-col items-center justify-center p-8 gap-4" style={{ height: '100%' }}>
              <div className="brand-badge" style={{ width: '48px', height: '48px', fontSize: '24px' }}>
                <Sparkles size={24} />
              </div>
              <div className="text-center">
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  How can I help with your enterprise documents today?
                </h3>
                <p className="text-secondary text-sm" style={{ marginTop: '4px', maxWidth: '480px' }}>
                  Ask natural language questions across your ingested knowledge base. Answers include verified citation provenance linking to specific pages and chunks.
                </p>
              </div>

              {/* Suggestions */}
              <div className="flex flex-col gap-2" style={{ width: '100%', maxWidth: '520px', marginTop: '12px' }}>
                <span className="text-muted text-xs font-semibold uppercase">Example Questions:</span>
                {suggestedPrompts.map((prompt, idx) => (
                  <button
                    key={idx}
                    className="card text-left"
                    style={{
                      padding: '10px 14px',
                      fontSize: '13px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      backgroundColor: 'var(--bg-sidebar)',
                    }}
                    onClick={() => {
                      setInputQuestion(prompt)
                    }}
                  >
                    "{prompt}"
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div>
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  citations={messageCitations[msg.id] || []}
                  isGrounded={messageGrounded[msg.id] !== undefined ? messageGrounded[msg.id] : true}
                  retrievalMetadata={messageTelemetry[msg.id]}
                  onCitationClick={handleCitationClick}
                />
              ))}

              {isSending && (
                <div className="chat-msg assistant">
                  <div className="chat-avatar assistant">
                    <Bot size={18} />
                  </div>
                  <div className="chat-bubble">
                    <div className="flex items-center gap-2">
                      <LoadingSpinner label="Evaluating documents & synthesizing grounded answer..." size={16} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Form Bar */}
        <form
          onSubmit={handleSendMessage}
          className="flex items-center gap-3 p-4"
          style={{
            borderTop: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-sidebar)',
          }}
        >
          <input
            type="text"
            className="input"
            style={{ height: '44px', fontSize: '14px' }}
            placeholder="Ask a question about your enterprise documents... (e.g. key rotation policy)"
            value={inputQuestion}
            onChange={(e) => setInputQuestion(e.target.value)}
            disabled={isSending}
          />
          <Button
            type="submit"
            variant="primary"
            disabled={!inputQuestion.trim() || isSending}
            isLoading={isSending}
            icon={<Send size={16} />}
            style={{ height: '44px', padding: '0 20px' }}
          >
            Ask
          </Button>
        </form>
      </div>
    </div>
  )
}

export default AssistantPage
