<template>
  <div class="max-w-5xl mx-auto p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-gray-800">Listino prezzi</h1>
      <button
        class="px-6 py-2.5 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary-dark transition-colors disabled:opacity-50"
        :disabled="saving"
        @click="save"
      >
        {{ saving ? 'Salvataggio...' : 'Salva' }}
      </button>
    </div>

    <!-- Stagioni -->
    <div class="bg-surface rounded-xl shadow-sm border border-border p-5">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-base font-semibold text-gray-700">Stagioni</h2>
        <button
          class="text-sm text-primary hover:text-primary-dark font-medium transition-colors"
          @click="addStagione"
        >
          + Aggiungi stagione
        </button>
      </div>
      <div class="space-y-4">
        <div
          v-for="(stagione, si) in data.stagioni"
          :key="si"
          class="border border-border rounded-lg p-4"
        >
          <div class="flex items-center gap-3 mb-3">
            <input
              v-model="stagione.colore"
              type="color"
              class="w-8 h-8 rounded border border-border cursor-pointer"
            />
            <input
              v-model="stagione.nome"
              type="text"
              placeholder="Nome stagione"
              class="flex-1 px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            />
            <button
              class="text-red-400 hover:text-red-600 text-sm transition-colors"
              @click="data.stagioni.splice(si, 1)"
              title="Rimuovi stagione"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="space-y-2 ml-11">
            <div
              v-for="(periodo, pi) in stagione.periodi"
              :key="pi"
              class="flex items-center gap-2"
            >
              <input
                v-model="periodo.da"
                type="date"
                class="px-3 py-1.5 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
              <span class="text-gray-400 text-xs">-</span>
              <input
                v-model="periodo.a"
                type="date"
                class="px-3 py-1.5 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
              <button
                class="text-red-400 hover:text-red-600 text-sm transition-colors"
                @click="stagione.periodi.splice(pi, 1)"
                title="Rimuovi periodo"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <button
              class="text-xs text-secondary hover:text-secondary-dark font-medium transition-colors"
              @click="stagione.periodi.push({ da: '', a: '' })"
            >
              + periodo
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Voci listino -->
    <div class="bg-surface rounded-xl shadow-sm border border-border p-5">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-base font-semibold text-gray-700">Voci listino</h2>
        <button
          class="text-sm text-primary hover:text-primary-dark font-medium transition-colors"
          @click="addVoce"
        >
          + Aggiungi voce
        </button>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border">
              <th class="text-left py-2 px-2 text-xs font-medium text-gray-500 uppercase">Categoria</th>
              <th class="text-left py-2 px-2 text-xs font-medium text-gray-500 uppercase">Nome</th>
              <th
                v-for="stagione in data.stagioni"
                :key="stagione.nome"
                class="text-center py-2 px-2 text-xs font-medium text-gray-500 uppercase"
              >
                <span class="inline-flex items-center gap-1">
                  <span
                    class="w-2.5 h-2.5 rounded-full inline-block"
                    :style="{ backgroundColor: stagione.colore }"
                  ></span>
                  {{ stagione.nome }}
                </span>
              </th>
              <th class="w-8"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(voce, vi) in data.voci"
              :key="vi"
              class="border-b border-border/50"
            >
              <td class="py-1.5 px-1">
                <input
                  v-model="voce.categoria"
                  type="text"
                  placeholder="Categoria"
                  class="w-full px-2 py-1.5 rounded border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                />
              </td>
              <td class="py-1.5 px-1">
                <input
                  v-model="voce.nome"
                  type="text"
                  placeholder="Nome voce"
                  class="w-full px-2 py-1.5 rounded border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                />
              </td>
              <td
                v-for="stagione in data.stagioni"
                :key="stagione.nome"
                class="py-1.5 px-1"
              >
                <input
                  v-model.number="voce.prezzi[stagione.nome]"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-full px-2 py-1.5 rounded border border-border bg-white text-sm text-center focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                />
              </td>
              <td class="py-1.5 px-1 text-center">
                <button
                  class="text-red-400 hover:text-red-600 transition-colors"
                  @click="data.voci.splice(vi, 1)"
                  title="Rimuovi voce"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </td>
            </tr>
            <tr v-if="data.voci.length === 0">
              <td :colspan="data.stagioni.length + 3" class="py-6 text-center text-gray-400 text-sm">
                Nessuna voce nel listino
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Toast -->
    <Transition name="toast">
      <div
        v-if="toast.show"
        class="fixed bottom-6 right-6 px-4 py-3 rounded-lg shadow-lg text-sm font-medium text-white z-50"
        :class="toast.type === 'error' ? 'bg-red-600' : 'bg-green-600'"
      >
        {{ toast.message }}
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getPrezzi, updatePrezzi } from '../api'

const data = reactive({ stagioni: [], voci: [] })
const saving = ref(false)
const toast = ref({ show: false, message: '', type: 'success' })
let toastTimer = null

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value.show = false }, 3000)
}

function addStagione() {
  data.stagioni.push({
    nome: '',
    colore: '#4A7C9B',
    periodi: [{ da: '', a: '' }],
  })
}

function addVoce() {
  const prezzi = {}
  for (const s of data.stagioni) {
    prezzi[s.nome] = 0
  }
  data.voci.push({ categoria: '', nome: '', prezzi })
}

async function save() {
  saving.value = true
  try {
    await updatePrezzi({ stagioni: data.stagioni, voci: data.voci })
    showToast('Listino salvato')
  } catch (e) {
    showToast(e.response?.data?.detail || 'Errore salvataggio', 'error')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const { data: loaded } = await getPrezzi()
    if (loaded.stagioni) data.stagioni = loaded.stagioni
    if (loaded.voci) data.voci = loaded.voci
  } catch {
    // Empty price list — start fresh
  }
})
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
</style>
