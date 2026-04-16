<template>
  <div class="prezzi-page">
    <div class="page-header">
      <h2>Listino Prezzi</h2>
      <div class="header-actions">
        <button class="btn-add-stagione" @click="addStagione">+ Stagione</button>
        <button class="btn-save" @click="save" :disabled="saving">
          {{ saving ? 'Salvataggio...' : 'Salva' }}
        </button>
      </div>
    </div>

    <div v-if="toast.show" class="toast" :class="toast.type === 'error' ? 'toast-err' : 'toast-ok'">
      {{ toast.message }}
    </div>

    <div v-if="listino" class="content">

      <!-- Stagioni -->
      <div class="section">
        <h3>Stagioni e Periodi</h3>
        <div class="stagioni-grid">
          <div
            v-for="(s, si) in listino.stagioni"
            :key="si"
            class="stagione-card"
            :style="{ borderTopColor: s.colore, background: s.colore + '22' }"
          >
            <div class="stagione-head">
              <input v-model="s.nome" class="stagione-nome" />
              <input type="color" v-model="s.colore" class="color-picker" />
              <button class="btn-remove-sm" @click="removeStagione(si)" :disabled="listino.stagioni.length <= 1">✕</button>
            </div>
            <div class="periodi">
              <div v-for="(p, pi) in s.periodi" :key="pi" class="periodo-row">
                <input type="date" v-model="p[0]" class="date-input" />
                <span class="periodo-sep">&rarr;</span>
                <input type="date" v-model="p[1]" class="date-input" />
                <button class="btn-remove-sm" @click="removePeriodo(si, pi)" :disabled="s.periodi.length <= 1">✕</button>
              </div>
              <button class="btn-add-periodo" @click="addPeriodo(si)">+ Periodo</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Price table -->
      <div class="section">
        <div class="table-header-row">
          <h3>Tariffe per Notte (&euro;)</h3>
          <button class="btn-add-voce" @click="addVoce">+ Voce</button>
        </div>

        <div class="table-wrap">
          <table class="price-table">
            <thead>
              <tr>
                <th class="th-cat">Categoria</th>
                <th class="th-nome">Voce</th>
                <th
                  v-for="(s, si) in listino.stagioni"
                  :key="si"
                  class="th-stagione"
                  :style="{ background: s.colore }"
                >
                  {{ s.nome }}
                </th>
                <th class="th-note">Note</th>
                <th class="th-del"></th>
              </tr>
            </thead>
            <tbody>
              <template v-for="cat in categorie" :key="cat">
                <tr
                  v-for="(v, vi) in vociPerCategoria(cat)"
                  :key="v.id"
                  class="price-row"
                >
                  <td
                    v-if="vi === 0"
                    class="td-cat"
                    :rowspan="vociPerCategoria(cat).length"
                  >
                    <input v-model="v.categoria" class="cat-input" />
                  </td>
                  <td class="td-nome">
                    <input v-model="v.nome" class="nome-input" />
                  </td>
                  <td
                    v-for="(s, si) in listino.stagioni"
                    :key="si"
                    class="td-price"
                  >
                    <input
                      type="number"
                      step="0.10"
                      min="0"
                      v-model.number="v.prezzi[si]"
                      class="price-input"
                      :style="{ background: s.colore + '44' }"
                      @focus="ensurePrezzi(v)"
                    />
                  </td>
                  <td class="td-note">
                    <input v-model="v.note" class="note-input" placeholder="—" />
                  </td>
                  <td class="td-del">
                    <button class="btn-remove-sm" @click="removeVoce(v.id)">✕</button>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <div class="hint">
          I prezzi sono in &euro; per notte. Le colonne seguono l'ordine delle stagioni definite sopra.
        </div>
      </div>

    </div>
    <div v-else class="loading">Caricamento listino...</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getPrezzi, updatePrezzi } from '../api'

