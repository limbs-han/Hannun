// 한눈 API 클라이언트 — 명세서: API명세서/한눈_API_5.md
// VITE_API_BASE_URL 이 없으면 App.vue 가 mock.ts 의 mockApi 를 씁니다.

export type ApiStance = 'positive' | 'neutral' | 'negative'
export type FeedSort = 'trending' | 'latest'

export const STANCES: ApiStance[] = ['positive', 'neutral', 'negative']
export const STANCE_LABEL: Record<ApiStance, string> = { positive: '긍정', neutral: '중립', negative: '부정' }
export const CATEGORIES = ['ALL', '정치', '경제', '사회', 'IT', '세계'] as const

/* 1. 메인 피드 / 6. 기간 검색 */
export interface IssueListItem {
  issueId: number
  category: string
  pressCount: number
  articleCount: number
  score?: number
  factSummary: string
  commonFactsBriefing: string[]
}

export interface CursorIssueResponse {
  items: IssueListItem[]
  nextCursorValue: number | string | null
  nextCursorId: number | null
  hasNext: boolean
}

/* 2·3. 이슈 상세 / 관점그룹 기사 */
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
  viewpointGroupPage: { page: number; size: number; totalCount: number; totalPages: number }
}

export interface ArticleCursorResponse {
  items: ArticleItem[]
  nextCursorPublished: string | null
  nextCursorArticleId: number | null
  hasNext: boolean
}

/* 4. 검색 */
export interface SearchSuggestionsResponse {
  popularKeywords: string[]
}

export interface SearchIssueItem {
  issueId: number
  category: string
  factSummary: string
  articleCount: number
  pressCount: number
}

export interface SearchResponse {
  resultType: 'LIST' | string
  keyword: string
  items: SearchIssueItem[]
  nextCursorValue: number | null
  nextCursorId: number | null
  hasNext: boolean
}

/* 5. 유저 로그 */
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

export interface IssuesQuery {
  category: string
  sort?: FeedSort
  cursorValue?: number | string | null
  cursorId?: number | null
}

export interface DateRangeQuery extends IssuesQuery {
  from: string
  to: string
}

export interface SearchQuery {
  keyword: string
  category?: string
  cursorValue?: number | null
  cursorId?: number | null
  /** 타이핑 중 실시간 미리보기면 true. 서버가 인기 검색어 집계에서 제외합니다. */
  preview?: boolean
}

export interface HannunApi {
  getIssues(q: IssuesQuery): Promise<CursorIssueResponse>
  getIssuesByDateRange(q: DateRangeQuery): Promise<CursorIssueResponse>
  getIssue(issueId: number, stance: ApiStance, page?: number): Promise<IssueDetailResponse>
  getViewpointGroupArticles(
    issueId: number,
    groupId: number,
    cursorPublished?: string | null,
    cursorArticleId?: number | null,
  ): Promise<ArticleCursorResponse>
  getSearchSuggestions(): Promise<SearchSuggestionsResponse>
  search(q: SearchQuery): Promise<SearchResponse>
  log(eventType: LogEventType, payload: Record<string, unknown>): Promise<void>
}

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

type Params = Record<string, string | number | boolean | null | undefined>

function buildUrl(path: string, params?: Params) {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value))
  }
  return url.toString()
}

async function request<T>(path: string, params?: Params, init?: RequestInit): Promise<T> {
  const res = await fetch(buildUrl(path, params), {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) throw new Error(`API ${res.status} ${path}`)
  return res.json() as Promise<T>
}

// 로그는 화면을 막지 않습니다 — 실패해도 조용히 버립니다.
export function sessionId() {
  const key = 'hannun-session-id'
  let id = localStorage.getItem(key)
  if (!id) {
    id = `sess_${crypto.randomUUID()}`
    localStorage.setItem(key, id)
  }
  return id
}

export const httpApi: HannunApi = {
  getIssues: (q) => request('/api/issues', { ...q, category: q.category, sort: q.sort ?? 'trending' }),

  getIssuesByDateRange: (q) => request('/api/issues/date-range', { ...q, sort: q.sort ?? 'trending' }),

  getIssue: (issueId, stance, page = 0) => request(`/api/issues/${issueId}`, { stance, page }),

  getViewpointGroupArticles: (issueId, groupId, cursorPublished, cursorArticleId) =>
    request(`/api/issues/${issueId}/viewpoint-groups/${groupId}/articles`, { cursorPublished, cursorArticleId }),

  getSearchSuggestions: () => request('/api/search/suggestions'),

  search: (q) => request('/api/search', { ...q }),

  async log(eventType, payload) {
    try {
      await request('/api/logs', undefined, {
        method: 'POST',
        body: JSON.stringify({ sessionId: sessionId(), eventType, occurredAt: new Date().toISOString(), payload }),
      })
    } catch {
      /* 수집 실패는 무시 */
    }
  },
}
