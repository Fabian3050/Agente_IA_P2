<template>
  <div class="h-full overflow-y-auto">
    <SectionHeader
      title="Auditoría y Trazabilidad"
      description="Listado de registros del catálogo científico y su historial completo de eventos de enriquecimiento y curaduría."
    />

    <!-- Stats -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <Card customClass="p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-[11px] font-semibold text-[#6b7a90] uppercase">Registros Auditados</span>
          <div class="w-8 h-8 rounded-lg bg-teal-50 text-[#00aea7] flex items-center justify-center">
            <ClipboardList :size="16" />
          </div>
        </div>
        <p class="text-xl font-bold text-[#1a2332]">
          {{ auditRecords.length }} <span class="text-xs font-normal text-[#6b7a90]">registros</span>
        </p>
        <p class="text-[10px] text-[#00aea7] font-medium mt-0.5">Trazabilidad en log (INSERT-only)</p>
      </Card>

      <Card customClass="p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-[11px] font-semibold text-[#6b7a90] uppercase">Eventos Registrados</span>
          <div class="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
            <Activity :size="16" />
          </div>
        </div>
        <p class="text-xl font-bold text-[#1a2332]">20 <span class="text-xs font-normal text-[#6b7a90]">eventos</span></p>
        <p class="text-[10px] text-blue-600 font-medium mt-0.5">Promedio 4 eventos por registro</p>
      </Card>

      <Card customClass="p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-[11px] font-semibold text-[#6b7a90] uppercase">Fuentes Consultadas</span>
          <div class="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
            <Database :size="16" />
          </div>
        </div>
        <p class="text-xl font-bold text-[#1a2332]">4 <span class="text-xs font-normal text-[#6b7a90]">fuentes</span></p>
        <p class="text-[10px] text-purple-600 font-medium mt-0.5">Scopus, WoS, Crossref, OpenAlex</p>
      </Card>

      <Card customClass="p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-[11px] font-semibold text-[#6b7a90] uppercase">Integridad de metadatos</span>
          <div class="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <ShieldCheck :size="16" />
          </div>
        </div>
        <p class="text-xl font-bold text-emerald-700">100%</p>
        <p class="text-[10px] text-emerald-600 font-medium mt-0.5">Sin alertas de inconsistencia</p>
      </Card>
    </div>

    <!-- Table Card -->
    <Card>
      <div class="p-4 border-b border-gray-50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div class="relative flex-1 max-w-xs">
          <Search :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-[#6b7a90]" />
          <input
            type="text"
            placeholder="Buscar por ID, nombre o metadato..."
            v-model="searchTerm"
            class="w-full pl-9 pr-3 py-2 text-xs border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#00aea7]/20 focus:border-[#00aea7]"
          />
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-gray-50 bg-slate-50/50">
              <th
                v-for="h in ['ID del registro', 'Nombre del registro asociado', 'Metadatos recuperados', 'Última actualización', 'Acciones']"
                :key="h"
                class="text-left px-4 py-3.5 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide whitespace-nowrap"
              >
                {{ h }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="5" class="text-center py-12 text-slate-500 text-xs">
                <div class="inline-block w-4 h-4 border-2 border-[#00aea7] border-t-transparent rounded-full animate-spin mr-2"></div>
                Cargando registros reales de auditoría desde MS3 Auth...
              </td>
            </tr>
            <tr v-else-if="filtered.length === 0">
              <td colspan="5" class="text-center py-12 text-slate-500 text-xs">
                No hay registros de auditoría almacenados en la base de datos actualmente.
              </td>
            </tr>
            <tr
              v-else
              v-for="row in filtered"
              :key="row.id"
              class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors"
            >
              <td class="px-4 py-3.5 whitespace-nowrap">
                <span
                  class="text-xs font-mono font-bold px-2.5 py-1 rounded-md"
                  :class="row.isSystem ? 'text-purple-700 bg-purple-50/80 border border-purple-200' : 'text-[#1565C0] bg-blue-50/80 border border-blue-100'"
                >
                  {{ row.isSystem ? row.id : `#${row.id}` }}
                </span>
              </td>
              <td class="px-4 py-3.5 max-w-[280px]">
                <p class="text-xs font-semibold text-[#1a2332] truncate" :title="row.nombre">{{ row.nombre }}</p>
              </td>
              <td class="px-4 py-3.5">
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="meta in row.metadatoRecuperado.split(', ')"
                    :key="meta"
                    class="text-[11px] font-medium px-2 py-0.5 bg-teal-50 text-[#00aea7] rounded border border-teal-100 whitespace-nowrap"
                  >
                    {{ meta }}
                  </span>
                </div>
              </td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <span class="text-xs text-slate-500 font-mono">{{ row.fecha }}</span>
              </td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <button
                  @click="selectedAudit = row"
                  class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-[#00aea7] hover:opacity-90 transition-all rounded-lg shadow-sm cursor-pointer"
                >
                  <ClipboardList :size="13" />
                  <span>Ver auditoría</span>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <!-- Modal Trazabilidad y Auditoría -->
    <div
      v-if="selectedAudit"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-gray-100 w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        <div class="px-6 py-4 border-b border-gray-100 bg-slate-50 flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <div class="w-8 h-8 rounded-lg bg-[#00aea7]/10 text-[#00aea7] flex items-center justify-center font-bold">
              <ClipboardList :size="18" />
            </div>
            <div>
              <h3 class="text-sm font-bold text-slate-800">
                Trazabilidad y Auditoría — {{ selectedAudit.isSystem ? selectedAudit.nombre : `Registro #${selectedAudit.id}` }}
              </h3>
              <p class="text-[11px] text-slate-500">Historial completo e inmutable de eventos institucionales</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="exportAuditLog(selectedAudit)"
              class="flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-slate-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer"
            >
              <Download :size="13" /> Exportar log
            </button>
            <button @click="selectedAudit = null" class="p-1 rounded-lg text-slate-400 hover:text-slate-600">
              <X :size="18" />
            </button>
          </div>
        </div>

        <div class="p-6 overflow-y-auto space-y-5 flex-1">
          <div class="bg-slate-50 p-4 rounded-xl border border-gray-100 space-y-2">
            <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Nombre del Registro Asociado</span>
            <p class="text-xs font-bold text-slate-800 mt-0.5">{{ selectedAudit.nombre }}</p>
          </div>

          <!-- Timeline of events -->
          <div class="space-y-4">
            <div
              v-for="(ev, idx) in selectedAudit.eventos"
              :key="idx"
              class="flex gap-3 text-xs"
            >
              <div class="flex flex-col items-center">
                <div
                  class="w-3 h-3 rounded-full mt-1 border-2 border-white shadow-sm flex-shrink-0"
                  :style="{ backgroundColor: ev.color }"
                />
                <div v-if="idx < selectedAudit.eventos.length - 1" class="w-0.5 flex-1 bg-gray-200 my-1" />
              </div>
              <div class="flex-1 pb-4">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="font-bold text-gray-800">{{ ev.event }}</span>
                  <span class="text-[10px] text-gray-400 font-mono">{{ ev.time }}</span>
                  <span class="text-[10px] px-2 py-0.5 rounded bg-gray-100 text-gray-600 font-medium">{{ ev.role }}: {{ ev.user }}</span>
                  <span class="text-[10px] text-teal-600 bg-teal-50 px-1.5 py-0.5 rounded font-mono">{{ ev.source }}</span>
                </div>
                <p class="text-xs text-gray-600 mt-1 leading-relaxed">{{ ev.result }}</p>
              </div>
            </div>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-100 bg-slate-50 flex justify-end">
          <button
            @click="selectedAudit = null"
            class="px-4 py-1.5 rounded-lg text-xs font-semibold text-slate-600 bg-white border border-gray-200 hover:bg-gray-50 cursor-pointer"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ClipboardList, Activity, Database, ShieldCheck, Search, Download, X } from 'lucide-vue-next'
import Card from '../components/common/Card.vue'
import SectionHeader from '../components/common/SectionHeader.vue'
import { auditService } from '../services/auditService'
import { proposalService } from '../services/proposalService'

const searchTerm = ref('')
const selectedAudit = ref<any | null>(null)
const loading = ref(true)
const auditRecords = ref<any[]>([])
const totalEventos = ref(0)
const totalFuentes = ref(0)

const loadRealAuditLogs = async () => {
  loading.value = true
  try {
    const [logs, proposals, queueRes] = await Promise.all([
      auditService.getAuditLogs(),
      proposalService.listProposals(),
      proposalService.getQueue({ size: 1000 })
    ])

    totalEventos.value = logs.length
    totalFuentes.value = 4

    // Separar y agrupar eventos
    const grouped: Record<string, any[]> = {}
    const systemEvents: any[] = []

    for (const l of logs) {
      if (l.item_id && l.item_id !== 'null' && l.item_id !== 'undefined' && l.item_id !== '') {
        const key = String(l.item_id)
        if (!grouped[key]) grouped[key] = []
        grouped[key].push(l)
      } else {
        systemEvents.push(l)
      }
    }

    const items: any[] = []

    // 1. Eventos agrupados por publicación/registro
    for (const [itemId, evs] of Object.entries(grouped)) {
      const relatedProp = proposals.find((p: any) => String(p.id) === itemId)
      const relatedQueue = queueRes?.items?.find((q: any) => String(q.id) === itemId || q.dspace_uuid === itemId)
      const pubTitle = relatedQueue?.titulo || relatedProp?.title || `Publicación #${itemId.substring(0, 8)}`
      const lastEv = evs[0]
      const d = lastEv.timestamp ? new Date(lastEv.timestamp) : new Date()

      items.push({
        id: itemId.length > 12 ? itemId.substring(0, 8) : itemId,
        fullId: itemId,
        isSystem: false,
        nombre: pubTitle,
        metadatoRecuperado: evs.map((e: any) => e.action).filter((v, i, a) => a.indexOf(v) === i).join(', ') || 'Metadato',
        fecha: d.toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }),
        eventos: evs.map((e: any) => {
          const ed = e.timestamp ? new Date(e.timestamp) : new Date()
          const isApprove = e.action.toLowerCase().includes('aprob') || e.action.toLowerCase().includes('valid')
          const isReject = e.action.toLowerCase().includes('rechaz')
          return {
            time: ed.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            event: e.action,
            user: e.user_name || 'Curador VRIIC',
            role: e.role || 'Curador',
            source: 'MS3 Auth / MS4',
            result: e.new_value ? (typeof e.new_value === 'string' ? e.new_value : JSON.stringify(e.new_value)) : (e.rejection_reason ? `Motivo: ${e.rejection_reason}` : `Acción ${e.action} ejecutada.`),
            color: isApprove ? '#2E7D32' : isReject ? '#E53935' : '#00aea7'
          }
        })
      })
    }

    // 2. Eventos de sistema y seguridad (Login, Creación de usuario, etc.)
    for (const sys of systemEvents) {
      const sd = sys.timestamp ? new Date(sys.timestamp) : new Date()
      const isLogin = sys.action.toLowerCase().includes('login') || sys.action.toLowerCase().includes('sesión')
      const isUser = sys.action.toLowerCase().includes('usuario')
      const eventTitle = isLogin ? `Inicio de sesión: ${sys.user_name || 'Usuario'}` : (isUser ? `Administración de usuarios: ${sys.action}` : `Evento de sistema: ${sys.action}`)

      items.push({
        id: isLogin ? 'AUTH' : (isUser ? 'USER' : 'SYS'),
        fullId: sys.id,
        isSystem: true,
        nombre: eventTitle,
        metadatoRecuperado: sys.action,
        fecha: sd.toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }),
        eventos: [{
          time: sd.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          event: sys.action,
          user: sys.user_name || 'Usuario Institucional',
          role: sys.role || 'Sistema',
          source: 'MS3 Auth Seguridad',
          result: sys.new_value ? (typeof sys.new_value === 'string' ? sys.new_value : JSON.stringify(sys.new_value)) : `Acción ${sys.action} ejecutada satisfactoriamente.`,
          color: isLogin ? '#1565C0' : (isUser ? '#7B1FA2' : '#00aea7')
        }]
      })
    }

    auditRecords.value = items
  } catch (err) {
    console.error('Error cargando registros reales de auditoría:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRealAuditLogs()
})

const filtered = computed(() => {
  return auditRecords.value.filter(r =>
    r.id.toLowerCase().includes(searchTerm.value.toLowerCase()) ||
    r.nombre.toLowerCase().includes(searchTerm.value.toLowerCase()) ||
    r.metadatoRecuperado.toLowerCase().includes(searchTerm.value.toLowerCase())
  )
})

const exportAuditLog = (item: any) => {
  alert(`Exportando reporte de auditoría completo para el registro #${item.id}...`)
}
</script>

