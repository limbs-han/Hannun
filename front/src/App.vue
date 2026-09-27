<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  httpApi,
  STANCES,
  type ApiStance,
  type ArticleItem,
  type FeedSort,
  type IssueDetailResponse,
  type IssueListItem,
  type LogEventType,
  type SearchIssueItem,
} from './api'
import hannunLogo from './assets/hannun-logo-transparent.png'

// 빈 VITE_API_BASE_URL 은 같은 도메인의 /api 를 뜻합니다.
const api = httpApi

type Issue = { id: number; category: string; title: string; press: number; articles: number; summary: string; time: string; score?: number; briefing?: string[] }
type Stance = '긍정' | '중립' | '부정'
type ViewArticle = { id?: number; source: string; headline: string; byline: string; time: string; link?: string; thumbnail?: string | null }
type PageName = 'home' | 'detail' | 'search'
type NavigationState = { __hannun: true; page: PageName; issueId?: number; keyword?: string }
type ViewpointCard = { number: string; groupId?: number; title: string; description: string; press: number; articleCount: number; remainingCount: number; articles: ViewArticle[] }
type CalendarDay = { key: string; date: string; label: number | null; selected: boolean; inRange: boolean; isStart: boolean; isEnd: boolean }

// BE 가 내려주는 category 값과 글자 단위로 일치해야 합니다 — 그대로 쿼리 파라미터로 나갑니다.
// '산업'은 '경제'로 통합하기로 해서 탭에 두지 않습니다(실제 통합은 수집·적재 단계에서 처리).
const categories = ['정치', '경제', '사회', '국제', '문화', 'IT/과학', '연예', '스포츠']
const stanceToApi: Record<Stance, ApiStance> = { 긍정: 'positive', 중립: 'neutral', 부정: 'negative' }
const apiToStance: Record<ApiStance, Stance> = { positive: '긍정', neutral: '중립', negative: '부정' }

/* ---------- 상태 ---------- */
const todayLabel = new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })
const page = ref<PageName>('home')
const category = ref('전체')
const sort = ref('화제성순')
const emptyIssue: Issue = { id: 0, category: '', title: '', press: 0, articles: 0, summary: '', time: '' }
const issues = ref<Issue[]>([])
const selected = ref<Issue>({ ...emptyIssue })
const query = ref('')
const keyword = ref('')
const searchOpen = ref(false)
const searchBox = ref<HTMLElement | null>(null)
const stance = ref<Stance | null>(null)
const hasRevealedRatio = ref(false)
const recent = ref<string[]>([])
const relatedSearchResults = ref<Issue[]>([])
const relatedSearchLoading = ref(false)
const relatedSearchTerm = ref('')
const popularKeywords = ref<string[]>([])
const detailData = ref<IssueDetailResponse | null>(null)
const detailLoading = ref(false)
const feedLoading = ref(false)
const feedHasNext = ref(false)
const feedCursorValue = ref<number | string | null>(null)
const feedCursorId = ref<number | null>(null)
const dateFromInput = ref('')
const dateToInput = ref('')
const appliedDateFrom = ref('')
const appliedDateTo = ref('')
const dateRangeError = ref('')
const datePickerOpen = ref(false)
const calendarViewDate = ref(new Date(new Date().getFullYear(), new Date().getMonth(), 1))
const results = ref<Issue[]>([])
const searchLoading = ref(false)
const searchTopIssues = ref<Issue[]>([])
const searchTopLoading = ref(false)
const searchHasNext = ref(false)
const searchCursorValue = ref<number | null>(null)
const searchCursorId = ref<number | null>(null)
const expandedCards = ref<string[]>([])
const groupArticles = ref<Record<number, ViewArticle[]>>({})
const groupCursor = ref<Record<number, { published: string | null; articleId: number | null; hasNext: boolean }>>({})
const feedSentinel = ref<HTMLElement | null>(null)
const searchSentinel = ref<HTMLElement | null>(null)
let feedObserver: IntersectionObserver | null = null
let searchObserver: IntersectionObserver | null = null
let relatedSearchTimer: ReturnType<typeof setTimeout> | null = null
let relatedSearchRequestId = 0
let detailRequestId = 0
let feedRequestId = 0

// 화제성 상위 2건은 맨 위 블럭으로 빼고, 목록에서는 중복 제거합니다.
// 3건 미만이면 블럭을 띄우지 않습니다 — 아래 목록이 비어버리기 때문입니다.
const featuredIssues = computed(() =>
  issues.value.length > 2
    ? [...issues.value].sort((a, b) => (b.score ?? b.articles) - (a.score ?? a.articles)).slice(0, 2)
    : [],
)
const feed = computed(() => {
  const top = new Set(featuredIssues.value.map((issue) => issue.id))
  return issues.value.filter((issue) => !top.has(issue.id))
})
const dateRangeActive = computed(() => sort.value === '최신순' && Boolean(appliedDateFrom.value && appliedDateTo.value))
const dateRangeLabel = computed(() => {
  if (dateFromInput.value && dateToInput.value) return `${dateFromInput.value} – ${dateToInput.value}`
  if (dateFromInput.value) return `${dateFromInput.value} – 종료일 선택`
  return '기간 선택'
})
const calendarTitle = computed(() => `${calendarViewDate.value.getFullYear()}년 ${calendarViewDate.value.getMonth() + 1}월`)
const calendarDays = computed<CalendarDay[]>(() => {
  const year = calendarViewDate.value.getFullYear()
  const month = calendarViewDate.value.getMonth()
  const firstWeekday = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cellCount = Math.ceil((firstWeekday + daysInMonth) / 7) * 7
  return Array.from({ length: cellCount }, (_, index) => {
    const day = index - firstWeekday + 1
    if (day < 1 || day > daysInMonth) return { key: `blank-${index}`, date: '', label: null, selected: false, inRange: false, isStart: false, isEnd: false }
    const date = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    const isStart = date === dateFromInput.value
    const isEnd = date === dateToInput.value
    return { key: date, date, label: day, selected: isStart || isEnd, inRange: Boolean(dateToInput.value && date > dateFromInput.value && date < dateToInput.value), isStart, isEnd }
  })
})
const hasNextViewpointPage = computed(() => {
  const info = detailData.value?.viewpointGroupPage
  return Boolean(info && info.page + 1 < info.totalPages)
})
const currentStanceArticleCount = computed(() => viewpointCards.value.reduce((sum, card) => sum + card.articleCount, 0))

