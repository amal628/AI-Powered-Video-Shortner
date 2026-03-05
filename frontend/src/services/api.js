// In Vite dev, call backend directly to avoid proxy stream resets on large downloads.
const API_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')
const REQUEST_TIMEOUT_MS = 120000
const UPLOAD_TIMEOUT_MS = 1800000
const TRANSCRIBE_TIMEOUT_MS = 600000
// Processing can legitimately exceed 15 minutes for long/high-quality videos.
// Set VITE_PROCESS_TIMEOUT_MS to a positive number to enforce a limit.
const PROCESS_TIMEOUT_MS = Number.isFinite(Number(import.meta.env.VITE_PROCESS_TIMEOUT_MS))
    ? Number(import.meta.env.VITE_PROCESS_TIMEOUT_MS)
    : 0

function createApiError(action, status, detail = '') {
    const message = detail
        ? `${action} failed (${status}): ${detail}`
        : `${action} failed with status ${status}`
    const err = new Error(message)
    err.status = status
    err.detail = detail
    err.action = action
    return err
}

async function parseErrorDetail(res) {
    try {
        const errData = await res.json()
        return errData?.detail || errData?.message || ''
    } catch (_) {
        return ''
    }
}

async function fetchWithTimeout(url, options, timeoutMs, action) {
    const maxAttempts = 2
    let lastError = null

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        // timeoutMs <= 0 means "no client-side timeout"
        if (!timeoutMs || timeoutMs <= 0) {
            try {
                return await fetch(url, options)
            } catch (err) {
                lastError = err
                const isNetworkFailure = err instanceof TypeError
                if (!isNetworkFailure || attempt === maxAttempts) {
                    const apiBase = API_URL || window.location.origin
                    throw createApiError(
                        action,
                        0,
                        `Cannot reach backend at ${apiBase}. Make sure backend is running on port 8000 and refresh.`
                    )
                }
            }
            continue
        }

        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), timeoutMs)

        try {
            return await fetch(url, { ...options, signal: controller.signal })
        } catch (err) {
            lastError = err
            if (err?.name === 'AbortError') {
                throw createApiError(action, 408, `Request timed out after ${Math.round(timeoutMs / 1000)} seconds`)
            }

            const isNetworkFailure = err instanceof TypeError
            if (!isNetworkFailure || attempt === maxAttempts) {
                const apiBase = API_URL || window.location.origin
                throw createApiError(
                    action,
                    0,
                    `Cannot reach backend at ${apiBase}. Make sure backend is running on port 8000 and refresh.`
                )
            }
        } finally {
            clearTimeout(timer)
        }
    }

    throw lastError || createApiError(action, 0, 'Unexpected network failure')
}

function uploadFormDataWithProgress(url, formData, timeoutMs, action, onProgress) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('POST', url, true)
        xhr.timeout = timeoutMs

        xhr.upload.onprogress = (event) => {
            if (!onProgress || !event.lengthComputable) {
                return
            }
            const progress = Math.round((event.loaded / event.total) * 100)
            onProgress(Math.max(0, Math.min(100, progress)))
        }

        xhr.onreadystatechange = () => {
            if (xhr.readyState !== XMLHttpRequest.DONE) {
                return
            }

            const status = xhr.status
            let payload = {}
            try {
                payload = xhr.responseText ? JSON.parse(xhr.responseText) : {}
            } catch (_) {
                payload = {}
            }

            if (status >= 200 && status < 300) {
                resolve(payload)
                return
            }

            const detail = payload?.detail || payload?.message || xhr.statusText || 'Upload failed'
            reject(createApiError(action, status || 0, detail))
        }

        xhr.onerror = () => {
            const apiBase = API_URL || window.location.origin
            reject(createApiError(action, 0, `Cannot reach backend at ${apiBase}. Make sure backend is running on port 8000 and refresh.`))
        }

        xhr.ontimeout = () => {
            reject(createApiError(action, 408, `Request timed out after ${Math.round(timeoutMs / 1000)} seconds`))
        }

        xhr.send(formData)
    })
}

export async function uploadFile(file) {
    try {
        const formData = new FormData()
        formData.append('file', file)

        const res = await fetchWithTimeout(`${API_URL}/api/upload-video/`, {
            method: 'POST',
            body: formData,
        }, REQUEST_TIMEOUT_MS, 'Upload')

        if (!res.ok) {
            const detail = await parseErrorDetail(res)
            throw createApiError('Upload', res.status, detail)
        }

        const data = await res.json()
        if (!data.file_id) throw new Error('Server did not return file ID')
        return data.file_id
    } catch (err) {
        console.error(err)
        throw err
    }
}

export async function uploadVideo(file, onProgress) {
    try {
        const formData = new FormData()
        formData.append('file', file)

        if (onProgress) onProgress(0)
        const data = await uploadFormDataWithProgress(
            `${API_URL}/api/upload-video/`,
            formData,
            UPLOAD_TIMEOUT_MS,
            'Upload',
            onProgress
        )
        if (!data.file_id) throw new Error('Server did not return file ID')

        if (onProgress) onProgress(100)

        return {
            file_id: data.file_id,
            original_name: file.name,
            subtitle_url: data.subtitle_url || null
        }
    } catch (err) {
        console.error(err)
        throw err
    }
}

export async function getShareUrl(filename) {
    try {
        const res = await fetchWithTimeout(`${API_URL}/api/share/${encodeURIComponent(filename)}`, {
            method: 'GET',
        }, REQUEST_TIMEOUT_MS, 'Share URL')

        if (!res.ok) {
            const detail = await parseErrorDetail(res)
            throw createApiError('Share URL', res.status, detail)
        }

        return await res.json()
    } catch (err) {
        console.error(err)
        throw err
    }
}

