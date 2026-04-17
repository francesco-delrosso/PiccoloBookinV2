<template>
  <div class="flex flex-col bg-surface rounded-xl shadow-sm border border-border mt-4" style="min-height: 320px">
    <!-- Header -->
    <div class="flex items-center justify-between px-5 py-3 border-b border-border">
      <h3 class="text-sm font-semibold text-gray-700">Messaggi</h3>
    </div>

    <!-- Messages -->
    <div ref="chatContainer" class="flex-1 overflow-y-auto px-4 py-4">
      <div
        v-if="!messaggi || messaggi.length === 0"
        class="flex items-center justify-center h-full text-gray-400 text-sm"
      >
        Nessun messaggio
      </div>

      <template v-for="(msg, idx) in messaggi" :key="msg.id">
        <!-- Date separator -->
        <div
          v-if="idx === 0 || !sameDay(messaggi[idx - 1].data_ora, msg.data_ora)"
          class="flex items-center gap-3 my-4"
        >
          <div class="flex-1 h-px bg-border"></div>
          <span class="text-xs text-gray-400 font-medium">{{ formatDate(msg.data_ora) }}</span>
          <div class="flex-1 h-px bg-border"></div>
        </div>

        <!-- Message bubble -->
        <div
          class="flex mb-3"
          :class="msg.mittente === 'Campeggio' ? 'justify-end' : 'justify-start'"
        >
          <div
            class="max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm"
            :class="msg.mittente === 'Campeggio'
              ? 'bg-primary/10 rounded-tr-sm'
              : 'bg-gray-100 rounded-tl-sm'"
          >
            <div
              class="text-xs font-semibold mb-1.5"
              :class="msg.mittente === 'Campeggio' ? 'text-primary-dark' : 'text-gray-500'"
            >
              {{ msg.mittente }}
            </div>
            <div
              class="message-body text-gray-800"
              v-html="renderText(msg.testo)"
            ></div>
            <div class="text-[11px] text-gray-400 mt-2 text-right">
              {{ formatTime(msg.data_ora) }}
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Compose -->
    <div class="px-4 py-3 border-t border-border">
      <div class="flex gap-2">
        <textarea
          v-model="newMessage"
          rows="2"
          placeholder="Scrivi un messaggio..."
          class="flex-1 px-3 py-2 text-sm rounded-lg border border-border bg-white resize-none focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
          @keydown.ctrl.enter="sendMessage"
        ></textarea>
        <button
          @click="sendMessage"
          :disabled="!newMessage.trim() || sending"
          class="self-end px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-40"
        >
          {{ sending ? '...' : 'Invia' }}
        </button>
      </div>
      <div class="text-[11px] text-gray-400 mt-1">Ctrl+Invio per inviare</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { inviaMessaggio } from '../api'
import { usePrenotazioniStore } from '../stores/prenotazioni'

const store = usePrenotazioniStore()

const props = defineProps({
  messaggi: { type: Array, default: () => [] },
  prenId: { type: Number, default: null },
})

const newMessage = ref('')
const sending = ref(false)

const chatContainer = ref(null)

async function sendMessage() {
  if (!newMessage.value.trim() || !props.prenId) return
  sending.value = true
  try {
    await inviaMessaggio(props.prenId, { testo: newMessage.value.trim() })
    newMessage.value = ''
    await store.selectPrenotazione(props.prenId)
    await store.fetchAll()
  } catch (e) {
    alert('Errore invio: ' + (e.response?.data?.detail || e.message))
  } finally {
    sending.value = false
  }
}

// URL regex for linkification
const URL_RE = /https?:\/\/[^\s<>"')\]]+/g
const EMAIL_RE = /\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b/g
const IMAGE_EXT_RE = /\.(jpg|jpeg|png|gif|webp|bmp)(\?[^\s]*)?$/i

function escapeHtml(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderText(text) {
  if (!text) return ''

  // Escape HTML first
  let html = escapeHtml(text)

  // Linkify URLs (check for images first)
  html = html.replace(URL_RE, (url) => {
    if (IMAGE_EXT_RE.test(url)) {
      return `<a href="${url}" target="_blank" rel="noopener" class="text-secondary underline">${url}</a><br><img src="${url}" class="mt-1 max-w-full max-h-48 rounded-lg" loading="lazy" onerror="this.style.display='none'" />`
    }
    return `<a href="${url}" target="_blank" rel="noopener" class="text-secondary underline hover:text-secondary-dark">${url}</a>`
  })

  // Linkify email addresses (that weren't already inside href)
  html = html.replace(/(?<!href=")(?<!">)\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b/g, (match) => {
    return `<a href="mailto:${match}" class="text-secondary underline hover:text-secondary-dark">${match}</a>`
  })

  // Preserve newlines
  html = html.replace(/\n/g, '<br>')

  return html
}

function sameDay(d1, d2) {
  if (!d1 || !d2) return false
  const a = new Date(d1)
  const b = new Date(d2)
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('it-IT', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  })
}

function formatTime(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleTimeString('it-IT', {
    hour: '2-digit', minute: '2-digit',
  })
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

watch(
  () => props.messaggi?.length,
  () => scrollToBottom(),
  { immediate: true }
)
</script>

<style scoped>
.message-body :deep(a) {
  color: var(--color-secondary);
  text-decoration: underline;
}
.message-body :deep(a:hover) {
  color: var(--color-secondary-dark);
}
.message-body :deep(img) {
  border-radius: 0.5rem;
  margin-top: 0.5rem;
}
</style>