/* ---------- 매핑 ---------- */
function mapIssue(item: IssueListItem | SearchIssueItem): Issue {
  return {
    id: item.issueId,
    category: item.category,
    title: item.factSummary,
    press: item.pressCount,
    articles: item.articleCount,
    summary: item.factSummary,
    time: '최근 보도',
    score: 'score' in item ? item.score : undefined,
    briefing: 'commonFactsBriefing' in item ? item.commonFactsBriefing : undefined,
  }
}

function mapArticle(article: ArticleItem): ViewArticle {
  return { id: article.articleId, source: article.company, headline: article.title, byline: article.reporter, time: formatDate(article.published), link: article.link, thumbnail: article.thumbnailUrl }
}

function formatDate(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(date)
}

function sendLog(eventType: LogEventType, payload: Record<string, unknown>) {
  void Promise.resolve(api.log(eventType, payload)).catch(() => undefined)
}

/* ---------- 1·6. 피드 ---------- */
async function loadFeed(reset = false) {
  if (!reset && (feedLoading.value || !feedHasNext.value)) return
  const requestId = ++feedRequestId
  feedLoading.value = true
  if (reset) { feedCursorValue.value = null; feedCursorId.value = null }
  try {
    const apiSort: FeedSort = sort.value === '최신순' ? 'latest' : 'trending'
    const params = { category: category.value === '전체' ? 'ALL' : category.value, sort: apiSort, cursorValue: reset ? null : feedCursorValue.value, cursorId: reset ? null : feedCursorId.value }
    const response = dateRangeActive.value
      ? await api.getIssuesByDateRange({ ...params, from: appliedDateFrom.value, to: appliedDateTo.value })
      : await api.getIssues(params)
    if (requestId !== feedRequestId) return
    const mapped = response.items.map(mapIssue)
    issues.value = reset ? mapped : [...issues.value, ...mapped.filter((item) => !issues.value.some((existing) => existing.id === item.id))]
    feedCursorValue.value = response.nextCursorValue
    feedCursorId.value = response.nextCursorId
    feedHasNext.value = response.hasNext
  } catch {
    if (requestId !== feedRequestId) return
    if (reset) issues.value = []
    feedHasNext.value = false
  } finally {
    if (requestId === feedRequestId) feedLoading.value = false
  }
}

function loadMoreFeed() {
  if (!feedLoading.value && feedHasNext.value) {
    sendLog('SCROLL_FEED', { cursorValue: feedCursorValue.value, cursorId: feedCursorId.value, category: category.value === '전체' ? 'ALL' : category.value, sort: sort.value === '최신순' ? 'latest' : 'trending' })
    void loadFeed(false)
  }
}

async function selectCategory(value: string) { category.value = value; home(); await loadFeed(true) }
async function selectSort(value: string) {
  if (sort.value === value) return
  sort.value = value
  datePickerOpen.value = false
  await loadFeed(true)
}

/* ---------- 6. 최신순 기간 선택 캘린더 ---------- */
async function applyDateRange() {
  if (!dateFromInput.value || !dateToInput.value) { dateRangeError.value = '시작일과 종료일을 모두 선택해주세요.'; return }
  if (dateFromInput.value > dateToInput.value) { dateRangeError.value = '시작일은 종료일보다 늦을 수 없습니다.'; return }
  dateRangeError.value = ''
  appliedDateFrom.value = dateFromInput.value
  appliedDateTo.value = dateToInput.value
  datePickerOpen.value = false
  await loadFeed(true)
}

async function clearDateRange() {
  dateFromInput.value = ''
  dateToInput.value = ''
  appliedDateFrom.value = ''
  appliedDateTo.value = ''
  dateRangeError.value = ''
  datePickerOpen.value = false
  await loadFeed(true)
}

function toggleDatePicker() {
  datePickerOpen.value = !datePickerOpen.value
  if (datePickerOpen.value && dateFromInput.value) {
    const [year, month] = dateFromInput.value.split('-').map(Number)
    calendarViewDate.value = new Date(year, month - 1, 1)
  }
}

function changeCalendarMonth(offset: number) {
  calendarViewDate.value = new Date(calendarViewDate.value.getFullYear(), calendarViewDate.value.getMonth() + offset, 1)
}

function selectCalendarDate(value: string) {
  dateRangeError.value = ''
  if (!dateFromInput.value || dateToInput.value) { dateFromInput.value = value; dateToInput.value = ''; return }
  if (value < dateFromInput.value) { dateToInput.value = dateFromInput.value; dateFromInput.value = value; return }
  dateToInput.value = value
}

function resetCalendarSelection() {
  dateFromInput.value = ''
  dateToInput.value = ''
  dateRangeError.value = ''
}

/* ---------- 2. 브리핑 · 관점 카드 ---------- */
const briefingFacts = computed(() => detailData.value?.commonFactsBriefing ?? [])

const viewpointCards = computed<ViewpointCard[]>(() => {
  if (detailData.value?.viewpointGroups?.length) {
    return detailData.value.viewpointGroups.map((group, index) => {
      const extra = groupArticles.value[group.groupId] ?? []
      return { number: String(index + 1).padStart(2, '0'), groupId: group.groupId, title: group.label, description: '', press: group.pressCount, articleCount: group.articleCount, remainingCount: Math.max(group.remainingCount - extra.length, 0), articles: [...group.previewArticles.map(mapArticle), ...extra] }
    })
  }
  return []
})

// 관점이 하나뿐이면 'VIEWPOINT 01 / 기타 관점' 머리말이 구분해 줄 상대가 없어서 지웁니다.
const singleViewpoint = computed(() => viewpointCards.value.length === 1)

/* ---------- 언론사 로고 ---------- */
// src/assets/press/<언론사명>.png|svg|jpg|webp 를 두면 자동으로 잡힙니다.
const pressLogoFiles = import.meta.glob('./assets/press/*.{png,svg,ico,jpg,jpeg,webp}', { eager: true, import: 'default' }) as Record<string, string>