export async function processVideo(fileId, options = {}) {
    try {
        const res = await fetchWithTimeout(`${API_URL}/api/process-video`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file_id: fileId,
                ...options
            }),
        }, PROCESS_TIMEOUT_MS, 'Processing')

        if (!res.ok) {
            const detail = await parseErrorDetail(res)
            throw createApiError('Processing', res.status, detail)
        }

        return await res.json()
    } catch (err) {
        console.error(err)
        throw err
    }
}

export async function getProcessingProgress(fileId) {
    try {
        const res = await fetchWithTimeout(
            `${API_URL}/api/process-progress/${encodeURIComponent(fileId)}`,
            { method: 'GET' },
            REQUEST_TIMEOUT_MS,
            'Processing progress'
        )

        if (!res.ok) {
            const detail = await parseErrorDetail(res)
            throw createApiError('Processing progress', res.status, detail)
        }

        return await res.json()
    } catch (err) {
        console.error(err)
        throw err
    }
}

export async function transcribeVideo(fileId, options = {}) {
    try {
        const res = await fetchWithTimeout(`${API_URL}/api/transcribe`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ file_id: fileId, ...options }),
        }, TRANSCRIBE_TIMEOUT_MS, 'Transcription')

        if (!res.ok) {
            const detail = await parseErrorDetail(res)
            throw createApiError('Transcription', res.status, detail)
        }

        return await res.json()
    } catch (err) {
        console.error(err)
        throw err
    }
}

export function downloadFile(filename) {
    return `${API_URL || window.location.origin}/api/download/${encodeURIComponent(filename)}`
}

export async function getVideoInfo(fileId) {
    try {
        const res = await fetchWithTimeout(`${API_URL}/api/video-info/${encodeURIComponent(fileId)}`, {
            method: 'GET',
        }, REQUEST_TIMEOUT_MS, 'Video Info')

        if (!res.ok) {
            const detail = await parseErrorDetail(res)
            throw createApiError('Video Info', res.status, detail)
        }

        return await res.json()
    } catch (err) {
        console.error(err)
        throw err
    }
}

// Subtitle API functions
export async function getSubtitleStatus(fileId) {
    try {
        const res = await fetchWithTimeout(`${API_URL}/api/subtitle-status/${encodeURIComponent(fileId)}`, {
            method: 'GET',
        }, REQUEST_TIMEOUT_MS, 'Subtitle Status')

        if (!res.ok) {
            const detail = await parseErrorDetail(res)
            throw createApiError('Subtitle Status', res.status, detail)
        }

        return await res.json()
    } catch (err) {
        console.error(err)
        throw err
    }
}

export async function generateSubtitles(fileId, options = {}) {
    try {
        const res = await fetchWithTimeout(`${API_URL}/api/generate-subtitles`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ file_id: fileId, ...options }),
        }, REQUEST_TIMEOUT_MS, 'Generate Subtitles')

        if (!res.ok) {
            const detail = await parseErrorDetail(res)
            throw createApiError('Generate Subtitles', res.status, detail)
        }

        return await res.json()
    } catch (err) {
        console.error(err)
        throw err
    }
}

export async function extractEmbeddedSubtitles(fileId, language = 'en') {
    try {
        const res = await fetchWithTimeout(`${API_URL}/api/extract-embedded-subtitles/${encodeURIComponent(fileId)}/${encodeURIComponent(language)}`, {
            method: 'GET',
        }, REQUEST_TIMEOUT_MS, 'Extract Embedded Subtitles')

        if (!res.ok) {
            const detail = await parseErrorDetail(res)
            throw createApiError('Extract Embedded Subtitles', res.status, detail)
        }

        return await res.json()
    } catch (err) {
        console.error(err)
        throw err
    }
}

export async function getSubtitleLanguages(fileId) {
    try {
        const res = await fetchWithTimeout(`${API_URL}/api/subtitle-languages/${encodeURIComponent(fileId)}`, {
            method: 'GET',
        }, REQUEST_TIMEOUT_MS, 'Subtitle Languages')

        if (!res.ok) {
            const detail = await parseErrorDetail(res)
            throw createApiError('Subtitle Languages', res.status, detail)
        }

        return await res.json()
    } catch (err) {
        console.error(err)
        throw err
    }
}

export async function downloadSubtitle(fileId, language = 'en') {
    try {
        const res = await fetchWithTimeout(`${API_URL}/api/download-subtitle/${encodeURIComponent(fileId)}/${encodeURIComponent(language)}`, {
            method: 'GET',
        }, REQUEST_TIMEOUT_MS, 'Download Subtitle')

        if (!res.ok) {
            const detail = await parseErrorDetail(res)
            throw createApiError('Download Subtitle', res.status, detail)
        }

        return await res.json()
    } catch (err) {
        console.error(err)
        throw err
    }
}

export async function clearSubtitles(fileId) {
    try {
        const res = await fetchWithTimeout(`${API_URL}/api/clear-subtitles/${encodeURIComponent(fileId)}`, {
            method: 'DELETE',
        }, REQUEST_TIMEOUT_MS, 'Clear Subtitles')

        if (!res.ok) {
            const detail = await parseErrorDetail(res)
            throw createApiError('Clear Subtitles', res.status, detail)
        }

        return await res.json()
    } catch (err) {
        console.error(err)
        throw err
    }
}

export async function segmentVideo(segmentRequest) {
    try {
        const res = await fetchWithTimeout(`${API_URL}/api/segment`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(segmentRequest),
        }, PROCESS_TIMEOUT_MS, 'Segmentation')

        if (!res.ok) {
            const detail = await parseErrorDetail(res)
            throw createApiError('Segmentation', res.status, detail)
        }

        return await res.json()
    } catch (err) {
        console.error(err)
        throw err
    }
}