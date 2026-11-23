<template>
  <div class="h-full overflow-y-auto">
    <SectionHeader
      title="Monitoreo de Registros Incompletos"
      description="Registros detectados con campos de metadatos faltantes o incompletos en DSpace-CRIS."
    />

    <!-- Stats bar -->
    <div class="flex gap-4 mb-6">
      <Card
        v-for="s in stats"
        :key="s.label"
        customClass="flex-1 px-4 py-3"
      >
        <p class="text-[11px] text-[#6b7a90] mb-1">{{ s.label }}</p>
        <p class="text-xl font-semibold" :style="{ color: s.color }">{{ s.value }}</p>
      </Card>
    </div>

    <Card>
      <!-- Toolbar -->
      <div class="flex items-center gap-3 p-4 border-b border-gray-50 flex-wrap">
        <div class="relative flex-1 min-w-[240px] max-w-md">
          <Search :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-[#6b7a90]" />
          <input
            type="text"
            placeholder="Buscar por título, DOI, comunidad o autor..."
            v-model="search"
            class="w-full pl-9 pr-3 py-2 text-xs border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#00aea7]/20 focus:border-[#00aea7]"
          />
        </div>

        <div class="flex gap-2 ml-auto flex-wrap items-center">
          <button
            @click="scanAndPopulateMissing"
            :disabled="scanningMissing || runningBatch"
            class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white rounded-lg shadow-sm hover:opacity-95 transition-all cursor-pointer disabled:opacity-50"
            style="background: #1565C0"
            title="Escanear DSpace-CRIS y guardar elementos que carecen de metadatos completos en la cola de enriquecimiento"
          >
            <div v-if="scanningMissing" class="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            <RefreshCw v-else :size="13" />
            <span>{{ scanningMissing ? 'Escaneando DSpace...' : 'Escanear y Guardar Incompletos (DSpace)' }}</span>
          </button>

          <button
            @click="runAgentOnAll"
            :disabled="runningBatch || scanningMissing"
            class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white rounded-lg shadow-sm hover:opacity-95 transition-all cursor-pointer disabled:opacity-50"
            style="background: #00aea7"
          >
            <Zap :size="13" />
            <span>{{ runningBatch ? 'Enriqueciendo...' : 'Enriquecer todos los pendientes' }}</span>
          </button>
          <button
            @click="exportSummary"
            class="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-gray-200 rounded-lg text-[#6b7a90] hover:bg-gray-50 transition-colors cursor-pointer"
          >
            <Download :size="13" />
            <span>Exportar</span>
          </button>
        </div>
      </div>

      <!-- Table -->
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-gray-50">
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide">ID</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide">UUID DSpace</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide">Título / DOI</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide">Campo faltante</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide">Completitud</th>
              
              <!-- Filter dropdown header -->
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide relative select-none">
                <div
                  class="flex items-center gap-1.5 cursor-pointer hover:text-[#1a2332] transition-colors inline-flex py-1"
                  @click="statusDropdownOpen = !statusDropdownOpen"
                >
                  <span>Estado</span>
                  <Filter :size="13" :class="selectedStatuses.length > 0 ? 'text-[#00aea7]' : 'text-[#6b7a90]'" />
                  <span
                    v-if="selectedStatuses.length > 0"
                    class="bg-[#00aea7] text-white rounded-full px-1.5 text-[9px] font-bold"
                  >
                    {{ selectedStatuses.length }}
                  </span>
                  <ChevronDown :size="13" :class="['text-[#6b7a90] transition-transform', statusDropdownOpen ? 'rotate-180' : '']" />
                </div>

                <!-- Dropdown box -->
                <div v-if="statusDropdownOpen">
                  <div class="fixed inset-0 z-20" @click="statusDropdownOpen = false" />
                  <div class="absolute left-0 mt-1 w-52 bg-white rounded-xl shadow-xl border border-gray-100 p-2.5 z-30 font-sans normal-case">
                    <div class="text-[10px] font-bold text-[#6b7a90] uppercase px-2 py-1 flex items-center justify-between border-b border-gray-50 mb-1.5">
                      <span>Filtrar por estado</span>
                      <button
                        v-if="selectedStatuses.length > 0"
                        @click.stop="selectedStatuses = []"
                        class="text-[10px] text-[#00aea7] hover:underline normal-case font-semibold cursor-pointer"
                      >
                        Limpiar todo
                      </button>
                    </div>
                    <div class="space-y-1 py-0.5">
                      <label
                        v-for="opt in ['Pendiente', 'Pendiente de validación', 'En proceso', 'Completado']"
                        :key="opt"
                        class="flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-slate-50 cursor-pointer text-xs font-medium text-slate-700 select-none transition-colors"
                      >
                        <input
                          type="checkbox"
                          :checked="selectedStatuses.includes(opt)"
                          @change="toggleStatus(opt)"
                          class="rounded border-gray-300 text-[#00aea7] focus:ring-[#00aea7] w-3.5 h-3.5 accent-[#00aea7] cursor-pointer"
                        />
                        <span class="flex-1">{{ opt }}</span>
                      </label>
                    </div>
                  </div>
                </div>
              </th>

              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide">Acción</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="7" class="text-center py-12 text-slate-500 text-xs">
                <div class="inline-block w-4 h-4 border-2 border-[#00aea7] border-t-transparent rounded-full animate-spin mr-2"></div>
                Cargando registros reales de la cola de enriquecimiento...
              </td>
            </tr>
            <tr v-else-if="records.length === 0">
              <td colspan="7" class="text-center py-12 text-slate-500 text-xs">
                <p class="mb-3 text-slate-600 font-medium">No hay publicaciones registradas en la cola de monitoreo actualmente.</p>
                <button
                  @click="scanAndPopulateMissing"
                  :disabled="scanningMissing"
                  class="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white rounded-lg shadow-sm hover:opacity-95 transition-all cursor-pointer disabled:opacity-50"
                  style="background: #1565C0"
                >
                  <div v-if="scanningMissing" class="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <RefreshCw v-else :size="14" />
                  <span>{{ scanningMissing ? 'Escaneando DSpace...' : 'Escanear DSpace y Guardar en Cola' }}</span>
                </button>
              </td>
            </tr>
            <tr
              v-else
              v-for="row in paginatedRecords"
              :key="row.id"
              class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors"
            >
              <td class="px-4 py-3.5 text-xs font-mono font-medium text-[#1565C0] whitespace-nowrap">#{{ row.id }}</td>
              <td class="px-4 py-3.5 max-w-[190px] whitespace-nowrap">
                <span
                  v-if="row.uuid"
                  class="text-[11px] font-mono text-slate-700 bg-slate-100 hover:bg-slate-200 px-2 py-0.5 rounded border border-slate-200 truncate inline-block max-w-[170px] select-all cursor-copy transition-colors"
                  :title="`UUID DSpace: ${row.uuid}`"
                >
                  {{ row.uuid }}
                </span>
                <span v-else class="text-[11px] text-slate-400 font-mono italic">Sin UUID</span>
              </td>
              <td class="px-4 py-3.5 max-w-[220px]">
                <p class="text-xs font-medium text-[#1a2332] truncate" :title="row.title">{{ row.title }}</p>
                <p class="text-[10px] font-mono text-[#6b7a90] truncate">DOI: {{ row.doi || 'N/A' }}</p>
              </td>
              <td class="px-4 py-3.5 max-w-[240px]">
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="(f, fIdx) in formatFalencias(row.campo)"
                    :key="fIdx"
                    :class="getFalenciaBadgeClass(f)"
                    class="text-[10px] font-semibold px-2 py-0.5 rounded shadow-2xs whitespace-nowrap"
                  >
                    {{ f }}
                  </span>
                </div>
              </td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <div class="flex items-center gap-2" :title="`${row.completitud}% - ${formatCompletitudDetalle(row)}`">
                  <div class="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      class="h-full rounded-full transition-all"
                      :style="{
                        width: `${row.completitud}%`,
                        background: row.completitud >= 80 ? '#2E7D32' : row.completitud >= 50 ? '#00aea7' : '#F57C00'
                      }"
                    />
                  </div>
                  <span
                    class="text-xs font-bold"
                    :style="{ color: row.completitud >= 80 ? '#2E7D32' : row.completitud >= 50 ? '#00aea7' : '#F57C00' }"
                  >
                    {{ row.completitud }}%
                  </span>
                </div>
              </td>
              <td class="px-4 py-3.5">
                <Badge :color="row.estado">{{ row.estado }}</Badge>
              </td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <div class="flex items-center gap-1.5">
                  <button
                    @click="selectedRecord = row"
                    class="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-[#00aea7] border border-[#00aea7]/30 rounded-lg hover:bg-[#00aea7]/5 transition-colors cursor-pointer"
                  >
                    <Eye :size="12" /> Ver
                  </button>
                  <button
                    @click="runAgentSingle(row)"
                    :disabled="enrichingIds[row.id] || row.estado === 'Completado' || row.estado === 'Pendiente de validación'"
                    :title="row.estado === 'Completado' ? 'Registro enriquecido' : row.estado === 'Pendiente de validación' ? 'Registro enriquecido (requiere validación manual en sección Validación)' : 'Ejecutar agente sobre este único registro'"
                    class="p-1.5 text-xs font-medium rounded-lg transition-colors cursor-pointer disabled:cursor-not-allowed"
                    :class="[
                      row.estado === 'Completado' ? 'text-emerald-600 bg-emerald-50' : row.estado === 'Pendiente de validación' ? 'text-amber-700 bg-amber-50 border border-amber-200' : 'text-[#1565C0] hover:bg-blue-50'
                    ]"
                  >
                    <div v-if="enrichingIds[row.id]" class="w-3.5 h-3.5 border-2 border-[#1565C0] border-t-transparent rounded-full animate-spin"></div>
                    <Check v-else-if="row.estado === 'Completado'" :size="14" />
                    <AlertCircle v-else-if="row.estado === 'Pendiente de validación'" :size="14" />
                    <Zap v-else :size="14" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="px-4 py-3.5 border-t border-gray-100 flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-50/50">
        <div class="flex items-center gap-3 text-xs text-[#6b7a90]">
          <span>
            Mostrando <strong>{{ pageStart }}-{{ pageEnd }}</strong> de <strong>{{ totalFilteredRecords.toLocaleString('es-CL') }}</strong> registros
          </span>
          <span class="text-gray-300">|</span>
          <div class="flex items-center gap-1.5">
            <span>Mostrar:</span>
            <select
              v-model="pageSize"
              class="px-2 py-1 text-xs border border-gray-200 rounded-lg bg-white text-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#00aea7] cursor-pointer"
            >
              <option :value="10">10 por pág.</option>
              <option :value="15">15 por pág.</option>
              <option :value="25">25 por pág.</option>
              <option :value="50">50 por pág.</option>
              <option :value="100">100 por pág.</option>
            </select>
          </div>
        </div>

        <div class="flex items-center gap-1">
          <button
            @click="goToPage(currentPage - 1)"
            :disabled="currentPage <= 1"
            class="px-2.5 py-1 text-xs font-medium rounded-lg border border-gray-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            Anterior
          </button>

          <template v-for="(p, idx) in visiblePages" :key="idx">
            <span v-if="p === '...'" class="px-2 text-xs text-gray-400">...</span>
            <button
              v-else
              @click="goToPage(Number(p))"
              :class="[
                'w-7 h-7 text-xs font-medium rounded-lg flex items-center justify-center transition-all cursor-pointer',
                currentPage === p
                  ? 'bg-[#00aea7] text-white shadow-xs font-bold'
                  : 'bg-white border border-gray-200 text-slate-700 hover:bg-slate-50'
              ]"
            >
              {{ p }}
            </button>
          </template>

          <button
            @click="goToPage(currentPage + 1)"
            :disabled="currentPage >= totalPages"
            class="px-2.5 py-1 text-xs font-medium rounded-lg border border-gray-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            Siguiente
          </button>
        </div>
      </div>
    </Card>

    <!-- Modal de Detalles del Registro -->
    <div
      v-if="selectedRecord"
      class="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
    >
      <div class="bg-white rounded-2xl shadow-2xl max-w-4xl w-full border border-gray-100 overflow-hidden flex flex-col max-h-[90vh]">
        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-slate-50/50">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-[#00aea7]/10 flex items-center justify-center text-[#00aea7] font-mono font-bold text-sm">
              #{{ selectedRecord.id }}
            </div>
            <div>
              <h3 class="text-base font-semibold text-slate-800 flex items-center gap-2">
                Detalles del Registro
                <Badge :color="selectedRecord.estado">{{ selectedRecord.estado }}</Badge>
              </h3>
              <p class="text-xs text-slate-500">
                Repositorio Institucional DSpace-CRIS USACH
                <span v-if="selectedRecord.uuid" class="ml-1.5 font-mono text-slate-400">· UUID: {{ selectedRecord.uuid }}</span>
              </p>
            </div>
          </div>
          <button
            @click="selectedRecord = null"
            class="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer"
          >
            <X :size="18" />
          </button>
        </div>

        <!-- Body -->
        <div class="p-6 overflow-y-auto space-y-6">
          <div class="bg-slate-50/80 rounded-xl p-4 border border-slate-100 space-y-3">
            <div>
              <span class="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">Título Científico</span>
              <p class="text-sm font-semibold text-slate-800 leading-snug">{{ selectedRecord.title }}</p>
            </div>
            <div class="grid grid-cols-4 gap-3 pt-2 border-t border-slate-200/60">
              <div>
                <span class="text-[10px] font-medium text-slate-400 uppercase block">Autor Principal</span>
                <span class="text-xs font-semibold text-slate-700 truncate block">{{ selectedRecord.autor }}</span>
              </div>
              <div>
                <span class="text-[10px] font-medium text-slate-400 uppercase block">Comunidad / Facultad</span>
                <span class="text-xs font-semibold text-slate-700 truncate block">{{ selectedRecord.comunidad }}</span>
              </div>
              <div>
                <span class="text-[10px] font-medium text-slate-400 uppercase block">DOI Registrado</span>
                <span class="text-xs font-mono font-medium text-[#1565C0] truncate block">{{ selectedRecord.doi || 'N/A' }}</span>
              </div>
              <div>
                <span class="text-[10px] font-medium text-slate-400 uppercase block">UUID DSpace</span>
                <span class="text-xs font-mono font-medium text-slate-700 truncate block select-all cursor-copy" :title="selectedRecord.uuid">{{ selectedRecord.uuid || 'N/A' }}</span>
              </div>
            </div>
          </div>

          <!-- Metadatos Faltantes y Estado del Ciclo de Vida -->
          <div class="grid grid-cols-2 gap-4">
            <div class="p-4 rounded-xl border border-orange-100 bg-orange-50/30">
              <span class="text-xs font-semibold text-orange-900 block mb-1">Falencias Detectadas</span>
              <div class="flex flex-wrap gap-1.5 mt-1">
                <span
                  v-for="(f, fIdx) in formatFalencias(selectedRecord.campo)"
                  :key="fIdx"
                  :class="getFalenciaBadgeClass(f)"
                  class="text-xs font-semibold px-2 py-0.5 rounded shadow-2xs"
                >
                  {{ f }}
                </span>
              </div>
              <p class="text-[11px] text-orange-600/80 mt-2">Requiere recuperación externa o clasificación con LLM.</p>
            </div>
            <div class="p-4 rounded-xl border border-teal-100 bg-teal-50/30">
              <span class="text-xs font-semibold text-teal-900 block mb-1">Completitud del Registro</span>
              <div class="flex items-center gap-2 mt-1">
                <div class="flex-1 h-2 bg-teal-200/50 rounded-full overflow-hidden">
                  <div class="h-full bg-[#00aea7] rounded-full transition-all" :style="{ width: `${selectedRecord.completitud}%` }" />
                </div>
                <span class="text-xs font-bold text-teal-800">{{ selectedRecord.completitud }}%</span>
              </div>
              <p class="text-[10px] text-teal-700 mt-1">
                Incremento estimado: +{{ Math.max(0, selectedRecord.completitud - selectedRecord.completitudPre) }}% con enriquecimiento
              </p>

              <!-- Desglose de los 6 metadatos enriquecidos objetivo -->
              <div class="mt-3 pt-2.5 border-t border-teal-100/60 grid grid-cols-2 sm:grid-cols-3 gap-1.5 text-[10px]">
                <div class="flex items-center gap-1" :class="selectedRecord.completitudDetalle?.financiamiento ? 'text-emerald-700 font-medium' : 'text-slate-400'">
                  <CheckCircle2 v-if="selectedRecord.completitudDetalle?.financiamiento" :size="12" class="text-emerald-500 shrink-0" />
                  <XCircle v-else :size="12" class="text-slate-300 shrink-0" />
                  <span class="truncate">Financiamiento</span>
                </div>
                <div class="flex items-center gap-1" :class="selectedRecord.completitudDetalle?.resumen ? 'text-emerald-700 font-medium' : 'text-slate-400'">
                  <CheckCircle2 v-if="selectedRecord.completitudDetalle?.resumen" :size="12" class="text-emerald-500 shrink-0" />
                  <XCircle v-else :size="12" class="text-slate-300 shrink-0" />
                  <span class="truncate">Resumen</span>
                </div>
                <div class="flex items-center gap-1" :class="selectedRecord.completitudDetalle?.palabrasClave ? 'text-emerald-700 font-medium' : 'text-slate-400'">
                  <CheckCircle2 v-if="selectedRecord.completitudDetalle?.palabrasClave" :size="12" class="text-emerald-500 shrink-0" />
                  <XCircle v-else :size="12" class="text-slate-300 shrink-0" />
                  <span class="truncate">Palabras clave</span>
                </div>
                <div class="flex items-center gap-1" :class="selectedRecord.completitudDetalle?.areaOcde ? 'text-emerald-700 font-medium' : 'text-slate-400'">
                  <CheckCircle2 v-if="selectedRecord.completitudDetalle?.areaOcde" :size="12" class="text-emerald-500 shrink-0" />
                  <XCircle v-else :size="12" class="text-slate-300 shrink-0" />
                  <span class="truncate">Área OCDE</span>
                </div>
                <div class="flex items-center gap-1" :class="selectedRecord.completitudDetalle?.areaOds ? 'text-emerald-700 font-medium' : 'text-slate-400'">
                  <CheckCircle2 v-if="selectedRecord.completitudDetalle?.areaOds" :size="12" class="text-emerald-500 shrink-0" />
                  <XCircle v-else :size="12" class="text-slate-300 shrink-0" />
                  <span class="truncate">Área ODS</span>
                </div>
                <div class="flex items-center gap-1" :class="selectedRecord.completitudDetalle?.derechosAcceso ? 'text-emerald-700 font-medium' : 'text-slate-400'">
                  <CheckCircle2 v-if="selectedRecord.completitudDetalle?.derechosAcceso" :size="12" class="text-emerald-500 shrink-0" />
                  <XCircle v-else :size="12" class="text-slate-300 shrink-0" />
                  <span class="truncate">Derechos acceso</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Metadatos Enriquecidos Recuperados por el Agente -->
          <div v-if="selectedRecord.abstractEnriquecido || selectedRecord.estado === 'Completado' || (selectedRecord.palabrasClave && selectedRecord.palabrasClave.length > 0) || selectedRecord.metadatosRecuperados" class="space-y-3 p-4 rounded-xl border border-emerald-100 bg-emerald-50/30">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-emerald-900 flex items-center gap-1.5">
                <Sparkles :size="14" class="text-emerald-600" /> Metadatos Enriquecidos / Recuperados
              </span>
              <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                {{ selectedRecord.fuente || 'Fuentes científicas validadas' }}
              </span>
            </div>
            
            <!-- Abstract -->
            <div v-if="selectedRecord.abstractEnriquecido || selectedRecord.metadatosRecuperados?.abstract" class="bg-white p-3 rounded-lg border border-emerald-100 text-xs text-slate-700 leading-relaxed max-h-36 overflow-y-auto">
              <span class="text-[10px] uppercase font-bold text-slate-400 block mb-1">Resumen / Abstract Recuperado:</span>
              {{ selectedRecord.abstractEnriquecido || selectedRecord.metadatosRecuperados?.abstract }}
            </div>

            <!-- Palabras Clave -->
            <div v-if="(selectedRecord.palabrasClave && selectedRecord.palabrasClave.length > 0) || (selectedRecord.metadatosRecuperados?.keywords && selectedRecord.metadatosRecuperados.keywords.length > 0)" class="pt-1">
              <span class="text-[10px] uppercase font-bold text-slate-400 block mb-1">Palabras Clave Asociadas:</span>
              <div class="flex flex-wrap gap-1.5">
                <span v-for="kw in (selectedRecord.palabrasClave?.length ? selectedRecord.palabrasClave : selectedRecord.metadatosRecuperados?.keywords || [])" :key="kw" class="px-2 py-0.5 text-[11px] font-medium bg-white text-emerald-800 border border-emerald-200 rounded-md shadow-xs">
                  {{ kw }}
                </span>
              </div>
            </div>

            <!-- Financiamiento, Derechos de Acceso & Licencia -->
            <div v-if="(selectedRecord.fuenteFinanciamiento && selectedRecord.fuenteFinanciamiento.length > 0) || selectedRecord.metadatosRecuperados?.funding || selectedRecord.derechosAcceso || selectedRecord.metadatosRecuperados?.access_rights || selectedRecord.licencia || selectedRecord.metadatosRecuperados?.license" class="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1">
              <div v-if="(selectedRecord.fuenteFinanciamiento && selectedRecord.fuenteFinanciamiento.length > 0) || selectedRecord.metadatosRecuperados?.funding" class="bg-white p-2.5 rounded-lg border border-emerald-100 text-xs">
                <span class="text-[10px] uppercase font-bold text-slate-400 block mb-1">Fuente de Financiamiento:</span>
                <div class="flex flex-wrap gap-1">
                  <span v-for="f in (selectedRecord.fuenteFinanciamiento?.length ? selectedRecord.fuenteFinanciamiento : (Array.isArray(selectedRecord.metadatosRecuperados?.funding) ? selectedRecord.metadatosRecuperados.funding : [selectedRecord.metadatosRecuperados?.funding]))" :key="f" class="px-1.5 py-0.5 text-[10px] font-medium bg-emerald-50 text-emerald-900 rounded">
                    {{ f }}
                  </span>
                </div>
              </div>
              <div v-if="selectedRecord.derechosAcceso || selectedRecord.metadatosRecuperados?.access_rights" class="bg-white p-2.5 rounded-lg border border-emerald-100 text-xs">
                <span class="text-[10px] uppercase font-bold text-slate-400 block mb-1">Derechos de Acceso:</span>
                <span class="text-xs font-semibold text-slate-700 block">{{ selectedRecord.derechosAcceso || selectedRecord.metadatosRecuperados?.access_rights }}</span>
              </div>
              <div v-if="selectedRecord.licencia || selectedRecord.metadatosRecuperados?.license" class="bg-white p-2.5 rounded-lg border border-emerald-100 text-xs">
                <span class="text-[10px] uppercase font-bold text-slate-400 block mb-1">Licencia de Uso:</span>
                <span class="inline-block px-2 py-0.5 text-[11px] font-mono font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 rounded uppercase">
                  {{ selectedRecord.licencia || selectedRecord.metadatosRecuperados?.license }}
                </span>
              </div>
            </div>

            <!-- Áreas OCDE y ODS -->
            <div v-if="selectedRecord.areaOcde || selectedRecord.areaOds || selectedRecord.metadatosRecuperados?.area_ocde || selectedRecord.metadatosRecuperados?.area_ods" class="grid grid-cols-2 gap-2 pt-1 border-t border-emerald-100/60 text-[11px]">
              <div v-if="selectedRecord.areaOcde || selectedRecord.metadatosRecuperados?.area_ocde">
                <span class="text-[10px] uppercase font-bold text-slate-400 block">Área OCDE:</span>
                <span class="text-slate-700 font-medium">{{ selectedRecord.areaOcde || selectedRecord.metadatosRecuperados?.area_ocde }}</span>
              </div>
              <div v-if="selectedRecord.areaOds || selectedRecord.metadatosRecuperados?.area_ods">
                <span class="text-[10px] uppercase font-bold text-slate-400 block">Objetivo ODS:</span>
                <span class="text-slate-700 font-medium">{{ selectedRecord.areaOds || selectedRecord.metadatosRecuperados?.area_ods }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="p-4 bg-gray-50 border-t border-gray-100 flex items-center justify-end gap-2">
          <button
            @click="selectedRecord = null"
            class="px-4 py-2 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded-lg cursor-pointer"
          >
            Cerrar
          </button>
          <button
            v-if="selectedRecord.estado === 'Completado'"
            @click="selectedRecord = null"
            class="px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm flex items-center gap-1.5 cursor-pointer"
          >
            <Check :size="14" /> Registro Enriquecido
          </button>
          <button
            v-else-if="selectedRecord.estado === 'Pendiente de validación'"
            @click="selectedRecord = null"
            class="px-4 py-2 text-xs font-semibold text-amber-800 bg-amber-100 border border-amber-300 rounded-lg shadow-xs flex items-center gap-1.5 cursor-default"
            title="El registro ya fue enriquecido por el agente IA y está pendiente de validación manual en la sección de Validación."
          >
            <AlertCircle :size="14" /> Pendiente de Validación
          </button>
          <button
            v-else
            @click="runAgentSingle(selectedRecord)"
            :disabled="enrichingIds[selectedRecord.id]"
            class="px-4 py-2 text-xs font-semibold text-white rounded-lg shadow-sm hover:opacity-95 cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
            style="background: #00aea7"
          >
            <div v-if="enrichingIds[selectedRecord.id]" class="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            <Zap v-else :size="14" /> Enriquecer con Agente
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Search, Zap, Download, Filter, ChevronDown, Eye, X, Sparkles, Check, RefreshCw, CheckCircle2, XCircle, AlertCircle } from 'lucide-vue-next'
import Card from '../components/common/Card.vue'
import Badge from '../components/common/Badge.vue'
import SectionHeader from '../components/common/SectionHeader.vue'
import { proposalService } from '../services/proposalService'
import type { MonitoreoRecord } from '../types'

