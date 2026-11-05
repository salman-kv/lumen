const TOKEN_KEY = 'kda_token'

export const getToken = () => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } }
export const setToken = (t) => { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch { /* private mode */ } }

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status }
}

function messageFrom(body, status) {
  const d = body?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d) && d[0]?.msg) return d[0].msg.replace(/^Value error, /, '')
  if (status === 429) return 'Too many requests. Please slow down for a moment.'
  return 'Something went wrong. Please try again.'
}

export async function api(path, { method = 'GET', json, form, auth = true } = {}) {
  const headers = {}
  const t = getToken()
  if (auth && t) headers.Authorization = `Bearer ${t}`
  let body
  if (json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(json) }
  if (form) body = form
  let res
  try { res = await fetch(`/api${path}`, { method, headers, body }) }
  catch { throw new ApiError('Cannot reach the server. Check your connection and try again.', 0) }
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && auth && t) { setToken(null); window.dispatchEvent(new Event('kda:logout')) }
    throw new ApiError(messageFrom(data, res.status), res.status)
  }
  return data
}

/** Upload with progress (fetch cannot report upload progress). */
export function uploadFile(path, file, onProgress, method = 'POST') {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open(method, `/api${path}`)
    const t = getToken()
    if (t) xhr.setRequestHeader('Authorization', `Bearer ${t}`)
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total)
    xhr.onload = () => {
      let data = null
      try { data = JSON.parse(xhr.responseText) } catch { /* empty */ }
      xhr.status >= 200 && xhr.status < 300 ? resolve(data) : reject(new ApiError(messageFrom(data, xhr.status), xhr.status))
    }
    xhr.onerror = () => reject(new ApiError('Upload failed. Check your connection and try again.', 0))
    const fd = new FormData()
    fd.append('file', file)
    xhr.send(fd)
  })
}

/** Public assistant: stream pipeline steps + answer tokens over SSE. */
export async function askStream(token, question, onEvent, signal) {
  let res
  try {
    res = await fetch('/api/ask/stream', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
      body: JSON.stringify({ token, question }),
    })
  } catch (e) {
    if (e.name === 'AbortError') return
    throw new ApiError('Cannot reach the assistant right now. Please try again.', 0)
  }
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new ApiError(messageFrom(data, res.status), res.status)
  }
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let i
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, i); buf = buf.slice(i + 2)
      if (chunk.startsWith('data:')) { try { onEvent(JSON.parse(chunk.slice(5))) } catch { /* ignore */ } }
    }
  }
}

export const fmtBytes = (n) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`)
