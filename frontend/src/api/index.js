import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 30000 })
const apiLong = axios.create({ baseURL: '/api', timeout: 0 })

export const getPrenotazioni = () => api.get('/prenotazioni/')
export const getPrenotazione = (id) => api.get(`/prenotazioni/${id}`)
export const updatePrenotazione = (id, data) => api.patch(`/prenotazioni/${id}`, data)
export const deletePrenotazione = (id) => api.delete(`/prenotazioni/${id}`)
export const addMessaggio = (id, data) => api.post(`/prenotazioni/${id}/messaggi`, data)
export const inviaMail = (id, data) => api.post(`/prenotazioni/${id}/invia-mail`, data)
export const traduciThread = (id) => api.post(`/prenotazioni/${id}/traduci`)
export const inviaMessaggio = (id, data) => api.post(`/prenotazioni/${id}/invia-messaggio`, data)

export const pollMail = (limit = 20) => apiLong.post(`/mail/poll?limit=${limit}`)
export const importFull = (mailLimit = 0, ollamaLimit = 100) =>
  apiLong.post(`/mail/import-full?mail_limit=${mailLimit}&ollama_limit=${ollamaLimit}`)
export const resetReimport = (ollamaLimit = 100) =>
  apiLong.post(`/mail/reset-reimport?ollama_limit=${ollamaLimit}`)
export const getJobStatus = () => api.get('/mail/job-status')
export const testCredenziali = () => api.post('/mail/test-credenziali')

export const getImpostazioni = () => api.get('/impostazioni/')
export const updateImpostazione = (data) => api.put('/impostazioni/', data)
export const updateImpostazioniBatch = (impostazioni) =>
  api.put('/impostazioni/batch', { impostazioni })

export const getModelli = () => api.get('/modelli/')
export const updateModello = (id, data) => api.put(`/modelli/${id}`, data)
export const previewModello = (id) => api.get(`/modelli/preview/${id}`)

export const getPrezzi = () => api.get('/prezzi/')
export const updatePrezzi = (data) => api.put('/prezzi/', data)