const listino = ref(null)
const saving = ref(false)
const toast = ref({ show: false, message: '', type: 'success' })
let toastTimer = null

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value.show = false }, 3000)
}

const categorie = computed(() => {
  if (!listino.value) return []
  const seen = new Set()
  const out = []
  for (const v of listino.value.voci) {
    if (!seen.has(v.categoria)) { seen.add(v.categoria); out.push(v.categoria) }
  }
  return out
})

function vociPerCategoria(cat) {
  return listino.value.voci.filter(v => v.categoria === cat)
}

function ensurePrezzi(voce) {
  const n = listino.value.stagioni.length
  while (voce.prezzi.length < n) voce.prezzi.push(0)
}

function addStagione() {
  listino.value.stagioni.push({ nome: 'Nuova', colore: '#d1fae5', periodi: [['', '']] })
  listino.value.voci.forEach(v => v.prezzi.push(0))
}

function removeStagione(si) {
  listino.value.stagioni.splice(si, 1)
  listino.value.voci.forEach(v => v.prezzi.splice(si, 1))
}

function addPeriodo(si) {
  listino.value.stagioni[si].periodi.push(['', ''])
}

function removePeriodo(si, pi) {
  listino.value.stagioni[si].periodi.splice(pi, 1)
}

let _nextId = 1
function addVoce() {
  const n = listino.value.stagioni.length
  listino.value.voci.push({
    id: `voce_${Date.now()}_${_nextId++}`,
    categoria: categorie.value[0] || 'Altro',
    nome: 'Nuova voce',
    prezzi: Array(n).fill(0),
    note: '',
  })
}

function removeVoce(id) {
  listino.value.voci = listino.value.voci.filter(v => v.id !== id)
}

async function load() {
  try {
    const { data } = await getPrezzi()
    listino.value = data
    const n = listino.value.stagioni.length
    listino.value.voci.forEach(v => {
      while (v.prezzi.length < n) v.prezzi.push(0)
      if (!('note' in v)) v.note = ''
      if (!v.id) v.id = `voce_${Date.now()}_${_nextId++}`
    })
  } catch (e) {
    showToast('Errore caricamento listino', 'error')
  }
}

