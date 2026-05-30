import { API_BASE_URL } from '../app/constants'

export function buildApiUrl(path: string) {
  return `${API_BASE_URL}${path}`
}

export async function extractApiError(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: unknown }

    if (typeof payload.detail === 'string') {
      return payload.detail
    }

    if (Array.isArray(payload.detail) && payload.detail.length > 0) {
      const firstIssue = payload.detail[0]

      if (
        firstIssue &&
        typeof firstIssue === 'object' &&
        'msg' in firstIssue &&
        typeof firstIssue.msg === 'string'
      ) {
        return firstIssue.msg
      }
    }
  } catch {
    return response.statusText || 'Request failed'
  }

  return response.statusText || 'Request failed'
}