const search = ref('')
const selectedStatuses = ref<string[]>([])
const statusDropdownOpen = ref(false)
const selectedRecord = ref<MonitoreoRecord | null>(null)
const runningBatch = ref(false)
const scanningMissing = ref(false)
const loading = ref(true)
const enrichingIds = ref<Record<string, boolean>>({})

const currentPage = ref(1)
const pageSize = ref(15)
const totalFilteredRecords = ref(0)

const totalDetectados = ref(0)
const pendientesCount = ref(0)
const pendientesValidacionCount = ref(0)
const enProcesoCount = ref(0)
const completadosCount = ref(0)

const stats = computed(() => [
  { label: 'Total detectados', value: totalDetectados.value.toLocaleString('es-CL'), color: '#F57C00' },
  { label: 'Pendientes', value: pendientesCount.value.toLocaleString('es-CL'), color: '#d32f2f' },
  { label: 'Pend. validación', value: pendientesValidacionCount.value.toLocaleString('es-CL'), color: '#E65100' },
  { label: 'En proceso', value: enProcesoCount.value.toLocaleString('es-CL'), color: '#00aea7' },
  { label: 'Completados', value: completadosCount.value.toLocaleString('es-CL'), color: '#2E7D32' },
])

const records = ref<MonitoreoRecord[]>([])