async function save() {
  saving.value = true
  try {
    await updatePrezzi(listino.value)
    showToast('Listino salvato')
  } catch (e) {
    showToast(e.response?.data?.detail || 'Errore salvataggio', 'error')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.prezzi-page {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  max-width: 1100px;
  margin: 0 auto;
  width: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}
.page-header h2 { font-size: 1.25rem; font-weight: 700; }

.header-actions { display: flex; gap: 0.5rem; }

.btn-save {
  background: var(--color-primary);
  color: white;
  font-weight: 600;
  padding: 0.45rem 1.1rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
.btn-save:disabled { opacity: 0.5; }

.btn-add-stagione {
  background: var(--color-secondary);
  color: white;
  font-weight: 600;
  padding: 0.45rem 1rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.toast {
  border-radius: 8px;
  padding: 0.6rem 1rem;
  margin-bottom: 1rem;
  font-weight: 500;
  font-size: 0.9rem;
}
.toast-ok { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }
.toast-err { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }

.content { display: flex; flex-direction: column; gap: 1.25rem; }

.section {
  background: white;
  border-radius: 10px;
  padding: 1.25rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.section h3 {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--color-primary-dark);
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 0.5rem;
  margin-bottom: 1rem;
}

/* Stagioni */
.stagioni-grid { display: flex; gap: 1rem; flex-wrap: wrap; }

.stagione-card {
  flex: 1;
  min-width: 200px;
  border: 1px solid var(--color-border);
  border-top: 4px solid;
  border-radius: 8px;
  padding: 0.75rem;
}

.stagione-head {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.6rem;
}

.stagione-nome {
  flex: 1;
  font-weight: 700;
  font-size: 0.9rem;
  border: 1px solid transparent;
  background: transparent;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
}
.stagione-nome:focus { border-color: var(--color-border); background: white; }

.color-picker {
  width: 32px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  cursor: pointer;
}

.periodi { display: flex; flex-direction: column; gap: 0.35rem; }
.periodo-row { display: flex; align-items: center; gap: 0.3rem; }

.date-input {
  flex: 1;
  font-size: 0.75rem;
  padding: 0.25rem 0.3rem;
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: 4px;
}

.periodo-sep { color: #9ca3af; font-size: 0.8rem; flex-shrink: 0; }

.btn-add-periodo {
  margin-top: 0.4rem;
  background: transparent;
  border: 1px dashed var(--color-border);
  color: #9ca3af;
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  align-self: flex-start;
  cursor: pointer;
}
.btn-add-periodo:hover { background: #f3f4f6; color: #374151; }

.btn-remove-sm {
  background: transparent;
  border: 1px solid #fca5a5;
  color: #dc2626;
  padding: 0.1rem 0.35rem;
  font-size: 0.7rem;
  border-radius: 4px;
  flex-shrink: 0;
  cursor: pointer;
}
.btn-remove-sm:hover { background: #fee2e2; }
.btn-remove-sm:disabled { opacity: 0.3; cursor: not-allowed; }

/* Table */
.table-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 0.5rem;
  margin-bottom: 0.85rem;
}
.table-header-row h3 { margin-bottom: 0; border-bottom: none; padding-bottom: 0; }

.btn-add-voce {
  background: var(--color-primary-light);
  color: white;
  font-size: 0.8rem;
  padding: 0.3rem 0.75rem;
  font-weight: 600;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.table-wrap { overflow-x: auto; }

.price-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }

.price-table th {
  padding: 0.5rem;
  text-align: center;
  font-size: 0.75rem;
  font-weight: 700;
  border-bottom: 2px solid var(--color-border);
  white-space: nowrap;
  color: white;
}

.th-cat { text-align: left; width: 100px; color: #374151; background: transparent !important; }
.th-nome { text-align: left; min-width: 160px; color: #374151; background: transparent !important; }
.th-stagione { min-width: 90px; }
.th-note { min-width: 100px; color: #374151; background: transparent !important; }
.th-del { width: 32px; background: transparent !important; }

.price-row td {
  border-bottom: 1px solid #f0f0f0;
  padding: 0.3rem 0.4rem;
  vertical-align: middle;
}

.td-cat {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--color-primary);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  vertical-align: top;
  padding-top: 0.6rem;
  border-right: 2px solid var(--color-border);
}

.cat-input {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--color-primary);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  border: 1px solid transparent;
  background: transparent;
  padding: 0.1rem 0.3rem;
  width: 90px;
  border-radius: 4px;
}
.cat-input:focus { border-color: var(--color-border); background: white; text-transform: none; }

.nome-input {
  border: 1px solid transparent;
  background: transparent;
  padding: 0.2rem 0.3rem;
  width: 100%;
  font-size: 0.83rem;
  border-radius: 4px;
}
.nome-input:focus { border-color: var(--color-border); background: white; }

.td-price { text-align: center; }

.price-input {
  width: 70px;
  text-align: right;
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 0.2rem 0.3rem;
  font-size: 0.83rem;
  font-weight: 500;
}
.price-input:focus { border-color: var(--color-border); background: white !important; }

.note-input {
  border: 1px solid transparent;
  background: transparent;
  padding: 0.2rem 0.3rem;
  font-size: 0.78rem;
  color: #9ca3af;
  width: 100%;
  border-radius: 4px;
}
.note-input:focus { border-color: var(--color-border); background: white; }

.td-del { text-align: center; }

.hint {
  margin-top: 0.85rem;
  font-size: 0.76rem;
  color: #9ca3af;
  background: #f8f9fa;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: #9ca3af;
  padding: 3rem;
}
</style>
