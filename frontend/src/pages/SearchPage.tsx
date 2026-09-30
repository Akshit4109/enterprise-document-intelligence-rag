import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Sparkles, Clock, Zap, Layers, AlertCircle, Cpu } from 'lucide-react'
import { searchApi } from '../api'
import { SearchResponse, RetrievalFilter } from '../types'
import { Card } from '../components/common/Card'
import { Badge } from '../components/common/Badge'
import { SearchBar } from '../components/search/SearchBar'
import { SearchResultCard } from '../components/search/SearchResultCard'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { EmptyState } from '../components/common/EmptyState'
import { ErrorBanner } from '../components/common/ErrorBanner'

export const SearchPage: React.FC = () => {
  const navigate = useNavigate()
  const [searchResponse, setSearchResponse] = useState<SearchResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [lastQuery, setLastQuery] = useState('')

  const handleSearch = async (
    query: string,
    topK: number,
    threshold?: number,
    filters?: RetrievalFilter,
    mode?: "auto" | "dense" | "keyword" | "hybrid" | "hybrid_reranked"
  ) => {
    setIsLoading(true)
    setErrorMessage(null)
    setLastQuery(query)
    try {
      const res = await searchApi.semanticSearch({
        query,
        top_k: topK,
        similarity_threshold: threshold,
        filters,
        mode: mode === "auto" ? undefined : mode,
      })
      setSearchResponse(res)
    } catch (err: any) {
      setErrorMessage(err.message || 'Search execution failed.')
    } finally {
      setIsLoading(false)
    }
  }

  const sampleQueries = [
    'What is the policy for cryptographic key rotation?',
    'Which database extension stores vector embeddings?',
    'Who is Harry?',
    'How are access control policies enforced per department?',
  ]

  return (
    <div className="flex flex-col gap-6">
      {/* Top Header */}
      <div>
        <h1 style={{ fontSize: '20px', fontWeight: 700 }}>Advanced Hybrid Search Console</h1>
        <p className="text-secondary text-sm">
          Execute dense vector search (pgvector), keyword search (PostgreSQL FTS), and Reciprocal Rank Fusion (RRF) with neural reranking.
        </p>
      </div>

      {/* Search Input Bar */}
      <SearchBar onSearch={handleSearch} isLoading={isLoading} />

      {/* Suggested Queries Chips */}
      {!searchResponse && !isLoading && (
        <div className="flex items-center gap-2" style={{ flexWrap: 'wrap' }}>
          <span className="text-muted text-xs flex items-center gap-1">
            <Sparkles size={13} style={{ color: 'var(--accent-cyan)' }} />
            Suggested Queries:
          </span>
          {sampleQueries.map((sq, idx) => (
            <button
              key={idx}
              className="btn btn-outline btn-sm"
              style={{ fontSize: '12px', padding: '4px 10px', borderRadius: 'var(--radius-full)' }}
              onClick={() => handleSearch(sq, 5, 0.25)}
            >
              {sq}
            </button>
          ))}
        </div>
      )}

      {errorMessage && (
        <ErrorBanner
          message="Search Failed"
          details={errorMessage}
          onRetry={() => lastQuery && handleSearch(lastQuery, 5)}
        />
      )}

      {/* Results Container */}
      {isLoading ? (
        <LoadingSpinner label="Retrieving & reranking knowledge chunks..." />
      ) : searchResponse ? (
        <div className="flex flex-col gap-4">
          {/* Telemetry Bar */}
          <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: '8px' }}>
            <div className="flex items-center gap-2 text-sm">
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                {searchResponse.total_results} matching chunks found
              </span>
              <span className="text-muted">for query "{searchResponse.query}"</span>
            </div>

            <div className="flex items-center gap-2">
              <Badge variant="green" icon={<Clock size={12} />}>
                {searchResponse.execution_time_ms.toFixed(1)}ms Latency
              </Badge>
              <Badge variant="purple" icon={<Layers size={12} />}>
                Mode: {searchResponse.retrieval_mode || 'hybrid'}
              </Badge>
            </div>
          </div>

          {searchResponse.results.length > 0 ? (
            <div className="flex flex-col gap-3">
              {searchResponse.results.map((result) => (
                <SearchResultCard
                  key={result.chunk_id}
                  result={result}
                  onNavigate={(docId, pageNum, chunkId) => {
                    const queryP = pageNum ? `?page=${pageNum}&chunk=${chunkId}` : `?chunk=${chunkId}`
                    navigate(`/documents/${docId}${queryP}`)
                  }}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<Search size={36} />}
              title="No relevant chunks passed the threshold"
              description="Try adjusting your query phrasing or lowering the relevance cutoff slider in Filters."
            />
          )}
        </div>
      ) : null}
    </div>
  )
}

export default SearchPage