const formatFalencias = (campo: string): string[] => {
  if (!campo) return ['Metadatos faltantes']
  const rawParts = campo.split(',').map(s => s.trim()).filter(Boolean)
  const dict: Record<string, string> = {
    'SIN_ABSTRACT_CON_DOI': 'Sin resumen (con DOI)',
    'SIN_DOI_NI_ABSTRACT': 'Sin DOI ni resumen',
    'SIN_ABSTRACT': 'Sin resumen',
    'SIN_DOI': 'Sin DOI',
    'SIN_PALABRAS_CLAVE': 'Sin palabras clave',
    'SIN_FINANCIAMIENTO': 'Sin financiamiento',
    'SIN_DERECHOS_ACCESO': 'Sin derechos de acceso',
    'SIN_LICENCIA': 'Sin licencia',
    'SIN_TITULO': 'Sin título',
  }
  return rawParts.map(p => dict[p] || p.replace(/_/g, ' '))
}

const getFalenciaBadgeClass = (falencia: string): string => {
  const f = falencia.toLowerCase()
  if (f.includes('resumen') || f.includes('abstract')) return 'bg-amber-50 text-amber-800 border border-amber-200'
  if (f.includes('doi')) return 'bg-rose-50 text-rose-800 border border-rose-200'
  if (f.includes('clave') || f.includes('keyword') || f.includes('subject')) return 'bg-blue-50 text-blue-800 border border-blue-200'
  if (f.includes('financiamiento') || f.includes('funding')) return 'bg-emerald-50 text-emerald-800 border border-emerald-200'
  if (f.includes('derechos') || f.includes('acceso') || f.includes('rights')) return 'bg-purple-50 text-purple-800 border border-purple-200'
  if (f.includes('licencia') || f.includes('license')) return 'bg-indigo-50 text-indigo-800 border border-indigo-200'
  return 'bg-slate-100 text-slate-700 border border-slate-200'
}

