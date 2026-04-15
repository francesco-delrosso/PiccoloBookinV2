<template>
  <div class="flex h-[calc(100vh-56px)]">
    <!-- Left sidebar -->
    <div class="w-[300px] shrink-0 bg-surface border-r border-border flex flex-col">
      <!-- Toolbar -->
      <div class="p-3 border-b border-border space-y-2">
        <div class="flex gap-2">
          <button
            class="flex-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-white hover:bg-primary-dark transition-colors disabled:opacity-50"
            :disabled="polling"
            @click="handlePoll"
          >
            {{ polling ? 'Controllo...' : 'Poll mail' }}
          </button>
          <button
            class="px-2 py-1.5 text-xs font-medium rounded-lg bg-red-50 text-red-600 hover:bg-red-100 transition-colors"
            title="Reset e reimport"
            @click="handleReset"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
        <div class="flex gap-2">
          <input
            v-model.number="importLimit"
            type="number"
            min="0"
            class="w-16 px-2 py-1.5 text-xs rounded-lg border border-border bg-white focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            title="0 = tutte"
            placeholder="0"
          />
          <button
            class="flex-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-secondary text-white hover:bg-secondary-dark transition-colors"
            @click="handleImport"
          >
            Import
          </button>
        </div>
      </div>

      <!-- Job status bar -->
      <div
        v-if="store.jobStatus?.status === 'running'"
        class="px-3 py-2 border-b border-border bg-blue-50"
      >
        <div class="flex items-center gap-2 mb-1">
          <span class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
          <span class="text-xs text-blue-700 font-medium truncate">{{ store.jobStatus.message || 'In corso...' }}</span>
        </div>
        <div class="flex items-center gap-2">
          <div class="flex-1 h-1.5 bg-blue-100 rounded-full overflow-hidden">
            <div
              class="h-full bg-blue-500 rounded-full transition-all duration-500"
              :style="{ width: jobProgress + '%' }"
            ></div>
          </div>
          <span class="text-xs text-blue-600 shrink-0">
            {{ store.jobStatus.processed || 0 }}/{{ store.jobStatus.total || '?' }}
          </span>
        </div>
      </div>

      <!-- Booking list -->
      <PrenotazioniList class="flex-1 min-h-0" @select="onSelect" />
    </div>

    <!-- Right panel -->
    <div class="flex-1 overflow-y-auto">
      <template v-if="store.selected">
        <DettaglioPrenotazione
          :prenotazione="store.selected"
          @action="handleAction"
          @traduci="traduci"
        />
        <ChatStorico
          :messaggi="store.selected.messaggi || []"
          :prenId="store.selected.id"
        />
      </template>
      <div v-else class="flex flex-col items-center justify-center h-full text-gray-400">
        <span class="text-5xl mb-4">&#9978;</span>
        <p class="text-lg font-medium">Seleziona una prenotazione</p>
      </div>
    </div>

    <!-- Modals -->
    <ModalAccetta
      v-if="modal === 'accetta'"
      :prenId="store.selected?.id"
      :defaultLingua="store.selected?.lingua || 'IT'"
      @close="modal = null"
      @sent="onModalSent"
    />
    <ModalRifiuta
      v-if="modal === 'rifiuta'"
      :prenId="store.selected?.id"
      :defaultLingua="store.selected?.lingua || 'IT'"
      @close="modal = null"
      @sent="onModalSent"
    />
    <ModalInfo
      v-if="modal === 'info'"
      :prenId="store.selected?.id"
      :defaultLingua="store.selected?.lingua || 'IT'"
      @close="modal = null"
      @sent="onModalSent"
    />

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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { usePrenotazioniStore } from '../stores/prenotazioni'
import { pollMail, importFull as importFullApi, resetReimport, deletePrenotazione, traduciThread } from '../api'
import PrenotazioniList from '../components/PrenotazioniList.vue'
import DettaglioPrenotazione from '../components/DettaglioPrenotazione.vue'
import ChatStorico from '../components/ChatStorico.vue'
import ModalAccetta from '../components/ModalAccetta.vue'
import ModalRifiuta from '../components/ModalRifiuta.vue'
import ModalInfo from '../components/ModalInfo.vue'

const store = usePrenotazioniStore()

const polling = ref(false)
const importLimit = ref(0)
const modal = ref(null)
const toast = ref({ show: false, message: '', type: 'success' })

let toastTimer = null
let refreshInterval = null

const jobProgress = computed(() => {
  const js = store.jobStatus
  if (!js || !js.total || js.total === 0) return 0
  return Math.round((js.processed / js.total) * 100)
})

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value.show = false }, 3000)
}

async function onSelect(id) {
  await store.selectPrenotazione(id)
}

async function handlePoll() {
  polling.value = true
  try {
    await pollMail(20)
    await store.fetchAll()
    showToast('Poll completato')
  } catch (e) {
    showToast(e.response?.data?.detail || 'Errore durante il poll', 'error')
  } finally {
    polling.value = false
  }
}

async function handleImport() {
  try {
    await importFullApi(importLimit.value, 100)
    store.startJobPolling()
    showToast('Import avviato')
  } catch (e) {
    showToast(e.response?.data?.detail || 'Errore durante l\'import', 'error')
  }
}

async function handleReset() {
  if (!confirm('Sei sicuro? Tutti i dati verranno cancellati e reimportati.')) return
  try {
    await resetReimport(100)
    store.startJobPolling()
    store.selected = null
    showToast('Reset e reimport avviato')
  } catch (e) {
    showToast(e.response?.data?.detail || 'Errore durante il reset', 'error')
  }
}

async function handleAction(action) {
  if (action === 'elimina') {
    if (!confirm('Eliminare questa prenotazione?')) return
    try {
      await deletePrenotazione(store.selected.id)
      store.selected = null
      await store.fetchAll()
      showToast('Prenotazione eliminata')
    } catch (e) {
      showToast(e.response?.data?.detail || 'Errore durante l\'eliminazione', 'error')
    }
    return
  }
  modal.value = action
}

async function traduci() {
  if (!store.selected) return
  try {
    await traduciThread(store.selected.id)
    await store.selectPrenotazione(store.selected.id)
    showToast('Traduzione completata')
  } catch (e) {
    showToast(e.response?.data?.detail || 'Errore durante la traduzione', 'error')
  }
}

async function onModalSent() {
  modal.value = null
  if (store.selected) {
    await store.selectPrenotazione(store.selected.id)
  }
  await store.fetchAll()
  showToast('Email inviata')
}

onMounted(async () => {
  await store.fetchAll()
  refreshInterval = setInterval(() => store.fetchAll(), 60000)
})

onUnmounted(() => {
  clearInterval(refreshInterval)
  clearTimeout(toastTimer)
  store.stopJobPolling()
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