// 로고 파일이 없는 곳은 이름 첫 글자 배지로 대체합니다.
const PRESS_COLORS: Record<string, string> = {
  연합뉴스: '#2b6b8f',
  한겨레: '#3f3f3c',
  경향신문: '#4c7c5a',
  오마이뉴스: '#b0453e',
  동아일보: '#2f5d9e',
  조선일보: '#35506e',
  세계일보: '#a2553f',
  서울신문: '#5b6bb5',
  국민일보: '#4a7ba7',
  매일경제: '#7a6aa8',
  한국경제: '#3f7f74',
}
const FALLBACK_COLORS = ['#2b6b8f', '#4c7c5a', '#b0453e', '#7a6aa8', '#a2553f', '#3f7f74', '#5b6bb5', '#3f3f3c']

function pressLogo(company: string) {
  const hit = Object.keys(pressLogoFiles).find((path) => path.slice(path.lastIndexOf('/') + 1).replace(/\.[^.]+$/, '') === company)
  return hit ? pressLogoFiles[hit] : null
}

function pressInitial(company: string) {
  return (company || '?').trim().charAt(0)
}

function pressColor(company: string) {
  if (PRESS_COLORS[company]) return PRESS_COLORS[company]
  let sum = 0
  for (const ch of company || '') sum = (sum + ch.charCodeAt(0)) % 997
  return FALLBACK_COLORS[sum % FALLBACK_COLORS.length]
}

// 서버에서 아직 받아올 수 있는 기사 수.
// hasNext 가 false 면 remainingCount 가 남아 있어도 더 가져올 수 없습니다.
// 이 값을 안 보고 remainingCount 만 믿으면, 실제로는 다 나왔는데 더보기 버튼이 남습니다.
function pendingFromServer(card: ViewpointCard) {
  // groupId 가 없으면 서버에서 더 받아올 곳이 없습니다.
  if (!card.groupId) return 0
  if (groupCursor.value[card.groupId]?.hasNext === false) return 0
  return card.remainingCount
}

// 위쪽에 보이지 않는 기사 수 = 이미 불러왔지만 접힌 것 + 아직 서버에 남은 것.
// 앞엣것을 빼먹으면 전부 불러온 뒤 접었을 때 버튼이 사라져 다시 펼칠 수 없습니다.
function hiddenCount(card: ViewpointCard) {
  return Math.max(card.articles.length - TOP_COUNT, 0) + pendingFromServer(card)
}

function articleTitle(article: ViewArticle) { return article.headline.replace('{issue}', selected.value.title) }

function briefingPreview(issue: Issue) {
  return issue.briefing ?? []
}

/* ---------- 라우팅 (히스토리) ---------- */
function applyNavigation(state: NavigationState) {
  page.value = state.page
  searchOpen.value = false
  expandedCards.value = []
  if (state.page === 'detail') {
    selected.value = issues.value.find((issue) => issue.id === state.issueId) ?? selected.value
    stance.value = '중립'
    hasRevealedRatio.value = false
  } else {
    stance.value = null
    hasRevealedRatio.value = false
    detailData.value = null
    if (state.page === 'search') { keyword.value = state.keyword ?? ''; query.value = keyword.value }
  }
  window.scrollTo(0, 0)
}

function navigate(state: NavigationState) { applyNavigation(state); window.history.pushState(state, '') }
function home() { navigate({ __hannun: true, page: 'home' }) }

// 로고 클릭 — 카테고리·정렬·기간·검색어까지 처음 들어온 상태로 되돌립니다.
// home() 은 selectCategory() 도 쓰므로 따로 둡니다(거기서 초기화하면 카테고리 선택이 바로 풀립니다).
async function resetToHome() {
  category.value = '전체'
  sort.value = '화제성순'
  query.value = ''
  keyword.value = ''
  searchOpen.value = false
  dateFromInput.value = ''
  dateToInput.value = ''
  appliedDateFrom.value = ''
  appliedDateTo.value = ''
  dateRangeError.value = ''
  datePickerOpen.value = false
  home()
  await loadFeed(true)
}

function detail(issue: Issue, referrer: 'MAIN_FEED' | 'SEARCH' = 'MAIN_FEED') {
  selected.value = issue
  // 직전에 열었던 이슈의 관점 비율·기사 목록이 새 이슈에 잠깐 노출되지 않도록 즉시 비웁니다.
  detailData.value = null
  groupArticles.value = {}
  groupCursor.value = {}
  navigate({ __hannun: true, page: 'detail', issueId: issue.id })
  sendLog('VIEW_ISSUE', { issueId: issue.id, category: issue.category, referrer })
  void loadIssueDetail(issue.id, 'neutral', 0, false, true)
}

// 서버는 요청한 관점에 기사가 없어도 빈 목록을 그대로 돌려줍니다. 중립이 0%인 이슈를
// 열면 첫 화면이 통째로 비어서, 기사가 가장 많은 관점을 찾아 한 번만 다시 부릅니다.
function fallbackStance(response: IssueDetailResponse, requested: ApiStance): ApiStance | null {
  if (response.viewpointGroups.length) return null
  let best: ApiStance | null = null
  for (const candidate of STANCES) {
    if (candidate === requested) continue
    const ratio = response.stanceRatio?.[candidate] ?? 0
    if (ratio > 0 && ratio > (best ? response.stanceRatio?.[best] ?? 0 : 0)) best = candidate
  }
  return best
}

