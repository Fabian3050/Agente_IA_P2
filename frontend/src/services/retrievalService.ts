import { ms1Client } from './api'
import type { ApiSource, CandidateMatch } from '../types'

export const retrievalService = {
  async getSources(): Promise<any[]> {
    try {
      const res = await ms1Client.get<any[]>('/sources')
      return res.data.map((s) => ({
        id: s.id,
        name: s.name || s.api_name || 'API',
        status: s.status || 'Conectado',
        latency: s.latency ? `${s.latency}` : '120ms',
        queries: s.queries_total ?? s.queries ?? 0,
        recovered: s.success_total ?? s.recovered ?? 0,
        availability: s.availability_pct ?? 99.8,
        lastQuery: s.last_query || 'Reciente',
        docUrl: s.doc_url || 'https://scholar.google.com',
        avgScore: s.avg_match_score || 0.0
      }))
    } catch {
      return []
    }
  },

  async pingSource(sourceName: string): Promise<{
    source: string
    status: string
    latency_ms: number
    available: boolean
    message: string
  }> {
    try {
      const res = await ms1Client.get(`/sources/${encodeURIComponent(sourceName)}/ping`)
      return res.data
    } catch (err: any) {
      return {
        source: sourceName,
        status: 'Error',
        latency_ms: 0,
        available: false,
        message: err.message || 'Error de conexión'
      }
    }
  },

  async retrieveByDoiOrTitle(itemId: string, doi?: string, title?: string): Promise<{
    outcome: string
    max_score: number
    best_source?: string
    consolidated?: any
    candidates?: CandidateMatch[]
  }> {
    const res = await ms1Client.post('/retrieve', {
      item_id: itemId,
      doi: doi || '',
      title: title || ''
    })
    return res.data
  }
}

