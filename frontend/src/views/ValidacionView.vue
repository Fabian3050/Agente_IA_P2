<template>
  <div class="h-full overflow-y-auto space-y-4">
    <SectionHeader
      title="Validación de metadatos"
      description="Asegure la calidad de los metadatos recuperados con coincidencia dudosa (< 80%) antes de su aprobación final."
    />

    <!-- Banner exclusivo para Perfil Académico -->
    <div
      v-if="user?.role === 'Academico'"
      class="p-4 bg-blue-50/80 border border-blue-200 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-blue-900 shadow-2xs"
    >
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center flex-shrink-0 font-bold shadow-xs">
          <ShieldCheck :size="18" />
        </div>
        <div>
          <p class="font-bold text-sm text-blue-950">Sesión Académica USACH</p>
          <p class="text-[11px] text-blue-800">
            Mostrando exclusivamente las publicaciones pendientes de validación asociadas a su ORCID:
            <span class="font-mono font-semibold bg-white/90 px-2 py-0.5 rounded border border-blue-300 ml-1 select-all text-blue-900">
              {{ user?.orcid || '0000-0001-9876-5432' }}
            </span>
          </p>
        </div>
      </div>
      <span class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-semibold bg-blue-100 text-blue-800 border border-blue-200 self-start sm:self-center">
        Validación por Autor
      </span>
    </div>

    <!-- Notificación Toast -->
    <div
      v-if="toast"
      class="p-3 rounded-xl border text-xs flex items-center justify-between shadow-sm transition-all"
      :class="toast.type === 'error' ? 'bg-red-50 border-red-200 text-red-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800'"
    >
      <div class="flex items-center gap-2">
        <ShieldCheck v-if="toast.type !== 'error'" :size="15" class="text-emerald-600 shrink-0" />
        <AlertTriangle v-else :size="15" class="text-red-600 shrink-0" />
        <span class="font-medium">{{ toast.message }}</span>
      </div>
      <button @click="toast = null" class="font-bold ml-3 opacity-70 hover:opacity-100 cursor-pointer">✕</button>
    </div>

    <Card>
      <div class="p-4 border-b border-gray-50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div class="relative flex-1 max-w-xs">
          <Search :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-[#6b7a90]" />
          <input
            type="text"
            placeholder="Buscar por ID, título, DOI o campo..."
            v-model="searchVal"
            class="w-full pl-9 pr-3 py-2 text-xs border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#00aea7]/20 focus:border-[#00aea7]"
          />
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <div class="flex flex-wrap gap-1">
            <button
              v-for="f in filterOptions"
              :key="f"
              @click="filterStatus = f"
              class="px-3 py-1.5 text-xs rounded-lg font-medium transition-all cursor-pointer"
              :style="{
                background: filterStatus === f ? '#00aea7' : '#f0f4f8',
                color: filterStatus === f ? '#fff' : '#6b7a90',
              }"
            >
              {{ f }}
            </button>
          </div>
          <button
            @click="loadProposals"
            :disabled="loading"
            class="p-1.5 text-[#6b7a90] hover:text-[#00aea7] bg-gray-50 hover:bg-[#00aea7]/10 rounded-lg border border-gray-200 transition-colors cursor-pointer"
            title="Recargar registros pendientes"
          >
            <RefreshCw :size="14" :class="{ 'animate-spin': loading }" />
          </button>
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-gray-50 bg-slate-50/50">
              <th
                v-for="h in ['ID & Título', 'DOI', 'Metadatos recuperados', 'Fuente', 'Confianza Enriquecimiento', 'Acciones']"
                :key="h"
                class="text-left px-4 py-3.5 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide"
              >
                {{ h }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="6" class="text-center py-12 text-slate-500 text-xs">
                <div class="inline-block w-4 h-4 border-2 border-[#00aea7] border-t-transparent rounded-full animate-spin mr-2"></div>
                Cargando propuestas reales de metadatos para validación...
              </td>
            </tr>
            <tr v-else-if="filtered.length === 0">
              <td colspan="6" class="text-center py-12 text-slate-500 text-xs">
                <p class="font-medium text-slate-600 mb-1">
                  {{ user?.role === 'Academico'
                    ? `No se encontraron publicaciones pendientes de validación asociadas a su ORCID (${user?.orcid || '0000-0001-9876-5432'}).`
                    : 'No hay metadatos pendientes de validación técnica en este filtro.' }}
                </p>
                <p class="text-[11px] text-slate-400">
                  {{ user?.role === 'Academico'
                    ? 'Cuando existan publicaciones con puntaje de coincidencia menor al 80% vinculadas a su identificador, aparecerán aquí para su validación.'
                    : 'Los registros con coincidencia algorítmica menor al 80% aparecerán aquí para revisión manual.' }}
                </p>
              </td>
            </tr>
            <tr
              v-else
              v-for="row in paginatedRecords"
              :key="row.id"
              class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors"
            >
              <td class="px-4 py-3.5 max-w-[240px]">
                <span class="text-xs font-mono font-bold text-[#1565C0]">#{{ row.id }}</span>
                <p class="text-xs font-medium text-[#1a2332] truncate mt-0.5" :title="row.title">{{ row.title }}</p>
              </td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <a
                  v-if="row.doi"
                  :href="formatDoiUrl(row.doi)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-1.5 text-xs font-mono font-medium text-[#1565C0] hover:text-[#0d47a1] hover:underline bg-blue-50/70 hover:bg-blue-100/70 px-2.5 py-1 rounded-md border border-blue-200 transition-colors"
                  :title="`Abrir documento oficial en doi.org: ${row.doi}`"
                >
                  <span class="max-w-[140px] truncate">{{ row.doi }}</span>
                  <ExternalLink :size="11" class="text-blue-500 shrink-0" />
                </a>
                <span v-else class="text-[11px] text-slate-400 font-mono italic">Sin DOI</span>
              </td>
              <td class="px-4 py-3.5 max-w-[220px]">
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="tag in row.camposLista"
                    :key="tag"
                    class="text-[10px] font-semibold px-2 py-0.5 bg-blue-50 text-blue-700 rounded border border-blue-100"
                  >
                    {{ tag }}
                  </span>
                  <span v-if="row.camposLista.length === 0" class="text-[11px] text-slate-400 italic">
                    {{ row.campo }}
                  </span>
                </div>
              </td>
              <td class="px-4 py-3.5 text-xs">
                <div class="flex items-center gap-1.5 font-semibold text-slate-800">
                  <Cpu :size="14" class="text-[#00aea7] shrink-0" />
                  <span>{{ row.fuenteHerramienta }}</span>
                </div>
                <p class="text-[10px] font-mono text-slate-400 mt-0.5">{{ row.sintaxis }}</p>
              </td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <div class="flex items-center gap-2">
                  <div class="w-14 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      class="h-full rounded-full"
                      :style="{ width: `${row.confianza}%`, background: row.confianza >= 60 ? '#F57C00' : '#E53935' }"
                    />
                  </div>
                  <span
                    class="text-xs font-bold"
                    :style="{ color: row.confianza >= 60 ? '#F57C00' : '#E53935' }"
                  >
                    {{ row.confianza }}%
                  </span>
                </div>
              </td>
              <td class="px-4 py-3.5">
                <div class="flex items-center gap-1.5 whitespace-nowrap">
                  <button
                    @click="selectedVal = row"
                    class="flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold text-[#00aea7] bg-[#00aea7]/10 border border-[#00aea7]/30 rounded-lg hover:bg-[#00aea7]/20 transition-all cursor-pointer shadow-sm"
                    title="Inspeccionar todos los metadatos recuperados"
                  >
                    <Eye :size="12" />
                    <span>Ver Detalle</span>
                  </button>
                  <button
                    @click="validateItem(row)"
                    :disabled="processingId === row.id"
                    class="flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-all cursor-pointer shadow-sm disabled:opacity-50"
                    title="Validar y aprobar el metadato recuperado"
                  >
                    <ShieldCheck :size="12" />
                    <span>Validar</span>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <Pagination
        v-if="filtered.length > 0"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total-items="filtered.length"
      />
    </Card>

    <!-- Modal Dinámico y Responsivo de Metadatos Recuperados -->
    <div
      v-if="selectedVal"
      @click.self="selectedVal = null"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/55 backdrop-blur-xs p-3 sm:p-6"
    >
      <div
        class="bg-white rounded-2xl shadow-2xl border border-gray-100 w-full max-w-[95vw] sm:max-w-[90vw] md:max-w-3xl lg:max-w-4xl max-h-[90vh] flex flex-col overflow-hidden"
        role="dialog"
        aria-modal="true"
      >
        <!-- Header Fijo -->
        <div class="px-5 py-4 border-b border-gray-100 bg-slate-50/80 flex items-center justify-between shrink-0 gap-3">
          <div class="flex items-center gap-3 min-w-0">
            <div class="w-9 h-9 rounded-xl bg-[#00aea7]/10 text-[#00aea7] flex items-center justify-center font-bold shrink-0">
              <Eye :size="18" />
            </div>
            <div class="min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <h3 class="text-sm font-bold text-slate-800">Validación de Metadatos Recuperados</h3>
                <span
                  class="px-2 py-0.5 text-[10px] font-bold rounded-full border"
                  :class="selectedVal.confianza >= 60 ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-red-50 text-red-700 border-red-200'"
                >
                  Confianza: {{ selectedVal.confianza }}%
                </span>
              </div>
              <p class="text-[11px] text-slate-500 truncate">
                ID #{{ selectedVal.id }} · Fuente: {{ selectedVal.fuenteHerramienta }}
              </p>
            </div>
          </div>
          <button
            @click="selectedVal = null"
            class="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/70 transition-colors cursor-pointer shrink-0"
            title="Cerrar modal (Esc)"
          >
            <X :size="18" />
          </button>
        </div>

        <!-- Cuerpo con Scroll Interno -->
        <div class="flex-1 overflow-y-auto min-h-0 p-4 sm:p-6 space-y-5">
          <!-- Información Principal de la Publicación -->
          <div class="space-y-2">
            <div class="flex items-center flex-wrap gap-2">
              <span class="text-[10px] font-bold uppercase tracking-wider text-[#00aea7] bg-[#00aea7]/10 px-2 py-0.5 rounded">
                Registro #{{ selectedVal.id }}
              </span>
              <span v-if="selectedVal.tipo_recurso" class="text-[10px] font-semibold text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                {{ selectedVal.tipo_recurso }}
              </span>
              <span v-if="selectedVal.tipo_falencia" class="text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                Falencia: {{ selectedVal.tipo_falencia }}
              </span>
            </div>
            <h4 class="text-sm sm:text-base font-bold text-slate-800 leading-snug">{{ selectedVal.title }}</h4>
            <div class="flex flex-wrap items-center gap-3 pt-1">
              <a
                v-if="selectedVal.doi"
                :href="formatDoiUrl(selectedVal.doi)"
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center gap-1.5 text-xs font-mono font-medium text-[#1565C0] hover:text-[#0d47a1] hover:underline bg-blue-50/70 hover:bg-blue-100/70 px-2.5 py-1 rounded-md border border-blue-200 transition-colors"
                :title="`Abrir documento oficial en doi.org: ${selectedVal.doi}`"
              >
                <span>DOI: {{ selectedVal.doi }}</span>
                <ExternalLink :size="11" class="text-blue-500 shrink-0" />
              </a>
              <span v-if="selectedVal.dspace_uuid" class="text-[11px] font-mono text-slate-400">
                UUID: {{ selectedVal.dspace_uuid }}
              </span>
            </div>
          </div>

          <!-- Alerta de Validación Algorítmica -->
          <div class="p-3 rounded-xl bg-amber-50/70 border border-amber-200/80 flex items-start gap-2.5 text-xs text-amber-900">
            <AlertTriangle :size="16" class="text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p class="font-semibold">Revisión Manual Requerida ({{ selectedVal.confianza }}% de coincidencia)</p>
              <p class="text-[11px] text-amber-800/90 mt-0.5">{{ selectedVal.detalle }}</p>
            </div>
          </div>

          <!-- Grid de Metadatos Recuperados -->
          <div class="space-y-4">
            <h5 class="text-xs font-bold uppercase tracking-wider text-slate-500 border-b border-gray-100 pb-1.5">
              Metadatos Recuperados por el Agente
            </h5>

            <!-- 1. Abstract / Resumen -->
            <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200/70 space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-[11px] font-bold text-slate-600 uppercase">Resumen (dc.description.abstract)</span>
                <span
                  class="text-[10px] font-semibold px-2 py-0.5 rounded"
                  :class="selectedVal.abstract_enriquecido ? 'bg-teal-50 text-teal-700 border border-teal-200' : 'bg-gray-100 text-gray-500'"
                >
                  {{ selectedVal.abstract_enriquecido ? 'Recuperado' : 'No recuperado' }}
                </span>
              </div>
              <div
                v-if="selectedVal.abstract_enriquecido"
                class="p-3 bg-white rounded-lg border border-slate-200 text-xs text-slate-800 leading-relaxed max-h-48 overflow-y-auto whitespace-pre-line"
              >
                {{ selectedVal.abstract_enriquecido }}
              </div>
              <p v-else class="text-xs text-slate-400 italic">No se recuperó un resumen nuevo para esta publicación.</p>

              <div v-if="selectedVal.resumen_original" class="pt-1">
                <span class="text-[10px] font-semibold text-slate-400 uppercase block mb-1">Resumen original en DSpace:</span>
                <div class="p-2.5 bg-gray-100/70 rounded-lg text-[11px] text-slate-600 max-h-24 overflow-y-auto">
                  {{ selectedVal.resumen_original }}
                </div>
              </div>
            </div>

            <!-- 2. Palabras Clave -->
            <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200/70 space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-[11px] font-bold text-slate-600 uppercase">Palabras Clave (dc.subject)</span>
                <span
                  class="text-[10px] font-semibold px-2 py-0.5 rounded"
                  :class="parsedKeywords(selectedVal.palabras_clave).length > 0 ? 'bg-teal-50 text-teal-700 border border-teal-200' : 'bg-gray-100 text-gray-500'"
                >
                  {{ parsedKeywords(selectedVal.palabras_clave).length }} término(s)
                </span>
              </div>
              <div v-if="parsedKeywords(selectedVal.palabras_clave).length > 0" class="flex flex-wrap gap-1.5">
                <span
                  v-for="(kw, idx) in parsedKeywords(selectedVal.palabras_clave)"
                  :key="idx"
                  class="px-2.5 py-1 bg-white text-slate-700 border border-slate-200 rounded-md text-xs font-medium shadow-2xs"
                >
                  {{ kw }}
                </span>
              </div>
              <p v-else class="text-xs text-slate-400 italic">Sin palabras clave recuperadas.</p>
            </div>

            <!-- 3. Clasificación OCDE y ODS -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <!-- Área OCDE -->
              <div class="p-3.5 rounded-xl bg-purple-50/40 border border-purple-200/60 space-y-2">
                <span class="text-[11px] font-bold text-purple-900 uppercase block">Clasificación OCDE (IA)</span>
                <div v-if="toArray(selectedVal.area_ocde).length > 0" class="flex flex-wrap gap-1.5">
                  <span
                    v-for="(ocde, idx) in toArray(selectedVal.area_ocde)"
                    :key="idx"
                    class="px-2.5 py-1 bg-white text-purple-800 border border-purple-200 rounded-md text-xs font-medium"
                  >
                    {{ ocde }}
                  </span>
                </div>
                <p v-else class="text-xs text-slate-400 italic">Sin clasificación OCDE asignada.</p>
              </div>

              <!-- Área ODS -->
              <div class="p-3.5 rounded-xl bg-emerald-50/40 border border-emerald-200/60 space-y-2">
                <span class="text-[11px] font-bold text-emerald-900 uppercase block">Objetivos ODS (IA)</span>
                <div v-if="toArray(selectedVal.area_ods).length > 0" class="flex flex-wrap gap-1.5">
                  <span
                    v-for="(ods, idx) in toArray(selectedVal.area_ods)"
                    :key="idx"
                    class="px-2.5 py-1 bg-white text-emerald-800 border border-emerald-200 rounded-md text-xs font-medium"
                  >
                    {{ ods }}
                  </span>
                </div>
                <p v-else class="text-xs text-slate-400 italic">Sin clasificación ODS asignada.</p>
              </div>
            </div>

            <!-- 4. Derechos de Acceso, Licencia y Financiamiento -->
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div class="p-3 rounded-xl bg-slate-50 border border-slate-200/70">
                <span class="text-[10px] font-bold text-slate-500 uppercase block mb-1">Derechos / Acceso OA</span>
                <span v-if="selectedVal.derechos_acceso" class="text-xs font-semibold text-slate-800 bg-white px-2 py-0.5 rounded border border-slate-200 inline-block">
                  {{ selectedVal.derechos_acceso }}
                </span>
                <span v-else class="text-xs text-slate-400 italic">No especificado</span>
              </div>

              <div class="p-3 rounded-xl bg-slate-50 border border-slate-200/70">
                <span class="text-[10px] font-bold text-slate-500 uppercase block mb-1">Licencia</span>
                <a
                  v-if="selectedVal.licencia && String(selectedVal.licencia).startsWith('http')"
                  :href="selectedVal.licencia"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-xs text-blue-600 hover:underline break-all inline-flex items-center gap-1"
                >
                  <span>{{ selectedVal.licencia }}</span>
                  <ExternalLink :size="10" class="shrink-0" />
                </a>
                <span v-else-if="selectedVal.licencia" class="text-xs font-medium text-slate-700 break-all">
                  {{ selectedVal.licencia }}
                </span>
                <span v-else class="text-xs text-slate-400 italic">No especificada</span>
              </div>

              <div class="p-3 rounded-xl bg-slate-50 border border-slate-200/70">
                <span class="text-[10px] font-bold text-slate-500 uppercase block mb-1">Financiamiento</span>
                <div v-if="toArray(selectedVal.fuente_financiamiento).length > 0" class="space-y-1">
                  <span
                    v-for="(f, idx) in toArray(selectedVal.fuente_financiamiento)"
                    :key="idx"
                    class="text-xs font-medium text-slate-700 block break-words"
                  >
                    {{ f }}
                  </span>
                </div>
                <span v-else class="text-xs text-slate-400 italic">No especificado</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer Fijo -->
        <div class="px-5 py-3.5 border-t border-gray-100 bg-slate-50/90 flex items-center justify-between flex-wrap gap-2 shrink-0">
          <button
            @click="rejectItem(selectedVal)"
            :disabled="processingId === selectedVal.id"
            class="px-3.5 py-2 text-xs font-semibold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 rounded-xl transition-all cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
            title="Descartar coincidencia errónea y devolver a cola pendiente"
          >
            <XCircle :size="14" />
            <span>Rechazar Coincidencia</span>
          </button>

          <div class="flex items-center gap-2 ml-auto">
            <button
              @click="selectedVal = null"
              class="px-4 py-2 text-xs font-semibold text-slate-600 bg-white hover:bg-gray-100 border border-gray-200 rounded-xl transition-all cursor-pointer"
            >
              Cerrar
            </button>
            <button
              @click="validateFromModal(selectedVal)"
              :disabled="processingId === selectedVal.id"
              class="px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-sm transition-all cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
            >
              <ShieldCheck :size="14" />
              <span>{{ processingId === selectedVal.id ? 'Validando...' : 'Validar y Aprobar' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { Search, Cpu, ShieldCheck, Eye, X, XCircle, ExternalLink, AlertTriangle, RefreshCw } from 'lucide-vue-next'
import Card from '../components/common/Card.vue'
import SectionHeader from '../components/common/SectionHeader.vue'
import Pagination from '../components/common/Pagination.vue'
import { proposalService } from '../services/proposalService'
import { authService } from '../services/authService'
import type { User } from '../types'

const props = defineProps<{
  user?: User | null
}>()

const searchVal = ref('')
const filterOptions = ['Todos', 'Confianza Media (60-79%)', 'Confianza Baja (<60%)']
const filterStatus = ref('Todos')
const selectedVal = ref<any | null>(null)
const loading = ref(true)
const processingId = ref<string | null>(null)
const validationRecords = ref<any[]>([])
const toast = ref<{ type: 'success' | 'error'; message: string } | null>(null)

const currentPage = ref(1)
const pageSize = ref(15)

watch([searchVal, filterStatus], () => {
  currentPage.value = 1
})

const showToast = (message: string, type: 'success' | 'error' = 'success') => {
  toast.value = { type, message }
  setTimeout(() => {
    if (toast.value?.message === message) {
      toast.value = null
    }
  }, 6000)
}

const formatDoiUrl = (doi?: string): string => {
  if (!doi) return '#'
  const clean = doi.trim().replace(/^https?:\/\/(dx\.)?doi\.org\//i, '')
  return `https://doi.org/${clean}`
}

const toArray = (val: any): string[] => {
  if (!val) return []
  if (Array.isArray(val)) return val.filter(Boolean).map((v) => String(v).trim())
  if (typeof val === 'string') {
    const trimmed = val.trim()
    if (!trimmed || trimmed === '[]' || trimmed === 'null') return []
    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) return parsed.filter(Boolean).map((v) => String(v).trim())
    } catch {
      // string normal
    }
    return [trimmed]
  }
  return [String(val)]
}

const parsedKeywords = (val: any): string[] => {
  const arr = toArray(val)
  const result: string[] = []
  for (const item of arr) {
    // Algunos registros de Crossref/OpenAlex agrupan keywords separadas por coma en un solo string
    const parts = item.split(',').map((s) => s.trim()).filter(Boolean)
    result.push(...parts)
  }
  return Array.from(new Set(result))
}

const buildCamposLista = (p: any): string[] => {
  const tags: string[] = []
  if (p.abstract_enriquecido) tags.push('Resumen')
  if (parsedKeywords(p.palabras_clave).length > 0) tags.push('Palabras clave')
  if (toArray(p.area_ocde).length > 0) tags.push('Área OCDE')
  if (toArray(p.area_ods).length > 0) tags.push('Área ODS')
  if (p.derechos_acceso || p.licencia) tags.push('Derechos/Licencia')
  if (toArray(p.fuente_financiamiento).length > 0) tags.push('Financiamiento')
  return tags
}

const loadProposals = async () => {
  loading.value = true
  try {
    const isAcademico = props.user?.role === 'Academico'
    const orcidParam = isAcademico && props.user?.orcid ? props.user.orcid : undefined
    const list = await proposalService.getValidationRecords(orcidParam)
    if (list && list.length > 0) {
      validationRecords.value = list.map((p: any) => ({
        id: String(p.id || '').substring(0, 8),
        fullId: p.fullId || p.id,
        rawId: p.id,
        dspace_uuid: p.dspace_uuid || '',
        title: p.title || 'Publicación Científica',
        doi: p.doi || p.candidate_doi || '',
        campo: p.campo || 'Metadatos externos',
        camposLista: buildCamposLista(p),
        propuestaIA: p.propuestaIA || 'Valor propuesto por fuente externa',
        fuenteHerramienta: p.fuenteHerramienta || 'Fuente Académica',
        sintaxis: p.sintaxis || 'Validación manual requerida (Confianza < 80%)',
        confianza: p.confianza !== undefined ? p.confianza : Math.round((p.match_score || 0.5) * 100),
        estado: 'Pendiente de Validación',
        detalle: p.detalle || 'Requiere validación manual por coincidencia menor al 80%.',
        orcid: p.orcid || null,
        tipo_recurso: p.tipo_recurso || '',
        tipo_falencia: p.tipo_falencia || '',
        resumen_original: p.resumen_original || '',
        abstract_enriquecido: p.abstract_enriquecido || '',
        palabras_clave: p.palabras_clave || [],
        area_ocde: p.area_ocde || [],
        area_ods: p.area_ods || [],
        derechos_acceso: p.derechos_acceso || '',
        licencia: p.licencia || '',
        fuente_financiamiento: p.fuente_financiamiento || [],
      }))
    } else {
      validationRecords.value = []
    }
  } catch (err) {
    console.error('Error cargando registros reales de validación:', err)
    validationRecords.value = []
  } finally {
    loading.value = false
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && selectedVal.value) {
    selectedVal.value = null
  }
}

onMounted(() => {
  loadProposals()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

const filtered = computed(() => {
  return validationRecords.value.filter((r) => {
    const s = searchVal.value.toLowerCase()
    const matchSearch =
      r.title.toLowerCase().includes(s) ||
      r.id.toLowerCase().includes(s) ||
      r.campo.toLowerCase().includes(s) ||
      (r.doi && r.doi.toLowerCase().includes(s))

    let matchFilter = true
    if (filterStatus.value === 'Confianza Media (60-79%)') {
      matchFilter = r.confianza >= 60 && r.confianza < 80
    } else if (filterStatus.value === 'Confianza Baja (<60%)') {
      matchFilter = r.confianza < 60
    }

    return matchSearch && matchFilter
  })
})

const paginatedRecords = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

const validateItem = async (item: any): Promise<boolean> => {
  processingId.value = item.id
  try {
    const targetId = item.rawId || item.fullId || item.id
    const storedUser = authService.getStoredUser()
    await proposalService.validateRecord(targetId, storedUser?.id)
    showToast(`Registro #${item.id} validado y aprobado exitosamente como ENRIQUECIDO.`)
    await loadProposals()
    return true
  } catch (err: any) {
    showToast(`Error al validar registro #${item.id}: ${err?.response?.data?.detail || err.message || err}`, 'error')
    return false
  } finally {
    processingId.value = null
  }
}

const validateFromModal = async (item: any) => {
  const ok = await validateItem(item)
  if (ok) {
    selectedVal.value = null
  }
}

const rejectItem = async (item: any) => {
  if (!confirm(`¿Desea rechazar esta coincidencia dudosa para #${item.id} y devolver el registro a la cola PENDIENTE?`)) {
    return
  }
  processingId.value = item.id
  try {
    const targetId = item.rawId || item.fullId || item.id
    await proposalService.rejectQueueItem(targetId, 'Coincidencia dudosa rechazada en validación manual')
    showToast(`Coincidencia rechazada para #${item.id}. El registro volvió a estado PENDIENTE.`)
    selectedVal.value = null
    await loadProposals()
  } catch (err: any) {
    showToast(`Error al rechazar registro #${item.id}: ${err?.response?.data?.detail || err.message || err}`, 'error')
  } finally {
    processingId.value = null
  }
}
</script>