async function loadIssueDetail(issueId: number, selectedApiStance: ApiStance, groupPage = 0, append = false, autoFallback = false) {
  const requestId = ++detailRequestId
  detailLoading.value = true
  let retryStance: ApiStance | null = null
  try {
    const response = await api.getIssue(issueId, selectedApiStance, groupPage)
    // 빠르게 관점을 바꿨을 때 늦게 도착한 이전 응답이 현재 탭과 기사 목록을 덮지 못하게 합니다.
    if (requestId !== detailRequestId) return
    // 관점 비율은 이슈 전체의 값이므로 탭 요청마다 달라지면 안 됩니다. 최초 응답값을 유지합니다.
    const previousRatio = detailData.value?.issueId === response.issueId ? detailData.value.stanceRatio : null
    if (previousRatio) response.stanceRatio = previousRatio
    if (append && detailData.value) response.viewpointGroups = [...detailData.value.viewpointGroups, ...response.viewpointGroups]
    detailData.value = response
    selected.value = { id: response.issueId, category: response.category, title: response.factSummary, press: response.pressCount, articles: response.articleCount, summary: response.factSummary, time: formatDate(response.lastReportedAt) }
    // 서버 selectedStance가 지연되거나 잘못 내려와도 사용자가 누른 관점을 선택 상태의 기준으로 삼습니다.
    stance.value = apiToStance[selectedApiStance]
    if (!append) { groupArticles.value = {}; groupCursor.value = {}; expandedCards.value = []; revealed.value = {} }
    // 긍정·부정 한쪽이 100% 면 누르기 전에도 그 사실이 곧바로 보여야 합니다(중립 100% 는 바 자체를 숨깁니다).
    if (!append && ((response.stanceRatio?.positive ?? 0) === 1 || (response.stanceRatio?.negative ?? 0) === 1)) hasRevealedRatio.value = true
    if (autoFallback && !append && groupPage === 0) retryStance = fallbackStance(response, selectedApiStance)
  } catch {
    if (requestId === detailRequestId && !append) detailData.value = null
  } finally {
    if (requestId === detailRequestId) detailLoading.value = false
  }
  // 재시도는 사용자가 직접 고른 관점에는 걸지 않습니다(빈 관점을 눌렀을 때 튕기면 안 됩니다).
  if (retryStance) { await loadIssueDetail(issueId, retryStance); return }
  void fillTopSlots()
}

async function choose(value: Stance) {
  if (detailLoading.value || stancePercent(value) === 0 || stance.value === value) return
  stance.value = value
  hasRevealedRatio.value = true
  expandedCards.value = []
  sendLog('STANCE_FILTER', { issueId: selected.value.id, stance: stanceToApi[value] })
  await loadIssueDetail(selected.value.id, stanceToApi[value])
}

function stancePercent(value: Stance) {
  const ratio = detailData.value?.stanceRatio?.[stanceToApi[value]]
  if (typeof ratio !== 'number' || !Number.isFinite(ratio)) return 0
  // API가 0~1 비율 또는 0~100 퍼센트 어느 형식으로 내려와도 동일하게 표시합니다.
  const percent = ratio <= 1 ? ratio * 100 : ratio
  return Math.min(100, Math.max(0, Math.round(percent)))
}

// 중립 기사만 존재하면 선택할 다른 관점이 없으므로 바를 숨기고 중립 기사 목록을 바로 보여줍니다.
// 합계의 반올림 오차와 관계없이 긍정·부정이 0인지로 판별합니다.
const neutralOnly = computed(() =>
  stancePercent('중립') > 0
  && stancePercent('긍정') === 0
  && stancePercent('부정') === 0,
)

function stanceSegmentClass(value: Stance) {
  const percent = stancePercent(value)
  return {
    active: stance.value === value,
    'is-zero': percent === 0,
    'is-compact': percent > 0 && percent <= 14,
    'is-tiny': percent > 0 && percent <= 5,
  }
}

/* ---------- 3. 관점그룹 기사 ---------- */
async function loadGroupArticles(groupId: number) {
  const cursor = groupCursor.value[groupId]
  if (cursor && !cursor.hasNext) return
  try {
    const response = await api.getViewpointGroupArticles(selected.value.id, groupId, cursor?.published, cursor?.articleId)
    const existing = groupArticles.value[groupId] ?? []
    // 서버가 previewArticles 를 다시 포함해 내려주므로 위에 이미 보인 기사도 걸러냅니다.
    const previewIds = new Set(
      (detailData.value?.viewpointGroups ?? []).find((g) => g.groupId === groupId)?.previewArticles.map((a) => a.articleId) ?? [],
    )
    const mapped = response.items
      .map(mapArticle)
      .filter((article) => !previewIds.has(article.id as number) && !existing.some((item) => item.id === article.id))
    groupArticles.value = { ...groupArticles.value, [groupId]: [...existing, ...mapped] }
    groupCursor.value = { ...groupCursor.value, [groupId]: { published: response.nextCursorPublished, articleId: response.nextCursorArticleId, hasNext: response.hasNext } }
  } catch {
    groupCursor.value = { ...groupCursor.value, [groupId]: { published: null, articleId: null, hasNext: false } }
  }
}

// 상단 블록은 대표기사 1건 + 관련기사 3건 = 4건으로 고정입니다.
// API 의 previewArticles 는 3건이라, 모자라면 상세를 연 뒤 한 번 더 당겨 4칸을 채웁니다.
const TOP_COUNT = 4

// 더보기는 10건씩 노출합니다. 서버가 한 번에 다 내려주든 나눠 내려주든
// 화면에서는 10건 단위로만 늘어납니다.
const REVEAL_STEP = 10
const revealed = ref<Record<string, number>>({})

function extraArticles(card: ViewpointCard) {
  return card.articles.slice(TOP_COUNT)
}

function visibleExtraArticles(card: ViewpointCard) {
  return extraArticles(card).slice(0, revealed.value[card.number] ?? REVEAL_STEP)
}

function canRevealMore(card: ViewpointCard) {
  return visibleExtraArticles(card).length < extraArticles(card).length || pendingFromServer(card) > 0
}

// 노출 목표치를 채울 만큼 서버에서 당겨옵니다(서버 페이지 크기가 10 보다 작을 수 있어서).
async function fillUpTo(card: ViewpointCard, target: number) {
  if (!card.groupId) return
  for (let i = 0; i < 5; i++) {
    if (extraArticles(card).length >= target) return
    if (groupCursor.value[card.groupId]?.hasNext === false) return
    await loadGroupArticles(card.groupId)
  }
}

async function revealMore(card: ViewpointCard) {
  const next = (revealed.value[card.number] ?? REVEAL_STEP) + REVEAL_STEP
  revealed.value = { ...revealed.value, [card.number]: next }
  await fillUpTo(card, next)
}

// previewArticles 가 4건이 안 되는 그룹은 상단 칸이 비므로 한 번만 더 불러옵니다.
async function fillTopSlots() {
  const groups = detailData.value?.viewpointGroups ?? []
  await Promise.all(
    groups.map((g) => {
      if (g.previewArticles.length >= TOP_COUNT) return undefined
      if (g.remainingCount <= 0) return undefined
      if (groupArticles.value[g.groupId]?.length) return undefined
      return loadGroupArticles(g.groupId)
    }),
  )
}

