<template>
  <div class="max-w-4xl mx-auto p-6 space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-gray-800">Impostazioni</h1>
      <button
        class="px-6 py-2.5 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary-dark transition-colors disabled:opacity-50"
        :disabled="saving"
        @click="saveSettings"
      >
        {{ saving ? 'Salvataggio...' : 'Salva impostazioni' }}
      </button>
    </div>

    <div v-if="toast.show" class="px-4 py-3 rounded-lg text-sm font-medium"
      :class="toast.type === 'error' ? 'bg-red-100 text-red-800 border border-red-200' : 'bg-green-100 text-green-800 border border-green-200'">
      {{ toast.message }}
    </div>

    <!-- IMAP -->
    <div class="bg-surface rounded-xl shadow-sm border border-border p-5">
      <h2 class="text-sm font-bold text-primary-dark mb-4 pb-2 border-b border-border">IMAP (ricezione mail)</h2>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Server IMAP</label>
          <input v-model="cfg.imap_server" placeholder="imap.gmail.com"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Porta</label>
          <input v-model="cfg.imap_port" placeholder="993"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Utente (email)</label>
          <input v-model="cfg.imap_user" placeholder="info@piccolocamping.com"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Password</label>
          <div class="flex gap-1">
            <input :type="showPwd.imap ? 'text' : 'password'" v-model="cfg.imap_password"
              class="flex-1 px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
            <button @click="showPwd.imap = !showPwd.imap"
              class="px-3 py-2 rounded-lg bg-gray-100 text-sm hover:bg-gray-200 transition-colors">
              {{ showPwd.imap ? '🙈' : '👁' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- SMTP -->
    <div class="bg-surface rounded-xl shadow-sm border border-border p-5">
      <h2 class="text-sm font-bold text-primary-dark mb-4 pb-2 border-b border-border">SMTP (invio mail)</h2>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Server SMTP</label>
          <input v-model="cfg.smtp_server" placeholder="smtp.gmail.com"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Porta</label>
          <input v-model="cfg.smtp_port" placeholder="587"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Utente SMTP</label>
          <input v-model="cfg.smtp_user" placeholder="info@piccolocamping.com"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Password SMTP</label>
          <div class="flex gap-1">
            <input :type="showPwd.smtp ? 'text' : 'password'" v-model="cfg.smtp_password"
              class="flex-1 px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
            <button @click="showPwd.smtp = !showPwd.smtp"
              class="px-3 py-2 rounded-lg bg-gray-100 text-sm hover:bg-gray-200 transition-colors">
              {{ showPwd.smtp ? '🙈' : '👁' }}
            </button>
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Email mittente (From)</label>
          <input v-model="cfg.email_mittente" placeholder="info@piccolocamping.com"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Email form sito</label>
          <input v-model="cfg.email_form_sito" placeholder="contatti@piccolocamping.com"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
      </div>
      <div class="mt-4 flex items-center gap-4">
        <button @click="testConnection" :disabled="testing"
          class="px-4 py-2 text-sm font-medium rounded-lg bg-secondary text-white hover:bg-secondary-dark transition-colors disabled:opacity-50">
          {{ testing ? 'Test in corso...' : 'Testa connessione IMAP + SMTP' }}
        </button>
        <div v-if="testResult" class="text-sm space-x-3">
          <span :class="testResult.imap?.ok ? 'text-green-600' : 'text-red-600'">
            IMAP: {{ testResult.imap?.ok ? 'OK' : testResult.imap?.error || 'Errore' }}
          </span>
          <span :class="testResult.smtp?.ok ? 'text-green-600' : 'text-red-600'">
            SMTP: {{ testResult.smtp?.ok ? 'OK' : testResult.smtp?.error || 'Errore' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Generale -->
    <div class="bg-surface rounded-xl shadow-sm border border-border p-5">
      <h2 class="text-sm font-bold text-primary-dark mb-4 pb-2 border-b border-border">Generale</h2>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Caparra %</label>
          <input type="number" v-model="cfg.caparra_percentuale" min="0" max="100"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Intervallo polling (minuti)</label>
          <input type="number" v-model="cfg.poll_interval_minutes" min="1"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
        <div class="col-span-2">
          <label class="block text-xs font-medium text-gray-500 mb-1">Domini da scartare (separati da virgola)</label>
          <input v-model="cfg.filtro_domini_scarta" placeholder="aruba.it,mailchimp.com"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
        <div class="col-span-2">
          <label class="block text-xs font-medium text-gray-500 mb-1">Parole oggetto da scartare (separati da virgola)</label>
          <input v-model="cfg.filtro_oggetto_scarta" placeholder="Fattura,Rinnovo,Scadenza"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
      </div>
    </div>

    <!-- Ollama -->
    <div class="bg-surface rounded-xl shadow-sm border border-border p-5">
      <h2 class="text-sm font-bold text-primary-dark mb-4 pb-2 border-b border-border">Ollama (LLM locale)</h2>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">URL Ollama</label>
          <input v-model="cfg.ollama_url" placeholder="http://localhost:11434"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Modello</label>
          <input v-model="cfg.ollama_model" placeholder="phi3:mini"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Worker paralleli</label>
          <input type="number" v-model="cfg.ollama_workers" min="1"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
      </div>
      <div class="mt-3 text-xs text-gray-500 bg-gray-50 rounded-lg p-3">
        Modelli consigliati: <code class="bg-gray-200 px-1 rounded">phi3:mini</code> (leggero ~2.3GB) ·
        <code class="bg-gray-200 px-1 rounded">mistral:7b-instruct-q4_K_M</code> (piu preciso ~4GB)<br>
        Installare con: <code class="bg-gray-200 px-1 rounded">ollama pull phi3:mini</code>
      </div>
    </div>

    <!-- Modelli email -->
    <div class="bg-surface rounded-xl shadow-sm border border-border p-5">
      <h2 class="text-sm font-bold text-primary-dark mb-4 pb-2 border-b border-border">Modelli Email</h2>
      <div class="flex gap-2 mb-4 flex-wrap">
        <button v-for="l in LINGUE" :key="l" @click="filterLingua = l"
          class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
          :class="filterLingua === l ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'">
          {{ l }}
        </button>
      </div>

      <div v-for="m in modelliFiltered" :key="m.id" class="border border-border rounded-lg p-4 mb-3 bg-gray-50/50">
        <div class="mb-2">
          <span class="text-xs font-bold uppercase tracking-wide text-primary bg-primary/10 px-2 py-0.5 rounded">
            {{ m.lingua }} — {{ m.tipo }}
          </span>
        </div>
        <div class="mb-2">
          <label class="block text-xs font-medium text-gray-500 mb-1">Soggetto</label>
          <input v-model="modelloEdits[m.id].soggetto"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        </div>
        <div class="mb-2">
          <label class="block text-xs font-medium text-gray-500 mb-1">
            Corpo <span class="text-gray-400 font-normal">(variabili: {nome} {cognome} {data_arrivo} {data_partenza} {adulti} {bambini} {posto_per} {costo_totale} {caparra} {testo_aggiuntivo})</span>
          </label>
          <textarea v-model="modelloEdits[m.id].corpo" rows="6"
            class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-y"></textarea>
        </div>
        <button @click="saveModello(m.id)"
          class="px-4 py-1.5 text-xs font-medium rounded-lg bg-primary-light text-white hover:bg-primary transition-colors">
          Salva modello
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { getImpostazioni, updateImpostazioniBatch, testCredenziali, getModelli, updateModello } from '../api'

const LINGUE = ['IT', 'EN', 'DE', 'FR', 'NL']

const showPwd = reactive({ imap: false, smtp: false })
const cfg = reactive({
  imap_server: '', imap_port: '993', imap_user: '', imap_password: '',
  smtp_server: '', smtp_port: '587', smtp_user: '', smtp_password: '',
  email_mittente: '', email_form_sito: '',
  caparra_percentuale: '30', poll_interval_minutes: '10',
  filtro_domini_scarta: '', filtro_oggetto_scarta: '',
  ollama_url: 'http://localhost:11434', ollama_model: 'phi3:mini', ollama_workers: '4',
})

const modelli = ref([])
const modelloEdits = reactive({})
const filterLingua = ref('IT')
const saving = ref(false)
const testing = ref(false)
const testResult = ref(null)
const toast = ref({ show: false, message: '', type: 'success' })

let toastTimer = null

const modelliFiltered = computed(() =>
  modelli.value.filter(m => m.lingua === filterLingua.value)
)

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value.show = false }, 3000)
}

onMounted(async () => {
  try {
    const [settRes, modRes] = await Promise.all([getImpostazioni(), getModelli()])
    // Settings come as array of {chiave, valore}
    for (const item of settRes.data) {
      if (item.chiave in cfg) {
        cfg[item.chiave] = item.valore || ''
      }
    }
    modelli.value = modRes.data
    for (const m of modRes.data) {
      modelloEdits[m.id] = { soggetto: m.soggetto, corpo: m.corpo }
    }
  } catch (e) {
    showToast('Errore caricamento impostazioni', 'error')
  }
})

async function saveSettings() {
  saving.value = true
  try {
    const batch = Object.entries(cfg).map(([chiave, valore]) => ({ chiave, valore: String(valore ?? '') }))
    await updateImpostazioniBatch(batch)
    showToast('Impostazioni salvate')
  } catch (e) {
    showToast(e.response?.data?.detail || 'Errore salvataggio', 'error')
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    const { data } = await testCredenziali()
    testResult.value = data
  } catch (e) {
    testResult.value = {
      imap: { ok: false, error: e.response?.data?.detail || e.message },
      smtp: { ok: false, error: '-' },
    }
  } finally {
    testing.value = false
  }
}

async function saveModello(id) {
  try {
    await updateModello(id, modelloEdits[id])
    showToast('Modello salvato')
  } catch (e) {
    showToast('Errore salvataggio modello', 'error')
  }
}
</script>
