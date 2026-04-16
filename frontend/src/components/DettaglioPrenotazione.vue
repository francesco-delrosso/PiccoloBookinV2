<template>
  <div class="bg-surface rounded-xl shadow-sm border border-border p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="text-xl font-semibold">
          <template v-if="p.nome || p.cognome">
            {{ [p.nome, p.cognome].filter(Boolean).join(' ') }}
          </template>
          <span v-else class="italic text-gray-400">Senza nome</span>
        </h2>
        <p class="text-sm text-gray-500 mt-0.5">{{ p.email }}</p>
      </div>
      <span
        class="inline-flex items-center gap-1 text-sm font-medium px-3 py-1 rounded-full"
        :class="statoClass(p.stato)"
      >
        <span v-if="p.stato === 'Nuova Risposta'" class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
        {{ p.stato }}
      </span>
    </div>

    <!-- Editable Fields Grid -->
    <div class="grid grid-cols-2 gap-4 mb-6">
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Nome</label>
        <input v-model="form.nome" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Cognome</label>
        <input v-model="form.cognome" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Email</label>
        <input v-model="form.email" type="email" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Telefono</label>
        <input v-model="form.telefono" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Data arrivo</label>
        <input v-model="form.data_arrivo" type="date" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Data partenza</label>
        <input v-model="form.data_partenza" type="date" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Adulti</label>
        <input v-model.number="form.adulti" type="number" min="0" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Bambini</label>
        <input v-model.number="form.bambini" type="number" min="0" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Posto per</label>
        <select v-model="form.posto_per" class="field-input">
          <option :value="null">--</option>
          <option value="tenda">Tenda</option>
          <option value="camper">Camper</option>
          <option value="caravan">Caravan</option>
          <option value="bungalow">Bungalow</option>
        </select>
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Costo totale</label>
        <input v-model.number="form.costo_totale" type="number" min="0" step="0.01" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Tipo richiesta</label>
        <select v-model="form.tipo_richiesta" class="field-input">
          <option value="Prenotazione">Prenotazione</option>
          <option value="Contatto">Contatto</option>
        </select>
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Lingua suggerita</label>
        <select v-model="form.lingua_suggerita" class="field-input">
          <option v-for="l in lingue" :key="l" :value="l">{{ l }}</option>
        </select>
      </div>
    </div>

    <!-- Save Button -->
    <div v-if="isDirty" class="mb-6">
      <button @click="save" :disabled="saving"
        class="px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-50">
        {{ saving ? 'Salvataggio...' : 'Salva modifiche' }}
      </button>
    </div>

    <!-- Action Buttons -->
    <div class="flex items-center gap-2 pt-4 border-t border-border">
      <button @click="$emit('action', 'accetta')"
        class="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors">
        Accetta
      </button>
      <button @click="$emit('action', 'rifiuta')"
        class="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors">
        Rifiuta
      </button>
      <button @click="$emit('action', 'info')"
        class="px-4 py-2 bg-secondary text-white text-sm font-medium rounded-lg hover:bg-secondary-dark transition-colors">
        Info
      </button>
      <button @click="$emit('action', 'elimina')"
        class="ml-auto px-4 py-2 bg-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-300 transition-colors">
        Elimina
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { updatePrenotazione } from '../api'
import { usePrenotazioniStore } from '../stores/prenotazioni'

const props = defineProps({
  prenotazione: { type: Object, default: null },
})
const emit = defineEmits(['action', 'saved'])
const store = usePrenotazioniStore()

const p = computed(() => props.prenotazione || {})
const lingue = ['IT', 'EN', 'DE', 'FR', 'NL']
const saving = ref(false)

const editableKeys = [
  'nome', 'cognome', 'email', 'telefono',
  'data_arrivo', 'data_partenza', 'adulti', 'bambini',
  'posto_per', 'costo_totale', 'tipo_richiesta', 'lingua_suggerita',
]

const form = ref({})

function resetForm() {
  const obj = {}
  for (const k of editableKeys) {
    obj[k] = p.value[k] ?? null
  }
  form.value = obj
}

watch(() => p.value.id, resetForm, { immediate: true })

const isDirty = computed(() => {
  for (const k of editableKeys) {
    const original = p.value[k] ?? null
    const current = form.value[k] ?? null
    if (String(original) !== String(current)) return true
  }
  return false
})

function statoClass(stato) {
  const map = {
    'Nuova': 'bg-blue-100 text-blue-800',
    'Nuova Risposta': 'bg-blue-100 text-blue-800',
    'In lavorazione': 'bg-yellow-100 text-yellow-800',
    'Attesa Bonifico': 'bg-orange-100 text-orange-800',
    'Confermata': 'bg-green-100 text-green-800',
    'Rifiutata': 'bg-red-100 text-red-800',
  }
  return map[stato] || 'bg-gray-100 text-gray-800'
}

async function save() {
  saving.value = true
  try {
    const changes = {}
    for (const k of editableKeys) {
      const original = p.value[k] ?? null
      const current = form.value[k] ?? null
      if (String(original) !== String(current)) {
        changes[k] = current
      }
    }
    await updatePrenotazione(p.value.id, changes)
    await store.selectPrenotazione(p.value.id)
    await store.fetchAll()
    emit('saved')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.field-input {
  width: 100%;
  padding: 0.375rem 0.625rem;
  border-radius: 0.5rem;
  border: 1px solid var(--color-border);
  background: white;
  font-size: 0.875rem;
}
.field-input:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(43, 107, 79, 0.15);
  border-color: var(--color-primary);
}
</style>