async function toggleOpinion(card: ViewpointCard) {
  if (expandedCards.value.includes(card.number)) {
    expandedCards.value = expandedCards.value.filter((number) => number !== card.number)
    return
  }
  if (card.groupId) {
    sendLog('EXPAND_GROUP', { issueId: selected.value.id, viewpointGroupId: card.groupId, remainingCount: card.remainingCount })
    revealed.value = { ...revealed.value, [card.number]: REVEAL_STEP }
    await fillUpTo(card, REVEAL_STEP)
  }
  expandedCards.value = [...expandedCards.value, card.number]
}

async function loadNextViewpointPage() {
  const info = detailData.value?.viewpointGroupPage
  if (!info || !stance.value || info.page + 1 >= info.totalPages) return
  const nextPage = info.page + 1
  sendLog('VIEWPOINT_GROUP_PAGE', { issueId: selected.value.id, page: nextPage, size: info.size })
  await loadIssueDetail(selected.value.id, stanceToApi[stance.value], nextPage, true)
}

function handleArticleClick(event: MouseEvent, card: ViewpointCard, article: ViewArticle) {
  if (!article.link) { event.preventDefault(); return }
  sendLog('VIEW_ARTICLE', { issueId: selected.value.id, viewpointGroupId: card.groupId, articleId: article.id })
}

/* ---------- 4. 검색 ---------- */
function clearRelatedSearch() {
  if (relatedSearchTimer) clearTimeout(relatedSearchTimer)
  relatedSearchTimer = null
  relatedSearchRequestId += 1
  relatedSearchLoading.value = false
  relatedSearchResults.value = []
  relatedSearchTerm.value = ''
}

function queueRelatedSearch(value = query.value) {
  if (relatedSearchTimer) clearTimeout(relatedSearchTimer)
  const term = value.trim()
  const requestId = ++relatedSearchRequestId
  relatedSearchTerm.value = term
  relatedSearchResults.value = []
  relatedSearchLoading.value = Boolean(term && searchOpen.value)
  if (!term || !searchOpen.value) return

  relatedSearchTimer = setTimeout(async () => {
    try {
      // 타이핑 중 호출 — 인기 검색어 집계에서 제외되도록 preview 를 켭니다.
      const response = await api.search({ keyword: term, category: category.value === '전체' ? undefined : category.value, preview: true })
      if (requestId !== relatedSearchRequestId || relatedSearchTerm.value !== term) return
      relatedSearchResults.value = response.items.map(mapIssue).slice(0, 6)
    } catch {
      if (requestId !== relatedSearchRequestId || relatedSearchTerm.value !== term) return
      relatedSearchResults.value = []
    } finally {
      if (requestId === relatedSearchRequestId) relatedSearchLoading.value = false
    }
  }, 120)
}

function startSearchComposition() {
  if (relatedSearchTimer) clearTimeout(relatedSearchTimer)
  relatedSearchTimer = null
  relatedSearchRequestId += 1
}

function handleSearchInput(event: Event) { queueRelatedSearch((event.target as HTMLInputElement).value) }
function finishSearchComposition(event: CompositionEvent) { queueRelatedSearch((event.target as HTMLInputElement).value) }

function highlightedSearchText(text: string) {
  const term = relatedSearchTerm.value
  if (!term) return [{ text, matched: false }]
  const source = text.toLocaleLowerCase()
  const target = term.toLocaleLowerCase()
  const parts: { text: string; matched: boolean }[] = []
  let cursor = 0
  let matchIndex = source.indexOf(target)
  while (matchIndex >= 0) {
    if (matchIndex > cursor) parts.push({ text: text.slice(cursor, matchIndex), matched: false })
    parts.push({ text: text.slice(matchIndex, matchIndex + term.length), matched: true })
    cursor = matchIndex + term.length
    matchIndex = source.indexOf(target, cursor)
  }
  if (cursor < text.length) parts.push({ text: text.slice(cursor), matched: false })
  return parts.length ? parts : [{ text, matched: false }]
}

// 인기 검색어는 홈 사이드에 상시 노출되므로 진입 시점에 불러옵니다.
async function loadPopularKeywords() {
  try {
    popularKeywords.value = (await api.getSearchSuggestions()).popularKeywords
  } catch {
    popularKeywords.value = []
  }
}

async function openSearch() {
  searchOpen.value = true
  sendLog('OPEN_SEARCH', {})
  if (query.value.trim()) queueRelatedSearch()
}

function clickPopularKeyword(word: string) { sendLog('CLICK_POPULAR_KEYWORD', { keyword: word }); query.value = word; void search(word) }
function openRelatedIssue(issue: Issue) { searchOpen.value = false; detail(issue, 'SEARCH') }

function removeRecentKeyword(word: string) {
  recent.value = recent.value.filter((item) => item !== word)
  localStorage.setItem('hannun-recent', JSON.stringify(recent.value))
}

async function search(word = query.value) {
  const value = word.trim()
  if (!value) return
  recent.value = [value, ...recent.value.filter((item) => item !== value)].slice(0, 10)
  localStorage.setItem('hannun-recent', JSON.stringify(recent.value))
  navigate({ __hannun: true, page: 'search', keyword: value })
  await loadSearch(true)
  void loadPopularKeywords()
}

async function loadSearch(reset = false) {
  if (searchLoading.value || (!reset && !searchHasNext.value)) return
  searchLoading.value = true
  if (reset) { searchCursorValue.value = null; searchCursorId.value = null; searchTopIssues.value = []; searchTopLoading.value = true }
  try {
    // 사용자가 확정한 검색 — preview:false 로 보내야 인기 검색어에 반영됩니다.
    const response = await api.search({ keyword: keyword.value, category: category.value === '전체' ? undefined : category.value, cursorValue: reset ? null : searchCursorValue.value, cursorId: reset ? null : searchCursorId.value, preview: false })
    const mapped = response.items.map(mapIssue)
    results.value = reset ? mapped : [...results.value, ...mapped.filter((item) => !results.value.some((existing) => existing.id === item.id))]
    if (reset) searchTopIssues.value = [...mapped].sort((a, b) => b.articles - a.articles).slice(0, 3)
    searchCursorValue.value = typeof response.nextCursorValue === 'number' ? response.nextCursorValue : null
    searchCursorId.value = response.nextCursorId
    searchHasNext.value = response.hasNext
  } catch {
    if (reset) { results.value = []; searchTopIssues.value = [] }
    searchHasNext.value = false
  } finally {
    searchLoading.value = false
    if (reset) searchTopLoading.value = false
  }
}

