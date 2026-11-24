import { ms3Client } from './api'
import { authService } from './authService'

export interface RealAuditLog {
  id: string
  user_id?: string
  user_name?: string
  role?: string
  item_id: string
  action: string
  previous_value?: any
  new_value?: any
  rejection_reason?: string
  timestamp: string
}

export const auditService = {
  async getAuditLogs(): Promise<RealAuditLog[]> {
    try {
      const res = await ms3Client.get<RealAuditLog[]>('/audit/')
      return Array.isArray(res.data) ? res.data : []
    } catch {
      return []
    }
  },

  async getAuditTrailForItem(itemId: string): Promise<RealAuditLog[]> {
    try {
      const res = await ms3Client.get<RealAuditLog[]>(`/audit/${itemId}`)
      return Array.isArray(res.data) ? res.data : []
    } catch {
      return []
    }
  },

  async recordAction(data: {
    user_id?: string
    item_id?: string
    action: string
    previous_value?: any
    new_value?: any
    rejection_reason?: string
  }): Promise<any> {
    try {
      const storedUser = authService.getStoredUser()
      const payload = {
        user_id: data.user_id || storedUser?.id || undefined,
        item_id: data.item_id ? String(data.item_id) : undefined,
        action: data.action,
        previous_value: data.previous_value,
        new_value: data.new_value,
        rejection_reason: data.rejection_reason,
      }
      const res = await ms3Client.post('/audit/', payload)
      return res.data
    } catch (err) {
      console.warn('Error registrando auditoría en MS3:', err)
      return null
    }
  }
}

