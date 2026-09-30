import React, { useState, useRef } from 'react'
import { Upload, FileUp, CheckCircle2, AlertCircle, FileText, Sparkles } from 'lucide-react'
import { documentsApi } from '../../api'
import { DocumentUploadResponse, ParsedSummary } from '../../types'
import { Modal } from '../common/Modal'
import { Button } from '../common/Button'
import { Badge } from '../common/Badge'

export interface DocumentUploadModalProps {
  isOpen: boolean
  onClose: () => void
  onUploadSuccess: (res: DocumentUploadResponse) => void
  currentUserId: string
}

export const DocumentUploadModal: React.FC<DocumentUploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
  currentUserId,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [department, setDepartment] = useState('Engineering')
  const [tagsInput, setTagsInput] = useState('')
  const [chunkSize, setChunkSize] = useState(500)
  const [chunkOverlap, setChunkOverlap] = useState(50)
  const [isUploading, setIsUploading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [uploadResult, setUploadResult] = useState<DocumentUploadResponse | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const resetForm = () => {
    setSelectedFile(null)
    setName('')
    setDescription('')
    setDepartment('Engineering')
    setTagsInput('')
    setErrorMessage(null)
    setUploadResult(null)
  }

  const handleClose = () => {
    resetForm()
    onClose()
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      setSelectedFile(file)
      if (!name) {
        setName(file.name.replace(/\.[^/.]+$/, ''))
      }
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleDragLeave = () => {
    setIsDragOver(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0]
      setSelectedFile(file)
      if (!name) {
        setName(file.name.replace(/\.[^/.]+$/, ''))
      }
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFile) {
      setErrorMessage('Please select a file to upload.')
      return
    }

    setIsUploading(true)
    setErrorMessage(null)

    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0)

    try {
      const result = await documentsApi.uploadDocument({
        file: selectedFile,
        name: name || selectedFile.name,
        description: description || undefined,
        owner_id: currentUserId,
        department: department || undefined,
        tags: tags.length > 0 ? tags : undefined,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
      })

      setUploadResult(result)
      onUploadSuccess(result)
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to upload document.')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={uploadResult ? 'Document Ingestion Complete' : 'Upload Enterprise Document'}
      maxWidth="620px"
      footer={
        uploadResult ? (
          <Button variant="primary" onClick={handleClose}>
            Done
          </Button>
        ) : (
          <>
            <Button variant="outline" onClick={handleClose} disabled={isUploading}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleSubmit}
              isLoading={isUploading}
              icon={<FileUp size={16} />}
              disabled={!selectedFile}
            >
              {isUploading ? 'Parsing & Embedding...' : 'Ingest Document'}
            </Button>
          </>
        )
      }
    >
      {uploadResult ? (
        <div className="flex flex-col gap-4">
          <div
            className="flex items-center gap-3 p-4"
            style={{
              backgroundColor: 'var(--success-light)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
            }}
          >
            <CheckCircle2 size={24} style={{ color: 'var(--success)', flexShrink: 0 }} />
            <div>
              <div style={{ fontWeight: 600, color: '#6ee7b7' }}>{uploadResult.message}</div>
              <div className="text-secondary text-xs">
                Document "{uploadResult.document.name}" (Version {uploadResult.version.version_number}) is ready for vector retrieval.
              </div>
            </div>
          </div>

          <div className="card" style={{ backgroundColor: 'var(--bg-input)' }}>
            <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Sparkles size={15} style={{ color: 'var(--accent-cyan)' }} />
              Parsing & Vectorization Summary
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '14px' }}>
              <div className="flex flex-col">
                <span className="text-muted text-xs">Total Pages</span>
                <span style={{ fontWeight: 600, fontSize: '16px' }}>{uploadResult.parsing_summary.total_pages}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-muted text-xs">Word Count</span>
                <span style={{ fontWeight: 600, fontSize: '16px' }}>{uploadResult.parsing_summary.word_count}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-muted text-xs">Generated Chunks</span>
                <span style={{ fontWeight: 600, fontSize: '16px', color: 'var(--accent-cyan)' }}>
                  {uploadResult.parsing_summary.chunk_count}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 mb-2">
              <Badge variant="purple">
                {uploadResult.parsing_summary.embedding_model || 'sentence-transformers/all-MiniLM-L6-v2'}
              </Badge>
              <Badge variant="blue">
                {uploadResult.parsing_summary.embedding_dimension || 384}d Dense Vectors
              </Badge>
            </div>

            {uploadResult.parsing_summary.preview_text && (
              <div style={{ marginTop: '10px' }}>
                <span className="text-muted text-xs">Content Preview:</span>
                <p
                  style={{
                    fontSize: '12.5px',
                    color: 'var(--text-secondary)',
                    backgroundColor: 'rgba(15, 23, 42, 0.5)',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-sm)',
                    marginTop: '4px',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {uploadResult.parsing_summary.preview_text}
                </p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {errorMessage && (
            <div
              className="flex items-center gap-2 p-3 text-sm"
              style={{
                backgroundColor: 'var(--danger-light)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: 'var(--radius-md)',
                color: '#fca5a5',
              }}
            >
              <AlertCircle size={16} />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Drag & Drop File Zone */}
          <div
            className={`dropzone ${isDragOver ? 'dragover' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".pdf,.docx,.txt"
              style={{ display: 'none' }}
              aria-label="Upload document file"
            />
            {selectedFile ? (
              <div className="flex flex-col items-center gap-2">
                <FileText size={36} style={{ color: 'var(--primary)' }} />
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{selectedFile.name}</div>
                  <div className="text-muted text-xs">
                    {(selectedFile.size / 1024).toFixed(1)} KB • Click or drop to replace
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <Upload size={32} style={{ color: 'var(--text-muted)' }} />
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    Drop your PDF, DOCX, or TXT file here
                  </div>
                  <div className="text-muted text-xs" style={{ marginTop: '2px' }}>
                    or click to browse local filesystem (Max 25 MB)
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Form Metadata */}
          <div className="form-group">
            <label className="form-label">Document Display Name</label>
            <input
              type="text"
              className="input"
              placeholder="e.g. Platform Architecture & Security Guidelines"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
            <div className="form-group">
              <label className="form-label">Department</label>
              <select
                className="select"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
              >
                <option value="Engineering">Engineering</option>
                <option value="Security">Security</option>
                <option value="HR">HR</option>
                <option value="Legal">Legal</option>
                <option value="Finance">Finance</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Classification Tags (comma-separated)</label>
              <input
                type="text"
                className="input"
                placeholder="e.g. security, pgvector, compliance"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Description (Optional)</label>
            <textarea
              className="textarea"
              placeholder="Brief summary of document purpose..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              style={{ minHeight: '60px' }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
            <div className="form-group">
              <label className="form-label">Chunk Size (chars)</label>
              <input
                type="number"
                className="input"
                value={chunkSize}
                onChange={(e) => setChunkSize(Number(e.target.value))}
                min={100}
                max={2000}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Chunk Overlap (chars)</label>
              <input
                type="number"
                className="input"
                value={chunkOverlap}
                onChange={(e) => setChunkOverlap(Number(e.target.value))}
                min={0}
                max={500}
              />
            </div>
          </div>
        </form>
      )}
    </Modal>
  )
}

export default DocumentUploadModal