function loadMoreSearch() {
  if (!searchLoading.value && searchHasNext.value) {
    sendLog('SEARCH_SCROLL', { keyword: keyword.value, cursorValue: searchCursorValue.value, cursorId: searchCursorId.value })
    void loadSearch(false)
  }
}

/* ---------- 전역 이벤트 ---------- */
function handlePopState(event: PopStateEvent) {
  const state = event.state as NavigationState | null
  if (!state?.__hannun) return
  applyNavigation(state)
  if (state.page === 'detail' && state.issueId) void loadIssueDetail(state.issueId, 'neutral', 0, false, true)
  if (state.page === 'search') void loadSearch(true)
}

function handleDocumentClick(event: MouseEvent) {
  if (searchOpen.value && !searchBox.value?.contains(event.target as Node)) searchOpen.value = false
  if (datePickerOpen.value && event.target instanceof Element && !event.target.closest('.date-range-filter')) datePickerOpen.value = false
}

watch(feedSentinel, (element, previous) => { if (previous) feedObserver?.unobserve(previous); if (element) feedObserver?.observe(element) })
watch(searchSentinel, (element, previous) => { if (previous) searchObserver?.unobserve(previous); if (element) searchObserver?.observe(element) })
watch(searchOpen, (isOpen) => { if (!isOpen) clearRelatedSearch() })

onMounted(() => {
  try { recent.value = JSON.parse(localStorage.getItem('hannun-recent') || '[]') } catch { recent.value = [] }
  window.history.replaceState({ __hannun: true, page: 'home' } satisfies NavigationState, '')
  window.addEventListener('popstate', handlePopState)
  document.addEventListener('click', handleDocumentClick)
  feedObserver = new IntersectionObserver((entries) => { if (entries.some((entry) => entry.isIntersecting)) loadMoreFeed() }, { rootMargin: '200px' })
  searchObserver = new IntersectionObserver((entries) => { if (entries.some((entry) => entry.isIntersecting)) loadMoreSearch() }, { rootMargin: '200px' })
  void loadFeed(true)
  void loadPopularKeywords()
})

onBeforeUnmount(() => {
  clearRelatedSearch()
  window.removeEventListener('popstate', handlePopState)
  document.removeEventListener('click', handleDocumentClick)
  feedObserver?.disconnect()
  searchObserver?.disconnect()
})
</script>