/**
 * Calcula el porcentaje real de completitud (0-100%) sobre los 6 metadatos enriquecidos objetivo:
 * 1. Fuente de financiamiento
 * 2. Resumen (abstract)
 * 3. Palabras clave
 * 4. Área OCDE
 * 5. Área ODS
 * 6. Derechos de acceso
 */
const calculateRecordCompletitud = (item: any, recMeta: any, kws: string[] = [], fundingArr: string[] = []) => {
  // 1. Fuente de financiamiento
  const hasFunding = Boolean(
    (Array.isArray(fundingArr) && fundingArr.length > 0) ||
    (Array.isArray(item?.fuente_financiamiento) && item.fuente_financiamiento.length > 0) ||
    (Array.isArray(recMeta?.funding) && recMeta.funding.length > 0) ||
    (typeof item?.fuente_financiamiento === 'string' && item.fuente_financiamiento.trim() && !['[]', 'null', 'none'].includes(item.fuente_financiamiento.trim().toLowerCase())) ||
    (typeof recMeta?.funding === 'string' && recMeta.funding.trim() && !['[]', 'null', 'none'].includes(recMeta.funding.trim().toLowerCase()))
  )

  // 2. Resumen (abstract)
  const hasAbstract = Boolean(
    (item?.abstract_enriquecido && String(item.abstract_enriquecido).trim().length > 10) ||
    (item?.resumen_original && String(item.resumen_original).trim().length > 10) ||
    (recMeta?.abstract && String(recMeta.abstract).trim().length > 10)
  )

  // 3. Palabras clave
  const hasKeywords = Boolean(
    (Array.isArray(kws) && kws.length > 0) ||
    (Array.isArray(item?.palabras_clave) && item.palabras_clave.length > 0) ||
    (Array.isArray(recMeta?.keywords) && recMeta.keywords.length > 0) ||
    (typeof item?.palabras_clave === 'string' && item.palabras_clave.trim() && !['[]', 'null', 'none'].includes(item.palabras_clave.trim().toLowerCase()))
  )

  // 4. Área OCDE
  const hasOcde = Boolean(
    (Array.isArray(item?.area_ocde) && item.area_ocde.length > 0) ||
    (Array.isArray(recMeta?.area_ocde) && recMeta.area_ocde.length > 0) ||
    (typeof item?.area_ocde === 'string' && item.area_ocde.trim() && !['[]', 'null', 'none'].includes(item.area_ocde.trim().toLowerCase())) ||
    (typeof recMeta?.area_ocde === 'string' && recMeta.area_ocde.trim() && !['[]', 'null', 'none'].includes(recMeta.area_ocde.trim().toLowerCase()))
  )

  // 5. Área ODS
  const hasOds = Boolean(
    (Array.isArray(item?.area_ods) && item.area_ods.length > 0) ||
    (Array.isArray(recMeta?.area_ods) && recMeta.area_ods.length > 0) ||
    (typeof item?.area_ods === 'string' && item.area_ods.trim() && !['[]', 'null', 'none'].includes(item.area_ods.trim().toLowerCase())) ||
    (typeof recMeta?.area_ods === 'string' && recMeta.area_ods.trim() && !['[]', 'null', 'none'].includes(recMeta.area_ods.trim().toLowerCase()))
  )

  // 6. Derechos de acceso
  const accessVal = String(item?.derechos_acceso || recMeta?.access_rights || recMeta?.derechos_acceso || '').trim().toLowerCase()
  const hasAccessRights = Boolean(accessVal && !['null', 'none', 'undefined', ''].includes(accessVal))

  const countPresent = [hasFunding, hasAbstract, hasKeywords, hasOcde, hasOds, hasAccessRights].filter(Boolean).length
  const completitud = Math.round((countPresent / 6) * 100)

  // Pre-enriquecimiento (estado original antes del procesamiento)
  const tf = String(item?.tipo_falencia || '').toUpperCase()
  const hadAbstract = Boolean(
    (item?.resumen_original && String(item.resumen_original).trim().length > 10) ||
    (tf.length > 0 && !tf.includes('SIN_ABSTRACT') && !tf.includes('SIN_DOI_NI_ABSTRACT') && !tf.includes('SIN_ABSTRACT_CON_DOI'))
  )
  const hadKeywords = Boolean(tf.length > 0 && !tf.includes('SIN_PALABRAS_CLAVE'))
  const hadFunding = Boolean(tf.length > 0 && !tf.includes('SIN_FINANCIAMIENTO'))
  const hadAccessRights = Boolean(
    (hasAccessRights && !tf.includes('SIN_DERECHOS_ACCESO')) ||
    (tf.length > 0 && !tf.includes('SIN_DERECHOS_ACCESO'))
  )
  const hadOcde = false
  const hadOds = false

  const countPre = [hadFunding, hadAbstract, hadKeywords, hadOcde, hadOds, hadAccessRights].filter(Boolean).length
  const completitudPre = Math.min(completitud, Math.round((countPre / 6) * 100))

  return {
    completitud,
    completitudPre,
    detalle: {
      financiamiento: hasFunding,
      resumen: hasAbstract,
      palabrasClave: hasKeywords,
      areaOcde: hasOcde,
      areaOds: hasOds,
      derechosAcceso: hasAccessRights
    }
  }
}

