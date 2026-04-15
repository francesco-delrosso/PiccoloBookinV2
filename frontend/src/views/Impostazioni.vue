<template>
  <div class="max-w-4xl mx-auto p-6 space-y-6">
    <!-- IMAP -->
    <Section title="IMAP">
      <div class="grid grid-cols-2 gap-4">
        <SettingField v-model="settings.imap_server" label="Server" />
        <SettingField v-model="settings.imap_port" label="Porta" type="number" />
        <SettingField v-model="settings.imap_user" label="Utente" />
        <SettingField v-model="settings.imap_password" label="Password" type="password" />
      </div>
    </Section>

    <!-- SMTP -->
    <Section title="SMTP">
      <div class="grid grid-cols-2 gap-4">
        <SettingField v-model="settings.smtp_server" label="Server" />
        <SettingField v-model="settings.smtp_port" label="Porta" type="number" />
        <SettingField v-model="settings.smtp_user" label="Utente" />
        <SettingField v-model="settings.smtp_password" label="Password" type="password" />
      </div>
      <div class="mt-4 flex items-center gap-4">
        <button
          class="px-4 py-2 text-sm font-medium rounded-lg bg-secondary text-white hover:bg-secondary-dark transition-colors disabled:opacity-50"
          :disabled="testingConn"
          @click="testConnection"
        >
          {{ testingConn ? 'Test in corso...' : 'Testa connessione' }}
        </button>
        <div v-if="testResult" class="text-sm">
          <span :class="testResult.imap_ok ? 'text-green-600' : 'text-red-600'">
            IMAP: {{ testResult.imap_ok ? 'OK' : testResult.imap_error || 'Errore' }}
          </span>
          <span class="mx-2 text-gray-300">|</span>
          <span :class="testResult.smtp_ok ? 'text-green-600' : 'text-red-600'">
            SMTP: {{ testResult.smtp_ok ? 'OK' : testResult.smtp_error || 'Errore' }}
          </span>
        </div>
      </div>
    </Section>

    <!-- Ollama -->
    <Section title="Ollama">
      <div class="grid grid-cols-2 gap-4">
        <SettingField v-model="settings.ollama_url" label="URL" />
        <SettingField v-model="settings.ollama_model" label="Modello" />
        <SettingField v-model="settings.ollama_workers" label="Workers" type="number" />
        <SettingField v-model="settings.poll_interval_minutes" label="Intervallo poll (min)" type="number" />
      </div>
    </Section>

    <!-- Email identity -->
    <Section title="Identita email">
      <div class="grid grid-cols-2 gap-4">
        <SettingField v-model="settings.email_mittente" label="Email mittente" />
        <SettingField v-model="settings.email_form_sito" label="Email form sito" />
        <SettingField v-model="settings.caparra_percentuale" label="Caparra %" type="number" />
      </div>
    </Section>

    <!-- Filtri spam -->
    <Section title="Filtri spam">
      <div class="space-y-4">
        <SettingField v-model="settings.filtro_domini_scarta" label="Domini da scartare (separati da virgola)" />
        <SettingField v-model="settings.filtro_oggetto_scarta" label="Oggetto da scartare (separati da virgola)" />
      </div>
    </Section>

    <!-- Save button -->
    <div class="flex justify-end">
      <button
        class="px-6 py-2.5 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary-dark transition-colors disabled:opacity-50"
        :disabled="saving"
        @click="saveSettings"
      >
        {{ saving ? 'Salvataggio...' : 'Salva impostazioni' }}
      </button>
    </div>

    <!-- Template editor -->
    <Section title="Template email">
      <div class="space-y-4">
        <div class="flex gap-4 items-end">
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-500 mb-1">Lingua</label>
            <select
              v-model="tplLingua"
              class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              @change="loadTemplate"
            >
              <option v-for="l in lingue" :key="l" :value="l">{{ l }}</option>
            </select>
          </div>
          <div class="flex-1">
            <label class="block text-xs font-medium text-gray-500 mb-1">Tipo</label>
            <select
              v-model="tplTipo"
              class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              @change="loadTemplate"
            >
              <option v-for="t in tipi" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
          <button
            class="px-4 py-2 text-sm font-medium rounded-lg bg-warm text-white hover:bg-warm-dark transition-colors"
            @click="loadPreview"
          >
            Anteprima
          </button>
        </div>

        <div v-if="currentModello">
          <div class="space-y-3">
            <div>
              <label class="block text-xs font-medium text-gray-500 mb-1">Soggetto</label>
              <input
                v-model="currentModello.soggetto"
                type="text"
                class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-500 mb-1">Corpo</label>
              <textarea
                v-model="currentModello.corpo"
                rows="10"
                class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-y"
              ></textarea>
            </div>
            <div class="flex justify-end">
              <button
                class="px-4 py-2 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary-dark transition-colors disabled:opacity-50"
                :disabled="savingTemplate"
                @click="saveTemplate"
              >
                {{ savingTemplate ? 'Salvataggio...' : 'Salva template' }}
              </button>
            </div>
          </div>
        </div>
        <div v-else class="text-sm text-gray-400 text-center py-4">
          Seleziona lingua e tipo per modificare il template
        </div>

        <!-- Preview -->
        <div v-if="preview" class="bg-gray-50 rounded-lg p-4 border border-border">
          <h3 class="text-xs font-semibold text-gray-500 uppercase mb-2">Anteprima</h3>
          <div class="text-sm font-medium mb-2">{{ preview.soggetto }}</div>
          <div class="text-sm text-gray-600 whitespace-pre-wrap">{{ preview.corpo }}</div>
        </div>
      </div>
    </Section>

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
import { ref, reactive, onMounted } from 'vue'
import {
  getImpostazioni,
  updateImpostazioniBatch,
  testCredenziali,
  getModelli,
  updateModello,
  previewModello,
} from '../api'

