import React, { useState } from 'react'
import { Search, SlidersHorizontal, ArrowRight } from 'lucide-react'
import { Button } from '../common/Button'
import { RetrievalFilter } from '../../types'

export interface SearchBarProps {
  onSearch: (
    query: string,
    topK: number,
    threshold?: number,
    filters?: RetrievalFilter,
    mode?: "auto" | "dense" | "keyword" | "hybrid" | "hybrid_reranked"
  ) => void
  isLoading?: boolean
  initialQuery?: string
  currentDepartment?: string
}

export const SearchBar: React.FC<SearchBarProps> = ({
  onSearch,
  isLoading,
  initialQuery = '',
  currentDepartment,
}) => {
  const [query, setQuery] = useState(initialQuery)
  const [showFilters, setShowFilters] = useState(false)
  const [topK, setTopK] = useState(5)
  const [threshold, setThreshold] = useState(0.25)
  const [mode, setMode] = useState<"auto" | "dense" | "keyword" | "hybrid" | "hybrid_reranked">("auto")
  const [selectedDept, setSelectedDept] = useState(currentDepartment || '')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    const filters: RetrievalFilter = {}
    if (selectedDept) filters.department = selectedDept

    onSearch(
      query.trim(),
      topK,
      threshold > 0 ? threshold : undefined,
      Object.keys(filters).length ? filters : undefined,
      mode
    )
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <div style={{ position: 'relative', flex: 1 }}>
          <Search
            size={18}
            style={{
              position: 'absolute',
              left: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--text-muted)',
            }}
          />
          <input
            type="text"
            className="input"
            style={{ paddingLeft: '38px', height: '44px', fontSize: '14.5px' }}
            placeholder="Search enterprise knowledge base via hybrid semantic and keyword retrieval..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Button
          type="button"
          variant={showFilters ? 'primary' : 'outline'}
          onClick={() => setShowFilters(!showFilters)}
          icon={<SlidersHorizontal size={16} />}
          style={{ height: '44px' }}
        >
          Filters
        </Button>
        <Button
          type="submit"
          variant="primary"
          isLoading={isLoading}
          icon={<ArrowRight size={16} />}
          style={{ height: '44px', padding: '0 20px' }}
        >
          Search
        </Button>
      </div>

      {showFilters && (
        <div
          className="card"
          style={{
            padding: '16px',
            backgroundColor: 'var(--bg-sidebar)',
            border: '1px solid var(--border-strong)',
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '16px',
          }}
        >
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Retrieval Mode</label>
            <select
              className="select"
              value={mode}
              onChange={(e) => setMode(e.target.value as any)}
            >
              <option value="auto">Auto (Configured Engine)</option>
              <option value="hybrid">Hybrid (Dense + FTS RRF)</option>
              <option value="hybrid_reranked">
                Hybrid + Reranker (Cross-Encoder)
              </option>
              <option value="dense">Dense Vector (pgvector)</option>
              <option value="keyword">Keyword Search (PostgreSQL FTS)</option>
            </select>
          </div>

          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Top Results (top_k): {topK}</label>
            <select
              className="select"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            >
              <option value={3}>Top 3 Chunks</option>
              <option value={5}>Top 5 Chunks</option>
              <option value={10}>Top 10 Chunks</option>
              <option value={20}>Top 20 Chunks</option>
            </select>
          </div>

          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">
              Relevance Cutoff: {threshold.toFixed(2)}
            </label>
            <input
              type="range"
              min="0.0"
              max="0.9"
              step="0.05"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--primary)', marginTop: '8px' }}
            />
          </div>

          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Filter Department</label>
            <select
              className="select"
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
            >
              <option value="">All Departments</option>
              <option value="Engineering">Engineering</option>
              <option value="Security">Security</option>
              <option value="HR">HR</option>
              <option value="Legal">Legal</option>
              <option value="Finance">Finance</option>
            </select>
          </div>
        </div>
      )}
    </form>
  )
}

export default SearchBar
