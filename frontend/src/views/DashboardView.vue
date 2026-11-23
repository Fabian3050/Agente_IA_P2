<template>
  <div class="flex gap-6 h-full min-h-0">
    <!-- Main content -->
    <div class="flex-1 min-w-0 overflow-y-auto pr-1">
      <SectionHeader
        title="Dashboard"
        description="Vista general del sistema de enriquecimiento de metadatos."
      />

      <!-- KPIs -->
      <div class="grid grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
        <Card v-for="kpi in kpis" :key="kpi.label" customClass="p-4">
          <div class="flex items-start gap-3">
            <div
              class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
              :style="{ background: kpi.bg }"
            >
              <component :is="kpi.icon" :size="20" :style="{ color: kpi.color }" />
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-xs text-[#6b7a90] leading-tight mb-1">{{ kpi.label }}</p>
              <p class="text-2xl font-semibold" :style="{ color: kpi.color }">{{ kpi.value }}</p>
              <div v-if="kpi.progress" class="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :style="{ width: `${kpi.progress}%`, background: kpi.color }"
                />
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Charts -->
      <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <!-- Donut Chart -->
        <Card customClass="p-5">
          <h3 class="text-sm font-semibold text-[#1a2332] mb-4">Distribución de metadatos incompletos</h3>
          <div class="flex items-center gap-6">
            <!-- Native SVG Donut Chart -->
            <div class="relative w-40 h-40 flex-shrink-0 flex items-center justify-center">
              <svg viewBox="0 0 100 100" class="w-full h-full -rotate-90 transform">
                <!-- Slices calculated via stroke-dasharray -->
                <circle
                  v-for="(slice, i) in calculatedDonutSlices"
                  :key="i"
                  cx="50"
                  cy="50"
                  r="35"
                  fill="transparent"
                  :stroke="slice.color"
                  stroke-width="18"
                  :stroke-dasharray="`${slice.dashLength} ${100 - slice.dashLength}`"
                  :stroke-dashoffset="slice.dashOffset"
                />
              </svg>
              <div class="absolute inset-0 flex flex-col items-center justify-center text-center">
                <span class="text-xs text-gray-400">Total</span>
                <span class="text-base font-bold text-gray-800">100%</span>
              </div>
            </div>

            <!-- Legend -->
            <div class="flex flex-col gap-2 flex-1 min-w-0">
              <div
                v-for="d in donutData"
                :key="d.name"
                class="flex items-center gap-2"
              >
                <div class="w-2.5 h-2.5 rounded-sm flex-shrink-0" :style="{ background: d.color }" />
                <span class="text-xs text-[#6b7a90] truncate">{{ d.name }}</span>
                <span class="text-xs font-semibold text-[#1a2332] ml-auto pl-2">{{ d.value }}%</span>
              </div>
            </div>
          </div>
        </Card>

        <!-- Bar Chart -->
        <Card customClass="p-5">
          <h3 class="text-sm font-semibold text-[#1a2332] mb-4">Registros enriquecidos esta semana</h3>
          <div class="h-44 w-full flex items-end justify-between gap-3 pt-6 pb-2 px-2 border-b border-gray-100">
            <div
              v-for="item in barData"
              :key="item.day"
              class="flex-1 flex flex-col items-center gap-1.5 h-full justify-end group"
            >
              <span class="text-[10px] font-medium text-gray-400 group-hover:text-[#00aea7] transition-colors">
                {{ item.value }}
              </span>
              <div
                class="w-full max-w-[28px] rounded-t-md transition-all duration-300 group-hover:opacity-85"
                :style="{
                  height: `${(item.value / maxBarValue) * 100}%`,
                  backgroundColor: '#00aea7'
                }"
              />
              <span class="text-[11px] text-[#6b7a90] font-medium">{{ item.day }}</span>
            </div>
          </div>
        </Card>
      </div>
    </div>

    <!-- Recent Activity Panel -->
    <aside class="w-72 flex-shrink-0 overflow-y-auto hidden lg:block">
      <Card customClass="p-4 h-full">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-semibold text-[#1a2332]">Actividad reciente</h3>
          <span
            @click="$emit('nav', 'auditoria')"
            class="text-xs text-[#00aea7] font-medium cursor-pointer hover:underline"
          >
            Ver todo
          </span>
        </div>
        <div class="flex flex-col gap-0">
          <div
            v-if="recentActivity.length === 0"
            class="py-8 text-center text-xs text-[#6b7a90]"
          >
            No hay actividad reciente registrada en la base de datos.
          </div>
          <div
            v-for="(item, i) in recentActivity"
            :key="i"
            class="flex gap-3 py-3 border-b border-gray-50 last:border-0"
          >
            <component
              :is="item.icon"
              :size="15"
              :style="{ color: item.color, flexShrink: 0, marginTop: '2px' }"
            />
            <div class="flex-1 min-w-0">
              <p class="text-xs text-[#1a2332] leading-snug">{{ item.text }}</p>
              <div class="flex items-center gap-1.5 mt-1">
                <span class="text-[11px] text-[#6b7a90]">{{ item.date }}</span>
                <span class="w-1 h-1 rounded-full bg-gray-400"></span>
                <span class="text-[11px] text-[#6b7a90]">{{ item.time }}</span>
                <span class="w-1 h-1 rounded-full bg-gray-400"></span>
                <span class="text-[11px] text-[#6b7a90] truncate">{{ item.user }}</span>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Database,
  AlertCircle,
  CheckCircle,
  Clock,
  TrendingUp,
  Zap,
  AlertTriangle
} from 'lucide-vue-next'
import Card from '../components/common/Card.vue'
import SectionHeader from '../components/common/SectionHeader.vue'
import { proposalService } from '../services/proposalService'
import { auditService } from '../services/auditService'
import type { Page } from '../types'

