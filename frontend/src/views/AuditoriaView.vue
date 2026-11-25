<template>
  <div class="h-full overflow-y-auto">
    <SectionHeader
      title="Auditoría y Trazabilidad Institucional"
      description="Bitácora inmutable (INSERT-only) de eventos: quién monitoreó registros, quién validó, aprobó o rechazó publicaciones y los metadatos implicados."
    />

    <!-- Stats Bar -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <Card customClass="p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-[11px] font-semibold text-[#6b7a90] uppercase">Eventos Totales</span>
          <div class="w-8 h-8 rounded-lg bg-teal-50 text-[#00aea7] flex items-center justify-center">
            <Activity :size="16" />
          </div>
        </div>
        <p class="text-xl font-bold text-[#1a2332]">
          {{ totalEventos }} <span class="text-xs font-normal text-[#6b7a90]">eventos</span>
        </p>
        <p class="text-[10px] text-[#00aea7] font-medium mt-0.5">Trazabilidad inmutable MS3</p>
      </Card>

      <Card customClass="p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-[11px] font-semibold text-[#6b7a90] uppercase">Monitoreos de Registros</span>
          <div class="w-8 h-8 rounded-lg bg-blue-50 text-[#1565C0] flex items-center justify-center">
            <RefreshCw :size="16" />
          </div>
        </div>
        <p class="text-xl font-bold text-[#1565C0]">
          {{ countMonitoreos }} <span class="text-xs font-normal text-[#6b7a90]">ejecuciones</span>
        </p>
        <p class="text-[10px] text-blue-600 font-medium mt-0.5">Escaneos DSpace-CRIS registrados</p>
      </Card>

      <Card customClass="p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-[11px] font-semibold text-[#6b7a90] uppercase">Curaduría (Aprob / Valid)</span>
          <div class="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <ShieldCheck :size="16" />
          </div>
        </div>
        <p class="text-xl font-bold text-emerald-700">
          {{ countCuraduria }} <span class="text-xs font-normal text-[#6b7a90]">decisiones</span>
        </p>
        <p class="text-[10px] text-emerald-600 font-medium mt-0.5">Decisiones humanas trazables</p>
      </Card>

      <Card customClass="p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-[11px] font-semibold text-[#6b7a90] uppercase">Usuarios Activos en Log</span>
          <div class="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
            <UserIcon :size="16" />
          </div>
        </div>
        <p class="text-xl font-bold text-purple-700">
          {{ uniqueUsersCount }} <span class="text-xs font-normal text-[#6b7a90]">responsables</span>
        </p>
        <p class="text-[10px] text-purple-600 font-medium mt-0.5">Control RBAC verificado</p>
      </Card>
    </div>

    <!-- Main Card -->
    <Card>
      <!-- Toolbar & Filters -->
      <div class="p-4 border-b border-gray-100 flex flex-col gap-3">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 flex-wrap">
          <div class="relative flex-1 min-w-[260px] max-w-md">
            <Search :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-[#6b7a90]" />
            <input
              type="text"
              placeholder="Buscar por publicación, usuario, acción o DOI..."
              v-model="searchTerm"
              class="w-full pl-9 pr-3 py-2 text-xs border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#00aea7]/20 focus:border-[#00aea7]"
            />
          </div>

          <div class="flex items-center gap-2">
            <!-- View Mode Switch -->
            <div class="flex bg-slate-100 p-0.5 rounded-lg border border-slate-200 text-xs font-medium">
              <button
                @click="viewMode = 'events'"
                :class="[
                  'px-3 py-1 rounded-md transition-all cursor-pointer',
                  viewMode === 'events' ? 'bg-white text-slate-800 shadow-xs font-semibold' : 'text-slate-600 hover:text-slate-800'
                ]"
              >
                Eventos Detallados
              </button>
              <button
                @click="viewMode = 'grouped'"
                :class="[
                  'px-3 py-1 rounded-md transition-all cursor-pointer',
                  viewMode === 'grouped' ? 'bg-white text-slate-800 shadow-xs font-semibold' : 'text-slate-600 hover:text-slate-800'
                ]"
              >
                Agrupado por Publicación
              </button>
            </div>

            <button
              @click="exportCurrentAudit"
              class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer"
            >
              <Download :size="13" />
              <span>Exportar</span>
            </button>
          </div>
        </div>

        <!-- Action Category Filters -->
        <div class="flex flex-wrap items-center gap-1.5 pt-1">
          <span class="text-[11px] font-semibold text-[#6b7a90] mr-1">Filtrar por tipo:</span>
          <button
            v-for="cat in filterCategories"
            :key="cat.key"
            @click="selectedCategory = cat.key"
            class="px-2.5 py-1 text-xs rounded-lg font-medium transition-all cursor-pointer border"
            :class="[
              selectedCategory === cat.key
                ? 'bg-[#00aea7] text-white border-[#00aea7] shadow-xs'
                : 'bg-white text-slate-600 border-gray-200 hover:bg-gray-50'
            ]"
          >
            {{ cat.label }}
            <span
              v-if="cat.count !== undefined"
              class="ml-1 text-[10px] px-1.5 py-0.2 rounded-full"
              :class="selectedCategory === cat.key ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-600'"
            >
              {{ cat.count }}
            </span>
          </button>
        </div>
      </div>

      <!-- Table View: Detailed Events (Primary) -->
      <div v-if="viewMode === 'events'" class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-gray-100 bg-slate-50/70">
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide whitespace-nowrap">Código</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide whitespace-nowrap">Acción</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide">Publicación Implicada</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide whitespace-nowrap">Usuario Responsable</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide">Detalle / Resultado</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide whitespace-nowrap">Fecha / Hora</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide whitespace-nowrap">Trazabilidad</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="7" class="text-center py-12 text-slate-500 text-xs">
                <div class="inline-block w-4 h-4 border-2 border-[#00aea7] border-t-transparent rounded-full animate-spin mr-2"></div>
                Cargando bitácora de auditoría inmutable desde MS3 Auth...
              </td>
            </tr>
            <tr v-else-if="filteredEvents.length === 0">
              <td colspan="7" class="text-center py-12 text-slate-500 text-xs">
                No se encontraron eventos de auditoría para los filtros aplicados.
              </td>
            </tr>
            <tr
              v-else
              v-for="ev in paginatedEvents"
              :key="ev.id"
              class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors"
            >
              <!-- Código -->
              <td class="px-4 py-3.5 whitespace-nowrap">
                <span class="text-xs font-mono font-medium text-[#1565C0] bg-blue-50/80 border border-blue-100 px-2 py-0.5 rounded-md">
                  #{{ ev.shortId }}
                </span>
              </td>

              <!-- Acción con Badge -->
              <td class="px-4 py-3.5 whitespace-nowrap">
                <span
                  class="text-xs font-semibold px-2.5 py-1 rounded-md border inline-flex items-center gap-1.5"
                  :class="getActionBadgeClass(ev.action)"
                >
                  <component :is="getActionIcon(ev.action)" :size="12" />
                  <span>{{ ev.action }}</span>
                </span>
              </td>

              <!-- Publicación Implicada -->
              <td class="px-4 py-3.5 max-w-[280px]">
                <div class="space-y-0.5">
                  <p class="text-xs font-semibold text-[#1a2332] truncate" :title="ev.publicationTitle">
                    {{ ev.publicationTitle }}
                  </p>
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <a
                      v-if="ev.doiUrl"
                      :href="ev.doiUrl"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="text-[10px] font-mono text-[#00aea7] hover:underline inline-flex items-center gap-0.5"
                      :title="`Abrir DOI: ${ev.doi}`"
                    >
                      <span>DOI: {{ ev.doi }}</span>
                      <ExternalLink :size="10" />
                    </a>
                    <span v-else-if="ev.itemId && !ev.isSystem && !ev.isMonitoring" class="text-[10px] font-mono text-slate-400">
                      ID: {{ ev.itemId }}
                    </span>
                    <span v-if="ev.campo" class="text-[10px] px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 font-medium">
                      {{ ev.campo }}
                    </span>
                  </div>
                </div>
              </td>

              <!-- Usuario Responsable (Nombre + Rol) -->
              <td class="px-4 py-3.5 whitespace-nowrap">
                <div>
                  <p class="text-xs font-medium text-[#1a2332]">{{ ev.userName }}</p>
                  <div class="flex items-center gap-1.5 mt-0.5">
                    <span
                      class="text-[10px] font-semibold px-1.5 py-0.5 rounded border"
                      :class="getRoleBadgeClass(ev.role)"
                    >
                      {{ ev.role }}
                    </span>
                    <span v-if="ev.userEmail" class="text-[10px] text-slate-400 truncate max-w-[120px]" :title="ev.userEmail">
                      {{ ev.userEmail }}
                    </span>
                  </div>
                </div>
              </td>

              <!-- Detalle / Resultado -->
              <td class="px-4 py-3.5 max-w-[260px]">
                <p class="text-xs text-slate-600 line-clamp-2 leading-relaxed" :title="ev.summary">
                  {{ ev.summary }}
                </p>
              </td>

              <!-- Fecha / Hora -->
              <td class="px-4 py-3.5 whitespace-nowrap">
                <span class="text-xs text-slate-600 font-mono block">{{ ev.formattedDate }}</span>
                <span class="text-[10px] text-slate-400 font-mono">{{ ev.formattedTime }}</span>
              </td>

              <!-- Acciones -->
              <td class="px-4 py-3.5 whitespace-nowrap">
                <button
                  @click="openEventModal(ev)"
                  class="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-[#00aea7] bg-[#00aea7]/10 hover:bg-[#00aea7]/20 border border-[#00aea7]/30 rounded-lg transition-colors cursor-pointer"
                  title="Ver detalle completo del evento y payload"
                >
                  <Eye :size="12" />
                  <span>Ver detalle</span>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Table View: Grouped by Publication -->
      <div v-else class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-gray-100 bg-slate-50/70">
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide whitespace-nowrap">ID / Referencia</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide">Nombre del Registro / Publicación</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide whitespace-nowrap">Acciones Registradas</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide whitespace-nowrap">Último Responsable</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide whitespace-nowrap">Última Fecha</th>
              <th class="text-left px-4 py-3 text-[11px] font-semibold text-[#6b7a90] uppercase tracking-wide whitespace-nowrap">Trazabilidad</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="6" class="text-center py-12 text-slate-500 text-xs">
                <div class="inline-block w-4 h-4 border-2 border-[#00aea7] border-t-transparent rounded-full animate-spin mr-2"></div>
                Cargando registros...
              </td>
            </tr>
            <tr v-else-if="filteredGrouped.length === 0">
              <td colspan="6" class="text-center py-12 text-slate-500 text-xs">
                No hay registros agrupados para mostrar.
              </td>
            </tr>
            <tr
              v-else
              v-for="grp in paginatedGrouped"
              :key="grp.id"
              class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors"
            >
              <td class="px-4 py-3.5 whitespace-nowrap">
                <span
                  class="text-xs font-mono font-bold px-2 py-0.5 rounded-md"
                  :class="grp.isSystem ? 'text-purple-700 bg-purple-50 border border-purple-200' : 'text-[#1565C0] bg-blue-50 border border-blue-100'"
                >
                  {{ grp.isSystem ? grp.id : `#${grp.id}` }}
                </span>
              </td>
              <td class="px-4 py-3.5 max-w-[280px]">
                <p class="text-xs font-semibold text-[#1a2332] truncate" :title="grp.nombre">{{ grp.nombre }}</p>
                <a
                  v-if="grp.doiUrl"
                  :href="grp.doiUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-[10px] font-mono text-[#00aea7] hover:underline inline-flex items-center gap-0.5 mt-0.5"
                >
                  <span>DOI: {{ grp.doi }}</span>
                  <ExternalLink :size="10" />
                </a>
              </td>
              <td class="px-4 py-3.5">
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="act in grp.distinctActions"
                    :key="act"
                    class="text-[10px] font-medium px-2 py-0.5 rounded border"
                    :class="getActionBadgeClass(act)"
                  >
                    {{ act }}
                  </span>
                </div>
              </td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <p class="text-xs font-medium text-slate-800">{{ grp.lastUser }}</p>
                <span class="text-[10px] font-semibold px-1.5 py-0.2 rounded border" :class="getRoleBadgeClass(grp.lastRole)">
                  {{ grp.lastRole }}
                </span>
              </td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <span class="text-xs text-slate-600 font-mono">{{ grp.fecha }}</span>
              </td>
              <td class="px-4 py-3.5 whitespace-nowrap">
                <button
                  @click="selectedAuditGroup = grp"
                  class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-[#00aea7] hover:opacity-95 transition-all rounded-lg shadow-sm cursor-pointer"
                >
                  <ClipboardList :size="13" />
                  <span>Ver historial ({{ grp.eventos.length }})</span>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <Pagination
        v-if="viewMode === 'events' && filteredEvents.length > 0"
        v-model:current-page="currentEventsPage"
        v-model:page-size="eventsPageSize"
        :total-items="filteredEvents.length"
      />
      <Pagination
        v-else-if="viewMode === 'grouped' && filteredGrouped.length > 0"
        v-model:current-page="currentGroupedPage"
        v-model:page-size="groupedPageSize"
        :total-items="filteredGrouped.length"
      />
    </Card>

    <!-- Modal Detalle de Evento Individual -->
    <div
      v-if="selectedEvent"
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
                Evento de Auditoría #{{ selectedEvent.shortId }}
              </h3>
              <p class="text-[11px] text-slate-500">Trazabilidad inmutable e integridad institucional</p>
            </div>
          </div>
          <button @click="selectedEvent = null" class="p-1 rounded-lg text-slate-400 hover:text-slate-600 cursor-pointer">
            <X :size="18" />
          </button>
        </div>

        <div class="p-6 overflow-y-auto space-y-4 flex-1 text-xs">
          <!-- Acción y Fecha -->
          <div class="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200/60 flex-wrap gap-2">
            <div>
              <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Acción Ejecutada</span>
              <span class="text-xs font-bold px-2.5 py-1 rounded-md border inline-flex items-center gap-1.5 mt-1" :class="getActionBadgeClass(selectedEvent.action)">
                <component :is="getActionIcon(selectedEvent.action)" :size="12" />
                {{ selectedEvent.action }}
              </span>
            </div>
            <div class="text-right">
              <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Fecha y Hora</span>
              <span class="font-mono text-slate-700 font-semibold">{{ selectedEvent.formattedDate }} — {{ selectedEvent.formattedTime }}</span>
            </div>
          </div>

          <!-- Usuario Responsable -->
          <div class="p-4 rounded-xl border border-gray-200/80 bg-white space-y-2">
            <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Usuario Responsable</span>
            <div class="flex items-center justify-between flex-wrap gap-2">
              <div>
                <p class="text-sm font-bold text-slate-800">{{ selectedEvent.userName }}</p>
                <p v-if="selectedEvent.userEmail" class="text-xs text-slate-500 font-mono">{{ selectedEvent.userEmail }}</p>
                <p v-if="selectedEvent.userId" class="text-[10px] text-slate-400 font-mono mt-0.5">UUID: {{ selectedEvent.userId }}</p>
              </div>
              <span class="text-xs font-semibold px-2.5 py-1 rounded-md border" :class="getRoleBadgeClass(selectedEvent.role)">
                Rol: {{ selectedEvent.role }}
              </span>
            </div>
          </div>

          <!-- Publicación Implicada -->
          <div class="p-4 rounded-xl border border-gray-200/80 bg-white space-y-2">
            <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Publicación o Recurso Implicado</span>
            <p class="text-xs font-bold text-slate-800">{{ selectedEvent.publicationTitle }}</p>
            <div class="flex items-center gap-3 flex-wrap pt-1 text-[11px]">
              <div v-if="selectedEvent.doi">
                <span class="text-slate-500 font-medium mr-1">DOI:</span>
                <a
                  v-if="selectedEvent.doiUrl"
                  :href="selectedEvent.doiUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="font-mono text-[#00aea7] hover:underline inline-flex items-center gap-1 font-semibold"
                >
                  {{ selectedEvent.doi }}
                  <ExternalLink :size="11" />
                </a>
                <span v-else class="font-mono text-slate-700">{{ selectedEvent.doi }}</span>
              </div>
              <div v-if="selectedEvent.itemId">
                <span class="text-slate-500 font-medium mr-1">ID Ítem / UUID:</span>
                <span class="font-mono text-slate-700 font-semibold">{{ selectedEvent.itemId }}</span>
              </div>
              <div v-if="selectedEvent.campo">
                <span class="text-slate-500 font-medium mr-1">Campo:</span>
                <span class="font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded">{{ selectedEvent.campo }}</span>
              </div>
            </div>
          </div>

          <!-- Resumen / Detalle -->
          <div class="p-4 rounded-xl bg-slate-50 border border-slate-200/60 space-y-1">
            <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Descripción del Evento</span>
            <p class="text-xs text-slate-700 leading-relaxed font-medium">{{ selectedEvent.summary }}</p>
          </div>

          <!-- Valores / Payload -->
          <div v-if="selectedEvent.newValue || selectedEvent.previousValue" class="space-y-2">
            <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Metadatos / Payload Registrado</span>
            <div v-if="selectedEvent.previousValue" class="p-3 bg-rose-50/50 border border-rose-200 rounded-lg">
              <span class="text-[10px] font-bold text-rose-800 uppercase block mb-1">Valor Anterior:</span>
              <pre class="text-[11px] font-mono text-rose-900 whitespace-pre-wrap break-all">{{ formatJson(selectedEvent.previousValue) }}</pre>
            </div>
            <div v-if="selectedEvent.newValue" class="p-3 bg-emerald-50/50 border border-emerald-200 rounded-lg">
              <span class="text-[10px] font-bold text-emerald-800 uppercase block mb-1">Valor Registrado / Nuevo:</span>
              <pre class="text-[11px] font-mono text-emerald-900 whitespace-pre-wrap break-all">{{ formatJson(selectedEvent.newValue) }}</pre>
            </div>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-100 bg-slate-50 flex justify-end">
          <button
            @click="selectedEvent = null"
            class="px-5 py-2 rounded-xl text-xs font-semibold text-white bg-[#00aea7] hover:bg-[#009b95] transition-all cursor-pointer shadow-sm"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>

    <!-- Modal Trazabilidad Agrupada por Registro -->
    <div
      v-if="selectedAuditGroup"
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
                Historial de Trazabilidad — {{ selectedAuditGroup.isSystem ? selectedAuditGroup.nombre : `Registro #${selectedAuditGroup.id}` }}
              </h3>
              <p class="text-[11px] text-slate-500">Eventos ordenados cronológicamente</p>
            </div>
          </div>
          <button @click="selectedAuditGroup = null" class="p-1 rounded-lg text-slate-400 hover:text-slate-600 cursor-pointer">
            <X :size="18" />
          </button>
        </div>

        <div class="p-6 overflow-y-auto space-y-4 flex-1">
          <div class="bg-slate-50 p-4 rounded-xl border border-gray-100 space-y-1">
            <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Nombre del Registro / Publicación</span>
            <p class="text-xs font-bold text-slate-800">{{ selectedAuditGroup.nombre }}</p>
            <a
              v-if="selectedAuditGroup.doiUrl"
              :href="selectedAuditGroup.doiUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="text-[11px] font-mono text-[#00aea7] hover:underline inline-flex items-center gap-1 font-semibold pt-0.5"
            >
              <span>DOI: {{ selectedAuditGroup.doi }}</span>
              <ExternalLink :size="11" />
            </a>
          </div>

          <!-- Timeline of events -->
          <div class="space-y-4 pt-2">
            <div
              v-for="(ev, idx) in selectedAuditGroup.eventos"
              :key="idx"
              class="flex gap-3 text-xs"
            >
              <div class="flex flex-col items-center">
                <div
                  class="w-3.5 h-3.5 rounded-full mt-1 border-2 border-white shadow-sm flex-shrink-0"
                  :style="{ backgroundColor: ev.color }"
                />
                <div v-if="idx < selectedAuditGroup.eventos.length - 1" class="w-0.5 flex-1 bg-gray-200 my-1" />
              </div>
              <div class="flex-1 pb-4">
                <div class="flex items-center gap-2 flex-wrap mb-1">
                  <span class="font-bold text-slate-800">{{ ev.event }}</span>
                  <span class="text-[10px] text-slate-400 font-mono">{{ ev.time }}</span>
                  <span class="text-[10px] px-2 py-0.5 rounded font-medium border" :class="getRoleBadgeClass(ev.role)">
                    {{ ev.role }}: {{ ev.user }}
                  </span>
                </div>
                <p class="text-xs text-slate-600 leading-relaxed">{{ ev.result }}</p>
              </div>
            </div>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-100 bg-slate-50 flex justify-end">
          <button
            @click="selectedAuditGroup = null"
            class="px-5 py-2 rounded-xl text-xs font-semibold text-white bg-[#00aea7] hover:bg-[#009b95] transition-all cursor-pointer shadow-sm"
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
import {
  ClipboardList,
  Activity,
  ShieldCheck,
  Search,
  Download,
  X,
  ExternalLink,
  User as UserIcon,
  RefreshCw,
  Zap,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Edit,
  Eye,
  Key,
  CalendarCheck
} from 'lucide-vue-next'
import Card from '../components/common/Card.vue'
import SectionHeader from '../components/common/SectionHeader.vue'
import Pagination from '../components/common/Pagination.vue'
import { auditService, type RealAuditLog } from '../services/auditService'
import { proposalService } from '../services/proposalService'

interface ParsedAuditEvent {
  id: string
  shortId: string
  action: string
  publicationTitle: string
  doi?: string
  doiUrl?: string
  itemId?: string
  campo?: string
  userName: string
  userEmail?: string
  userId?: string
  role: string
  summary: string
  formattedDate: string
  formattedTime: string
  timestampDate: Date
  isMonitoring: boolean
  isSystem: boolean
  previousValue?: any
  newValue?: any
}

const loading = ref(true)
const searchTerm = ref('')
const selectedCategory = ref('todos')
const viewMode = ref<'events' | 'grouped'>('events')

const rawAuditLogs = ref<RealAuditLog[]>([])
const parsedEvents = ref<ParsedAuditEvent[]>([])
const groupedRecords = ref<any[]>([])

const selectedEvent = ref<ParsedAuditEvent | null>(null)
const selectedAuditGroup = ref<any | null>(null)

// Paginación para vista de eventos
const currentEventsPage = ref(1)
const eventsPageSize = ref(15)

// Paginación para vista agrupada
const currentGroupedPage = ref(1)
const groupedPageSize = ref(15)

// Métricas de auditoría
const totalEventos = computed(() => parsedEvents.value.length)
const countMonitoreos = computed(() => parsedEvents.value.filter(e => e.isMonitoring).length)
const countCuraduria = computed(() => parsedEvents.value.filter(e => {
  const act = e.action.toLowerCase()
  return act.includes('aprob') || act.includes('valid') || act.includes('rechaz') || act.includes('edit')
}).length)
const uniqueUsersCount = computed(() => {
  const users = new Set(parsedEvents.value.map(e => e.userName).filter(Boolean))
  return Math.max(1, users.size)
})

const filterCategories = computed(() => [
  { key: 'todos', label: 'Todos', count: parsedEvents.value.length },
  { key: 'campana', label: 'Campaña Anual', count: parsedEvents.value.filter(e => e.action.toLowerCase().includes('campa')).length },
  { key: 'monitoreo', label: 'Monitoreo de registros', count: parsedEvents.value.filter(e => e.isMonitoring).length },
  { key: 'aprobaciones', label: 'Aprobaciones', count: parsedEvents.value.filter(e => e.action.toLowerCase().includes('aprob')).length },
  { key: 'validaciones', label: 'Validaciones', count: parsedEvents.value.filter(e => e.action.toLowerCase().includes('valid')).length },
  { key: 'rechazos', label: 'Rechazos', count: parsedEvents.value.filter(e => e.action.toLowerCase().includes('rechaz')).length },
  { key: 'ediciones', label: 'Ediciones', count: parsedEvents.value.filter(e => e.action.toLowerCase().includes('edit')).length },
  { key: 'seguridad', label: 'Seguridad / Sesión', count: parsedEvents.value.filter(e => e.isSystem).length },
])

const formatDoiUrl = (doi?: string): string => {
  if (!doi) return ''
  const clean = doi.trim()
  if (clean.startsWith('http://') || clean.startsWith('https://')) return clean
  return `https://doi.org/${clean}`
}

const formatJson = (val: any): string => {
  if (!val) return ''
  if (typeof val === 'string') {
    try {
      const parsed = JSON.parse(val)
      return JSON.stringify(parsed, null, 2)
    } catch {
      return val
    }
  }
  return JSON.stringify(val, null, 2)
}

const getActionIcon = (action: string) => {
  const a = action.toLowerCase()
  if (a.includes('campa')) return CalendarCheck
  if (a.includes('monitoreo')) return RefreshCw
  if (a.includes('valid')) return ShieldCheck
  if (a.includes('aprob')) return CheckCircle2
  if (a.includes('rechaz')) return XCircle
  if (a.includes('edit')) return Edit
  if (a.includes('enrique')) return Zap
  if (a.includes('login') || a.includes('sesión') || a.includes('sesion')) return Key
  return Activity
}

const getActionBadgeClass = (action: string): string => {
  const a = action.toLowerCase()
  if (a.includes('campa')) return 'bg-purple-50 text-purple-700 border-purple-200'
  if (a.includes('monitoreo')) return 'bg-blue-50 text-[#1565C0] border-blue-200'
  if (a.includes('valid')) return 'bg-teal-50 text-[#00aea7] border-teal-200'
  if (a.includes('aprob')) return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (a.includes('rechaz')) return 'bg-rose-50 text-rose-700 border-rose-200'
  if (a.includes('edit')) return 'bg-amber-50 text-amber-800 border-amber-200'
  if (a.includes('enrique')) return 'bg-cyan-50 text-cyan-800 border-cyan-200'
  if (a.includes('login') || a.includes('sesión')) return 'bg-indigo-50 text-indigo-700 border-indigo-200'
  return 'bg-slate-100 text-slate-700 border-slate-200'
}

const getRoleBadgeClass = (role: string): string => {
  const r = (role || '').toLowerCase()
  if (r.includes('admin')) return 'bg-amber-50 text-amber-800 border-amber-200'
  if (r.includes('curador')) return 'bg-purple-50 text-purple-700 border-purple-200'
  if (r.includes('academ')) return 'bg-blue-50 text-blue-700 border-blue-200'
  return 'bg-slate-100 text-slate-600 border-slate-200'
}

const openEventModal = (ev: ParsedAuditEvent) => {
  selectedEvent.value = ev
}

const loadRealAuditLogs = async () => {
  loading.value = true
  try {
    const [logs, proposals, queueRes] = await Promise.all([
      auditService.getAuditLogs(),
      proposalService.listProposals().catch(() => []),
      proposalService.getQueue({ size: 1000 }).catch(() => ({ items: [] }))
    ])

    rawAuditLogs.value = logs

    // Diccionario de lookup para publicaciones
    const queueMap: Record<string, any> = {}
    if (queueRes?.items) {
      for (const it of queueRes.items) {
        if (it.id) queueMap[String(it.id)] = it
        if (it.dspace_uuid) queueMap[String(it.dspace_uuid)] = it
      }
    }

    const proposalMap: Record<string, any> = {}
    if (Array.isArray(proposals)) {
      for (const p of proposals) {
        if (p.id) proposalMap[String(p.id)] = p
        if (p.uuid || p.uuid_dspace) proposalMap[String(p.uuid || p.uuid_dspace)] = p
      }
    }

    const events: ParsedAuditEvent[] = []
    const grouped: Record<string, any[]> = {}
    const systemEventsList: any[] = []

    for (const l of logs) {
      const actLower = (l.action || '').toLowerCase()
      const isMonitoring = actLower.includes('monitoreo')
      const isLogin = actLower.includes('login') || actLower.includes('sesión') || actLower.includes('sesion')
      const isUserMgmt = actLower.includes('usuario')
      const isSystem = isLogin || isUserMgmt || (!l.item_id && !isMonitoring)

      // Extraer metadatos de payload new_value si existen
      const newV = l.new_value || {}
      const prevV = l.previous_value

      // Resolver ID del ítem
      const resolvedItemId = l.item_id && l.item_id !== 'null' && l.item_id !== 'undefined' ? String(l.item_id) : (newV?.uuid || '')

      // Buscar publicación asociada
      const qItem = resolvedItemId ? queueMap[resolvedItemId] : null
      const pItem = resolvedItemId ? proposalMap[resolvedItemId] : null

      let pubTitle = ''
      if (actLower.includes('campa')) {
        pubTitle = 'Campaña Anual de Enriquecimiento (DSpace-CRIS)'
      } else if (isMonitoring) {
        pubTitle = 'Repositorio DSpace-CRIS (Monitoreo de Metadatos)'
      } else if (isSystem) {
        pubTitle = isLogin ? 'Módulo de Autenticación Institucional' : 'Gestión de Seguridad y Usuarios'
      } else {
        pubTitle = newV?.titulo || newV?.title || qItem?.titulo || qItem?.title || pItem?.title || (resolvedItemId ? `Publicación #${resolvedItemId.length > 12 ? resolvedItemId.substring(0, 8) : resolvedItemId}` : 'Publicación Institucional')
      }

      // Resolver DOI
      const doi = newV?.doi || qItem?.doi || pItem?.doi || (newV?.metadatos_recuperados?.doi) || ''
      const doiUrl = doi ? formatDoiUrl(doi) : ''

      // Campo afectado
      const campo = newV?.campo || qItem?.tipo_falencia || pItem?.field_name || ''

      // Resumen legible
      let summary = ''
      if (newV?.resumen) {
        summary = newV.resumen
      } else if (newV?.mensaje) {
        summary = newV.mensaje
      } else if (isMonitoring && newV?.total_revisados !== undefined) {
        summary = `Monitoreo institucional de DSpace-CRIS: ${Number(newV.total_revisados).toLocaleString('es-CL')} registros evaluados, ${newV.total_candidatos || 0} con campos incompletos detectados.`
      } else if (l.rejection_reason) {
        summary = `Decisión: Rechazado. Motivo: ${l.rejection_reason}`
      } else if (actLower.includes('aprob')) {
        summary = `Metadato (${campo || 'General'}) aprobado e integrado para publicación científica.`
      } else if (actLower.includes('valid')) {
        summary = `Metadato (${campo || 'General'}) validado satisfactoriamente por curador.`
      } else if (actLower.includes('edit')) {
        summary = `Metadato (${campo || 'General'}) modificado antes de resolución.`
      } else if (isLogin) {
        summary = `Inicio de sesión exitoso en el sistema mediante autenticación institucional.`
      } else {
        summary = `Acción '${l.action}' registrada en bitácora institucional.`
      }

      const d = l.timestamp ? new Date(l.timestamp) : new Date()

      const parsedEv: ParsedAuditEvent = {
        id: l.id,
        shortId: l.id.length > 8 ? l.id.substring(0, 8) : l.id,
        action: l.action || 'Acción',
        publicationTitle: pubTitle,
        doi: doi || undefined,
        doiUrl: doiUrl || undefined,
        itemId: resolvedItemId || undefined,
        campo: campo || undefined,
        userName: l.user_name || 'Curador VRIIC',
        userEmail: l.user_email || undefined,
        userId: l.user_id || undefined,
        role: l.role || 'Curador',
        summary: summary,
        formattedDate: d.toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' }),
        formattedTime: d.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        timestampDate: d,
        isMonitoring,
        isSystem,
        previousValue: prevV,
        newValue: newV
      }

      events.push(parsedEv)

      // Para la vista agrupada
      if (resolvedItemId && !isSystem && !isMonitoring) {
        if (!grouped[resolvedItemId]) grouped[resolvedItemId] = []
        grouped[resolvedItemId].push(parsedEv)
      } else {
        systemEventsList.push(parsedEv)
      }
    }

    parsedEvents.value = events

    // Construir registros agrupados
    const grpList: any[] = []

    for (const [itemId, evs] of Object.entries(grouped)) {
      const first = evs[0]
      const last = evs[evs.length - 1]
      grpList.push({
        id: itemId.length > 12 ? itemId.substring(0, 8) : itemId,
        fullId: itemId,
        isSystem: false,
        nombre: first.publicationTitle,
        doi: first.doi,
        doiUrl: first.doiUrl,
        distinctActions: Array.from(new Set(evs.map(e => e.action))),
        lastUser: first.userName,
        lastRole: first.role,
        fecha: `${first.formattedDate} ${first.formattedTime}`,
        eventos: evs.map(e => ({
          time: `${e.formattedDate} ${e.formattedTime}`,
          event: e.action,
          user: e.userName,
          role: e.role,
          result: e.summary,
          color: e.action.toLowerCase().includes('aprob') ? '#2E7D32' : e.action.toLowerCase().includes('rechaz') ? '#E53935' : e.action.toLowerCase().includes('monitoreo') ? '#1565C0' : '#00aea7'
        }))
      })
    }

    // Grupos especiales para monitoreo y sistema
    const monitoringEvs = events.filter(e => e.isMonitoring)
    if (monitoringEvs.length > 0) {
      const mFirst = monitoringEvs[0]
      grpList.unshift({
        id: 'MONITOR',
        fullId: 'monitoring-dspace',
        isSystem: true,
        nombre: 'Monitoreo Periódico de Repositorio DSpace-CRIS',
        distinctActions: ['Monitoreo de registros'],
        lastUser: mFirst.userName,
        lastRole: mFirst.role,
        fecha: `${mFirst.formattedDate} ${mFirst.formattedTime}`,
        eventos: monitoringEvs.map(e => ({
          time: `${e.formattedDate} ${e.formattedTime}`,
          event: e.action,
          user: e.userName,
          role: e.role,
          result: e.summary,
          color: '#1565C0'
        }))
      })
    }

    const sysEvs = events.filter(e => e.isSystem)
    if (sysEvs.length > 0) {
      const sFirst = sysEvs[0]
      grpList.push({
        id: 'AUTH/SYS',
        fullId: 'auth-security',
        isSystem: true,
        nombre: 'Seguridad y Accesos Institucionales',
        distinctActions: Array.from(new Set(sysEvs.map(e => e.action))),
        lastUser: sFirst.userName,
        lastRole: sFirst.role,
        fecha: `${sFirst.formattedDate} ${sFirst.formattedTime}`,
        eventos: sysEvs.map(e => ({
          time: `${e.formattedDate} ${e.formattedTime}`,
          event: e.action,
          user: e.userName,
          role: e.role,
          result: e.summary,
          color: '#7B1FA2'
        }))
      })
    }

    groupedRecords.value = grpList
  } catch (err) {
    console.error('Error cargando bitácora real de auditoría:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRealAuditLogs()
})

// Filtrado de eventos
const filteredEvents = computed(() => {
  let list = parsedEvents.value

  // Filtro de categoría
  if (selectedCategory.value === 'campana') {
    list = list.filter(e => e.action.toLowerCase().includes('campa'))
  } else if (selectedCategory.value === 'monitoreo') {
    list = list.filter(e => e.isMonitoring)
  } else if (selectedCategory.value === 'aprobaciones') {
    list = list.filter(e => e.action.toLowerCase().includes('aprob'))
  } else if (selectedCategory.value === 'validaciones') {
    list = list.filter(e => e.action.toLowerCase().includes('valid'))
  } else if (selectedCategory.value === 'rechazos') {
    list = list.filter(e => e.action.toLowerCase().includes('rechaz'))
  } else if (selectedCategory.value === 'ediciones') {
    list = list.filter(e => e.action.toLowerCase().includes('edit'))
  } else if (selectedCategory.value === 'seguridad') {
    list = list.filter(e => e.isSystem)
  }

  // Filtro de búsqueda textual
  if (searchTerm.value.trim()) {
    const q = searchTerm.value.toLowerCase().trim()
    list = list.filter(e =>
      e.id.toLowerCase().includes(q) ||
      e.action.toLowerCase().includes(q) ||
      e.publicationTitle.toLowerCase().includes(q) ||
      e.userName.toLowerCase().includes(q) ||
      (e.userEmail && e.userEmail.toLowerCase().includes(q)) ||
      (e.doi && e.doi.toLowerCase().includes(q)) ||
      (e.campo && e.campo.toLowerCase().includes(q)) ||
      e.summary.toLowerCase().includes(q)
    )
  }

  return list
})

// Paginación de eventos
const paginatedEvents = computed(() => {
  const start = (currentEventsPage.value - 1) * eventsPageSize.value
  return filteredEvents.value.slice(start, start + eventsPageSize.value)
})

// Filtrado de registros agrupados
const filteredGrouped = computed(() => {
  let list = groupedRecords.value
  if (searchTerm.value.trim()) {
    const q = searchTerm.value.toLowerCase().trim()
    list = list.filter(g =>
      g.id.toLowerCase().includes(q) ||
      g.nombre.toLowerCase().includes(q) ||
      (g.doi && g.doi.toLowerCase().includes(q)) ||
      g.lastUser.toLowerCase().includes(q)
    )
  }
  return list
})

// Paginación de agrupados
const paginatedGrouped = computed(() => {
  const start = (currentGroupedPage.value - 1) * groupedPageSize.value
  return filteredGrouped.value.slice(start, start + groupedPageSize.value)
})

const exportCurrentAudit = () => {
  const dataToExport = filteredEvents.value.map(e => ({
    Codigo: `#${e.shortId}`,
    Accion: e.action,
    Publicacion: e.publicationTitle,
    DOI: e.doi || '',
    Usuario: e.userName,
    Email: e.userEmail || '',
    Rol: e.role,
    Detalle: e.summary,
    Fecha: e.formattedDate,
    Hora: e.formattedTime
  }))
  const jsonBlob = new Blob([JSON.stringify(dataToExport, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(jsonBlob)
  const a = document.createElement('a')
  a.href = url
  a.download = `auditoria_trazabilidad_${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
}
</script>