<template>
  <header>
    <div class="head wrap">
      <time>{{ todayLabel }}</time>
      <button class="logo" aria-label="한눈 홈으로 이동" @click="resetToHome">
        <span class="logo-mark"><img :src="hannunLogo" alt="한눈" /></span>
        <span class="logo-tagline">사실 먼저, 관점은 원할 때</span>
      </button>
      <div ref="searchBox" class="searchbox">
        <form @submit.prevent="search()">
          <button aria-label="검색">
            <svg class="search-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none"><circle cx="10" cy="10" r="6.5" /><path d="m14.8 14.8 5.2 5.2" /></svg>
          </button>
          <input
            v-model="query"
            autocomplete="off"
            placeholder="이슈, 키워드 검색"
            aria-label="이슈 검색"
            @focus="openSearch"
            @input="handleSearchInput"
            @compositionstart="startSearchComposition"
            @compositionend="finishSearchComposition"
          />
        </form>
        <div v-if="searchOpen" class="recent">
          <section v-if="relatedSearchTerm" class="related-search">
            <div><b><strong>{{ relatedSearchTerm }}</strong> 관련 이슈</b><time v-if="relatedSearchLoading">검색 중</time></div>
            <button v-for="issue in relatedSearchResults" :key="issue.id" @click="openRelatedIssue(issue)">
              <span>{{ issue.category }}</span>
              <div>
                <b>
                  <template v-for="(part, index) in highlightedSearchText(issue.title)" :key="index">
                    <strong v-if="part.matched">{{ part.text }}</strong><template v-else>{{ part.text }}</template>
                  </template>
                </b>
                <small>{{ issue.press }}개 언론사 · 관련 기사 {{ issue.articles }}건</small>
              </div>
            </button>
            <p v-if="!relatedSearchLoading && !relatedSearchResults.length">연관된 이슈가 없습니다.</p>
          </section>
          <section v-else class="recent-words">
            <b>최근 검색어</b>
            <p v-if="!recent.length">최근 검색어가 없습니다.</p>
            <div v-else class="recent-chips">
              <div v-for="word in recent" :key="word" class="recent-word">
                <button class="recent-word-label" @click="search(word)">{{ word }}</button>
                <button class="recent-word-remove" :aria-label="`${word} 최근 검색어 삭제`" @click.stop="removeRecentKeyword(word)">×</button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
    <nav class="wrap">
      <button v-for="item in categories" :key="item" :class="{ active: category === item }" @click="selectCategory(item)">{{ item }}</button>
    </nav>
  </header>

  <main class="wrap" @click="searchOpen = false">
    <!-- 1·6. 메인 피드 -->
    <section v-if="page === 'home' && featuredIssues.length" class="hero" aria-labelledby="hero-title">
        <div class="hero-head"><span>TOP ISSUES</span><h2 id="hero-title">화제성 높은 이슈</h2></div>
        <div class="hero-grid">
          <a v-for="(issue, index) in featuredIssues" :key="issue.id" :href="`?issue=${issue.id}`" @click.prevent="detail(issue)">
            <div><em>{{ String(index + 1).padStart(2, '0') }}</em><span>{{ issue.category }}</span></div>
            <h3>{{ issue.title }}</h3>
            <div class="hero-brief">
              <ol><li v-for="fact in briefingPreview(issue)" :key="fact">{{ fact }}</li></ol>
            </div>
            <p>{{ issue.press }}개 언론사 · 관련 기사 <strong>{{ issue.articles }}건</strong></p>
          </a>
        </div>
      </section>

    <!-- 홈과 상세가 같은 2단 레이아웃을 공유합니다(오른쪽 인기 검색어). -->
    <div v-if="page !== 'search'" class="layout" :class="{ 'is-detail': page === 'detail' }">
        <section v-if="page === 'home'" class="feed">
          <div class="title">
            <div>
              <button :class="{ active: sort === '화제성순' }" @click="selectSort('화제성순')">화제성순</button>
              <button :class="{ active: sort === '최신순' }" @click="selectSort('최신순')">최신순</button>
            </div>
            <form v-if="sort === '최신순'" class="date-range-filter" @submit.prevent="applyDateRange">
              <span>{{ dateRangeActive ? '기간 기준' : '실시간 기준' }}</span>
              <button class="date-picker-trigger" type="button" :aria-expanded="datePickerOpen" @click="toggleDatePicker">{{ dateRangeLabel }} <b>▾</b></button>
              <button v-if="dateRangeActive" class="date-range-reset" type="button" :disabled="feedLoading" @click="clearDateRange">초기화</button>
              <div v-if="datePickerOpen" class="date-picker" @click.stop>
                <div class="date-picker-head">
                  <button type="button" aria-label="이전 달" @click="changeCalendarMonth(-1)">‹</button>
                  <strong>{{ calendarTitle }}</strong>
                  <button type="button" aria-label="다음 달" @click="changeCalendarMonth(1)">›</button>
                </div>
                <div class="date-picker-week"><span v-for="day in ['일', '월', '화', '수', '목', '금', '토']" :key="day">{{ day }}</span></div>
                <div class="date-picker-days" :class="{ ranged: dateFromInput && dateToInput }">
                  <template v-for="day in calendarDays" :key="day.key">
                    <button v-if="day.label" type="button" :class="{ selected: day.selected, 'in-range': day.inRange, start: day.isStart, end: day.isEnd }" @click="selectCalendarDate(day.date)">{{ day.label }}</button>
                    <span v-else></span>
                  </template>
                </div>
                <p>{{ dateFromInput ? (dateToInput ? `${dateFromInput}부터 ${dateToInput}까지` : '종료일을 선택해주세요.') : '시작일을 선택해주세요.' }}</p>
                <div class="date-picker-actions">
                  <button type="button" @click="resetCalendarSelection">다시 선택</button>
                  <button type="submit" :disabled="feedLoading || !dateFromInput || !dateToInput">적용</button>
                </div>
              </div>
              <small v-if="dateRangeError" role="alert">{{ dateRangeError }}</small>
            </form>
          </div>

          <article v-for="issue in feed" :key="issue.id">
            <a class="feed-card" :href="`?issue=${issue.id}`" @click.prevent="detail(issue)">
              <div class="feed-article-body">
                <div class="feed-kicker"><span>{{ issue.category }}</span><small>·　{{ issue.time }}</small></div>
                <h3>{{ issue.title }}</h3>
                <div class="feed-meta-row">
                  <div class="feed-meta"><span>{{ issue.press }}개 언론사</span><i>·</i><span>관련 기사 <strong>{{ issue.articles }}건</strong> 묶음</span></div>
                </div>
              </div>
              <div class="feed-briefing-preview">
                <strong>공통사실 브리핑</strong>
                <ol><li v-for="fact in briefingPreview(issue)" :key="fact">{{ fact }}</li></ol>
              </div>
            </a>
          </article>

          <div v-if="feedLoading && !feed.length" class="loading">뉴스를 불러오는 중입니다…</div>
          <div v-else-if="!feed.length" class="empty">
            <b>표시할 이슈가 없습니다.</b>
            <p v-if="dateRangeActive">{{ appliedDateFrom }} ~ {{ appliedDateTo }} 기간에 해당하는 이슈가 없습니다. 기간을 넓혀보세요.</p>
            <p v-else-if="category !== '전체'">‘{{ category }}’ 카테고리에 표시할 이슈가 없습니다. 다른 카테고리를 선택해보세요.</p>
            <p v-else>아직 수집된 이슈가 없습니다. 잠시 후 다시 확인해주세요.</p>
          </div>

          <button v-if="feedHasNext" ref="feedSentinel" class="more" :disabled="feedLoading" @click="loadMoreFeed">
            {{ feedLoading ? '뉴스를 불러오는 중입니다　○' : '더 많은 뉴스 불러오기' }}
          </button>
        </section>

      <div v-else class="detail-main">
      <section class="detail">
        <span>{{ selected.category }}</span>
        <h1>{{ selected.title }}</h1>
        <p>최초 보도 {{ formatDate(detailData?.firstReportedAt) }}　 최근 보도 {{ formatDate(detailData?.lastReportedAt) }}　 {{ selected.press }}개 언론사　 기사 {{ selected.articles }}건</p>
        <div v-if="detailData && !neutralOnly" class="stanceBtns detail-stance" :class="{ 'ratio-mode': hasRevealedRatio }" aria-label="관점 선택">
          <button
            v-for="item in (['긍정', '중립', '부정'] as Stance[])"
            :key="item"
            :class="stanceSegmentClass(item)"
            :style="{ '--ratio': stancePercent(item) }"
            :aria-label="hasRevealedRatio ? `${item} ${stancePercent(item)}%` : item"
            :disabled="detailLoading || stancePercent(item) === 0"
            @click="choose(item)"
          >
            <span v-if="!hasRevealedRatio || stancePercent(item) > 0">{{ item }}</span>
            <b v-if="hasRevealedRatio && stancePercent(item) > 0">{{ stancePercent(item) }}%</b>
          </button>
        </div>
      </section>

      <section class="briefing">
        <div class="briefing-head">
          <div><label>COMMON FACTS</label><h2>공통사실 브리핑</h2></div>
        </div>
        <ol class="briefing-sentences">
          <li v-for="fact in briefingFacts" :key="fact"><span class="briefing-text">{{ fact }}</span></li>
        </ol>
      </section>

      <section class="view">
        <div class="stances">
          <div v-if="stance" class="group">
            <div class="opinion-stack">
              <article v-for="card in viewpointCards" :key="card.groupId ?? card.number" class="opinion-card">
                <div class="opinion-head"><span v-if="!singleViewpoint">VIEWPOINT {{ card.number }}</span><small>{{ card.press }}개 언론사 · 기사 {{ card.articleCount }}건</small></div>
                <h3 v-if="!singleViewpoint">{{ card.title }}</h3>
                <p v-if="card.description" class="opinion-summary">{{ card.description }}</p>

                <div v-if="card.articles.length" class="opinion-news-grid">
                  <a class="latest-news" :href="card.articles[0].link || '#'" target="_blank" rel="noopener noreferrer" @click="handleArticleClick($event, card, card.articles[0])">
                    <img v-if="card.articles[0].thumbnail" :src="card.articles[0].thumbnail" :alt="`${card.articles[0].source} 최신 기사`" />
                    <span class="source">
                      <img v-if="pressLogo(card.articles[0].source)" class="press-logo" :src="pressLogo(card.articles[0].source)!" :alt="`${card.articles[0].source} 로고`" />
                      <i v-else class="press-logo" :style="{ background: pressColor(card.articles[0].source) }" aria-hidden="true">{{ pressInitial(card.articles[0].source) }}</i>
                      {{ card.articles[0].source }}
                    </span>
                    <b>{{ articleTitle(card.articles[0]) }}</b>
                    <small>{{ card.articles[0].time }} · {{ card.articles[0].byline }}</small>
                  </a>
                  <div class="other-news">
                    <a
                      v-for="article in card.articles.slice(1, TOP_COUNT)"
                      :key="article.id ?? `${article.source}-${article.headline}`"
                      :href="article.link || '#'"
                      target="_blank"
                      rel="noopener noreferrer"
                      @click="handleArticleClick($event, card, article)"
                    >
                      <span class="source">
                        <img v-if="pressLogo(article.source)" class="press-logo" :src="pressLogo(article.source)!" :alt="`${article.source} 로고`" />
                        <i v-else class="press-logo" :style="{ background: pressColor(article.source) }" aria-hidden="true">{{ pressInitial(article.source) }}</i>
                        {{ article.source }}
                      </span>
                      <b>{{ articleTitle(article) }}</b>
                      <small>{{ article.time }} · {{ article.byline }}</small>
                    </a>
                  </div>
                </div>

                <div v-if="expandedCards.includes(card.number)" class="expanded-news">
                  <a
                    v-for="article in visibleExtraArticles(card)"
                    :key="article.id ?? `${article.source}-${article.headline}`"
                    :href="article.link || '#'"
                    target="_blank"
                    rel="noopener noreferrer"
                    @click="handleArticleClick($event, card, article)"
                  >
                    <div>
                      <span class="source">
                        <img v-if="pressLogo(article.source)" class="press-logo" :src="pressLogo(article.source)!" :alt="`${article.source} 로고`" />
                        <i v-else class="press-logo" :style="{ background: pressColor(article.source) }" aria-hidden="true">{{ pressInitial(article.source) }}</i>
                        {{ article.source }}
                      </span>
                      <b>{{ articleTitle(article) }}</b>
                      <small>{{ article.time }} · {{ article.byline }}</small>
                    </div>
                    <em>↗</em>
                  </a>
                  <button v-if="canRevealMore(card)" class="opinion-more" @click="revealMore(card)">기사 더 보기 ↓</button>
                </div>

                <button v-if="hiddenCount(card) > 0 || expandedCards.includes(card.number)" class="opinion-more" @click="toggleOpinion(card)">
                  {{ expandedCards.includes(card.number) ? '관련 기사 접기 ↑' : '관련 기사 더보기 ↓' }}
                </button>
              </article>

              <p v-if="detailLoading" class="guide">관점 묶음을 불러오는 중입니다.</p>
              <p v-else-if="!viewpointCards.length" class="guide">이 관점으로 분류된 보도가 없습니다.</p>
              <button v-else-if="hasNextViewpointPage" class="coverage-more" @click="loadNextViewpointPage">다음 관점 묶음 불러오기 ›</button>
              <p v-else class="guide">현재 관점 기사 {{ currentStanceArticleCount }}건</p>
            </div>
          </div>
        </div>
      </section>
      </div>

        <aside v-if="popularKeywords.length" class="trends" aria-labelledby="trends-title">
          <div class="trends-head"><span>REALTIME</span><h2 id="trends-title">인기 검색어</h2></div>
          <ol class="trend-list">
            <li v-for="(word, index) in popularKeywords" :key="word">
              <button @click="clickPopularKeyword(word)"><em>{{ index + 1 }}</em><span>{{ word }}</span></button>
            </li>
          </ol>
        </aside>
    </div>

    <!-- 4-2. 검색 결과 -->
    <template v-if="page === 'search'">
      <section class="results">
        <label>SEARCH RESULTS</label>
        <h1>‘{{ keyword }}’ 검색 결과</h1>
        <p>개별 기사가 아닌 관련 이슈를 모아 보여드립니다.</p>

        <section class="search-top-issues" aria-labelledby="search-top-title">
          <div class="search-top-head"><div><span>TOP ISSUES</span><h2 id="search-top-title">관련 주요 뉴스</h2></div></div>
          <div class="search-top-grid">
            <a v-for="(issue, index) in searchTopIssues" :key="issue.id" :href="`?issue=${issue.id}`" @click.prevent="detail(issue, 'SEARCH')">
              <div><em>{{ String(index + 1).padStart(2, '0') }}</em><span>{{ issue.category }}</span></div>
              <h3>{{ issue.title }}</h3>
              <p>{{ issue.press }}개 언론사 · 관련 기사 <strong>{{ issue.articles }}건</strong></p>
            </a>
            <div v-for="index in (searchTopLoading ? 3 : 0)" :key="`top-loading-${index}`" class="search-top-skeleton" aria-hidden="true"></div>
          </div>
        </section>

        <div class="search-list-head"><b>검색 결과</b></div>
        <div class="list">
          <article v-for="issue in results" :key="issue.id" class="search-result-item" @click="detail(issue, 'SEARCH')">
            <span>{{ issue.category }}</span>
            <div><h3>{{ issue.title }}</h3><small>{{ issue.press }}개 언론사 · 관련 기사 <strong>{{ issue.articles }}건</strong></small></div>
            <b aria-hidden="true">›</b>
          </article>
          <div v-if="!results.length && !searchLoading" class="empty"><b>검색 결과가 없습니다.</b><p>다른 키워드로 다시 검색해보세요.</p></div>
          <button v-if="searchHasNext" ref="searchSentinel" class="more" :disabled="searchLoading" @click="loadMoreSearch">
            {{ searchLoading ? '검색 결과를 불러오는 중입니다　○' : '검색 결과 더보기' }}
          </button>
        </div>
      </section>
    </template>
  </main>

  <footer>
    <div class="wrap"><b>한눈</b><span>복잡한 뉴스의 핵심을 한눈에</span><small>© 2026 HANNUN NEWS</small></div>
  </footer>
</template>
