import React from 'react'
import { Bot, User, ShieldCheck, AlertCircle, Cpu } from 'lucide-react'
import { Message, CitationSource } from '../../types'
import { Badge } from '../common/Badge'
import CitationCard from './CitationCard'

export interface ChatMessageProps {
  message: Message
  citations?: CitationSource[]
  isGrounded?: boolean
  retrievalMetadata?: Record<string, unknown>
  onCitationClick?: (citation: CitationSource) => void
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  citations = [],
  isGrounded = true,
  retrievalMetadata,
  onCitationClick,
}) => {
  const isAssistant = message.role === 'assistant'

  const formattedTime = message.created_at
    ? new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : ''

  // Function to render text with clickable citation markers [1], [2], etc.
  const renderFormattedText = (text: string) => {
    const parts = text.split(/(\[\d+\])/g)
    return parts.map((part, index) => {
      const match = part.match(/^\[(\d+)\]$/)
      if (match) {
        const sourceIndex = parseInt(match[1], 10)
        const matchedCitation = citations.find((c) => c.source_index === sourceIndex)
        return (
          <button
            key={index}
            className="citation-badge"
            onClick={() => {
              if (matchedCitation && onCitationClick) {
                onCitationClick(matchedCitation)
              }
            }}
            title={matchedCitation ? `Jump to ${matchedCitation.document_name} Page ${matchedCitation.page_number || 1}` : `Citation ${sourceIndex}`}
          >
            [{sourceIndex}]
          </button>
        )
      }
      return <span key={index}>{part}</span>
    })
  }

  const engineName = (retrievalMetadata?.engine as string) || (message.message_metadata?.engine as string)
  const retryCount = (retrievalMetadata?.retry_attempts as number) || (message.message_metadata?.retry_attempts as number)

  return (
    <div className={`chat-msg ${message.role}`}>
      <div className={`chat-avatar ${message.role}`}>
        {isAssistant ? <Bot size={18} /> : <User size={18} />}
      </div>

      <div className="chat-bubble">
        <div className="chat-bubble-header">
          <div className="flex items-center gap-2">
            <span className="chat-sender">
              {isAssistant ? 'Document Intelligence Assistant' : 'You'}
            </span>
            {isAssistant && (
              <>
                {isGrounded ? (
                  <Badge variant="green" icon={<ShieldCheck size={11} />}>
                    Grounded Answer
                  </Badge>
                ) : (
                  <Badge variant="amber" icon={<AlertCircle size={11} />}>
                    Insufficient Context
                  </Badge>
                )}
                {engineName && (
                  <Badge variant="purple" icon={<Cpu size={11} />}>
                    {engineName}
                  </Badge>
                )}
                {retryCount && retryCount > 1 && (
                  <Badge variant="blue">
                    {retryCount} Queries Evaluated
                  </Badge>
                )}
              </>
            )}
          </div>
          {formattedTime && <span className="chat-timestamp">{formattedTime}</span>}
        </div>

        <div className="chat-text">
          <p>{renderFormattedText(message.content)}</p>
        </div>

        {/* Citations Section */}
        {isAssistant && citations.length > 0 && (
          <div style={{ marginTop: '16px' }}>
            <div
              style={{
                fontSize: '12px',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                marginBottom: '8px',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              Verified Sources & Citations ({citations.length})
            </div>
            <div className="flex flex-col gap-2">
              {citations.map((cit) => (
                <CitationCard
                  key={cit.source_index}
                  citation={cit}
                  onNavigateToCitation={onCitationClick}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default ChatMessage
