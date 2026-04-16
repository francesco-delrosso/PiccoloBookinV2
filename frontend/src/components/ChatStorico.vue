<template>
  <div class="flex flex-col bg-surface rounded-xl shadow-sm border border-border mt-4" style="min-height: 320px">
    <!-- Header -->
    <div class="flex items-center justify-between px-5 py-3 border-b border-border">
      <h3 class="text-sm font-semibold text-gray-700">Messaggi</h3>
      <div class="flex items-center gap-2">
        <button
          v-if="hasTranslations"
          @click="showTranslated = !showTranslated"
          class="px-3 py-1 text-xs font-medium rounded-lg border transition-colors"
          :class="showTranslated ? 'bg-secondary/10 text-secondary-dark border-secondary/30' : 'border-border hover:bg-gray-50'"
        >
          {{ showTranslated ? 'Originale' : 'Tradotto' }}
        </button>
        <button
          @click="$emit('traduci')"
          :disabled="translating"
          class="px-3 py-1 text-xs font-medium text-white bg-secondary rounded-lg hover:bg-secondary-dark transition-colors disabled:opacity-50"
        >
          {{ translating ? 'Traduzione...' : 'Traduci' }}
        </button>
      </div>
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
              v-html="renderText(showTranslated && msg.testo_tradotto ? msg.testo_tradotto : msg.testo)"
            ></div>
            <div class="text-[11px] text-gray-400 mt-2 text-right">
              {{ formatTime(msg.data_ora) }}
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  messaggi: { type: Array, default: () => [] },
  translating: { type: Boolean, default: false },
})

defineEmits(['traduci'])

const chatContainer = ref(null)
const showTranslated = ref(false)

const hasTranslations = computed(() =>
  props.messaggi?.some((m) => m.testo_tradotto)
)

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
