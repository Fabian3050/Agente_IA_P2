<template>
  <div class="h-full overflow-y-auto space-y-4">
    <SectionHeader
      title="Validación de metadatos"
      description="Asegure la calidad de los metadatos antes de su aprobación final."
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

    <Card>
      <div class="p-4 border-b border-gray-50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div class="relative flex-1 max-w-xs">
          <Search :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-[#6b7a90]" />
          <input
            type="text"
            placeholder="Buscar por ID, título o campo..."
            v-model="searchVal"
            class="w-full pl-9 pr-3 py-2 text-xs border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#00aea7]/20 focus:border-[#00aea7]"
          />
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <div class="flex gap-1">
            <button
              v-for="f in ['Todos', 'Apto p/ Aprobación', 'Anomalía Técnica']"
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
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-gray-50 bg-slate-50/50">
              <th
                v-for="h in ['ID & Título', 'DOI', 'Campo evaluado', 'Fuente', 'Confianza Enriquecimiento', 'Acciones']"
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
                    : 'No hay metadatos pendientes de validación técnica en este momento.' }}
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
              v-for="row in filtered"
              :key="row.id"
              class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors"
            >
              <td class="px-4 py-3.5 max-w-[220px]">
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
                  <span>{{ row.doi }}</span>
                  <ExternalLink :size="11" class="text-blue-500 shrink-0" />
                </a>
                <span v-else class="text-[11px] text-slate-400 font-mono italic">Sin DOI</span>
              </td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <span class="text-xs font-semibold px-2.5 py-1 bg-blue-50 text-blue-700 rounded-md border border-blue-100">
                  {{ row.campo }}
                </span>
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
                      :style="{ width: `${row.confianza}%`, background: row.confianza >= 80 ? '#2E7D32' : '#F57C00' }"
                    />
                  </div>
                  <span
                    class="text-xs font-bold"
                    :style="{ color: row.confianza >= 80 ? '#2E7D32' : '#F57C00' }"
                  >
                    {{ row.confianza }}%
                  </span>
                </div>
              </td>
              <td class="px-4 py-3.5">
                <div class="flex items-center gap-1.5 whitespace-nowrap">
                  <button
                    @click="validateItem(row)"
                    class="flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-all cursor-pointer shadow-sm"
                    title="Validar el metadato recuperado"
                  >
                    <ShieldCheck :size="12" />
                    <span>Validar</span>
                  </button>
                  <button
                    @click="selectedVal = row"
                    class="flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold text-[#00aea7] bg-[#00aea7]/10 border border-[#00aea7]/30 rounded-lg hover:bg-[#00aea7]/20 transition-all cursor-pointer shadow-sm"
                    title="Ver el metadato recuperado"
                  >
                    <Eye :size="12" />
                    <span>Ver</span>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <!-- Modal de Metadato Recuperado -->
    <div
      v-if="selectedVal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-gray-100 w-full max-w-lg overflow-hidden flex flex-col">
        <div class="px-6 py-4 border-b border-gray-100 bg-slate-50 flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <div class="w-8 h-8 rounded-lg bg-[#00aea7]/10 text-[#00aea7] flex items-center justify-center font-bold">
              <Eye :size="18" />
            </div>
            <div>
              <h3 class="text-sm font-bold text-slate-800">Metadato Recuperado</h3>
              <p class="text-[11px] text-slate-500">Valor extraído y evaluado algorítmicamente</p>
            </div>
          </div>
          <button
            @click="selectedVal = null"
            class="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors cursor-pointer"
          >
            <X :size="18" />
          </button>
        </div>

        <div class="p-6 space-y-4">
          <div>
            <span class="text-[10px] font-bold uppercase tracking-wider text-[#00aea7] block mb-1">ID Registro #{{ selectedVal.id }}</span>
            <h4 class="text-base font-bold text-slate-800 leading-snug">{{ selectedVal.title }}</h4>
            <div v-if="selectedVal.doi" class="mt-2">
              <a
                :href="formatDoiUrl(selectedVal.doi)"
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center gap-1.5 text-xs font-mono font-medium text-[#1565C0] hover:text-[#0d47a1] hover:underline bg-blue-50/70 hover:bg-blue-100/70 px-2.5 py-1 rounded-md border border-blue-200 transition-colors"
                :title="`Abrir documento oficial en doi.org: ${selectedVal.doi}`"
              >
                <span>{{ selectedVal.doi }}</span>
                <ExternalLink :size="11" class="text-blue-500 shrink-0" />
              </a>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-slate-50 border border-slate-200/60 space-y-3">
            <div>
              <span class="text-[11px] font-semibold text-slate-500 uppercase block mb-1">Campo evaluado</span>
              <span class="text-xs font-semibold px-2.5 py-1 bg-blue-50 text-blue-700 rounded-md border border-blue-100 inline-block">
                {{ selectedVal.campo }}
              </span>
            </div>

            <div>
              <span class="text-[11px] font-semibold text-slate-500 uppercase block mb-1">Valor propuesto por IA (Metadato)</span>
              <div class="p-3 bg-white rounded-lg border border-slate-200 font-mono text-xs text-teal-900 font-medium break-words">
                {{ selectedVal.propuestaIA }}
              </div>
            </div>
          </div>

          <div class="p-3 rounded-xl border border-gray-100 bg-gray-50/50">
            <span class="text-[10px] text-slate-400 font-bold uppercase block mb-0.5">Sintaxis / Formato</span>
            <span class="font-mono text-slate-600 text-[11px] block">{{ selectedVal.sintaxis }}</span>
            <p class="text-[11px] text-slate-500 mt-2">{{ selectedVal.detalle }}</p>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-100 bg-slate-50 flex justify-end gap-2">
          <button
            @click="validateItem(selectedVal); selectedVal = null"
            class="px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-sm transition-all cursor-pointer flex items-center gap-1.5"
          >
            <ShieldCheck :size="14" /> Validar metadato
          </button>
          <button
            @click="selectedVal = null"
            class="px-5 py-2 text-xs font-semibold text-white bg-[#00aea7] hover:bg-[#009b95] rounded-xl shadow-sm transition-all cursor-pointer"
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
import { Search, Cpu, ShieldCheck, Eye, X, ExternalLink } from 'lucide-vue-next'
import Card from '../components/common/Card.vue'
import SectionHeader from '../components/common/SectionHeader.vue'
import { proposalService } from '../services/proposalService'
import type { User } from '../types'

const props = defineProps<{
  user?: User | null
}>()

const searchVal = ref('')
const filterStatus = ref('Todos')
const selectedVal = ref<any | null>(null)
const loading = ref(true)
const validationRecords = ref<any[]>([])

const formatDoiUrl = (doi?: string): string => {
  if (!doi) return '#'
  const clean = doi.trim().replace(/^https?:\/\/(dx\.)?doi\.org\//i, '')
  return `https://doi.org/${clean}`
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
        title: p.title || 'Publicación Científica',
        doi: p.doi || p.candidate_doi || '',
        campo: p.campo || 'Metadatos externos',
        propuestaIA: p.propuestaIA || 'Valor propuesto por fuente externa',
        fuenteHerramienta: p.fuenteHerramienta || 'Fuente Académica',
        sintaxis: p.sintaxis || 'Validación manual requerida (Confianza < 80%)',
        confianza: p.confianza !== undefined ? p.confianza : Math.round((p.match_score || 0.5) * 100),
        color: (p.confianza || 0) >= 80 ? '#2E7D32' : '#F57C00',
        estado: 'Pendiente de Validación',
        detalle: p.detalle || 'Requiere validación manual por coincidencia menor al 80%.',
        orcid: p.orcid || null
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

onMounted(() => {
  loadProposals()
})

const filtered = computed(() => {
  return validationRecords.value.filter((r) => {
    const s = searchVal.value.toLowerCase()
    const matchSearch =
      r.title.toLowerCase().includes(s) ||
      r.id.includes(s) ||
      r.campo.toLowerCase().includes(s) ||
      (r.doi && r.doi.toLowerCase().includes(s))
    const matchFilter = filterStatus.value === 'Todos' || r.estado === filterStatus.value
    return matchSearch && matchFilter
  })
})

const validateItem = async (item: any) => {
  try {
    const targetId = item.rawId || item.fullId || item.id
    await proposalService.validateRecord(targetId)
    item.estado = 'Validado / Aprobado'
    alert(`¡Validación exitosa para el registro #${item.id}! El metadato ha sido aprobado y marcado como enriquecido.`)
    await loadProposals()
  } catch (err: any) {
    alert(`Error al validar registro #${item.id}: ${err?.response?.data?.detail || err.message || err}`)
  }
}
</script>

