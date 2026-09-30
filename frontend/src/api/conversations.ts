import apiClient from './client'
import {
  Conversation,
  ConversationDetail,
  ConversationCreateRequest,
  MessageCreateRequest,
  ConversationalRAGResponse,
} from '../types'

export interface ListConversationsParams {
  user_id: string
  skip?: number
  limit?: number
}

export const conversationsApi = {
  async createConversation(request: ConversationCreateRequest): Promise<Conversation> {
    const response = await apiClient.post<Conversation>('/api/v1/conversations', request)
    return response.data
  },

  async listConversations(params: ListConversationsParams): Promise<Conversation[]> {
    const response = await apiClient.get<Conversation[]>('/api/v1/conversations', { params })
    return response.data
  },

  async getConversation(conversationId: string): Promise<ConversationDetail> {
    const response = await apiClient.get<ConversationDetail>(`/api/v1/conversations/${conversationId}`)
    return response.data
  },

  async sendMessage(conversationId: string, request: MessageCreateRequest): Promise<ConversationalRAGResponse> {
    const response = await apiClient.post<ConversationalRAGResponse>(
      `/api/v1/conversations/${conversationId}/messages`,
      request
    )
    return response.data
  },
}
