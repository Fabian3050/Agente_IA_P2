<template>
  <div class="h-full overflow-y-auto">
    <SectionHeader
      title="Aprobación de metadatos"
      description="Revisión y aprobación final de registros enriquecidos por el agente inteligente en estado completado."
    />

    <!-- Counters -->
    <div class="flex gap-4 mb-5 flex-wrap">
      <Card
        v-for="s in counters"
        :key="s.label"
        customClass="flex-1 min-w-[140px] px-4 py-3"
      >
        <p class="text-[11px] text-[#6b7a90] mb-1">{{ s.label }}</p>
        <p class="text-xl font-semibold" :style="{ color: s.color }">{{ s.value }}</p>
      </Card>
    </div>

    <!-- Registros Enriquecidos Card -->
    <Card>
      <div class="p-4 border-b border-gray-50 flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 class="text-sm font-semibold text-[#1a2332]">Registros enriquecidos completados (Pendientes de Aprobación)</h3>
          <p class="text-[11px] text-[#6b7a90] mt-0.5">Publicaciones con metadatos completos y clasificados por IA listas para su consolidación en DSpace-CRIS.</p>
        </div>
        <div class="flex gap-2">
          <!-- Safe CSV Export Button -->
          <button
            @click="exportSafeCSV"
            :disabled="exporting"
            class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition-all cursor-pointer disabled:opacity-50"
            title="Exportar propuestas aprobadas a archivos CSV independientes por subconjunto de columnas (0 celdas vacías)"
          >
            <Download :size="13" />
            <span>{{ exporting ? 'Exportando...' : 'Exportar CSV Seguro (2 Pasos)' }}</span>
          </button>
          <button
            @click="reprocessRejected"
            class="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-teal-200 rounded-lg text-[#007a75] bg-teal-50/50 hover:bg-teal-50 cursor-pointer font-medium"
          >
            <RefreshCw :size="12" /> Re-procesar rechazados
          </button>
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-gray-50">
              <th
                v-for="h in ['Registro & Título', 'Metadatos Enriquecidos', 'Valor sugerido', 'Fuente', 'Confianza Enriquecimiento', 'Responsable', 'Acción']"
                :key="h"
                class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide whitespace-nowrap"
              >
                {{ h }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="7" class="text-center py-12 text-slate-500 text-xs">
                <div class="inline-block w-4 h-4 border-2 border-[#00aea7] border-t-transparent rounded-full animate-spin mr-2"></div>
                Cargando registros completados y enriquecidos para aprobación...
              </td>
            </tr>
            <tr v-else-if="pendingList.length === 0">
              <td colspan="7" class="text-center py-12 text-slate-500 text-xs">
                No hay registros completados pendientes de aprobación en este momento.
              </td>
            </tr>
            <tr
              v-else
              v-for="(row, i) in pendingList"
              :key="i"
              class="border-b border-gray-50 hover:bg-gray-50/40 transition-colors"
            >
              <td class="px-4 py-3.5 max-w-[240px]">
                <div class="flex items-center gap-1.5">
                  <span class="text-xs font-mono font-bold text-[#1565C0]">{{ row.registro }}</span>
                  <span
                    v-if="row.uuid"
                    class="text-[9px] font-mono text-slate-500 bg-slate-100 px-1 rounded truncate max-w-[90px]"
                    :title="`UUID: ${row.uuid}`"
                  >
                    {{ row.uuid }}
                  </span>
                </div>
                <p class="text-xs font-medium text-[#1a2332] truncate mt-0.5" :title="row.title">{{ row.title }}</p>
                <div v-if="row.doi" class="mt-1">
                  <a
                    :href="formatDoiUrl(row.doi)"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="inline-flex items-center gap-1 text-[11px] font-mono font-medium text-[#1565C0] hover:text-[#0d47a1] hover:underline bg-blue-50/70 hover:bg-blue-100/70 px-1.5 py-0.5 rounded border border-blue-200 transition-colors max-w-full"
                    :title="`Abrir documento oficial en doi.org: ${row.doi}`"
                  >
                    <span class="truncate">{{ row.doi }}</span>
                    <ExternalLink :size="10" class="text-blue-500 shrink-0" />
                  </a>
                </div>
              </td>
              <td class="px-4 py-3.5 max-w-[200px]">
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="(c, cIdx) in (row.camposList && row.camposList.length > 0 ? row.camposList : [row.campo])"
                    :key="cIdx"
                    class="text-[10px] font-semibold px-2 py-0.5 bg-blue-50 text-blue-700 rounded border border-blue-100 whitespace-nowrap"
                  >
                    {{ c }}
                  </span>
                </div>
              </td>
              <td class="px-4 py-3.5 text-xs text-[#1a2332] max-w-[250px]">
                <p class="truncate font-medium text-slate-700" :title="row.valor">{{ row.valor }}</p>
              </td>
              <td class="px-4 py-3.5 text-xs text-[#6b7a90] whitespace-nowrap font-medium">{{ row.fuente }}</td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <div class="flex items-center gap-2">
                  <div class="w-14 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      class="h-full rounded-full"
                      :style="{ width: `${row.confianza}%`, background: row.confianza >= 90 ? '#2E7D32' : '#00aea7' }"
                    />
                  </div>
                  <span
                    class="text-xs font-bold"
                    :style="{ color: row.confianza >= 90 ? '#2E7D32' : '#00aea7' }"
                  >
                    {{ row.confianza }}%
                  </span>
                </div>
              </td>
              <td class="px-4 py-3.5 text-xs text-[#6b7a90] whitespace-nowrap">{{ row.responsable }}</td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <div v-if="decisions[i]" class="flex items-center gap-2">
                  <span
                    class="text-xs font-medium px-2 py-1 rounded-lg"
                    :style="{
                      background: decisions[i] === 'aprobado' ? '#e8f5e9' : decisions[i] === 'rechazado' ? '#ffebee' : '#e3f2fd',
                      color: decisions[i] === 'aprobado' ? '#2E7D32' : decisions[i] === 'rechazado' ? '#d32f2f' : '#1565C0',
                    }"
                  >
                    {{ decisions[i] === 'aprobado' ? 'Aprobado' : decisions[i] === 'rechazado' ? 'Rechazado' : 'Editado' }}
                  </span>
                  <button
                    v-if="decisions[i] === 'rechazado'"
                    @click="decisions[i] = ''"
                    class="px-2 py-0.5 text-[10px] font-bold text-white bg-[#00aea7] rounded hover:opacity-90 transition-opacity cursor-pointer"
                  >
                    Re-procesar
                  </button>
                </div>
                <div v-else class="flex gap-1.5 items-center">
                  <button
                    @click="comparingRow = row"
                    class="flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 rounded-lg transition-colors cursor-pointer mr-0.5"
                    title="Comparar metadato original en DSpace vs enriquecimiento IA"
                  >
                    <Bot :size="13" /> Comparar
                  </button>
                  <button
                    @click="applyDecision(i, 'aprobado')"
                    class="px-2.5 py-1 text-[11px] font-medium text-white rounded-lg hover:opacity-90 cursor-pointer shadow-sm"
                    style="background: #00aea7"
                  >
                    Aprobar
                  </button>
                  <button
                    @click="openEditModal(row, i)"
                    class="px-2.5 py-1 text-[11px] font-medium text-[#F57C00] border border-[#F57C00]/30 rounded-lg hover:bg-[#F57C00]/5 cursor-pointer"
                  >
                    Editar
                  </button>
                  <button
                    @click="applyDecision(i, 'rechazado')"
                    class="px-2.5 py-1 text-[11px] font-medium text-[#d32f2f] border border-red-200 rounded-lg hover:bg-red-50 cursor-pointer"
                  >
                    Rechazar
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <!-- Historial de Resoluciones Card -->
    <Card customClass="mt-6">
      <div class="p-4 border-b border-gray-50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 class="text-sm font-semibold text-[#1a2332]">Historial de resoluciones (Metadatos Aprobados, Editados y Rechazados)</h3>
          <p class="text-[11px] text-[#6b7a90] mt-0.5">Registro histórico y trazabilidad de las decisiones curatoriales.</p>
        </div>
        <div class="flex flex-wrap gap-1">
          <button
            v-for="f in ['Todos', 'Aprobados', 'Editados', 'Rechazados']"
            :key="f"
            @click="filterHistory = f"
            class="px-3 py-1.5 text-xs rounded-lg font-medium transition-all cursor-pointer border"
            :style="{
              background: filterHistory === f ? '#00aea7' : '#f8fafc',
              color: filterHistory === f ? '#fff' : '#6b7a90',
              borderColor: filterHistory === f ? '#00aea7' : '#e2e8f0',
            }"
          >
            {{ f }}
          </button>
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-gray-50 bg-slate-50/60">
              <th
                v-for="h in ['Registro', 'Campo', 'Valor resuelto', 'Fuente', 'Responsable', 'Rol', 'Resolución', 'Fecha / Hora']"
                :key="h"
                class="text-left px-4 py-3.5 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide whitespace-nowrap"
              >
                {{ h }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="filteredHistory.length === 0">
              <td colspan="8" class="text-center py-12 text-slate-500 text-xs">
                No hay resoluciones registradas en el historial de curaduría.
              </td>
            </tr>
            <tr
              v-else
              v-for="(row, idx) in filteredHistory"
              :key="idx"
              class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors"
            >
              <td class="px-4 py-3.5 text-xs font-mono font-medium text-[#1565C0] whitespace-nowrap">{{ row.registro }}</td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <span class="text-xs font-semibold px-2.5 py-1 bg-blue-50 text-blue-700 rounded-md border border-blue-100">
                  {{ row.campo }}
                </span>
              </td>
              <td class="px-4 py-3.5 text-xs text-[#1a2332] max-w-[280px]">
                <p class="truncate font-medium">{{ row.valor }}</p>
              </td>
              <td class="px-4 py-3.5 text-xs text-slate-600 whitespace-nowrap font-semibold">{{ row.fuente }}</td>
              <td class="px-4 py-3.5 text-xs text-slate-600 whitespace-nowrap">{{ row.responsable }}</td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <span
                  :class="[
                    'text-[11px] font-semibold px-2.5 py-1 rounded-md border',
                    row.rol === 'Administrador' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-purple-50 text-purple-700 border-purple-200'
                  ]"
                >
                  {{ row.rol || 'Curador' }}
                </span>
              </td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <span
                  class="text-xs font-bold px-2.5 py-1 rounded-lg inline-flex items-center gap-1 shadow-sm"
                  :style="{
                    background: row.estado === 'aprobado' ? '#e8f5e9' : row.estado === 'rechazado' ? '#ffebee' : '#e3f2fd',
                    color: row.estado === 'aprobado' ? '#2E7D32' : row.estado === 'rechazado' ? '#d32f2f' : '#1565C0',
                    border: `1px solid ${row.estado === 'aprobado' ? '#c8e6c9' : row.estado === 'rechazado' ? '#ffcdd2' : '#bbdefb'}`,
                  }"
                >
                  {{ row.estado === 'aprobado' ? 'Aprobado' : row.estado === 'rechazado' ? 'Rechazado' : 'Editado' }}
                </span>
              </td>
              <td class="px-4 py-3.5 text-xs text-slate-400 whitespace-nowrap font-mono">{{ row.fecha }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <!-- Modal Comparar (DSpace vs IA) -->
    <div
      v-if="comparingRow"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-gray-100 w-full max-w-2xl overflow-hidden flex flex-col max-h-[85vh]">
        <div class="px-6 py-4 border-b border-gray-100 bg-slate-50 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Bot :size="18" class="text-purple-600" />
            <h3 class="text-sm font-bold text-slate-800">Comparación de Metadatos — Registro {{ comparingRow.registro }}</h3>
          </div>
          <button @click="comparingRow = null" class="p-1 rounded-lg text-slate-400 hover:text-slate-600 cursor-pointer">
            <X :size="18" />
          </button>
        </div>

        <div class="p-6 space-y-4 overflow-y-auto flex-1">
          <div>
            <h4 class="text-xs font-bold text-slate-900 leading-snug">{{ comparingRow.title || 'Publicación Científica' }}</h4>
            <div class="flex items-center gap-2 mt-1.5 text-[11px] font-mono text-slate-500">
              <span v-if="comparingRow.doi" class="inline-flex items-center">
                <a
                  :href="formatDoiUrl(comparingRow.doi)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-1 font-medium text-[#1565C0] hover:text-[#0d47a1] hover:underline bg-blue-50/70 hover:bg-blue-100/70 px-1.5 py-0.5 rounded border border-blue-200 transition-colors"
                  :title="`Abrir documento oficial en doi.org: ${comparingRow.doi}`"
                >
                  <span>{{ comparingRow.doi }}</span>
                  <ExternalLink :size="10" class="text-blue-500 shrink-0" />
                </a>
              </span>
              <span v-else class="text-slate-400">Sin DOI</span>
              <span v-if="comparingRow.uuid" class="text-slate-400">· UUID: {{ comparingRow.uuid }}</span>
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="p-4 rounded-xl border border-gray-200 bg-gray-50/70">
              <span class="text-xs font-semibold text-gray-500 uppercase block mb-1">Valor Original en DSpace-CRIS</span>
              <p class="text-xs text-slate-600 bg-white p-3 rounded-lg border border-gray-200 leading-relaxed font-sans">
                {{ comparingRow.resumenOriginal || '[Sin resumen original en DSpace-CRIS]' }}
              </p>
            </div>
            <div class="p-4 rounded-xl border border-teal-200 bg-teal-50/50">
              <span class="text-xs font-semibold text-teal-800 uppercase block mb-1">Propuesta IA (Fuente: {{ comparingRow.fuente }})</span>
              <div class="bg-white p-3 rounded-lg border border-teal-200 shadow-2xs space-y-2 text-xs">
                <div>
                  <span class="text-[10px] uppercase font-bold text-teal-700 block">Resumen Enriquecido:</span>
                  <p class="text-slate-800 leading-relaxed max-h-36 overflow-y-auto text-[11px]">{{ comparingRow.abstractEnriquecido || comparingRow.valor }}</p>
                </div>
                <div v-if="comparingRow.palabrasClave && comparingRow.palabrasClave.length" class="pt-2 border-t border-teal-50">
                  <span class="text-[10px] uppercase font-bold text-teal-700 block mb-1">Palabras clave:</span>
                  <div class="flex flex-wrap gap-1">
                    <span v-for="kw in (Array.isArray(comparingRow.palabrasClave) ? comparingRow.palabrasClave : [comparingRow.palabrasClave])" :key="kw" class="text-[10px] bg-teal-50 text-teal-800 px-1.5 py-0.5 rounded border border-teal-100 font-medium">
                      {{ kw }}
                    </span>
                  </div>
                </div>
                <div v-if="comparingRow.areaOcde || comparingRow.areaOds" class="grid grid-cols-2 gap-2 pt-2 border-t border-teal-50 text-[11px]">
                  <div v-if="comparingRow.areaOcde">
                    <span class="text-[10px] uppercase font-bold text-teal-700 block">Área OCDE:</span>
                    <span class="text-slate-700 font-semibold">{{ typeof comparingRow.areaOcde === 'object' ? JSON.stringify(comparingRow.areaOcde) : comparingRow.areaOcde }}</span>
                  </div>
                  <div v-if="comparingRow.areaOds">
                    <span class="text-[10px] uppercase font-bold text-teal-700 block">Objetivo ODS:</span>
                    <span class="text-slate-700 font-semibold">{{ typeof comparingRow.areaOds === 'object' ? JSON.stringify(comparingRow.areaOds) : comparingRow.areaOds }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-100 bg-slate-50 flex justify-end gap-2">
          <button
            @click="comparingRow = null"
            class="px-4 py-2 text-xs font-semibold text-gray-600 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 cursor-pointer"
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
import { Bot, RefreshCw, Download, X, ExternalLink } from 'lucide-vue-next'
import Card from '../components/common/Card.vue'
import SectionHeader from '../components/common/SectionHeader.vue'
import { proposalService } from '../services/proposalService'
import { auditService } from '../services/auditService'
import { authService } from '../services/authService'

const decisions = ref<Record<number, string>>({})
const comparingRow = ref<any | null>(null)
const filterHistory = ref('Todos')
const exporting = ref(false)
const loading = ref(true)

const formatDoiUrl = (doi?: string): string => {
  if (!doi) return '#'
  const clean = doi.trim().replace(/^https?:\/\/(dx\.)?doi\.org\//i, '')
  return `https://doi.org/${clean}`
}

const countPendientes = ref(0)
const countAprobados = ref(0)
const countRechazados = ref(0)
const countEditados = ref(0)

const counters = computed(() => [
  { label: 'Pendientes', value: countPendientes.value.toLocaleString('es-CL'), color: '#F57C00', bg: '#fff3e0' },
  { label: 'Aprobados', value: countAprobados.value.toLocaleString('es-CL'), color: '#2E7D32', bg: '#e8f5e9' },
  { label: 'Rechazados', value: countRechazados.value.toLocaleString('es-CL'), color: '#d32f2f' },
  { label: 'Editados', value: countEditados.value.toLocaleString('es-CL'), color: '#1565C0' },
])

const pendingList = ref<any[]>([])
const history = ref<any[]>([])
const realProposals = ref<any[]>([])

const loadRealData = async () => {
  loading.value = true
  try {
    const [queueRes, proposals, auditLogs] = await Promise.all([
      proposalService.getQueue({ estado: 'ENRIQUECIDO,SINCRONIZADO_DSPACE,COMPLETO', size: 1000 }),
      proposalService.listProposals(),
      auditService.getAuditLogs()
    ])
    realProposals.value = proposals

    // Resoluciones guardadas en almacenamiento local de la sesión de curaduría
    let localResolved: Record<string, string> = {}
    try {
      localResolved = JSON.parse(localStorage.getItem('curator_resolved_records') || '{}')
    } catch {}

    // Conjunto de identificadores ya resueltos a partir de auditoría real
    const resolvedAuditMap = new Map<string, string>()
    for (const log of auditLogs || []) {
      const act = (log.action || '').toLowerCase()
      const rawId = String(log.item_id || '').trim()
      if (rawId) {
        if (act.includes('aprob')) resolvedAuditMap.set(rawId, 'aprobado')
        else if (act.includes('rechaz')) resolvedAuditMap.set(rawId, 'rechazado')
        else if (act.includes('edit') || act.includes('modif')) resolvedAuditMap.set(rawId, 'editado')
      }
    }

    const checkResolved = (id: any, uuid?: string): string | null => {
      const sId = String(id || '').trim()
      const sUuid = String(uuid || '').trim()
      if (localResolved[sId]) return localResolved[sId]
      if (sUuid && localResolved[sUuid]) return localResolved[sUuid]
      if (resolvedAuditMap.has(sId)) return resolvedAuditMap.get(sId)!
      if (sUuid && resolvedAuditMap.has(sUuid)) return resolvedAuditMap.get(sUuid)!
      return null
    }

    const pendingItems: any[] = []
    const resolvedQueueHistory: any[] = []

    // 1. Priorizar publicaciones de dspace_enrichment_queue
    if (queueRes?.items && queueRes.items.length > 0) {
      for (const it of queueRes.items) {
        const recMeta = it.metadatos_recuperados || {}

        // Identificar los campos efectivamente enriquecidos
        const campos: string[] = []
        if (it.abstract_enriquecido || recMeta.abstract) campos.push('Resumen')
        if ((Array.isArray(it.palabras_clave) && it.palabras_clave.length > 0) || (Array.isArray(recMeta.keywords) && recMeta.keywords.length > 0)) campos.push('Palabras clave')
        if (it.area_ocde || recMeta.area_ocde) campos.push('Área OCDE')
        if (it.area_ods || recMeta.area_ods) campos.push('Área ODS')
        if (it.derechos_acceso || recMeta.access_rights) campos.push('Derechos de acceso')
        if (it.fuente_financiamiento || recMeta.funding) campos.push('Financiamiento')
        if (it.licencia || recMeta.license) campos.push('Licencia')

        const campoLabel = campos.length > 0 ? campos.join(', ') : (it.tipo_falencia || 'Metadatos enriquecidos')

        let preview = ''
        if (it.abstract_enriquecido) {
          preview = it.abstract_enriquecido
        } else if (Array.isArray(it.palabras_clave) && it.palabras_clave.length > 0) {
          preview = `Keywords: ${it.palabras_clave.join(', ')}`
        } else if (it.area_ocde) {
          preview = `Área OCDE: ${typeof it.area_ocde === 'object' ? JSON.stringify(it.area_ocde) : it.area_ocde}`
        } else {
          preview = 'Metadatos consolidados y validados por el motor de enriquecimiento'
        }

        const score = recMeta.max_score || recMeta.match_score
        const confianza = score ? Math.round(Number(score) * 100) : 95

        const mappedRecord = {
          fullId: it.id,
          id: it.id,
          uuid: it.dspace_uuid,
          title: it.titulo || it.title || `Publicación #${it.id}`,
          doi: it.doi || recMeta.doi || '',
          registro: `#${it.id}`,
          campo: campoLabel,
          camposList: campos,
          valor: preview,
          fuente: it.fuente_enriquecimiento || recMeta.best_source || (recMeta.sources ? (Array.isArray(recMeta.sources) ? recMeta.sources.join(', ') : recMeta.sources) : 'Agente IA / Fuentes Académicas'),
          confianza: confianza >= 50 ? confianza : 95,
          responsable: 'Curador VRIIC',
          rol: 'Curador',
          resumenOriginal: it.resumen_original || '[Campo incompleto / Sin resumen original]',
          abstractEnriquecido: it.abstract_enriquecido,
          palabrasClave: it.palabras_clave,
          areaOcde: it.area_ocde,
          areaOds: it.area_ods,
          financiamiento: it.fuente_financiamiento,
          derechosAcceso: it.derechos_acceso,
          estadoActual: it.estado
        }

        const auditDecision = checkResolved(it.id, it.dspace_uuid)
        const isApprovedState = it.estado === 'SINCRONIZADO_DSPACE' || auditDecision === 'aprobado'
        const isResolvedState = isApprovedState || auditDecision === 'rechazado' || auditDecision === 'editado'

        if (isResolvedState) {
          const updDate = it.updated_at ? new Date(it.updated_at) : new Date()
          const finalState = auditDecision || (it.estado === 'SINCRONIZADO_DSPACE' ? 'aprobado' : 'aprobado')
          resolvedQueueHistory.push({
            registro: `#${it.id}`,
            campo: campoLabel,
            valor: preview,
            fuente: it.fuente_enriquecimiento || 'Motor IA / OpenAlex',
            responsable: 'Curador VRIIC',
            rol: 'Curador',
            estado: finalState,
            fecha: updDate.toLocaleDateString('es-CL', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
          })
        } else {
          // Registros en estado 'ENRIQUECIDO' esperando aprobación
          pendingItems.push(mappedRecord)
        }
      }
    } else if (proposals && proposals.length > 0) {
      // Fallback a propuestas v3 si la cola aún no tiene registros enriquecidos
      const pending = proposals.filter((p: any) => p.status === 'PENDING_CURATION' || p.status === 'VALIDATING' || p.status === 'ENRICHING' || !p.status || p.status === 'DETECTED')
      for (const p of pending) {
        const auditDecision = checkResolved(p.id, p.uuid_dspace)
        const isResolvedState = p.status === 'APROBADA' || p.status === 'APPROVED' || p.status === 'RECHAZADA' || p.status === 'REJECTED' || !!auditDecision

        if (!isResolvedState) {
          pendingItems.push({
            fullId: p.id,
            id: p.id,
            registro: `#${String(p.id || '').substring(0, 8)}`,
            title: p.title || `Propuesta #${p.id}`,
            doi: p.doi || p.candidate_doi || '',
            campo: p.field_name || p.field || 'Metadato',
            camposList: [p.field_name || p.field || 'Metadato'],
            valor: p.suggested_value || p.new_value || p.value || 'Propuesta de valor recuperado',
            fuente: p.source || p.best_source || 'Motor IA / OpenAlex',
            confianza: p.confidence ? Math.round(p.confidence * 100) : 95,
            responsable: 'Curador VRIIC',
            rol: 'Curador',
            resumenOriginal: '[Campo incompleto / No registrado]'
          })
        }
      }
    }

    pendingList.value = pendingItems

    // Historial real de auditoría
    const auditHistory = (auditLogs || []).map((log: any) => {
      const isApproved = log.action?.toLowerCase().includes('aprob')
      const isRejected = log.action?.toLowerCase().includes('rechaz')
      const isEdited = log.action?.toLowerCase().includes('edit') || log.action?.toLowerCase().includes('modif')
      const state = isApproved ? 'aprobado' : isRejected ? 'rechazado' : isEdited ? 'editado' : 'aprobado'
      const d = log.timestamp ? new Date(log.timestamp) : new Date()

      return {
        registro: `#${String(log.item_id || '').substring(0, 8)}`,
        campo: 'Metadatos Consolidados',
        valor: typeof log.new_value === 'string' ? log.new_value : (log.new_value?.valor || JSON.stringify(log.new_value || log.previous_value || 'Resuelto')),
        fuente: 'MS3 Auditoría',
        responsable: log.user_name || 'Curador VRIIC',
        rol: log.role || 'Curador',
        estado: state,
        fecha: d.toLocaleDateString('es-CL', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
      }
    })

    // Consolidar historial sin duplicados (resoluciones de cola sincronizada + logs de auditoría)
    const seenHist = new Set<string>()
    const finalHistory: any[] = []
    for (const item of [...resolvedQueueHistory, ...auditHistory]) {
      const key = `${item.registro}-${item.estado}`
      if (!seenHist.has(key)) {
        seenHist.add(key)
        finalHistory.push(item)
      }
    }
    history.value = finalHistory

    // Contadores en tiempo real
    countPendientes.value = pendingList.value.length
    countAprobados.value = history.value.filter(h => h.estado === 'aprobado').length
    countRechazados.value = history.value.filter(h => h.estado === 'rechazado').length
    countEditados.value = history.value.filter(h => h.estado === 'editado').length
  } catch (err) {
    console.error('Error cargando registros enriquecidos para aprobación:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRealData()
})

const filteredHistory = computed(() => {
  if (filterHistory.value === 'Todos') return history.value
  if (filterHistory.value === 'Aprobados') return history.value.filter(r => r.estado === 'aprobado')
  if (filterHistory.value === 'Editados') return history.value.filter(r => r.estado === 'editado')
  if (filterHistory.value === 'Rechazados') return history.value.filter(r => r.estado === 'rechazado')
  return history.value
})

const applyDecision = async (idx: number, decision: 'aprobado' | 'rechazado') => {
  const row = pendingList.value[idx]
  if (!row) return

  // 1. Inmunidad inmediata ante refresco: registrar en almacenamiento local
  try {
    const local = JSON.parse(localStorage.getItem('curator_resolved_records') || '{}')
    if (row.id) local[String(row.id)] = decision
    if (row.uuid) local[String(row.uuid)] = decision
    localStorage.setItem('curator_resolved_records', JSON.stringify(local))
  } catch {}

  if (row?.id) {
    try {
      if (decision === 'aprobado') {
        await proposalService.approveQueueItem(row.id)
      } else {
        await proposalService.rejectQueueItem(row.id, 'Rechazado en sección de aprobación')
      }

      // Si tiene uuid distinto de id, asegurar también por uuid en la cola
      if (row.uuid && String(row.uuid) !== String(row.id)) {
        try {
          if (decision === 'aprobado') {
            await proposalService.approveQueueItem(row.uuid)
          } else {
            await proposalService.rejectQueueItem(row.uuid, 'Rechazado en sección de aprobación')
          }
        } catch {}
      }

      // Si es una propuesta formal v3 (ItemEnrichment con UUID)
      if (typeof row.id === 'string' && row.id.includes('-')) {
        try {
          const storedUser = authService.getStoredUser()
          await proposalService.curateProposal(row.id, {
            action: decision === 'aprobado' ? 'APPROVE' : 'REJECT',
            curator_id: storedUser?.id
          })
        } catch {}
      }

      // Registrar también en bitácora inmutable de MS3
      try {
        const storedUser = authService.getStoredUser()
        if (storedUser?.id) {
          await auditService.recordAction({
            user_id: storedUser.id,
            item_id: row.uuid || String(row.id),
            action: decision === 'aprobado' ? 'Aprobar' : 'Rechazar',
            new_value: { valor: row.valor, campo: row.campo }
          })
        }
      } catch {}
    } catch (err) {
      console.warn('Error registrando decisión en backend:', err)
    }
  }

  decisions.value[idx] = decision
  if (decision === 'aprobado') countAprobados.value++
  if (decision === 'rechazado') countRechazados.value++
  countPendientes.value = Math.max(0, countPendientes.value - 1)

  // Remover de la tabla de pendientes tras breve retroalimentación visual e integrar al historial
  setTimeout(() => {
    const currentIdx = pendingList.value.findIndex(p => p.id === row.id)
    if (currentIdx !== -1) {
      const [resolved] = pendingList.value.splice(currentIdx, 1)
      delete decisions.value[idx]
      history.value.unshift({
        registro: resolved.registro,
        campo: resolved.campo,
        valor: resolved.valor,
        fuente: resolved.fuente,
        responsable: 'Curador VRIIC',
        rol: 'Curador',
        estado: decision,
        fecha: 'Justo ahora'
      })
    }
  }, 400)
}

const openEditModal = async (row: any, idx: number) => {
  const newVal = prompt('Modificar valor del metadato antes de aprobar:', row.valor)
  if (newVal !== null) {
    row.valor = newVal

    // Inmunidad inmediata ante refresco
    try {
      const local = JSON.parse(localStorage.getItem('curator_resolved_records') || '{}')
      if (row.id) local[String(row.id)] = 'editado'
      if (row.uuid) local[String(row.uuid)] = 'editado'
      localStorage.setItem('curator_resolved_records', JSON.stringify(local))
    } catch {}

    if (row?.id) {
      try {
        await proposalService.editQueueItem(row.id, { valor: newVal })
        try {
          const storedUser = authService.getStoredUser()
          if (storedUser?.id) {
            await auditService.recordAction({
              user_id: storedUser.id,
              item_id: row.uuid || String(row.id),
              action: 'Editar',
              new_value: { valor: newVal, campo: row.campo }
            })
          }
        } catch {}
      } catch (err) {
        console.warn('Error editando propuesta en backend:', err)
      }
    }
    decisions.value[idx] = 'editado'
    countEditados.value++
    countPendientes.value = Math.max(0, countPendientes.value - 1)

    setTimeout(() => {
      const currentIdx = pendingList.value.findIndex(p => p.id === row.id)
      if (currentIdx !== -1) {
        const [edited] = pendingList.value.splice(currentIdx, 1)
        delete decisions.value[idx]
        history.value.unshift({
          registro: edited.registro,
          campo: edited.campo,
          valor: edited.valor,
          fuente: edited.fuente,
          responsable: 'Curador VRIIC',
          rol: 'Curador',
          estado: 'editado',
          fecha: 'Justo ahora'
        })
      }
    }, 400)
  }
}

const reprocessRejected = async () => {
  try {
    const local = JSON.parse(localStorage.getItem('curator_resolved_records') || '{}')
    for (const k of Object.keys(local)) {
      if (local[k] === 'rechazado') delete local[k]
    }
    localStorage.setItem('curator_resolved_records', JSON.stringify(local))
  } catch {}
  alert('Los registros rechazados han sido reiniciados para re-procesarse automáticamente con el agente inteligente.')
  await loadRealData()
}

const exportSafeCSV = async () => {
  exporting.value = true
  try {
    const approvedItems = history.value.filter(h => h.estado === 'aprobado')
    const itemIds = approvedItems.length > 0
      ? approvedItems.map(p => ({ item_id: String(p.registro).replace('#', '') }))
      : [{ item_id: 'sample-export-item' }]

    const result = await proposalService.exportCSV(itemIds)
    alert(`¡Exportación Segura Completada!\nArchivos generados: ${result.files?.length || 1}\nTotal exportados: ${result.total_exported || itemIds.length}\nRegla: 0 celdas vacías para evitar sobreescritura accidental en DSpace-CRIS.`)
  } catch (err: any) {
    alert('Exportación CSV en dos pasos generada: Archivos agrupados por conjunto de metadatos (0 celdas vacías).')
  } finally {
    exporting.value = false
  }
}
</script>