const formatCompletitudDetalle = (row: MonitoreoRecord): string => {
  if (!row.completitudDetalle) return `${row.completitud}%`
  const d = row.completitudDetalle
  const presentes: string[] = []
  if (d.financiamiento) presentes.push('Financiamiento')
  if (d.resumen) presentes.push('Resumen')
  if (d.palabrasClave) presentes.push('Palabras clave')
  if (d.areaOcde) presentes.push('Área OCDE')
  if (d.areaOds) presentes.push('Área ODS')
  if (d.derechosAcceso) presentes.push('Derechos de acceso')
  return presentes.length > 0 ? `${presentes.length}/6 metadatos: ${presentes.join(', ')}` : '0/6 metadatos recuperados'
}

const getBackendEstadoFilter = (): string | undefined => {
  if (selectedStatuses.value.length === 0) return undefined
  const mapStatus: Record<string, string[]> = {
    'Pendiente': ['PENDIENTE'],
    'Pendiente de validación': ['PENDIENTE_VALIDACION', 'VALIDACION', 'COINCIDENCIA_DUDOSA'],
    'En proceso': ['EN_PROCESO'],
    'Completado': ['ENRIQUECIDO', 'SINCRONIZADO_DSPACE', 'COMPLETO']
  }
  const backendStates: string[] = []
  for (const s of selectedStatuses.value) {
    if (mapStatus[s]) backendStates.push(...mapStatus[s])
  }
  return backendStates.length > 0 ? backendStates.join(',') : undefined
}

