import React from 'react'
import { MessageSquare, Plus, Clock, ChevronRight } from 'lucide-react'
import { Conversation } from '../../types'
import { Button } from '../common/Button'
import { Badge } from '../common/Badge'

export interface ConversationListProps {
  conversations: Conversation[]
  selectedConversationId?: string | null
  onSelectConversation: (conv: Conversation) => void
  onNewConversation: () => void
  isLoading?: boolean
}

export const ConversationList: React.FC<ConversationListProps> = ({
  conversations,
  selectedConversationId,
  onSelectConversation,
  onNewConversation,
  isLoading,
}) => {
  return (
    <div
      className="card"
      style={{
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'var(--bg-sidebar)',
      }}
    >
      <div className="flex items-center justify-between" style={{ marginBottom: '16px' }}>
        <div className="flex items-center gap-2">
          <MessageSquare size={16} style={{ color: 'var(--primary)' }} />
          <span style={{ fontWeight: 600, fontSize: '13.5px' }}>Conversations</span>
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={onNewConversation}
          icon={<Plus size={14} />}
        >
          New Chat
        </Button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {conversations.length === 0 ? (
          <div className="text-center p-6 text-muted text-xs">
            No previous conversations. Start a new session above!
          </div>
        ) : (
          conversations.map((conv) => {
            const isSelected = conv.id === selectedConversationId
            const formattedDate = conv.updated_at
              ? new Date(conv.updated_at).toLocaleDateString([], {
                  month: 'short',
                  day: 'numeric',
                })
              : ''

            return (
              <div
                key={conv.id}
                onClick={() => onSelectConversation(conv)}
                style={{
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-md)',
                  cursor: 'pointer',
                  backgroundColor: isSelected ? 'var(--primary-light)' : 'transparent',
                  border: `1px solid ${isSelected ? 'var(--primary)' : 'transparent'}`,
                  transition: 'all 0.15s ease',
                }}
                className="flex items-center justify-between"
              >
                <div style={{ minWidth: 0, flex: 1, marginRight: '8px' }}>
                  <div
                    style={{
                      fontWeight: isSelected ? 600 : 500,
                      fontSize: '13px',
                      color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {conv.title || 'Untitled Conversation'}
                  </div>
                  <div className="flex items-center gap-1 text-muted text-xs" style={{ marginTop: '2px' }}>
                    <Clock size={10} />
                    <span>{formattedDate}</span>
                    <span>•</span>
                    <span>{conv.message_count} msgs</span>
                  </div>
                </div>

                <ChevronRight
                  size={14}
                  style={{ color: isSelected ? 'var(--primary)' : 'var(--text-muted)', flexShrink: 0 }}
                />
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

export default ConversationList
