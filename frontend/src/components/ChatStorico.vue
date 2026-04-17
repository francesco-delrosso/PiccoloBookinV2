<template>
  <div class="flex flex-col bg-surface rounded-xl shadow-sm border border-border mt-4" style="min-height: 320px">
    <!-- Header -->
    <div class="flex items-center justify-between px-5 py-3 border-b border-border">
      <h3 class="text-sm font-semibold text-gray-700">Messaggi</h3>
      <span class="text-xs text-gray-400">{{ messaggi?.length || 0 }} messaggi</span>
    </div>

    <!-- Messages (Aruba Mail style) -->
    <div ref="chatContainer" class="flex-1 overflow-y-auto">
      <div
        v-if="!messaggi || messaggi.length === 0"
        class="flex items-center justify-center h-full text-gray-400 text-sm py-12"
      >
        Nessun messaggio
      </div>

      <template v-for="(msg, idx) in messaggi" :key="msg.id">
        <!-- Separator between messages -->
        <div v-if="idx > 0" class="border-t border-border"></div>

        <!-- Message card -->
        <div
          class="message-card px-5 py-4"
          :class="msg.mittente === 'Campeggio' ? 'bg-[#f4faf6]' : 'bg-white'"
        >
          <!-- Header row: sender + date -->
          <div class="flex items-start justify-between gap-4">
            <div class="min-w-0">
              <span class="font-semibold text-sm text-gray-800">
                {{ senderDisplay(msg) }}
              </span>
              <div class="text-xs text-gray-400 mt-0.5">
                A: {{ recipientDisplay(msg) }}
              </div>
            </div>
            <span class="text-xs text-gray-400 whitespace-nowrap flex-shrink-0 pt-0.5">
              {{ formatDateTime(msg.data_ora) }}
            </span>
          </div>

          <!-- Body -->
          <div
            class="message-body text-sm text-gray-700 leading-relaxed mt-3"
            v-html="renderText(msg.testo)"
          ></div>
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
import { ref, watch, nextTick } from 'vue'
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

const CAMPEGGIO_EMAIL = 'info@piccolocamping.com'

function senderDisplay(msg) {
  if (msg.mittente === 'Campeggio') return CAMPEGGIO_EMAIL
  // Use email from parent booking if available, otherwise fallback
  const sel = store.selected
  if (sel && sel.email) return sel.email
  return msg.mittente
}

function recipientDisplay(msg) {
  if (msg.mittente === 'Campeggio') {
    const sel = store.selected
    if (sel && sel.email) return sel.email
    return 'Cliente'
  }
  return CAMPEGGIO_EMAIL
}

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

function formatDateTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const day = d.getDate()
  const months = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']
  const month = months[d.getMonth()]
  const year = d.getFullYear()
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  return `${day} ${month} ${year} - ${hours}:${minutes}`
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
  color: var(--color-secondary, #2B6B4F);
  text-decoration: underline;
}
.message-body :deep(a:hover) {
  color: var(--color-secondary-dark, #1f5039);
}
.message-body :deep(img) {
  border-radius: 0.5rem;
  margin-top: 0.5rem;
}
</style>