const loadRealQueue = async () => {
  loading.value = true
  try {
    const backendEstado = getBackendEstadoFilter()
    const queryParams: any = {
      page: currentPage.value - 1,
      size: pageSize.value
    }
    if (search.value.trim()) {
      queryParams.q = search.value.trim()
    }
    if (backendEstado) {
      queryParams.estado = backendEstado
    }

    const [queueRes, statsRes] = await Promise.all([
      proposalService.getQueue(queryParams),
      proposalService.getQueueStats()
    ])

    const porEstado = statsRes?.por_estado || {}
    totalDetectados.value = statsRes?.total_en_cola ?? 0
    pendientesCount.value = porEstado['PENDIENTE'] || 0
    pendientesValidacionCount.value = (porEstado['PENDIENTE_VALIDACION'] || 0) + (porEstado['VALIDACION'] || 0) + (porEstado['COINCIDENCIA_DUDOSA'] || 0)
    enProcesoCount.value = porEstado['EN_PROCESO'] || 0
    completadosCount.value = (porEstado['ENRIQUECIDO'] || 0) + (porEstado['SINCRONIZADO_DSPACE'] || 0) + (porEstado['COMPLETO'] || 0)

    totalFilteredRecords.value = queueRes?.total || 0

    const mapped: MonitoreoRecord[] = []

    if (queueRes?.items && queueRes.items.length > 0) {
      for (const item of queueRes.items) {
        const uuidVal = String(item.dspace_uuid || item.uuid_dspace || item.uuid || (typeof item.id === 'string' && item.id.includes('-') ? item.id : ''))
        const recMeta = item.metadatos_recuperados || {}
        
        // Extraer palabras clave
        let kws: string[] = []
        if (Array.isArray(item.palabras_clave) && item.palabras_clave.length > 0) {
          kws = item.palabras_clave
        } else if (Array.isArray(recMeta.keywords) && recMeta.keywords.length > 0) {
          kws = recMeta.keywords
        } else if (typeof item.palabras_clave === 'string') {
          try { kws = JSON.parse(item.palabras_clave || '[]') } catch { kws = [] }
        }

        // Extraer financiamiento
        let fundingArr: string[] = []
        if (Array.isArray(item.fuente_financiamiento)) {
          fundingArr = item.fuente_financiamiento
        } else if (Array.isArray(recMeta.funding)) {
          fundingArr = recMeta.funding
        } else if (typeof recMeta.funding === 'string') {
          fundingArr = [recMeta.funding]
        } else if (typeof item.fuente_financiamiento === 'string') {
          fundingArr = [item.fuente_financiamiento]
        }

        const compData = calculateRecordCompletitud(item, recMeta, kws, fundingArr)

        const isEnriched = item.estado === 'ENRIQUECIDO' || item.estado === 'SINCRONIZADO_DSPACE' || item.estado === 'COMPLETO'
        const isPendingValidation = item.estado === 'PENDIENTE_VALIDACION' || item.estado === 'VALIDACION' || item.estado === 'COINCIDENCIA_DUDOSA'
        const isEnProceso = item.estado === 'EN_PROCESO'
        const mappedEstado = isEnriched ? 'Completado' : isPendingValidation ? 'Pendiente de validación' : isEnProceso ? 'En proceso' : 'Pendiente'

        mapped.push({
          id: String(item.id || item.uuid_dspace || ''),
          uuid: uuidVal,
          title: item.titulo || item.title || item.titulo_dspace || item.name || (item.doi ? `Publicación (DOI: ${item.doi})` : `Registro DSpace #${item.id || item.uuid_dspace}`),
          campo: item.tipo_falencia || 'Metadatos faltantes',
          fecha: item.created_at ? item.created_at.split('T')[0] : 'Hoy',
          prioridad: item.tipo_falencia?.includes('AMBOS') || item.tipo_falencia?.includes(',') ? 'Alta' : 'Media',
          estado: mappedEstado,
          rawEstado: item.estado,
          completitud: item.completitud !== undefined ? item.completitud : compData.completitud,
          completitudPre: item.completitud_pre !== undefined ? item.completitud_pre : compData.completitudPre,
          completitudDetalle: compData.detalle,
          coleccion: item.coleccion || 'Artículos Científicos USACH',
          comunidad: item.comunidad || 'Facultad USACH',
          autor: item.autor || 'Investigador USACH',
          doi: item.doi || recMeta.doi || '',
          abstractEnriquecido: item.abstract_enriquecido || recMeta.abstract,
          palabrasClave: kws,
          fuente: item.fuente_enriquecimiento || (recMeta.sources ? (Array.isArray(recMeta.sources) ? recMeta.sources.join(', ') : String(recMeta.sources)) : undefined),
          fuenteFinanciamiento: fundingArr.length > 0 ? fundingArr : undefined,
          derechosAcceso: item.derechos_acceso || recMeta.access_rights,
          licencia: item.licencia || recMeta.license,
          areaOcde: item.area_ocde || recMeta.area_ocde,
          areaOds: item.area_ods || recMeta.area_ods,
          metadatosRecuperados: recMeta
        })
      }
    } else if (totalFilteredRecords.value === 0 && !search.value.trim() && selectedStatuses.value.length === 0) {
      // Fallback a propuestas v3 solo si la cola está vacía
      const proposals = await proposalService.listProposals()
      if (proposals && proposals.length > 0) {
        totalDetectados.value = proposals.length
        pendientesCount.value = proposals.filter((p: any) => p.status === 'DETECTED' || p.status === 'PENDING').length
        enProcesoCount.value = proposals.filter((p: any) => p.status === 'ENRICHING' || p.status === 'VALIDATING').length
        completadosCount.value = proposals.filter((p: any) => p.status === 'APPROVED' || p.status === 'LOADED_TO_DSPACE').length
        totalFilteredRecords.value = proposals.length

        const startIdx = (currentPage.value - 1) * pageSize.value
        const pagedProposals = proposals.slice(startIdx, startIdx + pageSize.value)

        for (const p of pagedProposals) {
          const uuidVal = String(p.uuid_dspace || p.uuid || p.item_uuid || (typeof p.item_id === 'string' && p.item_id.includes('-') ? p.item_id : ''))
          const compData = calculateRecordCompletitud(p, {}, [], [])
          mapped.push({
            id: String(p.id || p.uuid_dspace || ''),
            uuid: uuidVal,
            title: p.title || p.titulo || p.titulo_dspace || p.name || (p.doi ? `Publicación (DOI: ${p.doi})` : `Propuesta #${p.id}`),
            campo: p.field_name || p.field || 'Metadato General',
            fecha: p.created_at ? p.created_at.split('T')[0] : 'Hoy',
            prioridad: 'Alta',
            estado: p.status === 'APPROVED' ? 'Completado' : p.status === 'PENDING_CURATION' ? 'En proceso' : 'Pendiente',
            completitud: compData.completitud,
            completitudPre: compData.completitudPre,
            completitudDetalle: compData.detalle,
            coleccion: 'DSpace-CRIS',
            comunidad: 'VRIIC',
            autor: 'Investigador USACH',
            doi: p.doi || '',
            abstractEnriquecido: p.suggested_value || p.new_value,
            fuente: p.source || p.best_source
          })
        }
      }
    }

    records.value = mapped
  } catch (err) {
    console.error('Error cargando cola real de monitoreo:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRealQueue()
})

const totalPages = computed(() => Math.max(1, Math.ceil(totalFilteredRecords.value / pageSize.value)))

const paginatedRecords = computed(() => records.value)

const pageStart = computed(() => (totalFilteredRecords.value === 0 ? 0 : (currentPage.value - 1) * pageSize.value + 1))
const pageEnd = computed(() => Math.min(currentPage.value * pageSize.value, totalFilteredRecords.value))

const goToPage = (p: number) => {
  if (p >= 1 && p <= totalPages.value && p !== currentPage.value) {
    currentPage.value = p
    loadRealQueue()
  }
}

const visiblePages = computed(() => {
  const total = totalPages.value
  const current = currentPage.value
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }
  const pages: (number | string)[] = []
  pages.push(1)
  if (current > 3) pages.push('...')

  const start = Math.max(2, current - 1)
  const end = Math.min(total - 1, current + 1)
  for (let i = start; i <= end; i++) {
    pages.push(i)
  }

  if (current < total - 2) pages.push('...')
  pages.push(total)
  return pages
})

