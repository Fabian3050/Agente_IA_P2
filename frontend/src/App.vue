<template>
  <!-- If not logged in, show LoginPage -->
  <LoginView
    v-if="!isLoggedIn"
    @login-success="handleLoginSuccess"
  />

  <!-- Main Application Layout -->
  <div v-else class="flex h-screen w-screen overflow-hidden bg-[#F7F9FB] font-sans antialiased text-[#1a2332]">
    <!-- Collapsible USACH Sidebar -->
    <Sidebar
      :current="currentPage"
      :collapsed="sidebarCollapsed"
      :user="currentUser"
      @nav="navigate"
      @toggle="sidebarCollapsed = !sidebarCollapsed"
    />

    <!-- Main Workspace Area -->
    <div class="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
      <!-- Top Application Header -->
      <Header
        :page="currentPage"
        :user="currentUser"
        @nav="navigate"
        @logout="handleLogout"
      />

      <!-- Active View Content Container -->
      <main class="flex-1 p-6 overflow-hidden min-h-0 bg-[#F7F9FB]">
        <!-- Fallback si intenta acceder a una sección no autorizada para su rol -->
        <div
          v-if="!isPageAllowed(currentPage)"
          class="h-full flex items-center justify-center p-8"
        >
          <div class="max-w-md w-full bg-white p-8 rounded-2xl border border-rose-200 shadow-sm text-center">
            <div class="w-14 h-14 rounded-2xl bg-rose-50 border border-rose-200 text-rose-600 flex items-center justify-center mx-auto mb-4">
              <ShieldAlert :size="28" />
            </div>
            <h2 class="text-base font-bold text-[#1a2332] mb-1">Acceso Restringido</h2>
            <p class="text-xs text-[#6b7a90] mb-4 leading-relaxed">
              El rol <strong>{{ currentUser?.role || 'Asignado' }}</strong> no cuenta con autorización para acceder al módulo <strong>{{ currentPage }}</strong>.
            </p>
            <button
              @click="navigate(getDefaultPageForRole(currentUser?.role))"
              class="w-full py-2.5 px-4 rounded-xl text-white text-xs font-semibold shadow-xs hover:opacity-95 transition-all cursor-pointer"
              style="background: #00aea7"
            >
              Ir a mi sección autorizada
            </button>
          </div>
        </div>

        <DashboardView
          v-else-if="currentPage === 'dashboard'"
          @nav="navigate"
        />

        <MonitoreoView
          v-else-if="currentPage === 'monitoreo'"
        />

        <ValidacionView
          v-else-if="currentPage === 'validacion'"
          :user="currentUser"
        />

        <AprobacionView
          v-else-if="currentPage === 'aprobacion'"
        />

        <AuditoriaView
          v-else-if="currentPage === 'auditoria'"
        />

        <ReportesView
          v-else-if="currentPage === 'reportes' || currentPage === 'recuperacion'"
        />

        <UsuariosView
          v-else-if="currentPage === 'usuarios'"
        />

        <ConfiguracionView
          v-else-if="currentPage === 'configuracion'"
        />

        <PerfilView
          v-else-if="currentPage === 'perfil'"
          :user="currentUser"
        />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ShieldAlert } from 'lucide-vue-next'
import Sidebar from './components/layout/Sidebar.vue'
import Header from './components/layout/Header.vue'
import LoginView from './views/LoginView.vue'
import DashboardView from './views/DashboardView.vue'
import MonitoreoView from './views/MonitoreoView.vue'
import ValidacionView from './views/ValidacionView.vue'
import AprobacionView from './views/AprobacionView.vue'
import AuditoriaView from './views/AuditoriaView.vue'
import ReportesView from './views/ReportesView.vue'
import UsuariosView from './views/UsuariosView.vue'
import ConfiguracionView from './views/ConfiguracionView.vue'
import PerfilView from './views/PerfilView.vue'

import { authService } from './services/authService'
import type { Page, User } from './types'

const isLoggedIn = ref(false)
const currentUser = ref<User | null>(null)
const currentPage = ref<Page>('dashboard')
const sidebarCollapsed = ref(false)

/**
 * Matriz estricta de permisos por rol (RBAC):
 * - Perfil Academico: 'validacion' (solo sus publicaciones por ORCID) y 'perfil'. Todo lo demás restringido.
 * - Curador: 'dashboard', 'monitoreo', 'validacion', 'aprobacion' y 'perfil'. Todo lo demás restringido.
 * - Administrador: acceso total a todas las secciones.
 */
const isPageAllowed = (page: Page): boolean => {
  const role = currentUser.value?.role || 'Curador'
  if (role === 'Administrador' || role === 'Admin') {
    return true
  }
  if (role === 'Curador' || role === 'Curador_VRIIC') {
    return ['dashboard', 'monitoreo', 'validacion', 'aprobacion', 'perfil'].includes(page)
  }
  if (role === 'Academico') {
    return ['validacion', 'perfil'].includes(page)
  }
  return page === 'perfil'
}

const getDefaultPageForRole = (role?: string): Page => {
  if (role === 'Academico') return 'validacion'
  return 'dashboard'
}

const navigate = (page: Page) => {
  if (isPageAllowed(page)) {
    currentPage.value = page
  } else {
    currentPage.value = getDefaultPageForRole(currentUser.value?.role)
  }
}

const handleLoginSuccess = (user: User) => {
  currentUser.value = user
  isLoggedIn.value = true
  currentPage.value = getDefaultPageForRole(user.role)
}

const handleLogout = () => {
  authService.logout()
  currentUser.value = null
  isLoggedIn.value = false
}

onMounted(async () => {
  // Check if session token exists
  if (authService.isAuthenticated()) {
    const user = authService.getStoredUser()
    if (user) {
      currentUser.value = user
      isLoggedIn.value = true
      currentPage.value = isPageAllowed(currentPage.value) ? currentPage.value : getDefaultPageForRole(user.role)
      // Validar validez del token con MS3 (/auth/me)
      try {
        const remoteUser = await authService.getCurrentUser()
        if (remoteUser) {
          currentUser.value = remoteUser
          if (!isPageAllowed(currentPage.value)) {
            currentPage.value = getDefaultPageForRole(remoteUser.role)
          }
        }
      } catch {
        // Si el token expiró o es inválido, cerrar sesión
        handleLogout()
      }
    }
  }
})
</script>

