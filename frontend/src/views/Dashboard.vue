<template>
  <div class="flex flex-col md:flex-row h-screen">
    <!-- Icon sidebar (left on desktop, bottom on mobile) -->
    <div class="order-last md:order-first w-full md:w-[52px] shrink-0 bg-primary-dark flex md:flex-col items-center justify-around md:justify-start md:py-4 md:gap-1 py-1">
      <div class="hidden md:flex w-8 h-8 rounded-lg bg-white/20 items-center justify-center text-white font-bold text-xs md:mb-4">PC</div>
      <button v-for="nav in navItems" :key="nav.id"
        @click="activePanel = nav.id; mobileShowDetail = false"
        class="nav-icon" :class="activePanel === nav.id ? 'bg-white/20 text-white' : 'text-white/50 hover:text-white hover:bg-white/10'"
        :title="nav.label">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" :d="nav.icon" />
        </svg>
      </button>
    </div>

    <!-- List sidebar (desktop: always visible; mobile: hidden when detail shown) -->
    <div v-if="activePanel === 'mail'" class="w-full md:w-[300px] shrink-0 bg-surface border-r border-border flex flex-col"
      :class="mobileShowDetail ? 'hidden md:flex' : 'flex'"
    >
      <!-- Import toolbar -->
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

    <!-- Right panel (mobile: hidden when list shown, desktop: always) -->
    <div class="flex-1 flex flex-col min-w-0"
      :class="activePanel === 'mail' && !mobileShowDetail ? 'hidden md:flex' : 'flex'">

      <!-- MAIL panel -->
      <template v-if="activePanel === 'mail'">
        <template v-if="store.selected">
          <!-- Toolbar -->
          <div class="md:hidden px-3 py-2 border-b border-border bg-surface">
            <button @click="mobileShowDetail = false" class="text-sm text-secondary font-medium">&larr; Lista</button>
          </div>
          <div class="px-4 py-2 border-b border-border bg-surface flex items-center gap-2 shrink-0">
            <button @click="handleAction('accetta')"
              class="tb-btn bg-green-600 hover:bg-green-700 text-white">Accetta</button>
            <button @click="handleAction('accetta_noCaparra')"
              class="tb-btn bg-white text-green-700 border border-green-300 hover:bg-green-50">Senza caparra</button>
            <button @click="handleAction('rifiuta')"
              class="tb-btn bg-red-600 hover:bg-red-700 text-white">Rifiuta</button>
            <button v-if="store.selected.stato === 'Attesa Bonifico'" @click="confirmBonifico"
              class="tb-btn bg-warm hover:bg-warm-dark text-white">Bonifico ricevuto</button>
            <button @click="handleAction('elimina')"
              class="tb-btn ml-auto bg-red-100 text-red-700 hover:bg-red-600 hover:text-white">Elimina</button>
          </div>
          <DettaglioPrenotazione :prenotazione="store.selected" @saved="onSaved" />
          <ChatStorico class="flex-1 min-h-0" :messaggi="store.selected.messaggi || []" :prenId="store.selected.id" />
        </template>
        <div v-else class="flex flex-col items-center justify-center h-full text-gray-400">
          <span class="text-4xl mb-3">&#9993;</span>
          <p class="text-sm">Seleziona una prenotazione</p>
        </div>
      </template>

      <!-- CALENDARIO panel -->
      <div v-else-if="activePanel === 'calendario'" class="flex-1 overflow-y-auto">
        <Calendario />
      </div>

      <!-- PREZZI panel -->
      <div v-else-if="activePanel === 'prezzi'" class="flex-1 overflow-y-auto">
        <Prezzi />
      </div>

      <!-- IMPOSTAZIONI panel -->
      <div v-else-if="activePanel === 'impostazioni'" class="flex-1 overflow-y-auto">
        <Impostazioni />
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
import Calendario from '../views/Calendario.vue'
import Prezzi from '../views/Prezzi.vue'
import Impostazioni from '../views/Impostazioni.vue'

const store = usePrenotazioniStore()

const activePanel = ref('mail')
const mobileShowDetail = ref(false)

const navItems = [
  { id: 'mail', label: 'Mail', icon: 'M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75' },
  { id: 'calendario', label: 'Calendario', icon: 'M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5' },
  { id: 'prezzi', label: 'Listino', icon: 'M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z' },
  { id: 'impostazioni', label: 'Impostazioni', icon: 'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
]

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
  activePanel.value = 'mail'
  await store.selectPrenotazione(id)
  mobileShowDetail.value = true
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
.nav-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  transition: all 0.15s;
}
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
