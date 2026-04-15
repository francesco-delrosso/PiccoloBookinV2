<template>
  <div class="flex flex-col h-full bg-surface rounded-xl shadow-sm border border-border">
    <!-- Header -->
    <div class="flex items-center justify-between px-5 py-3 border-b border-border">
      <h3 class="text-sm font-semibold text-gray-700">Messaggi</h3>
      <div class="flex items-center gap-2">
        <button
          v-if="hasTranslations"
          @click="showTranslated = !showTranslated"
          class="px-3 py-1 text-xs font-medium rounded-lg border border-border hover:bg-gray-50 transition-colors"
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
    <div ref="chatContainer" class="flex-1 overflow-y-auto p-4 space-y-3">
      <div
        v-if="!messaggi || messaggi.length === 0"
        class="flex items-center justify-center h-full text-gray-400 text-sm"
      >
        Nessun messaggio
      </div>
      <div
        v-for="msg in messaggi"
        :key="msg.id"
        class="flex"
        :class="msg.mittente === 'Campeggio' ? 'justify-end' : 'justify-start'"
      >
        <div
          class="max-w-[75%] px-4 py-3 rounded-xl text-sm"
          :class="msg.mittente === 'Campeggio'
            ? 'bg-primary/10 rounded-tr-none'
            : 'bg-gray-100 rounded-tl-none'"
        >
          <div class="text-xs font-semibold mb-1" :class="msg.mittente === 'Campeggio' ? 'text-primary-dark' : 'text-gray-600'">
            {{ msg.mittente }}
          </div>
          <div class="whitespace-pre-wrap text-gray-800">
            {{ showTranslated && msg.testo_tradotto ? msg.testo_tradotto : msg.testo }}
          </div>
          <div class="text-xs text-gray-400 mt-2 text-right">
            {{ formatTimestamp(msg.data_invio) }}
          </div>
        </div>
      </div>
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

function formatTimestamp(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('it-IT', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
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