/* --- Sub-components ---------------------------------------------------- */

const Section = {
  props: ['title'],
  template: `<div class="bg-surface rounded-xl shadow-sm border border-border p-5">
    <h2 class="text-base font-semibold text-gray-700 mb-4">{{ title }}</h2>
    <slot />
  </div>`,
}

const SettingField = {
  props: ['modelValue', 'label', 'type'],
  emits: ['update:modelValue'],
  template: `<div>
    <label class="block text-xs font-medium text-gray-500 mb-1">{{ label }}</label>
    <input
      :type="type || 'text'"
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
      class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
    />
  </div>`,
}

/* --- State -------------------------------------------------------------- */

const settings = reactive({})
const saving = ref(false)
const testingConn = ref(false)
const testResult = ref(null)

const modelli = ref([])
const lingue = ['IT', 'EN', 'DE', 'FR', 'NL']
const tipi = ['accetta', 'rifiuta', 'info']
const tplLingua = ref('IT')
const tplTipo = ref('accetta')
const currentModello = ref(null)
const savingTemplate = ref(false)
const preview = ref(null)

const toast = ref({ show: false, message: '', type: 'success' })
let toastTimer = null

/* --- Toast -------------------------------------------------------------- */

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value.show = false }, 3000)
}

/* --- Settings ----------------------------------------------------------- */

async function loadSettings() {
  try {
    const { data } = await getImpostazioni()
    for (const item of data) {
      settings[item.chiave] = item.valore
    }
  } catch (e) {
    showToast('Errore caricamento impostazioni', 'error')
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const batch = Object.entries(settings).map(([chiave, valore]) => ({
      chiave,
      valore: valore ?? '',
    }))
    await updateImpostazioniBatch(batch)
    showToast('Impostazioni salvate')
  } catch (e) {
    showToast(e.response?.data?.detail || 'Errore salvataggio', 'error')
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  testingConn.value = true
  testResult.value = null
  try {
    const { data } = await testCredenziali()
    testResult.value = data
  } catch (e) {
    showToast(e.response?.data?.detail || 'Errore test connessione', 'error')
  } finally {
    testingConn.value = false
  }
}

/* --- Templates ---------------------------------------------------------- */

async function loadModelli() {
  try {
    const { data } = await getModelli()
    modelli.value = data
    loadTemplate()
  } catch (e) {
    showToast('Errore caricamento modelli', 'error')
  }
}

function loadTemplate() {
  const found = modelli.value.find(
    (m) => m.lingua === tplLingua.value && m.tipo === tplTipo.value
  )
  currentModello.value = found ? { ...found } : null
  preview.value = null
}

async function saveTemplate() {
  if (!currentModello.value) return
  savingTemplate.value = true
  try {
    await updateModello(currentModello.value.id, {
      soggetto: currentModello.value.soggetto,
      corpo: currentModello.value.corpo,
    })
    const idx = modelli.value.findIndex((m) => m.id === currentModello.value.id)
    if (idx !== -1) {
      modelli.value[idx] = { ...currentModello.value }
    }
    showToast('Template salvato')
  } catch (e) {
    showToast(e.response?.data?.detail || 'Errore salvataggio template', 'error')
  } finally {
    savingTemplate.value = false
  }
}

async function loadPreview() {
  if (!currentModello.value) return
  try {
    const { data } = await previewModello(currentModello.value.id)
    preview.value = data
  } catch (e) {
    showToast(e.response?.data?.detail || 'Errore anteprima', 'error')
  }
}

/* --- Lifecycle ---------------------------------------------------------- */

onMounted(async () => {
  await Promise.all([loadSettings(), loadModelli()])
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
