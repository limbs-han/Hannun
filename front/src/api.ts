export type ApiStance = 'positive' | 'neutral' | 'negative'
export type FeedSort = 'trending' | 'latest'

export interface IssueListItem {
  issueId: number
  category: string
  pressCount: number
  articleCount: number
  score?: number
  factSummary: string
  commonFactsBriefing: string[]
}

export interface SearchIssueItem {
  issueId: number
  category: string
  pressCount: number
  articleCount: number
  factSummary: string
}

export interface CursorIssueResponse {
  items: IssueListItem[]
  nextCursorValue: number | string | null
  nextCursorId: number | null
  hasNext: boolean
}

export interface ArticleItem {
  articleId: number
  company: string
  title: string
  link: string
  published: string
  category: string
  categoryStr: string
  reporter: string
  thumbnailUrl: string | null
}

export interface ViewpointGroup {
  groupId: number
  label: string
  stance: ApiStance
  articleCount: number
  pressCount: number
  previewArticles: ArticleItem[]
  remainingCount: number
}

export interface IssueDetailResponse {
  issueId: number
  category: string
  firstReportedAt: string
  lastReportedAt: string
  pressCount: number
  articleCount: number
  factSummary: string
  commonFactsBriefing: string[]
  stanceRatio: Record<ApiStance, number>
  selectedStance: ApiStance
  viewpointGroups: ViewpointGroup[]
  viewpointGroupPage: {
    page: number
    size: number
    totalCount: number
    totalPages: number
  }
}

export interface ArticleCursorResponse {
  items: ArticleItem[]
  nextCursorPublished: string | null
  nextCursorArticleId: number | null
  hasNext: boolean
}

export interface SearchSuggestionsResponse {
  popularKeywords: string[]
}

export interface SearchResponse {
  resultType: 'LIST' | string
  keyword: string
  items: SearchIssueItem[]
  nextCursorValue: number | null
  nextCursorId: number | null
  hasNext: boolean
}

export type LogEventType =
  | 'SCROLL_FEED'
  | 'VIEW_ISSUE'
  | 'STANCE_FILTER'
  | 'VIEWPOINT_GROUP_PAGE'
  | 'VIEW_ARTICLE'
  | 'EXPAND_GROUP'
  | 'OPEN_SEARCH'
  | 'CLICK_POPULAR_KEYWORD'
  | 'SEARCH_SCROLL'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

function buildUrl(path: string, params?: Record<string, string | number | undefined | null>) {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin)
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value))
  })
  return url.toString()
}

async function request<T>(path: string, options?: RequestInit, params?: Record<string, string | number | undefined | null>): Promise<T> {
  const response = await fetch(buildUrl(path, params), {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!response.ok) throw new Error(`API ${response.status}: ${path}`)
  return response.json() as Promise<T>
}

export const api = {
  getIssues(params: {
    category: string
    sort?: FeedSort
    cursorValue?: number | string | null
    cursorId?: number | null
  }) {
    return request<CursorIssueResponse>('/api/issues', undefined, params)
  },

  getIssue(issueId: number, stance: ApiStance, page = 0) {
    return request<IssueDetailResponse>(`/api/issues/${issueId}`, undefined, { stance, page })
  },

  getViewpointGroupArticles(
    issueId: number,
    groupId: number,
    cursorPublished?: string | null,
    cursorArticleId?: number | null,
  ) {
    return request<ArticleCursorResponse>(`/api/issues/${issueId}/viewpoint-groups/${groupId}/articles`, undefined, {
      cursorPublished,
      cursorArticleId,
    })
  },

  getSearchSuggestions() {
    return request<SearchSuggestionsResponse>('/api/search/suggestions')
  },

  search(params: {
    keyword: string
    category?: string
    cursorValue?: number | null
    cursorId?: number | null
  }) {
    return request<SearchResponse>('/api/search', undefined, params)
  },

  log(sessionId: string, eventType: LogEventType, payload: Record<string, unknown>) {
    return request<{ accepted: boolean }>('/api/logs', {
      method: 'POST',
      body: JSON.stringify({ sessionId, eventType, occurredAt: new Date().toISOString(), payload }),
    })
  },
}
