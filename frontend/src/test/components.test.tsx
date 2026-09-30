import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Badge } from '../components/common/Badge'
import { Button } from '../components/common/Button'
import { DocumentTable } from '../components/documents/DocumentTable'
import { SearchResultCard } from '../components/search/SearchResultCard'
import { CitationCard } from '../components/chat/CitationCard'
import { ChatMessage } from '../components/chat/ChatMessage'
import { SearchBar } from '../components/search/SearchBar'
import { Document, RetrievedChunk, CitationSource, Message } from '../types'

describe('Enterprise Frontend Component Suites', () => {
  it('renders SearchBar with hybrid_reranked mode option and triggers onSearch', () => {
    const handleSearch = vi.fn()
    render(<SearchBar onSearch={handleSearch} initialQuery="test query" />)

    // Open filters
    const filterBtn = screen.getByRole('button', { name: /filters/i })
    fireEvent.click(filterBtn)

    // Mode dropdown should contain hybrid_reranked option
    const selects = screen.getAllByRole('combobox')
    const modeSelect = selects[0] as HTMLSelectElement
    expect(modeSelect).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Hybrid \+ Reranker \(Cross-Encoder\)/i })).toBeInTheDocument()

    // Change mode to hybrid_reranked
    fireEvent.change(modeSelect, { target: { value: 'hybrid_reranked' } })

    // Submit search
    const submitBtn = screen.getByRole('button', { name: /search/i })
    fireEvent.click(submitBtn)

    expect(handleSearch).toHaveBeenCalledWith(
      'test query',
      5,
      0.25,
      undefined,
      'hybrid_reranked'
    )
  })

  it('renders Badge with custom variants and icons', () => {
    render(<Badge variant="green">Active</Badge>)
    const badge = screen.getByText('Active')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('badge-green')
  })

  it('renders Button with loading state and handles clicks', () => {
    const handleClick = vi.fn()
    const { rerender } = render(
      <Button variant="primary" onClick={handleClick}>
        Submit
      </Button>
    )
    const btn = screen.getByRole('button', { name: /submit/i })
    expect(btn).toBeInTheDocument()
    fireEvent.click(btn)
    expect(handleClick).toHaveBeenCalledTimes(1)

    rerender(
      <Button variant="primary" isLoading={true} onClick={handleClick}>
        Submit
      </Button>
    )
    expect(btn).toBeDisabled()
  })

  it('renders DocumentTable with document rows and triggers navigation callback', () => {
    const sampleDocs: Document[] = [
      {
        id: 'doc-123',
        name: 'Enterprise Architecture Overview',
        description: 'Comprehensive design specifications',
        document_type: 'pdf',
        owner_id: 'usr_eng_lead',
        department: 'Engineering',
        tags: ['architecture', 'pgvector'],
        extra_metadata: {},
        status: 'active',
        created_at: '2026-09-02T10:00:00Z',
        updated_at: '2026-09-02T10:00:00Z',
      },
    ]

    const onSelect = vi.fn()
    render(
      <MemoryRouter>
        <DocumentTable documents={sampleDocs} onSelectDocument={onSelect} />
      </MemoryRouter>
    )

    expect(screen.getByText('Enterprise Architecture Overview')).toBeInTheDocument()
    expect(screen.getByText('PDF')).toBeInTheDocument()
    expect(screen.getByText('usr_eng_lead')).toBeInTheDocument()

    const row = screen.getByText('Enterprise Architecture Overview').closest('tr')
    if (row) fireEvent.click(row)
    expect(onSelect).toHaveBeenCalledWith(sampleDocs[0])
  })

  it('renders SearchResultCard with similarity score and handles inspect navigation', () => {
    const sampleResult: RetrievedChunk = {
      chunk_id: 'chunk-456',
      document_id: 'doc-123',
      document_name: 'Security Guidelines',
      document_version_id: 'ver-789',
      version_number: 1,
      page_number: 4,
      source_filename: 'security_guidelines.pdf',
      content: 'Cryptographic encryption keys must be rotated every 90 days.',
      similarity_score: 0.845,
      chunk_index: 2,
      metadata: {},
      citation_label: '[1]',
    }

    const onNav = vi.fn()
    render(
      <MemoryRouter>
        <SearchResultCard result={sampleResult} onNavigate={onNav} />
      </MemoryRouter>
    )

    expect(screen.getByText('Security Guidelines')).toBeInTheDocument()
    expect(screen.getByText(/Cryptographic encryption keys/)).toBeInTheDocument()
    expect(screen.getByText(/Similarity: 0.8450/)).toBeInTheDocument()
    expect(screen.getByText('Page 4')).toBeInTheDocument()

    const inspectBtn = screen.getByRole('button', { name: /inspect/i })
    fireEvent.click(inspectBtn)
    expect(onNav).toHaveBeenCalledWith('doc-123', 4, 'chunk-456')
  })

  it('renders CitationCard with provenance details and triggers deep link', () => {
    const citation: CitationSource = {
      source_index: 1,
      document_id: 'doc-999',
      document_name: 'Compliance Handbook',
      document_version_id: 'ver-888',
      version_number: 2,
      page_number: 12,
      source_filename: 'compliance.pdf',
      chunk_id: 'chunk-111',
      similarity_score: 0.91,
      snippet: 'MFA is required for all administrative access.',
      citation_label: '[1]',
    }

    const onCitationClick = vi.fn()
    render(
      <MemoryRouter>
        <CitationCard citation={citation} onNavigateToCitation={onCitationClick} />
      </MemoryRouter>
    )

    expect(screen.getByText('Compliance Handbook')).toBeInTheDocument()
    expect(screen.getByText('Page 12')).toBeInTheDocument()
    expect(screen.getByText('v2')).toBeInTheDocument()
    expect(screen.getByText(/MFA is required/)).toBeInTheDocument()

    const card = screen.getByText('Compliance Handbook').closest('.citation-card')
    if (card) fireEvent.click(card)
    expect(onCitationClick).toHaveBeenCalledWith(citation)
  })

  it('renders ChatMessage with citation markers and metadata badge', () => {
    const message: Message = {
      id: 'msg-1',
      conversation_id: 'conv-1',
      role: 'assistant',
      content: 'According to the compliance guidelines [1], encryption keys are rotated periodically.',
      message_metadata: { engine: 'langgraph', retry_attempts: 1 },
      created_at: '2026-09-02T12:00:00Z',
    }

    const citations: CitationSource[] = [
      {
        source_index: 1,
        document_id: 'doc-999',
        document_name: 'Compliance Handbook',
        document_version_id: 'ver-888',
        version_number: 1,
        page_number: 3,
        source_filename: 'compliance.pdf',
        chunk_id: 'chunk-111',
        similarity_score: 0.88,
        snippet: 'Keys must be rotated every 90 days.',
        citation_label: '[1]',
      },
    ]

    const onCitationClick = vi.fn()
    render(
      <MemoryRouter>
        <ChatMessage
          message={message}
          citations={citations}
          isGrounded={true}
          retrievalMetadata={{ engine: 'langgraph' }}
          onCitationClick={onCitationClick}
        />
      </MemoryRouter>
    )

    expect(screen.getByText(/According to the compliance guidelines/)).toBeInTheDocument()
    expect(screen.getByText('Grounded Answer')).toBeInTheDocument()
    expect(screen.getByText('langgraph')).toBeInTheDocument()

    const citationBadge = screen.getByRole('button', { name: '[1]' })
    expect(citationBadge).toBeInTheDocument()
    fireEvent.click(citationBadge)
    expect(onCitationClick).toHaveBeenCalledWith(citations[0])
  })
})