defineEmits<{
  (e: 'nav', page: Page): void
}>()

const loading = ref(true)
const totalMonitoreados = ref(0)
const registrosIncompletos = ref(0)
const metadatosEnriquecidos = ref(0)
const pendientesValidacion = ref(0)
const porcentajeCompletitud = ref(100)
const tiempoPromedio = ref('--')

const donutData = ref([
  { name: 'Abstract', value: 0, color: '#00aea7' },
  { name: 'Palabras clave', value: 0, color: '#F57C00' },
  { name: 'Área OCDE', value: 0, color: '#7B1FA2' },
  { name: 'Área ODS', value: 0, color: '#2E7D32' },
  { name: 'Derechos de acceso', value: 0, color: '#E53935' },
])

const barData = ref([
  { day: 'Lun', value: 0 },
  { day: 'Mar', value: 0 },
  { day: 'Mié', value: 0 },
  { day: 'Jue', value: 0 },
  { day: 'Vie', value: 0 },
  { day: 'Sáb', value: 0 },
  { day: 'Dom', value: 0 },
])

const recentActivity = ref<any[]>([])

const kpis = computed(() => [
  { label: 'Total registros monitoreados', value: totalMonitoreados.value.toLocaleString('es-CL'), icon: Database, color: '#1565C0', bg: '#e3f2fd' },
  { label: 'Registros incompletos', value: registrosIncompletos.value.toLocaleString('es-CL'), icon: AlertCircle, color: '#F57C00', bg: '#fff3e0' },
  { label: 'Metadatos enriquecidos', value: metadatosEnriquecidos.value.toLocaleString('es-CL'), icon: CheckCircle, color: '#00aea7', bg: '#e0f7f6' },
  { label: 'Pendientes de validación', value: pendientesValidacion.value.toLocaleString('es-CL'), icon: Clock, color: '#7B1FA2', bg: '#f3e5f5' },
  { label: 'Porcentaje de completitud', value: `${porcentajeCompletitud.value}%`, icon: TrendingUp, color: '#2E7D32', bg: '#e8f5e9', progress: porcentajeCompletitud.value },
  { label: 'Tiempo prom. por registro', value: tiempoPromedio.value, icon: Zap, color: '#E53935', bg: '#ffebee' },
])

const maxBarValue = computed(() => {
  const max = Math.max(...barData.value.map(b => b.value))
  return max > 0 ? max : 1
})

const circumference = 2 * Math.PI * 35

const calculatedDonutSlices = computed(() => {
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

onMounted(async () => {
  loading.value = true
  try {
    const stats = await proposalService.getDashboardStats()
    if (stats) {
      totalMonitoreados.value = stats.total_monitoreados || 0
      registrosIncompletos.value = stats.registros_incompletos || 0
      metadatosEnriquecidos.value = stats.metadatos_enriquecidos || 0
      pendientesValidacion.value = stats.pendientes_validacion || 0
      porcentajeCompletitud.value = stats.porcentaje_completitud ?? 100
      tiempoPromedio.value = stats.tiempo_promedio || '--'

      if (Array.isArray(stats.donut_data) && stats.donut_data.length > 0) {
        donutData.value = stats.donut_data
      }
      if (Array.isArray(stats.bar_data) && stats.bar_data.length > 0) {
        barData.value = stats.bar_data
      }
      if (Array.isArray(stats.recent_activity) && stats.recent_activity.length > 0) {
        recentActivity.value = stats.recent_activity.map((log: any) => {
          const d = new Date(log.timestamp)
          const dateStr = d.toLocaleDateString('es-CL', { day: '2-digit', month: 'short' })
          const timeStr = d.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })
          const action = log.action || 'Acción'
          const isApproved = action.toLowerCase().includes('aprob')
          const isRejected = action.toLowerCase().includes('rechaz')

          return {
            icon: isApproved ? CheckCircle : isRejected ? AlertTriangle : AlertCircle,
            color: isApproved ? '#2E7D32' : isRejected ? '#E53935' : '#00aea7',
            text: `${action} registro #${log.item_id?.substring(0, 8) || ''}`,
            date: dateStr,
            time: timeStr,
            user: log.user_name || log.role || 'Curador'
          }
        })
      }
    }
  } catch (err) {
    console.error('Error cargando métricas reales de dashboard:', err)
  } finally {
    loading.value = false
  }
})
</script>

