import { defineStore } from 'pinia'
import { getPrenotazioni, getPrenotazione, getJobStatus } from '../api'

export const usePrenotazioniStore = defineStore('prenotazioni', {
  state: () => ({
    list: [],
    selected: null,
    filters: { stato: '', tipo: '', search: '' },
    jobStatus: null,
    _jobPollInterval: null,
  }),

  getters: {
    filtered(state) {
      let items = state.list
      if (state.filters.stato) {
        items = items.filter((p) => p.stato === state.filters.stato)
      }
      if (state.filters.tipo) {
        items = items.filter((p) => p.tipo_richiesta === state.filters.tipo)
      }
      if (state.filters.search) {
        const q = state.filters.search.toLowerCase()
        items = items.filter(
          (p) =>
            (p.nome && p.nome.toLowerCase().includes(q)) ||
            (p.cognome && p.cognome.toLowerCase().includes(q)) ||
            (p.email && p.email.toLowerCase().includes(q))
        )
      }
      return items
    },
  },

  actions: {
    async fetchAll() {
      const { data } = await getPrenotazioni()
      this.list = data
    },
    async selectPrenotazione(id) {
      if (!id) { this.selected = null; return }
      const { data } = await getPrenotazione(id)
      this.selected = data
    },
    startJobPolling() {
      if (this._jobPollInterval) return
      this._jobPollInterval = setInterval(async () => {
        try {
          const { data } = await getJobStatus()
          this.jobStatus = data
          if (['completed', 'done', 'error', 'idle'].includes(data.status)) {
            this.stopJobPolling()
            this.fetchAll()
          }
        } catch { /* ignore */ }
      }, 5000)
    },
    stopJobPolling() {
      if (this._jobPollInterval) {
        clearInterval(this._jobPollInterval)
        this._jobPollInterval = null
      }
    },
  },
})
