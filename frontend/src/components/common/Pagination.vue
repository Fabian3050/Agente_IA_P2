<template>
  <div class="px-4 py-3 border-t border-gray-100 bg-slate-50/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-slate-600 select-none">
    <!-- Info y selector de tamaño -->
    <div class="flex items-center gap-3 flex-wrap">
      <span class="text-slate-500">
        Mostrando <span class="font-semibold text-slate-800">{{ startItem }}</span> a
        <span class="font-semibold text-slate-800">{{ endItem }}</span> de
        <span class="font-bold text-[#00aea7]">{{ totalItems.toLocaleString('es-CL') }}</span> registros
      </span>

      <div class="flex items-center gap-1.5 ml-0 sm:ml-2">
        <label for="page-size-select" class="text-slate-400 text-[11px]">Por pág:</label>
        <select
          id="page-size-select"
          :value="pageSize"
          @change="onPageSizeChange"
          class="px-2 py-1 bg-white border border-gray-200 rounded-md text-xs font-medium text-slate-700 focus:outline-none focus:ring-1 focus:ring-[#00aea7] cursor-pointer"
        >
          <option v-for="opt in pageSizeOptions" :key="opt" :value="opt">
            {{ opt }}
          </option>
        </select>
      </div>
    </div>

    <!-- Navegación de páginas -->
    <div v-if="totalPages > 1" class="flex items-center gap-1">
      <!-- Primera página -->
      <button
        @click="goToPage(1)"
        :disabled="currentPage === 1"
        class="p-1.5 rounded-md border border-gray-200 bg-white text-slate-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        title="Primera página"
      >
        <ChevronsLeft :size="14" />
      </button>

      <!-- Página anterior -->
      <button
        @click="goToPage(currentPage - 1)"
        :disabled="currentPage === 1"
        class="p-1.5 rounded-md border border-gray-200 bg-white text-slate-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        title="Página anterior"
      >
        <ChevronLeft :size="14" />
      </button>

      <!-- Botones numéricos -->
      <div class="flex items-center gap-1 px-1">
        <template v-for="(p, idx) in visiblePages" :key="idx">
          <span
            v-if="p === '...'"
            class="px-1.5 text-slate-400 font-mono"
          >
            ...
          </span>
          <button
            v-else
            @click="goToPage(p as number)"
            :class="[
              'min-w-[28px] h-7 px-2 text-xs font-semibold rounded-md transition-colors cursor-pointer',
              currentPage === p
                ? 'bg-[#00aea7] text-white shadow-xs'
                : 'bg-white border border-gray-200 text-slate-700 hover:bg-gray-50'
            ]"
          >
            {{ p }}
          </button>
        </template>
      </div>

      <!-- Página siguiente -->
      <button
        @click="goToPage(currentPage + 1)"
        :disabled="currentPage === totalPages"
        class="p-1.5 rounded-md border border-gray-200 bg-white text-slate-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        title="Página siguiente"
      >
        <ChevronRight :size="14" />
      </button>

      <!-- Última página -->
      <button
        @click="goToPage(totalPages)"
        :disabled="currentPage === totalPages"
        class="p-1.5 rounded-md border border-gray-200 bg-white text-slate-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        title="Última página"
      >
        <ChevronsRight :size="14" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    currentPage: number
    pageSize: number
    totalItems: number
    pageSizeOptions?: number[]
  }>(),
  {
    pageSizeOptions: () => [10, 25, 50, 100]
  }
)

const emit = defineEmits<{
  (e: 'update:currentPage', page: number): void
  (e: 'update:pageSize', size: number): void
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.totalItems / props.pageSize)))

const startItem = computed(() => {
  if (props.totalItems === 0) return 0
  return (props.currentPage - 1) * props.pageSize + 1
})

const endItem = computed(() => {
  return Math.min(props.totalItems, props.currentPage * props.pageSize)
})

const visiblePages = computed<(number | string)[]>(() => {
  const total = totalPages.value
  const current = props.currentPage

  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }

  if (current <= 4) {
    return [1, 2, 3, 4, 5, '...', total]
  }

  if (current >= total - 3) {
    return [1, '...', total - 4, total - 3, total - 2, total - 1, total]
  }

  return [1, '...', current - 1, current, current + 1, '...', total]
})

const goToPage = (page: number) => {
  if (page >= 1 && page <= totalPages.value && page !== props.currentPage) {
    emit('update:currentPage', page)
  }
}

const onPageSizeChange = (event: Event) => {
  const target = event.target as HTMLSelectElement
  const newSize = parseInt(target.value, 10)
  if (!isNaN(newSize) && newSize > 0) {
    emit('update:pageSize', newSize)
    emit('update:currentPage', 1)
  }
}
</script>

