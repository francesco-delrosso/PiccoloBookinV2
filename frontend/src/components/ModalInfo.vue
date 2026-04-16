<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      @click.self="$emit('close')"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-border rounded-t-xl bg-secondary/10">
          <h3 class="text-lg font-semibold text-secondary-dark">Richiedi informazioni</h3>
        </div>

        <div class="p-6 space-y-4">
          <!-- Lingua -->
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Lingua</label>
            <select
              v-model="lingua"
              class="w-full px-2.5 py-1.5 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            >
              <option v-for="l in lingue" :key="l" :value="l">{{ l }}</option>
            </select>
          </div>

          <!-- Testo aggiuntivo -->
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Testo aggiuntivo</label>
            <textarea
              v-model="testoAggiuntivo"
              rows="4"
              class="w-full px-2.5 py-1.5 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-none"
              placeholder="Scrivi le informazioni da richiedere..."
            ></textarea>
          </div>

          <!-- Preview -->
          <div v-if="preview" class="bg-gray-50 rounded-lg p-4 max-h-48 overflow-y-auto">
            <label class="block text-xs font-medium text-gray-500 mb-2">Anteprima</label>
            <div class="text-sm text-gray-700 whitespace-pre-wrap">{{ preview }}</div>
          </div>
          <div v-else-if="loadingPreview" class="text-sm text-gray-400">Caricamento anteprima...</div>
        </div>

        <!-- Footer -->
        <div class="px-6 py-4 border-t border-border flex justify-end gap-3">
          <button
            @click="$emit('close')"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
          >
            Annulla
          </button>
          <button
            @click="send"
            :disabled="sending || !selectedModello"
            class="px-4 py-2 text-sm font-medium text-white bg-secondary rounded-lg hover:bg-secondary-dark transition-colors disabled:opacity-50"
          >
            {{ sending ? 'Invio...' : 'Invia' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getModelli, previewModello, inviaMail } from '../api'
import { usePrenotazioniStore } from '../stores/prenotazioni'

const props = defineProps({
  show: { type: Boolean, default: true },
  prenId: { type: Number, default: null },
  defaultLingua: { type: String, default: 'IT' },
})

const emit = defineEmits(['close', 'sent'])
const store = usePrenotazioniStore()

const lingue = ['IT', 'EN', 'DE', 'FR', 'NL', 'ES']
const lingua = ref(props.defaultLingua)
const testoAggiuntivo = ref('')
const modelli = ref([])
const preview = ref('')
const loadingPreview = ref(false)
const sending = ref(false)

const selectedModello = computed(() =>
  modelli.value.find((m) => m.lingua === lingua.value && m.tipo === 'info')
)

async function loadModelli() {
  lingua.value = props.defaultLingua
  testoAggiuntivo.value = ''
  preview.value = ''
  try {
    const { data } = await getModelli()
    modelli.value = data
  } catch { /* ignore */ }
}

onMounted(loadModelli)

watch(() => props.show, (val) => {
  if (val) loadModelli()
})

watch(() => selectedModello.value?.id, async (id) => {
  if (!id) { preview.value = ''; return }
  loadingPreview.value = true
  try {
    const { data } = await previewModello(id)
    preview.value = data.preview || data.corpo || ''
  } catch {
    preview.value = ''
  } finally {
    loadingPreview.value = false
  }
})

async function send() {
  if (!selectedModello.value || !props.prenId) return
  sending.value = true
  try {
    await inviaMail(props.prenId, {
      modello_id: selectedModello.value.id,
      testo_aggiuntivo: testoAggiuntivo.value,
    })
    await store.selectPrenotazione(props.prenId)
    await store.fetchAll()
    emit('sent')
    emit('close')
  } finally {
    sending.value = false
  }
}
</script>
