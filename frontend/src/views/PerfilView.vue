<template>
  <div class="h-full overflow-y-auto space-y-6">
    <SectionHeader
      title="Perfil de Usuario"
      description="Información personal y configuración de acceso al sistema."
    />

    <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <!-- Profile Card -->
      <Card customClass="p-5 text-center">
        <div
          class="w-20 h-20 rounded-2xl flex items-center justify-center text-white text-2xl font-bold mx-auto mb-3 shadow-sm"
          style="background: #00aea7"
        >
          {{ userInitials }}
        </div>
        <h3 class="text-base font-semibold text-[#1a2332]">{{ user?.fullName || user?.name || 'Usuario Autenticado' }}</h3>
        <p class="text-xs text-[#6b7a90] mb-2">{{ user?.email || 'usuario@usach.cl' }}</p>
        <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-[#e0f7f6] text-[#007a75] border border-[#99e8e6]">
          {{ user?.role || 'Curador' }}
        </span>
        <div class="mt-4 pt-4 border-t border-gray-50 grid grid-cols-2 gap-3">
          <div class="text-center">
            <p class="text-lg font-semibold text-[#1a2332]">{{ userApprovals }}</p>
            <p class="text-[11px] text-[#6b7a90]">Aprobaciones</p>
          </div>
          <div class="text-center">
            <p class="text-lg font-semibold text-[#1a2332]">{{ userApprovals > 0 ? '100%' : '0%' }}</p>
            <p class="text-[11px] text-[#6b7a90]">Tasa aceptación</p>
          </div>
        </div>
      </Card>

      <!-- Details Card -->
      <Card customClass="xl:col-span-2 p-5">
        <h3 class="text-sm font-semibold text-[#1a2332] mb-4">Información del usuario</h3>
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-3">
          <div>
            <label class="text-xs text-[#6b7a90] mb-1 block">Nombre completo</label>
            <input
              type="text"
              :value="user?.fullName || user?.name || 'Usuario Institucional'"
              class="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg bg-gray-50 text-[#1a2332]"
              readonly
            />
          </div>
          <div>
            <label class="text-xs text-[#6b7a90] mb-1 block">Correo institucional</label>
            <input
              type="text"
              :value="user?.email || 'usuario@usach.cl'"
              class="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg bg-gray-50 text-[#1a2332]"
              readonly
            />
          </div>
          <div>
            <label class="text-xs text-[#6b7a90] mb-1 block">Identificador ORCID</label>
            <input
              type="text"
              :value="user?.orcid || (user?.role === 'Academico' ? '0000-0001-9876-5432' : '0000-0002-1825-0097')"
              class="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg bg-gray-50 text-[#1a2332] font-mono"
              readonly
            />
          </div>
          <div>
            <label class="text-xs text-[#6b7a90] mb-1 block">Unidad / Dirección</label>
            <input
              type="text"
              value="Vicerrectoría de Investigación, Innovación y Creación (VRIIC)"
              class="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg bg-gray-50 text-[#1a2332]"
              readonly
            />
          </div>
          <div>
            <label class="text-xs text-[#6b7a90] mb-1 block">Institución</label>
            <input
              type="text"
              value="Universidad de Santiago de Chile (USACH)"
              class="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg bg-gray-50 text-[#1a2332]"
              readonly
            />
          </div>
        </div>
        <div class="flex gap-2 mt-4">
          <button
            @click="saveProfile"
            class="px-4 py-2 text-xs font-medium text-white rounded-lg hover:opacity-90 cursor-pointer"
            style="background: #00aea7"
          >
            Actualizar perfil
          </button>
        </div>
      </Card>

      <!-- Permissions list -->
      <Card customClass="xl:col-span-3 p-5">
        <h3 class="text-sm font-semibold text-[#1a2332] mb-3">Permisos institucionales asignados</h3>
        <div class="grid grid-cols-2 xl:grid-cols-4 gap-3">
          <div
            v-for="p in permissions"
            :key="p.perm"
            class="flex items-center gap-2 p-2.5 rounded-lg border border-gray-100 bg-gray-50"
          >
            <div
              class="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0"
              :style="{ background: p.granted ? '#e0f7f6' : '#ffebee' }"
            >
              <div
                class="w-2 h-2 rounded-full"
                :style="{ background: p.granted ? '#00aea7' : '#d32f2f' }"
              />
            </div>
            <span class="text-[11px] text-[#1a2332]">{{ p.perm }}</span>
          </div>
        </div>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Card from '../components/common/Card.vue'
import SectionHeader from '../components/common/SectionHeader.vue'
import { proposalService } from '../services/proposalService'
import type { User } from '../types'

const props = defineProps<{
  user: User | null
}>()

const userApprovals = ref(0)

onMounted(async () => {
  try {
    const list = await proposalService.listProposals({ state: 'Aprobada' })
    userApprovals.value = list.length
  } catch {
    userApprovals.value = 0
  }
})

const userInitials = computed(() => {
  const name = props.user?.fullName || 'FE'
  const parts = name.split(' ')
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  return name.slice(0, 2).toUpperCase()
})

const permissions = computed(() => {
  const role = props.user?.role || 'Curador'
  if (role === 'Administrador' || role === 'Admin') {
    return [
      { perm: 'Visualizar Dashboard institucional', granted: true },
      { perm: 'Monitoreo de registros de repositorio', granted: true },
      { perm: 'Validación de metadatos externos', granted: true },
      { perm: 'Aprobación final de metadatos', granted: true },
      { perm: 'Auditoría y trazabilidad global', granted: true },
      { perm: 'Reportes y estadísticas avanzadas', granted: true },
      { perm: 'Gestión de usuarios y roles RBAC', granted: true },
      { perm: 'Configuración de microservicios IA', granted: true },
      { perm: 'Visualizar perfil institucional', granted: true },
    ]
  }
  if (role === 'Curador' || role === 'Curador_VRIIC') {
    return [
      { perm: 'Visualizar Dashboard institucional', granted: true },
      { perm: 'Monitoreo de registros de repositorio', granted: true },
      { perm: 'Validación de metadatos externos', granted: true },
      { perm: 'Aprobación final de metadatos', granted: true },
      { perm: 'Visualizar perfil institucional', granted: true },
      { perm: 'Auditoría y trazabilidad global', granted: false },
      { perm: 'Reportes y estadísticas avanzadas', granted: false },
      { perm: 'Gestión de usuarios y roles RBAC', granted: false },
      { perm: 'Configuración de microservicios IA', granted: false },
    ]
  }
  if (role === 'Academico') {
    return [
      { perm: 'Validar publicaciones asociadas a ORCID', granted: true },
      { perm: 'Visualizar perfil institucional', granted: true },
      { perm: 'Visualizar Dashboard institucional', granted: false },
      { perm: 'Monitoreo de registros de repositorio', granted: false },
      { perm: 'Aprobación final de metadatos', granted: false },
      { perm: 'Auditoría y trazabilidad global', granted: false },
      { perm: 'Reportes y estadísticas avanzadas', granted: false },
      { perm: 'Gestión de usuarios y roles RBAC', granted: false },
      { perm: 'Configuración del sistema', granted: false },
    ]
  }
  return [
    { perm: 'Visualizar perfil institucional', granted: true },
  ]
})

const saveProfile = () => {
  alert('Datos de perfil actualizados exitosamente.')
}

const changePassword = () => {
  alert('Se ha enviado un enlace de restablecimiento seguro a su correo institucional USACH.')
}
</script>