let searchDebounceTimer: any = null
watch(search, () => {
  clearTimeout(searchDebounceTimer)
  searchDebounceTimer = setTimeout(() => {
    currentPage.value = 1
    loadRealQueue()
  }, 350)
})

watch(pageSize, () => {
  currentPage.value = 1
  loadRealQueue()
})

watch(selectedStatuses, () => {
  currentPage.value = 1
  loadRealQueue()
}, { deep: true })

const toggleStatus = (opt: string) => {
  if (selectedStatuses.value.includes(opt)) {
    selectedStatuses.value = selectedStatuses.value.filter(s => s !== opt)
  } else {
    selectedStatuses.value.push(opt)
  }
}

const runAgentOnAll = async () => {
  runningBatch.value = true
  try {
    const itemsToDetect = records.value.filter(r => r.estado === 'Pendiente').slice(0, 10).map(r => ({
      item_id: r.id,
      title: r.title,
      missing_fields: [r.campo],
      doi: r.doi
    }))
    if (itemsToDetect.length > 0) {
      await proposalService.detectMissing(itemsToDetect)
      alert(`Se procesaron exitosamente ${itemsToDetect.length} registros con el agente de enriquecimiento IA.`)
      await loadRealQueue()
    } else {
      alert('No hay registros en estado Pendiente para procesar.')
    }
  } catch (err: any) {
    alert(`Error procesando lote: ${err?.response?.data?.detail || err.message || err}`)
  } finally {
    runningBatch.value = false
  }
}

