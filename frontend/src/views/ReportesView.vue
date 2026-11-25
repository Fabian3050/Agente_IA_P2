<template>
  <div class="h-full overflow-y-auto space-y-6 print:p-0 print:space-y-4">
    <!-- Encabezado de Sección -->
    <div class="flex items-start justify-between flex-wrap gap-4">
      <SectionHeader
        title="Reportes y Estadísticas de Recuperación"
        description="Análisis integral del rendimiento del agente inteligente, consultas a fuentes externas y enriquecimiento del repositorio científico."
      />
      <!-- Badge de Estado de Datos -->
      <div class="flex items-center gap-2 print:hidden">
        <span class="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
          <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          Datos en tiempo real (PostgreSQL)
        </span>
      </div>
    </div>

    <!-- Selector de período y exportación -->
    <div class="flex items-center gap-3 flex-wrap print:hidden">
      <div class="inline-flex p-1 bg-gray-100 rounded-lg">
        <button
          v-for="p in periods"
          :key="p.key"
          @click="selectPeriod(p.key)"
          class="px-4 py-1.5 text-xs rounded-md font-medium transition-all cursor-pointer"
          :class="selectedPeriod === p.key ? 'bg-white text-[#00aea7] shadow-sm font-semibold' : 'text-[#6b7a90] hover:text-[#1a2332]'"
        >
          {{ p.label }}
        </button>
      </div>

      <div class="ml-auto flex items-center gap-2">
        <button
          @click="loadAllData"
          :disabled="loading"
          class="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-[#6b7a90] bg-white border border-gray-200 rounded-lg hover:bg-gray-50 shadow-sm transition-all cursor-pointer disabled:opacity-50"
          title="Recargar datos desde la base de datos"
        >
          <RefreshCw :size="13" :class="{ 'animate-spin': loading }" />
          <span>Actualizar</span>
        </button>

        <button
          @click="exportPdf"
          class="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white rounded-lg hover:opacity-90 shadow-sm transition-all cursor-pointer"
          style="background: #F57C00"
        >
          <Download :size="13" />
          <span>Exportar PDF / Imprimir</span>
        </button>
      </div>
    </div>

    <!-- Notificación Toast Temporal -->
    <div
      v-if="toastMessage"
      class="p-3 text-xs rounded-lg bg-blue-50 text-blue-800 border border-blue-200 flex items-center justify-between transition-all"
    >
      <div class="flex items-center gap-2">
        <CheckCircle2 :size="16" class="text-blue-600 flex-shrink-0" />
        <span>{{ toastMessage }}</span>
      </div>
      <button @click="toastMessage = null" class="text-xs font-bold text-blue-600 hover:text-blue-800 ml-3">✕</button>
    </div>

    <!-- Sección 1: Rendimiento y Actividad General -->
    <div>
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-xs font-bold uppercase tracking-wider text-[#6b7a90]">
          1. Rendimiento y Actividad General del Agente IA ({{ currentPeriodLabel }})
        </h3>
        <span class="text-[11px] text-[#6b7a90] print:block">
          Universo total monitoreado: <strong class="text-[#1a2332]">{{ totalMonitoreados.toLocaleString('es-CL') }}</strong> registros
        </span>
      </div>

      <!-- Tarjetas KPIs -->
      <div class="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
        <Card
          v-for="s in generalKpis"
          :key="s.label"
          customClass="p-4 relative overflow-hidden"
        >
          <p class="text-xs text-[#6b7a90] mb-1">{{ s.label }}</p>
          <div class="flex items-baseline gap-2">
            <p class="text-2xl font-bold text-[#1a2332]">{{ s.value }}</p>
            <span v-if="s.subtitle" class="text-[11px] text-[#6b7a90]">{{ s.subtitle }}</span>
          </div>
          <div class="mt-2 text-[11px] text-gray-500 flex items-center gap-1">
            <span :class="s.badgeColor">{{ s.badgeText }}</span>
          </div>
        </Card>
      </div>

      <!-- Tarjeta extra: Métricas del LLM y Clasificación Autónoma -->
      <div class="mb-4 bg-gradient-to-r from-teal-50/60 to-blue-50/40 border border-[#00aea7]/20 rounded-xl p-3.5 flex items-center justify-between flex-wrap gap-3">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-lg bg-[#00aea7]/15 flex items-center justify-center text-[#00aea7]">
            <Cpu :size="18" />
          </div>
          <div>
            <h4 class="text-xs font-bold text-[#1a2332]">Motor de Inferencia LLM (Ollama)</h4>
            <p class="text-[11px] text-[#6b7a90]">Clasificación temática en Áreas OCDE y Objetivos de Desarrollo Sostenible (ODS)</p>
          </div>
        </div>
        <div class="flex items-center gap-6 text-xs">
          <div>
            <span class="text-gray-500 text-[11px]">Inferencias registradas:</span>
            <strong class="text-[#1a2332] ml-1.5 font-bold">{{ llmCalls.toLocaleString('es-CL') }}</strong>
          </div>
          <div class="h-4 w-px bg-gray-200"></div>
          <div>
            <span class="text-gray-500 text-[11px]">Tiempo prom. de respuesta:</span>
            <strong class="text-[#00aea7] ml-1.5 font-bold">{{ llmAvgSeconds }}s</strong>
          </div>
        </div>
      </div>

      <!-- Weekly Activity & Donut -->
      <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card customClass="p-5 xl:col-span-2">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-[#1a2332]">Actividad cronológica del período</h3>
            <span class="text-[11px] text-gray-500">Valores reales registrados en base de datos</span>
          </div>

          <div class="h-60 w-full flex items-end justify-between gap-6 pt-6 pb-2 px-4 border-b border-gray-100">
            <div
              v-for="item in weeklyData"
              :key="item.week"
              class="flex-1 flex flex-col items-center gap-2 h-full justify-end"
            >
              <div class="w-full flex items-end justify-center gap-2 h-full">
                <!-- Detectados -->
                <div class="flex flex-col items-center justify-end h-full w-5">
                  <span class="text-[9px] text-[#1f92ff] font-semibold mb-1 opacity-80">{{ item.detectados }}</span>
                  <div
                    class="w-full rounded-t bg-[#1f92ff] transition-all hover:opacity-85 shadow-sm"
                    :style="{ height: `${calcBarHeight(item.detectados, maxWeeklyDetectados)}%` }"
                    :title="`Detectados: ${item.detectados.toLocaleString('es-CL')}`"
                  />
                </div>

                <!-- Enriquecidos -->
                <div class="flex flex-col items-center justify-end h-full w-5">
                  <span class="text-[9px] text-[#00aea7] font-semibold mb-1">{{ item.enriquecidos }}</span>
                  <div
                    class="w-full rounded-t bg-[#00aea7] transition-all hover:opacity-85 shadow-sm"
                    :style="{ height: `${calcBarHeight(item.enriquecidos, maxWeeklyEnriquecidos)}%` }"
                    :title="`Enriquecidos con éxito: ${item.enriquecidos}`"
                  />
                </div>

                <!-- Aprobados -->
                <div class="flex flex-col items-center justify-end h-full w-5">
                  <span class="text-[9px] text-[#F57C00] font-semibold mb-1">{{ item.aprobados }}</span>
                  <div
                    class="w-full rounded-t bg-[#F57C00] transition-all hover:opacity-85 shadow-sm"
                    :style="{ height: `${calcBarHeight(item.aprobados, maxWeeklyAprobados)}%` }"
                    :title="`Aprobados para DSpace: ${item.aprobados}`"
                  />
                </div>
              </div>
              <span class="text-[11px] text-gray-600 font-medium mt-1">{{ item.week }}</span>
            </div>
          </div>

          <div class="flex items-center justify-center gap-6 mt-3 text-xs">
            <span class="flex items-center gap-1.5 text-gray-600">
              <span class="w-2.5 h-2.5 rounded-sm bg-[#1f92ff]"></span> Detectados en cola
            </span>
            <span class="flex items-center gap-1.5 text-gray-600 font-medium">
              <span class="w-2.5 h-2.5 rounded-sm bg-[#00aea7]"></span> Enriquecidos por Agente
            </span>
            <span class="flex items-center gap-1.5 text-gray-600 font-medium">
              <span class="w-2.5 h-2.5 rounded-sm bg-[#F57C00]"></span> Aprobados / Completos
            </span>
          </div>
        </Card>

        <!-- Distribución de campos Donut -->
        <Card customClass="p-5 xl:col-span-1 flex flex-col justify-between">
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-sm font-semibold text-[#1a2332]">Campos Enriquecidos</h3>
            <span class="text-[11px] text-[#6b7a90]">{{ totalCamposEnriquecidos }} recuperados</span>
          </div>

          <div class="flex flex-col items-center gap-4 my-auto">
            <div class="relative w-36 h-36 flex items-center justify-center">
              <svg viewBox="0 0 100 100" class="w-full h-full -rotate-90 transform">
                <circle
                  v-for="(slice, i) in donutSlices"
                  :key="i"
                  cx="50"
                  cy="50"
                  r="35"
                  fill="transparent"
                  :stroke="slice.color"
                  stroke-width="18"
                  :stroke-dasharray="`${slice.dashLength} ${circumference - slice.dashLength}`"
                  :stroke-dashoffset="slice.dashOffset"
                />
              </svg>
              <div class="absolute inset-0 flex flex-col items-center justify-center text-center">
                <span class="text-xs font-bold text-[#1a2332]">5</span>
                <span class="text-[9px] text-[#6b7a90]">Metadatos</span>
              </div>
            </div>

            <div class="w-full space-y-1.5 pt-2 border-t border-gray-50">
              <div
                v-for="d in donutData"
                :key="d.name"
                class="flex items-center gap-2"
              >
                <div class="w-2.5 h-2.5 rounded-sm flex-shrink-0" :style="{ background: d.color }" />
                <span class="text-xs text-[#6b7a90] truncate">{{ d.name }}</span>
                <span class="text-xs text-gray-400">({{ d.count || 0 }})</span>
                <span class="text-xs font-semibold text-[#1a2332] ml-auto pl-2">{{ d.value }}%</span>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>

    <!-- Sección 2: Estadísticas de Recuperación desde Fuentes Externas -->
    <div class="pt-2">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-xs font-bold uppercase tracking-wider text-[#6b7a90]">
          2. Conectividad y Tasa de Éxito de Fuentes Académicas Externas
        </h3>
        <span class="text-[11px] text-[#6b7a90]">
          Métricas calculadas sobre <strong>{{ totalQueriesAcrossSources }}</strong> consultas atómicas registradas
        </span>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-4">
        <Card
          v-for="api in sources"
          :key="api.name"
          customClass="p-5 flex flex-col justify-between"
        >
          <div>
            <div class="flex items-start justify-between mb-3">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-[#e0f7f6] flex items-center justify-center">
                  <Globe :size="18" style="color: #00aea7" />
                </div>
                <div>
                  <h3 class="text-sm font-semibold text-[#1a2332]">{{ api.name }}</h3>
                  <p class="text-[11px] text-[#6b7a90]">Última consulta: {{ api.lastQuery }}</p>
                </div>
              </div>
              <Badge :color="api.status === 'Conectado' ? 'green' : 'gray'">{{ api.status }}</Badge>
            </div>

            <div class="grid grid-cols-3 gap-2 mb-3">
              <div class="bg-gray-50 rounded-lg p-2.5 text-center">
                <p class="text-[11px] text-[#6b7a90] mb-0.5">Recuperados</p>
                <p class="text-sm font-semibold text-[#1a2332]">{{ api.recovered.toLocaleString() }}</p>
              </div>
              <div class="bg-gray-50 rounded-lg p-2.5 text-center">
                <p class="text-[11px] text-[#6b7a90] mb-0.5">Consultas</p>
                <p class="text-sm font-semibold text-[#1a2332]">{{ api.queries.toLocaleString() }}</p>
              </div>
              <div class="bg-gray-50 rounded-lg p-2.5 text-center">
                <p class="text-[11px] text-[#6b7a90] mb-0.5">Efectividad</p>
                <p class="text-sm font-semibold" :style="{ color: api.availability >= 80 ? '#2E7D32' : (api.availability >= 50 ? '#F57C00' : '#E53935') }">
                  {{ api.availability }}%
                </p>
              </div>
            </div>

            <!-- Barra de efectividad -->
            <div class="h-1.5 bg-gray-100 rounded-full overflow-hidden mb-3">
              <div
                class="h-full rounded-full transition-all"
                :style="{
                  width: `${api.availability}%`,
                  background: api.availability >= 80 ? '#00aea7' : (api.availability >= 50 ? '#F57C00' : '#E53935')
                }"
              />
            </div>

            <div class="flex items-center justify-between text-[11px] text-gray-500 mb-3 px-0.5">
              <span>Latencia: <strong>{{ api.latency }}</strong></span>
              <span v-if="api.avgScore">Score de similitud: <strong>{{ api.avgScore }}</strong></span>
            </div>
          </div>

          <!-- Acciones de la API -->
          <div class="flex items-center gap-2 pt-2 border-t border-gray-100 print:hidden">
            <button
              @click="refreshSource(api.name)"
              :disabled="pingingSource === api.name"
              class="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs text-[#00aea7] border border-[#00aea7]/30 rounded-lg hover:bg-[#00aea7]/5 transition-colors cursor-pointer disabled:opacity-50"
            >
              <RefreshCw :size="12" :class="{ 'animate-spin': pingingSource === api.name }" />
              <span>{{ pingingSource === api.name ? 'Probando...' : 'Probar Conexión' }}</span>
            </button>
            <button
              @click="openDoc(api.docUrl)"
              class="flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs text-[#6b7a90] border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer"
              title="Abrir documentación de la API"
            >
              <ExternalLink :size="12" />
              <span>Docs</span>
            </button>
          </div>
        </Card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Download, Globe, RefreshCw, ExternalLink, Cpu, CheckCircle2 } from 'lucide-vue-next'
import Card from '../components/common/Card.vue'
import Badge from '../components/common/Badge.vue'
import SectionHeader from '../components/common/SectionHeader.vue'
import { retrievalService } from '../services/retrievalService'
import { proposalService } from '../services/proposalService'

const periods = [
  { key: 'week', label: 'Esta semana' },
  { key: 'month', label: 'Este mes' },
  { key: 'quarter', label: 'Último trimestre' },
  { key: 'all', label: 'Histórico Anual' }
]

const selectedPeriod = ref('month')
const loading = ref(false)
const pingingSource = ref<string | null>(null)
const toastMessage = ref<string | null>(null)

// Métricas reactivas
const totalMonitoreados = ref(13109)
const totalProcesados = ref(0)
const tasaExito = ref('100%')
const totalValidaciones = ref(0)
const totalAprobaciones = ref(0)
const llmCalls = ref(0)
const llmAvgSeconds = ref(0)

const currentPeriodLabel = computed(() => {
  const p = periods.find(i => i.key === selectedPeriod.value)
  return p ? p.label : 'Este mes'
})

const generalKpis = computed(() => [
  {
    label: 'Registros Procesados',
    value: totalProcesados.value.toLocaleString('es-CL'),
    subtitle: `de ${totalMonitoreados.value.toLocaleString('es-CL')} en cola`,
    badgeText: `${totalProcesados.value} ítems evaluados por el agente`,
    badgeColor: 'text-[#00aea7] font-medium'
  },
  {
    label: 'Tasa de Éxito',
    value: tasaExito.value,
    badgeText: 'Recuperación exitosa de metadatos',
    badgeColor: 'text-emerald-600 font-medium'
  },
  {
    label: 'Validaciones Requeridas',
    value: totalValidaciones.value.toLocaleString('es-CL'),
    badgeText: 'Match score < 80% o revisión curador',
    badgeColor: 'text-amber-600 font-medium'
  },
  {
    label: 'Aprobaciones Realizadas',
    value: totalAprobaciones.value.toLocaleString('es-CL'),
    badgeText: 'Aprobados para carga a DSpace-CRIS',
    badgeColor: 'text-blue-600 font-medium'
  },
])

const weeklyData = ref([
  { week: 'Sem 1', enriquecidos: 0, detectados: 0, aprobados: 0 },
  { week: 'Sem 2', enriquecidos: 0, detectados: 0, aprobados: 0 },
  { week: 'Sem 3', enriquecidos: 0, detectados: 0, aprobados: 0 },
  { week: 'Sem 4', enriquecidos: 0, detectados: 0, aprobados: 0 },
])

const maxWeeklyDetectados = computed(() => Math.max(...weeklyData.value.map(w => w.detectados), 1))
const maxWeeklyEnriquecidos = computed(() => Math.max(...weeklyData.value.map(w => w.enriquecidos), 1))
const maxWeeklyAprobados = computed(() => Math.max(...weeklyData.value.map(w => w.aprobados), 1))

const calcBarHeight = (val: number, max: number) => {
  if (val <= 0 || max <= 0) return 4
  const pct = Math.round((val / max) * 88)
  return Math.max(pct, 12)
}

const donutData = ref([
  { name: 'Abstract', value: 25, count: 0, color: '#00aea7' },
  { name: 'Palabras clave', value: 25, count: 0, color: '#F57C00' },
  { name: 'Área OCDE', value: 18, count: 0, color: '#7B1FA2' },
  { name: 'Área ODS', value: 18, count: 0, color: '#2E7D32' },
  { name: 'Derechos de acceso', value: 14, count: 0, color: '#E53935' },
])

const totalCamposEnriquecidos = computed(() => {
  return donutData.value.reduce((acc, curr) => acc + (curr.count || 0), 0)
})

const sources = ref<any[]>([])

const totalQueriesAcrossSources = computed(() => {
  return sources.value.reduce((acc, s) => acc + (s.queries || 0), 0)
})

const circumference = 2 * Math.PI * 35

const donutSlices = computed(() => {
  let accumulated = 0
  const total = donutData.value.reduce((acc, curr) => acc + curr.value, 0)
  return donutData.value.map((item) => {
    const fraction = total > 0 ? item.value / total : 0
    const dashLength = fraction * circumference
    const dashOffset = -accumulated
    accumulated += dashLength
    return {
      color: item.color,
      dashLength,
      dashOffset,
    }
  })
})

const selectPeriod = async (key: string) => {
  selectedPeriod.value = key
  await loadAnalytics()
}

const loadAnalytics = async () => {
  try {
    const analytics = await proposalService.getReportsAnalytics(selectedPeriod.value)
    if (analytics) {
      if (analytics.kpis) {
        totalMonitoreados.value = analytics.kpis.total_monitoreados ?? 13109
        totalProcesados.value = analytics.kpis.total_procesados ?? 0
        tasaExito.value = analytics.kpis.tasa_exito ?? '100%'
        totalValidaciones.value = analytics.kpis.total_validaciones ?? 0
        totalAprobaciones.value = analytics.kpis.total_aprobaciones ?? 0
        llmCalls.value = analytics.kpis.llm_calls ?? 0
        llmAvgSeconds.value = analytics.kpis.llm_avg_seconds ?? 0
      }

      if (analytics.weekly_activity && Array.isArray(analytics.weekly_activity)) {
        weeklyData.value = analytics.weekly_activity
      }

      if (analytics.fields_distribution && Array.isArray(analytics.fields_distribution)) {
        donutData.value = analytics.fields_distribution
      }
    }
  } catch (err) {
    console.error('Error cargando analítica de reportes:', err)
  }
}

const loadSources = async () => {
  try {
    const realSources = await retrievalService.getSources()
    if (realSources && realSources.length > 0) {
      sources.value = realSources
    }
  } catch (err) {
    console.error('Error cargando fuentes de recuperación:', err)
  }
}

const loadAllData = async () => {
  loading.value = true
  try {
    await Promise.all([loadAnalytics(), loadSources()])
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadAllData()
})

const refreshSource = async (name: string) => {
  pingingSource.value = name
  try {
    const res = await retrievalService.pingSource(name)
    const target = sources.value.find(s => s.name.toLowerCase() === name.toLowerCase())
    if (target) {
      target.status = res.status
      target.latency = `${res.latency_ms}ms`
    }
    toastMessage.value = `Prueba de conexión con ${name}: ${res.message}`
    setTimeout(() => {
      if (toastMessage.value?.includes(name)) {
        toastMessage.value = null
      }
    }, 6000)
  } catch (err: any) {
    toastMessage.value = `Error verificando ${name}: ${err.message}`
  } finally {
    pingingSource.value = null
  }
}

const openDoc = (url: string) => {
  if (url) {
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

const exportPdf = () => {
  window.print()
}
</script>

<style scoped>
@media print {
  /* Ocultar barra de navegación, botones y scrollbars al imprimir */
  body {
    background: white !important;
    color: black !important;
  }
}
</style>
