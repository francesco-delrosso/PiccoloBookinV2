<template>
  <div class="flex h-[calc(100vh-56px)]">
    <!-- Left sidebar -->
    <div class="w-[340px] shrink-0 bg-surface border-r border-border flex flex-col">
      <!-- Import toolbar (compact) -->
      <div class="px-3 py-2 border-b border-border flex items-center gap-2">
        <button class="px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-white hover:bg-primary-dark disabled:opacity-50"
          :disabled="polling" @click="handlePoll">
          {{ polling ? '...' : 'Poll' }}
        </button>
        <input v-model.number="importLimit" type="number" min="0" placeholder="0" title="0 = tutte"
          class="w-14 px-2 py-1.5 text-xs rounded-lg border border-border bg-white" />
        <button class="px-3 py-1.5 text-xs font-medium rounded-lg bg-secondary text-white hover:bg-secondary-dark"
          @click="handleImport">Import</button>
        <button class="ml-auto px-2 py-1.5 text-xs rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50"
          title="Reset e reimport" @click="handleReset">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>

      <!-- Job status -->
      <div v-if="store.jobStatus?.status === 'running'" class="px-3 py-2 border-b border-border bg-blue-50">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
          <div class="flex-1 h-1.5 bg-blue-100 rounded-full overflow-hidden">
            <div class="h-full bg-blue-500 rounded-full transition-all" :style="{ width: jobProgress + '%' }"></div>
          </div>
          <span class="text-xs text-blue-600">{{ store.jobStatus.processed || 0 }}/{{ store.jobStatus.total || '?' }}</span>
        </div>
      </div>

      <!-- Booking list -->
      <PrenotazioniList class="flex-1 min-h-0" @select="onSelect" />
    </div>

    <!-- Right panel -->
    <div class="flex-1 flex flex-col min-w-0">
      <template v-if="store.selected">
        <!-- Toolbar -->
        <div class="px-4 py-2 border-b border-border bg-surface flex items-center gap-2 shrink-0">
          <button @click="handleAction('accetta')"
            class="tb-btn bg-green-600 hover:bg-green-700 text-white">Accetta</button>
          <button @click="handleAction('accetta_noCaparra')"
            class="tb-btn bg-white text-green-700 border border-green-300 hover:bg-green-50">Senza caparra</button>
          <button @click="handleAction('rifiuta')"
            class="tb-btn bg-red-600 hover:bg-red-700 text-white">Rifiuta</button>
          <button @click="handleAction('info')"
            class="tb-btn bg-secondary hover:bg-secondary-dark text-white">Info</button>
          <button v-if="store.selected.stato === 'Attesa Bonifico'" @click="confirmBonifico"
            class="tb-btn bg-warm hover:bg-warm-dark text-white">Bonifico ricevuto</button>
          <button @click="handleAction('elimina')"
            class="tb-btn ml-auto bg-white text-gray-400 border border-gray-200 hover:text-red-600 hover:border-red-200">Elimina</button>
        </div>

        <!-- Compact data bar -->
        <DettaglioPrenotazione :prenotazione="store.selected" @saved="onSaved" />

        <!-- Messages -->
        <ChatStorico
          class="flex-1 min-h-0"
          :messaggi="store.selected.messaggi || []"
          :prenId="store.selected.id"
        />
      </template>
      <div v-else class="flex flex-col items-center justify-center h-full text-gray-400">
        <span class="text-4xl mb-3">&#9993;</span>
        <p class="text-sm">Seleziona una prenotazione</p>
      </div>
    </div>

    <!-- Modal -->
    <ModalEmail
      v-if="modal"
      :tipo="modal"
      :prenId="store.selected?.id"
      :prenotazione="store.selected"
      :defaultLingua="store.selected?.lingua_suggerita || 'IT'"
      @close="modal = null"
      @sent="onModalSent"
    />

    <!-- Toast -->
    <Transition name="toast">
      <div v-if="toast.show"
        class="fixed bottom-6 right-6 px-4 py-3 rounded-lg shadow-lg text-sm font-medium text-white z-50"
        :class="toast.type === 'error' ? 'bg-red-600' : 'bg-green-600'">
        {{ toast.message }}
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { usePrenotazioniStore } from '../stores/prenotazioni'
import { pollMail, importFull as importFullApi, resetReimport, deletePrenotazione, updatePrenotazione } from '../api'
import PrenotazioniList from '../components/PrenotazioniList.vue'
import DettaglioPrenotazione from '../components/DettaglioPrenotazione.vue'
import ChatStorico from '../components/ChatStorico.vue'
import ModalEmail from '../components/ModalEmail.vue'

const store = usePrenotazioniStore()

const polling = ref(false)
const importLimit = ref(0)
const modal = ref(null)
const toast = ref({ show: false, message: '', type: 'success' })

let toastTimer = null
let refreshInterval = null

const jobProgress = computed(() => {
  const js = store.jobStatus
  if (!js || !js.total) return 0
  return Math.round((js.processed / js.total) * 100)
})

// Tab title notification
const daGestireCount = computed(() =>
  store.list.filter(p => ['Nuova', 'Nuova Risposta', 'In lavorazione', 'Attesa Bonifico'].includes(p.stato)).length
)
watch(daGestireCount, (n) => {
  document.title = n > 0 ? `(${n}) Piccolo Camping` : 'Piccolo Camping'
}, { immediate: true })

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value.show = false }, 3000)
}

async function onSelect(id) {
  await store.selectPrenotazione(id)
}

async function onSaved() {
  if (store.selected) await store.selectPrenotazione(store.selected.id)
  await store.fetchAll()
}

async function handlePoll() {
  polling.value = true
  try {
    await pollMail(20)
    await store.fetchAll()
    showToast('Poll completato')
  } catch (e) {
    showToast(e.response?.data?.detail || 'Errore poll', 'error')
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
    showToast(e.response?.data?.detail || 'Errore import', 'error')
  }
}

async function handleReset() {
  if (!confirm('Eliminare tutto e reimportare?')) return
  try {
    await resetReimport(100)
    store.startJobPolling()
    store.selected = null
    showToast('Reset avviato')
  } catch (e) {
    showToast(e.response?.data?.detail || 'Errore reset', 'error')
  }
}

async function confirmBonifico() {
  if (!store.selected) return
  try {
    await updatePrenotazione(store.selected.id, { stato: 'Confermata' })
    await store.selectPrenotazione(store.selected.id)
    await store.fetchAll()
    showToast('Bonifico confermato')
  } catch (e) {
    showToast('Errore', 'error')
  }
}

async function handleAction(action) {
  if (action === 'elimina') {
    if (!confirm('Eliminare questa prenotazione?')) return
    try {
      await deletePrenotazione(store.selected.id)
      store.selected = null
      await store.fetchAll()
      showToast('Eliminata')
    } catch (e) {
      showToast('Errore eliminazione', 'error')
    }
    return
  }
  modal.value = action
}

async function onModalSent() {
  modal.value = null
  if (store.selected) await store.selectPrenotazione(store.selected.id)
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
  document.title = 'Piccolo Camping'
})
</script>

<style scoped>
.tb-btn {
  padding: 0.35rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 0.4rem;
  transition: all 0.15s;
  white-space: nowrap;
}
.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(10px); }
</style>
