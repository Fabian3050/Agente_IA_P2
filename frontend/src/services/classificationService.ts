import { ms2Client } from './api'

export interface OCDEItemResult {
  codigo: string
  nombre: string
  subarea?: string
  disciplina?: string
  prioridad: number
  justificacion?: string
  confidence_score: number
}

export interface ODSItemResult {
  numero: number
  nombre: string
  prioridad: number
  justificacion?: string
  confidence_score: number
}

export interface ClassificationResultResponse {
  item_id?: string
  area_ocde?: string[]
  area_ods?: string[]
  ocde_classifications: OCDEItemResult[]
  ods_classifications: ODSItemResult[]
  is_ocde_sufficient: boolean
  is_ods_sufficient: boolean
  ocde_reasoning?: string
  ods_reasoning?: string
  execution_time_total_ms: number
}

export interface ClassificationResult {
  code: string
  label: string
  confidence: number
  justification?: string
}

export const classificationService = {
  async getCategories(scheme: 'OCDE' | 'ODS' = 'OCDE') {
    try {
      const res = await ms2Client.get('/categories', { params: { scheme } })
      return res.data
    } catch {
      return []
    }
  },

  /**
   * Invoca el endpoint real de clasificación semántica unificada de MS2 (POST /classify).
   * Ejecuta la taxonomía jerárquica OCDE en 2 pasos y la clasificación ODS.
   */
  async classify(params: {
    title?: string
    abstract?: string
    keywords?: string
    itemId?: string
    temperature?: number
  }): Promise<ClassificationResultResponse | null> {
    try {
      const res = await ms2Client.post<ClassificationResultResponse>('/classify', {
        item_id: params.itemId || undefined,
        title: params.title || '',
        abstract: params.abstract || '',
        keywords: params.keywords || null,
        temperature: params.temperature ?? 0.0,
        repetition_number: 1,
      })
      return res.data
    } catch (error) {
      console.error('[MS2 Client] Error al clasificar ítem en /classify:', error)
      return null
    }
  },

  /**
   * Método de compatibilidad para clasificar texto y obtener el resultado principal
   */
  async classifyText(
    title: string,
    abstractText: string,
    scheme: 'OCDE' | 'ODS' = 'OCDE',
    keywords?: string
  ): Promise<ClassificationResult | null> {
    try {
      const res = await this.classify({
        title,
        abstract: abstractText,
        keywords,
      })
      if (!res) return null

      if (scheme === 'OCDE') {
        const top = res.ocde_classifications?.[0]
        if (top) {
          return {
            code: top.codigo,
            label: top.nombre,
            confidence: Math.round((top.confidence_score || 0) * 100),
            justification: top.justificacion,
          }
        }
      } else {
        const top = res.ods_classifications?.[0]
        if (top) {
          return {
            code: `ODS ${top.numero}`,
            label: top.nombre,
            confidence: Math.round((top.confidence_score || 0) * 100),
            justification: top.justificacion,
          }
        }
      }
      return null
    } catch {
      return null
    }
  }
}


