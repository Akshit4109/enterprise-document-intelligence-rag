import { CitationSource } from './rag'
import { RetrievalFilter } from './search'

export type MessageRole = 'user' | 'assistant' | 'system'

export interface Message {
  id: string
  conversation_id: string
  role: MessageRole
  content: string
  message_metadata: Record<string, unknown>
  created_at: string
}

export interface Conversation {
  id: string
  user_id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface ConversationDetail {
  id: string
  user_id: string
  title: string
  created_at: string
  updated_at: string
  messages: Message[]
}

export interface ConversationCreateRequest {
  user_id: string
  title?: string
}

export interface MessageCreateRequest {
  content: string
  top_k?: number
  similarity_threshold?: number
  filters?: RetrievalFilter
}

export interface ConversationalRAGResponse {
  conversation_id: string
  user_message: Message
  assistant_message: Message
  sources: CitationSource[]
  is_grounded: boolean
  retrieval_metadata: Record<string, unknown>
}
