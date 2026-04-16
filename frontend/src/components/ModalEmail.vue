<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="$emit('close')">
      <div class="bg-white rounded-xl shadow-xl w-full mx-6 flex flex-col" style="max-width: 720px; max-height: 85vh">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-border rounded-t-xl" :class="headerBg">
          <h3 class="text-lg font-semibold" :class="headerText">{{ title }}</h3>
          <p class="text-sm mt-0.5 opacity-70" :class="headerText">{{ prenotazioneSummary }}</p>
        </div>

        <!-- Body -->
        <div class="flex-1 overflow-y-auto p-6 space-y-4">
          <!-- Lingua -->
          <div class="flex items-center gap-3">
            <label class="text-sm font-medium text-gray-600">Lingua:</label>
            <div class="flex gap-1">
              <button
                v-for="l in lingue" :key="l"
                @click="switchLingua(l)"
                class="px-3 py-1 text-xs font-medium rounded-lg transition-colors"
                :class="lingua === l ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
              >{{ l }}</button>
            </div>
          </div>

          <!-- Oggetto -->
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Oggetto</label>
            <input
              v-model="editSubject"
              class="w-full px-3 py-2 rounded-lg border border-border text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            />
          </div>

          <!-- Email body (editable) -->
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Corpo email (modificabile)</label>
            <textarea
              v-model="editBody"
              class="w-full px-4 py-3 rounded-lg border border-border bg-white focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-y"
              style="min-height: 300px; font-size: 14px; line-height: 1.7; font-family: 'Georgia', 'Times New Roman', serif;"
            ></textarea>
          </div>
        </div>

        <!-- Footer -->
        <div class="px-6 py-4 border-t border-border flex items-center justify-between">
          <span class="text-xs text-gray-400">La mail verra inviata a {{ clientEmail }}</span>
          <div class="flex gap-3">
            <button
              @click="$emit('close')"
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
            >Annulla</button>
            <button
              @click="send"
              :disabled="sending || !editBody.trim()"
              class="px-5 py-2 text-sm font-medium text-white rounded-lg transition-colors disabled:opacity-50"
              :class="sendBtnClass"
            >{{ sending ? 'Invio...' : sendLabel }}</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getModelli, getImpostazioni, inviaMessaggio } from '../api'
import { usePrenotazioniStore } from '../stores/prenotazioni'

const props = defineProps({
  tipo: { type: String, required: true }, // 'accetta' | 'rifiuta' | 'info'
  prenId: { type: Number, required: true },
  prenotazione: { type: Object, required: true },
  defaultLingua: { type: String, default: 'IT' },
})

const emit = defineEmits(['close', 'sent'])
const store = usePrenotazioniStore()

const lingue = ['IT', 'EN', 'DE', 'FR', 'NL', 'ES']
const lingua = ref(props.defaultLingua || 'IT')
const modelli = ref([])
const caparraPerc = ref(30)
const editSubject = ref('')
const editBody = ref('')
const sending = ref(false)

const config = computed(() => {
  const map = {
    accetta: { title: 'Accetta prenotazione', headerBg: 'bg-green-50', headerText: 'text-green-800', sendBtn: 'bg-green-600 hover:bg-green-700', sendLabel: 'Invia accettazione' },
    rifiuta: { title: 'Rifiuta prenotazione', headerBg: 'bg-red-50', headerText: 'text-red-800', sendBtn: 'bg-red-600 hover:bg-red-700', sendLabel: 'Invia rifiuto' },
    info: { title: 'Invia informazioni', headerBg: 'bg-blue-50', headerText: 'text-blue-800', sendBtn: 'bg-secondary hover:bg-secondary-dark', sendLabel: 'Invia' },
  }
  return map[props.tipo] || map.info
})

const title = computed(() => config.value.title)
const headerBg = computed(() => config.value.headerBg)
const headerText = computed(() => config.value.headerText)
const sendBtnClass = computed(() => config.value.sendBtn)
const sendLabel = computed(() => config.value.sendLabel)

const clientEmail = computed(() => props.prenotazione?.email || '')
const prenotazioneSummary = computed(() => {
  const p = props.prenotazione
  if (!p) return ''
  const parts = []
  if (p.nome || p.cognome) parts.push([p.nome, p.cognome].filter(Boolean).join(' '))
  if (p.data_arrivo) parts.push(`${p.data_arrivo} → ${p.data_partenza || '?'}`)
  return parts.join(' — ')
})

function applyTemplate(template) {
  if (!template) return
  const p = props.prenotazione || {}
  const costo = p.costo_totale || 0
  const caparra = costo ? (costo * caparraPerc.value / 100).toFixed(2) : ''

  const vars = {
    nome: p.nome || '',
    cognome: p.cognome || '',
    data_arrivo: p.data_arrivo || '',
    data_partenza: p.data_partenza || '',
    adulti: p.adulti != null ? String(p.adulti) : '',
    bambini: p.bambini != null ? String(p.bambini) : '',
    posto_per: p.posto_per || '',
    costo_totale: costo ? String(costo) : '',
    caparra: caparra,
    caparra_percentuale: String(caparraPerc.value),
    testo_aggiuntivo: '',
  }

  let subject = template.soggetto || ''
  let body = template.corpo || ''
  for (const [k, v] of Object.entries(vars)) {
    subject = subject.replaceAll(`{${k}}`, v)
    body = body.replaceAll(`{${k}}`, v)
  }

  editSubject.value = subject
  editBody.value = body
}

function switchLingua(l) {
  lingua.value = l
  const tpl = modelli.value.find(m => m.lingua === l && m.tipo === props.tipo)
  applyTemplate(tpl)
}

onMounted(async () => {
  try {
    const [modRes, settRes] = await Promise.all([getModelli(), getImpostazioni()])
    modelli.value = modRes.data
    const capRow = settRes.data.find(s => s.chiave === 'caparra_percentuale')
    if (capRow) caparraPerc.value = parseInt(capRow.valore) || 30
  } catch { /* ignore */ }

  // Apply initial template
  const tpl = modelli.value.find(m => m.lingua === lingua.value && m.tipo === props.tipo)
  applyTemplate(tpl)
})

async function send() {
  if (!editBody.value.trim()) return
  sending.value = true
  try {
    await inviaMessaggio(props.prenId, {
      testo: editBody.value,
      soggetto: editSubject.value,
      tipo_azione: props.tipo,
    })
    await store.selectPrenotazione(props.prenId)
    await store.fetchAll()
    emit('sent')
    emit('close')
  } catch (e) {
    alert('Errore invio: ' + (e.response?.data?.detail || e.message))
  } finally {
    sending.value = false
  }
}
</script>