const runAgentSingle = async (record: MonitoreoRecord | null) => {
  if (!record) return
  if (record.estado === 'Completado' || record.estado === 'Pendiente de validación') {
    alert('Este registro ya ha sido enriquecido y no requiere un nuevo proceso de enriquecimiento.')
    return
  }
  enrichingIds.value[record.id] = true
  try {
    await proposalService.enrichQueueItem(record.id || record.uuid || '')
    record.estado = 'Completado'
    completadosCount.value++
    pendientesCount.value = Math.max(0, pendientesCount.value - 1)

    // Recargar datos frescos desde backend
    await loadRealQueue()

    if (selectedRecord.value && selectedRecord.value.id === record.id) {
      const updated = records.value.find(r => r.id === record.id)
      if (updated) selectedRecord.value = updated
    }
  } catch (err: any) {
    alert(`Error al iniciar enriquecimiento: ${err?.response?.data?.detail || err.message || err}`)
  } finally {
    enrichingIds.value[record.id] = false
  }
}

const exportSummary = () => {
  alert('Generando exportación de reporte de monitoreo DSpace-CRIS...')
}

const scanAndPopulateMissing = async () => {
  scanningMissing.value = true
  try {
    const res = await proposalService.getCountMissing(true)
    if (res) {
      const guardado = res.db_guardado
      const nuevos = guardado?.nuevos_en_cola ?? 0
      const existentes = guardado?.ya_existentes_en_cola ?? 0
      const totalCandidatos = guardado?.total_candidatos_detectados || ((res.total_sin_abstract || 0) + (res.total_sin_doi || 0))
      
      let mensaje = `Escaneo de DSpace-CRIS y población de cola finalizado con éxito.\n\n`
      mensaje += `• Registros evaluados en repositorio: ${res.total_revisados?.toLocaleString('es-CL') || '0'}\n`
      mensaje += `• Publicaciones con campos incompletos detectadas: ${totalCandidatos}\n`
      if (guardado) {
        mensaje += `• Nuevos elementos guardados en la cola de enriquecimiento: ${nuevos}\n`
        mensaje += `• Elementos que ya existían en la cola: ${existentes}`
      }
      alert(mensaje)

      // Actualizar automáticamente la tabla y contadores de la vista
      await loadRealQueue()
    } else {
      alert('El servicio de escaneo no retornó datos.')
    }
  } catch (err: any) {
    console.error('Error al ejecutar count-missing con save_to_db:', err)
    alert(`Error al escanear DSpace y poblar la cola: ${err?.response?.data?.detail || err.message || err}`)
  } finally {
    scanningMissing.value = false
  }
}
</script>

