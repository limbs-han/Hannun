<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api, type ApiStance, type ArticleItem, type FeedSort, type IssueDetailResponse, type IssueListItem, type SearchIssueItem } from './api'
import hannunLogo from './assets/hannun-logo-transparent.png'
import summitNewsImage from './assets/summit-news.png'

type Issue = { id: number; category: string; title: string; press: number; articles: number; summary: string; time: string; score?: number; briefing?: string[] }
type Stance = '긍정' | '중립' | '부정'
type ViewArticle = { id?: number; source: string; headline: string; byline: string; time: string; link?: string; thumbnail?: string | null }
type ViewGroup = { press: number; articles: number; summary: string; lead: ViewArticle; related: ViewArticle[] }
type BriefingFact = { text: string; source?: string; url?: string; headline?: string; time?: string }
type PageName = 'home' | 'detail' | 'search'
type NavigationState = { __hannun: true; page: PageName; issueId?: number; keyword?: string }
type ViewpointCard = { number: string; groupId?: number; title: string; description: string; press: number; articleCount: number; remainingCount: number; articles: ViewArticle[] }

const mockIssues: Issue[] = [
  { id: 1, category: '정치', title: '한·미 정상회담, 안보·경제 협력 확대에 공감', press: 25, articles: 322, summary: '정상회담에서 양국은 안보 협력과 경제 현안에 대한 공조 확대 방안을 논의했습니다.', time: '1시간 전' },
  { id: 2, category: '경제', title: '한은, 기준금리 연 2.25% 동결…“성장과 물가 균형 필요”', press: 21, articles: 282, summary: '한국은행은 대내외 경제 여건과 금융시장 상황을 종합적으로 고려해 기준금리를 동결했습니다.', time: '2시간 전' },
  { id: 3, category: '사회', title: '수도권 집중호우로 2명 사망·7,000여 명 대피', press: 18, articles: 242, summary: '집중호우가 이어지며 침수 피해가 늘어 정부가 긴급 대응과 주민 대피를 지원하고 있습니다.', time: '2시간 전' },
  { id: 4, category: '정치', title: '여야, 민생 법안 처리 위한 임시국회 일정 합의', press: 28, articles: 121, summary: '여야가 주요 민생 법안의 우선 처리와 상임위원회 일정에 합의했습니다.', time: '3시간 전' },
  { id: 5, category: '세계', title: '주요국 정상회의 개막, 기후 대응 공동선언 논의', press: 25, articles: 98, summary: '각국 정상은 기후위기 공동 대응과 에너지 전환을 위한 협력 방안을 논의합니다.', time: '4시간 전' },
  { id: 6, category: '경제', title: '가계대출 증가세 다시 확대…금융당국 “관리 강화”', press: 22, articles: 87, summary: '최근 가계대출이 다시 늘면서 금융당국이 전 금융권의 대출 관리 강화를 주문했습니다.', time: '5시간 전' },
  { id: 7, category: 'IT', title: '정부, AI 기본법 시행령 입법 예고…산업 지원 본격화', press: 18, articles: 64, summary: '인공지능 산업 육성과 신뢰 기반 조성을 위한 세부 기준이 마련됩니다.', time: '6시간 전' },
  { id: 8, category: '경제', title: '국제 유가 3%대 상승…에너지 시장 변동성 확대', press: 16, articles: 58, summary: '주요 산유국의 공급 전망 변화로 국제 유가가 상승하며 시장 변동성이 커졌습니다.', time: '7시간 전' },
  { id: 9, category: '사회', title: '청년층 고용률 석 달 연속 하락…맞춤 대책 추진', press: 15, articles: 51, summary: '청년 고용 지표가 둔화하면서 정부가 산업별 맞춤형 일자리 지원책을 추진합니다.', time: '8시간 전' },
  { id: 10, category: '세계', title: '우크라이나 재건 회의, 국제사회 주요 합의 발표', press: 14, articles: 46, summary: '국제사회가 우크라이나 재건을 위한 재정 지원과 장기 협력 방안을 발표했습니다.', time: '9시간 전' },
]

const categories = ['정치', '경제', '사회', 'IT', '세계']
const stanceToApi: Record<Stance, ApiStance> = { 긍정: 'positive', 중립: 'neutral', 부정: 'negative' }
const apiToStance: Record<ApiStance, Stance> = { positive: '긍정', neutral: '중립', negative: '부정' }

const articleGroups: Record<Stance, ViewGroup> = {
  긍정: { press: 8, articles: 11, summary: '예상되는 긍정적 효과와 향후 기대를 중심으로 보도한 기사들입니다.', lead: { source: '비즈포커스', headline: '{issue}…협력 확대가 가져올 기대 효과', byline: '이다온 기자', time: '45분 전' }, related: [{ source: '경제인사이트', headline: '전문가들 “후속 협의가 성과로 이어질 것”', byline: '박지훈 기자', time: '1시간 전' }, { source: '데일리뷰', headline: '주요 합의 내용과 산업계가 기대하는 변화', byline: '최서윤 기자', time: '2시간 전' }, { source: '포커스뉴스', headline: '협력 확대, 국내 시장에 새로운 기회 될까', byline: '오현우 기자', time: '3시간 전' }] },
  중립: { press: 12, articles: 24, summary: '확인된 사실과 핵심 내용, 남은 과제를 균형 있게 정리한 기사들입니다.', lead: { source: '뉴스라인', headline: '{issue}…핵심 내용과 향후 일정', byline: '김한결 기자', time: '30분 전' }, related: [{ source: '하루뉴스', headline: '이번 이슈에서 확인된 주요 사실 5가지', byline: '정민서 기자', time: '1시간 전' }, { source: '시사브리프', headline: '주요 발표 내용과 추가로 확인해야 할 쟁점', byline: '유지현 기자', time: '2시간 전' }, { source: '데일리리포트', headline: '시간순으로 보는 주요 경과와 관계자 발언', byline: '한유진 기자', time: '3시간 전' }] },
  부정: { press: 7, articles: 9, summary: '실효성과 후속 조치, 예상되는 한계를 짚은 기사들입니다.', lead: { source: '이슈저널', headline: '{issue}…실효성과 후속 조치는 아직 과제', byline: '서지민 기자', time: '50분 전' }, related: [{ source: '팩트포커스', headline: '표현보다 실행이 중요…확인할 세부 조건', byline: '김우주 기자', time: '1시간 전' }, { source: '시사인사이드', headline: '엇갈리는 평가, 아직 남아 있는 세 가지 쟁점', byline: '문예린 기자', time: '2시간 전' }, { source: '뉴스체크', headline: '반복된 약속과 불투명한 일정을 따져보니', byline: '이선우 기자', time: '4시간 전' }] },
}

const viewpointNotes: Record<Stance, string[]> = {
  긍정: ['협력의 실질적 효과와 산업·사회적 파급을 기대하는 견해입니다.', '후속 협의가 예정대로 이어진다면 구체적인 성과가 가능하다는 견해입니다.', '이번 발표가 국내 시장과 관련 산업에 새로운 기회를 열 수 있다는 견해입니다.'],
  중립: ['현재까지 확인된 합의 내용과 향후 일정을 중심으로 보는 견해입니다.', '발표된 사실과 관계자 발언을 바탕으로 핵심 쟁점을 정리한 견해입니다.', '결과를 단정하기보다 후속 조치와 실행 과정을 지켜봐야 한다는 견해입니다.'],
  부정: ['표현된 합의에 비해 구체적인 실행 방안이 부족하다는 견해입니다.', '예정된 후속 조치가 실제 성과로 이어질지 불투명하다는 견해입니다.', '과거의 유사한 약속과 비교할 때 실효성을 더 엄격히 확인해야 한다는 견해입니다.'],
}

const companionArticles: Record<Stance, ViewArticle[]> = {
  긍정: [{ source: '오늘브리프', headline: '{issue}…현장이 기대하는 새로운 기회', byline: '강서현 기자', time: '1시간 전' }, { source: '트렌드뉴스', headline: '후속 협력 논의, 성과로 이어지려면', byline: '임도윤 기자', time: '2시간 전' }, { source: '비즈리포트', headline: '산업계가 본 주요 기회와 예상 효과', byline: '전하윤 기자', time: '4시간 전' }],
  중립: [{ source: '오늘브리프', headline: '{issue}…확인된 사실과 아직 남은 과제', byline: '강서현 기자', time: '1시간 전' }, { source: '팩트데일리', headline: '관계자 발언으로 본 핵심 쟁점', byline: '임도윤 기자', time: '2시간 전' }, { source: '이슈리포트', headline: '후속 일정과 앞으로 확인할 세부 내용', byline: '전하윤 기자', time: '4시간 전' }],
  부정: [{ source: '오늘브리프', headline: '{issue}…실행 방안은 왜 빠졌나', byline: '강서현 기자', time: '1시간 전' }, { source: '팩트데일리', headline: '후속 조치의 한계와 현실적인 변수', byline: '임도윤 기자', time: '2시간 전' }, { source: '이슈리포트', headline: '유사 사례와 비교한 실효성 점검', byline: '전하윤 기자', time: '4시간 전' }],
}

const additionalArticles: ViewArticle[] = [{ source: '현장리포트', headline: '{issue} 관련 현장 반응과 후속 일정', byline: '백지안 기자', time: '5시간 전' }, { source: '뉴스인사이트', headline: '전문가들이 짚은 핵심 변수와 예상 시나리오', byline: '송민준 기자', time: '6시간 전' }, { source: '오늘의쟁점', headline: '발표 이후 남은 쟁점과 추가로 확인할 과제', byline: '노서연 기자', time: '7시간 전' }]
const viewpointTotals = [{ press: 18, articles: 242 }, { press: 15, articles: 187 }, { press: 12, articles: 134 }]

const page = ref<PageName>('home')
const category = ref('전체')
const sort = ref('화제성순')
const issues = ref<Issue[]>([...mockIssues])
const selected = ref<Issue>(mockIssues[0])
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
const defaultPopularKeywords = [
  '한국',
  '재개발 규제 완화',
  'AI 기본법',
  '한·미 정상회담',
  '기준금리 동결',
  '수도권 집중호우',
  '민생 법안',
  '기후 대응',
  '가계대출',
  '국제 유가',
]
const popularKeywords = ref<string[]>([...defaultPopularKeywords])
const detailData = ref<IssueDetailResponse | null>(null)
const detailLoading = ref(false)
const feedLoading = ref(false)
const feedHasNext = ref(false)
const feedCursorValue = ref<number | string | null>(null)
const feedCursorId = ref<number | null>(null)
const results = ref<Issue[]>([])
const searchLoading = ref(false)
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
let sessionId = ''

const feed = computed(() => issues.value)
const currentGroup = computed(() => (stance.value ? articleGroups[stance.value] : null))
const hasNextViewpointPage = computed(() => {
  const info = detailData.value?.viewpointGroupPage
  return Boolean(info && info.page + 1 < info.totalPages)
})
const currentStanceArticleCount = computed(() => viewpointCards.value.reduce((sum, card) => sum + card.articleCount, 0))

function mapIssue(item: IssueListItem | SearchIssueItem): Issue {
  return { id: item.issueId, category: item.category, title: item.factSummary, press: item.pressCount, articles: item.articleCount, summary: item.factSummary, time: '최근 보도', score: 'score' in item ? item.score : undefined, briefing: 'commonFactsBriefing' in item ? item.commonFactsBriefing : undefined }
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

function fallbackFeed() {
  const filtered = category.value === '전체' ? mockIssues : mockIssues.filter((issue) => issue.category === category.value)
  return [...filtered].sort((a, b) => sort.value === '최신순' ? b.id - a.id : b.articles - a.articles)
}

async function loadFeed(reset = false) {
  if (feedLoading.value || (!reset && !feedHasNext.value)) return
  feedLoading.value = true
  if (reset) { feedCursorValue.value = null; feedCursorId.value = null }
  try {
    const response = await api.getIssues({ category: category.value === '전체' ? 'ALL' : category.value, sort: (sort.value === '최신순' ? 'latest' : 'trending') satisfies FeedSort, cursorValue: reset ? null : feedCursorValue.value, cursorId: reset ? null : feedCursorId.value })
    const mapped = response.items.map(mapIssue)
    issues.value = reset ? mapped : [...issues.value, ...mapped.filter((item) => !issues.value.some((existing) => existing.id === item.id))]
    feedCursorValue.value = response.nextCursorValue
    feedCursorId.value = response.nextCursorId
    feedHasNext.value = response.hasNext
  } catch {
    if (reset) issues.value = fallbackFeed()
    feedHasNext.value = false
  } finally { feedLoading.value = false }
}

function loadMoreFeed() {
  if (!feedLoading.value && feedHasNext.value) {
    sendLog('SCROLL_FEED', { cursorValue: feedCursorValue.value, cursorId: feedCursorId.value, category: category.value === '전체' ? 'ALL' : category.value, sort: sort.value === '최신순' ? 'latest' : 'trending' })
    void loadFeed(false)
  }
}

async function selectCategory(value: string) { category.value = value; home(); await loadFeed(true) }
async function selectSort(value: string) { sort.value = value; await loadFeed(true) }

const briefingFacts = computed<BriefingFact[]>(() => {
  if (detailData.value?.commonFactsBriefing?.length) return detailData.value.commonFactsBriefing.map((text) => ({ text }))
  return [
    { text: `${selected.value.title} 관련 공식 발표가 있었으며, 핵심 의제와 합의 방향이 공개됐습니다.`, source: '연합뉴스', url: 'https://www.yna.co.kr/', headline: `${selected.value.title}…공식 발표 핵심 내용`, time: '30분 전' },
    { text: '현재까지 확인된 내용은 관계 기관의 발표와 현장 브리핑을 통해 교차 확인됐습니다.', source: 'KBS', url: 'https://news.kbs.co.kr/', headline: '관계 기관 발표로 확인한 주요 사실과 쟁점', time: '1시간 전' },
    { text: '구체적인 실행 일정과 세부 방안은 향후 후속 협의를 통해 확정될 예정입니다.', source: '한국일보', url: 'https://www.hankookilbo.com/', headline: '후속 협의에서 결정될 일정과 세부 과제', time: '2시간 전' },
  ]
})

const viewpointCards = computed<ViewpointCard[]>(() => {
  if (detailData.value?.viewpointGroups?.length) {
    return detailData.value.viewpointGroups.map((group, index) => {
      const extra = groupArticles.value[group.groupId] ?? []
      return { number: String(index + 1).padStart(2, '0'), groupId: group.groupId, title: group.label, description: '', press: group.pressCount, articleCount: group.articleCount, remainingCount: Math.max(group.remainingCount - extra.length, 0), articles: [...group.previewArticles.map(mapArticle), ...extra] }
    })
  }
  if (!stance.value || !currentGroup.value) return []
  const base = [currentGroup.value.lead, ...currentGroup.value.related].slice(0, 3)
  return base.map((article, index) => ({ number: String(index + 1).padStart(2, '0'), title: articleTitle(article), description: viewpointNotes[stance.value!][index], press: viewpointTotals[index].press, articleCount: viewpointTotals[index].articles, remainingCount: 2, articles: [article, companionArticles[stance.value!][index], currentGroup.value!.related[Math.min(index + 1, currentGroup.value!.related.length - 1)], additionalArticles[index], additionalArticles[(index + 1) % additionalArticles.length], additionalArticles[(index + 2) % additionalArticles.length]] }))
})

function applyNavigation(state: NavigationState) {
  page.value = state.page; searchOpen.value = false; expandedCards.value = []
  if (state.page === 'detail') { selected.value = issues.value.find((issue) => issue.id === state.issueId) ?? selected.value; stance.value = '중립'; hasRevealedRatio.value = false }
  else { stance.value = null; hasRevealedRatio.value = false; detailData.value = null; if (state.page === 'search') { keyword.value = state.keyword ?? ''; query.value = keyword.value } }
  window.scrollTo(0, 0)
}

function navigate(state: NavigationState) { applyNavigation(state); window.history.pushState(state, '') }
function home() { navigate({ __hannun: true, page: 'home' }) }

function detail(issue: Issue, referrer: 'MAIN_FEED' | 'SEARCH' = 'MAIN_FEED') {
  selected.value = issue
  navigate({ __hannun: true, page: 'detail', issueId: issue.id })
  sendLog('VIEW_ISSUE', { issueId: issue.id, category: issue.category, referrer })
  void loadIssueDetail(issue.id, 'neutral')
}

async function loadIssueDetail(issueId: number, selectedApiStance: ApiStance, groupPage = 0, append = false) {
  if (detailLoading.value) return
  detailLoading.value = true
  try {
    const response = await api.getIssue(issueId, selectedApiStance, groupPage)
    if (append && detailData.value) response.viewpointGroups = [...detailData.value.viewpointGroups, ...response.viewpointGroups]
    detailData.value = response
    selected.value = { id: response.issueId, category: response.category, title: response.factSummary, press: response.pressCount, articles: response.articleCount, summary: response.factSummary, time: formatDate(response.lastReportedAt) }
    stance.value = apiToStance[response.selectedStance]
    if (!append) { groupArticles.value = {}; groupCursor.value = {}; expandedCards.value = [] }
  } catch { if (!append) detailData.value = null }
  finally { detailLoading.value = false }
}

async function choose(value: Stance) {
  stance.value = value; hasRevealedRatio.value = true; expandedCards.value = []
  sendLog('STANCE_FILTER', { issueId: selected.value.id, stance: stanceToApi[value] })
  await loadIssueDetail(selected.value.id, stanceToApi[value])
}

function stancePercent(value: Stance) {
  const ratio = detailData.value?.stanceRatio?.[stanceToApi[value]]
  if (typeof ratio === 'number') return Math.round(ratio * 100)
  return value === '긍정' ? 32 : value === '중립' ? 46 : 22
}

function stanceSegmentClass(value: Stance) {
  const percent = stancePercent(value)
  return {
    active: stance.value === value,
    'is-zero': percent === 0,
    'is-compact': percent > 0 && percent <= 14,
    'is-tiny': percent > 0 && percent <= 5,
  }
}

function articleTitle(article: ViewArticle) { return article.headline.replace('{issue}', selected.value.title) }
function briefingPreview(issue: Issue) { return issue.briefing?.length ? issue.briefing : [issue.summary, `${issue.press}개 언론사의 관련 보도를 바탕으로 핵심 내용을 교차 확인했습니다.`, `관련 기사 ${issue.articles}건에서 공통으로 확인되는 사실과 후속 쟁점을 정리했습니다.`] }

async function loadGroupArticles(groupId: number) {
  const cursor = groupCursor.value[groupId]
  if (cursor && !cursor.hasNext) return
  try {
    const response = await api.getViewpointGroupArticles(selected.value.id, groupId, cursor?.published, cursor?.articleId)
    const existing = groupArticles.value[groupId] ?? []
    const mapped = response.items.map(mapArticle).filter((article) => !existing.some((item) => item.id === article.id))
    groupArticles.value = { ...groupArticles.value, [groupId]: [...existing, ...mapped] }
    groupCursor.value = { ...groupCursor.value, [groupId]: { published: response.nextCursorPublished, articleId: response.nextCursorArticleId, hasNext: response.hasNext } }
  } catch { groupCursor.value = { ...groupCursor.value, [groupId]: { published: null, articleId: null, hasNext: false } } }
}

async function toggleOpinion(card: ViewpointCard) {
  if (expandedCards.value.includes(card.number)) { expandedCards.value = expandedCards.value.filter((number) => number !== card.number); return }
  if (card.groupId) { sendLog('EXPAND_GROUP', { issueId: selected.value.id, viewpointGroupId: card.groupId, remainingCount: card.remainingCount }); if (!(groupArticles.value[card.groupId]?.length)) await loadGroupArticles(card.groupId) }
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
      const response = await api.search({ keyword: term, category: category.value === '전체' ? undefined : category.value })
      if (requestId !== relatedSearchRequestId || relatedSearchTerm.value !== term) return
      relatedSearchResults.value = response.items.map(mapIssue).slice(0, 6)
    } catch {
      if (requestId !== relatedSearchRequestId || relatedSearchTerm.value !== term) return
      relatedSearchResults.value = mockIssues.filter((issue) => `${issue.title} ${issue.summary} ${issue.category}`.includes(term)).slice(0, 6)
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

function handleSearchInput(event: Event) {
  queueRelatedSearch((event.target as HTMLInputElement).value)
}

function finishSearchComposition(event: CompositionEvent) {
  const value = (event.target as HTMLInputElement).value
  queueRelatedSearch(value)
}

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

async function openSearch() {
  searchOpen.value = true; sendLog('OPEN_SEARCH', {})
  if (query.value.trim()) { queueRelatedSearch(); return }
  try {
    const response = await api.getSearchSuggestions()
    popularKeywords.value = [...new Set([...response.popularKeywords, ...defaultPopularKeywords])].slice(0, 10)
  } catch { /* 목업 유지 */ }
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
}

async function loadSearch(reset = false) {
  if (searchLoading.value || (!reset && !searchHasNext.value)) return
  searchLoading.value = true
  if (reset) { searchCursorValue.value = null; searchCursorId.value = null }
  try {
    const response = await api.search({ keyword: keyword.value, category: category.value === '전체' ? undefined : category.value, cursorValue: reset ? null : searchCursorValue.value, cursorId: reset ? null : searchCursorId.value })
    const mapped = response.items.map(mapIssue)
    results.value = reset ? mapped : [...results.value, ...mapped.filter((item) => !results.value.some((existing) => existing.id === item.id))]
    searchCursorValue.value = typeof response.nextCursorValue === 'number' ? response.nextCursorValue : null
    searchCursorId.value = response.nextCursorId
    searchHasNext.value = response.hasNext
  } catch { if (reset) results.value = mockIssues.filter((issue) => `${issue.title} ${issue.summary} ${issue.category}`.includes(keyword.value)); searchHasNext.value = false }
  finally { searchLoading.value = false }
}

function loadMoreSearch() { if (!searchLoading.value && searchHasNext.value) { sendLog('SEARCH_SCROLL', { keyword: keyword.value, cursorValue: searchCursorValue.value, cursorId: searchCursorId.value }); void loadSearch(false) } }
function sendLog(eventType: Parameters<typeof api.log>[1], payload: Record<string, unknown>) { if (sessionId) void api.log(sessionId, eventType, payload).catch(() => undefined) }

function handlePopState(event: PopStateEvent) {
  const state = event.state as NavigationState | null
  if (!state?.__hannun) return
  applyNavigation(state)
  if (state.page === 'detail' && state.issueId) void loadIssueDetail(state.issueId, 'neutral')
  if (state.page === 'search') void loadSearch(true)
}

function handleDocumentClick(event: MouseEvent) { if (searchOpen.value && !searchBox.value?.contains(event.target as Node)) searchOpen.value = false }
watch(feedSentinel, (element, previous) => { if (previous) feedObserver?.unobserve(previous); if (element) feedObserver?.observe(element) })
watch(searchSentinel, (element, previous) => { if (previous) searchObserver?.unobserve(previous); if (element) searchObserver?.observe(element) })
watch(searchOpen, (isOpen) => { if (!isOpen) clearRelatedSearch() })

onMounted(() => {
  try { recent.value = JSON.parse(localStorage.getItem('hannun-recent') || '[]') } catch { recent.value = [] }
  sessionId = localStorage.getItem('hannun-session-id') || `sess_${crypto.randomUUID()}`
  localStorage.setItem('hannun-session-id', sessionId)
  window.history.replaceState({ __hannun: true, page: 'home' } satisfies NavigationState, '')
  window.addEventListener('popstate', handlePopState); document.addEventListener('click', handleDocumentClick)
  feedObserver = new IntersectionObserver((entries) => { if (entries.some((entry) => entry.isIntersecting)) loadMoreFeed() }, { rootMargin: '200px' })
  searchObserver = new IntersectionObserver((entries) => { if (entries.some((entry) => entry.isIntersecting)) loadMoreSearch() }, { rootMargin: '200px' })
  void loadFeed(true)
})

onBeforeUnmount(() => { clearRelatedSearch(); window.removeEventListener('popstate', handlePopState); document.removeEventListener('click', handleDocumentClick); feedObserver?.disconnect(); searchObserver?.disconnect() })
</script>

<template>
  <header>
    <div class="head wrap">
      <time>2026년 8월 27일 목요일</time>
      <button class="logo" aria-label="한눈 홈으로 이동" @click="home">
        <span class="logo-mark"><img :src="hannunLogo" alt="한눈"></span>
        <span class="logo-tagline">사실 먼저, 관점은 원할 때</span>
      </button>
      <div ref="searchBox" class="searchbox">
        <form @submit.prevent="search()"><input v-model="query" autocomplete="off" @focus="openSearch" @input="handleSearchInput" @compositionstart="startSearchComposition" @compositionend="finishSearchComposition" placeholder="이슈, 키워드 검색" aria-label="이슈 검색"><button aria-label="검색"><svg class="search-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none"><circle cx="10" cy="10" r="6.5"/><path d="m14.8 14.8 5.2 5.2"/></svg></button></form>
        <div v-if="searchOpen" class="recent">
          <section v-if="relatedSearchTerm" class="related-search">
            <div><b><strong>{{ relatedSearchTerm }}</strong> 관련 이슈</b><time v-if="relatedSearchLoading">검색 중</time></div>
            <button v-for="issue in relatedSearchResults" :key="issue.id" @click="openRelatedIssue(issue)"><span>{{ issue.category }}</span><div><b><template v-for="(part, index) in highlightedSearchText(issue.title)" :key="index"><strong v-if="part.matched">{{ part.text }}</strong><template v-else>{{ part.text }}</template></template></b><small>{{ issue.press }}개 언론사 · 관련 기사 {{ issue.articles }}건</small></div></button>
            <p v-if="!relatedSearchLoading && !relatedSearchResults.length">연관된 이슈가 없습니다.</p>
          </section>
          <template v-else>
            <section class="recent-words"><b>최근 검색어</b><p v-if="!recent.length">최근 검색어가 없습니다.</p><div v-for="word in recent" :key="word" class="recent-word"><button class="recent-word-label" @click="search(word)">{{ word }}</button><button class="recent-word-remove" :aria-label="`${word} 최근 검색어 삭제`" @click.stop="removeRecentKeyword(word)">×</button></div></section>
            <section class="search-trends"><div><b>인기 검색어</b><time>실시간</time></div><button v-for="(word, index) in popularKeywords" :key="word" @click="clickPopularKeyword(word)"><em>{{ index + 1 }}</em><span>{{ word }}</span></button></section>
          </template>
        </div>
      </div>
    </div>
    <nav class="wrap"><button v-for="item in categories" :key="item" :class="{ active: category === item }" @click="selectCategory(item)">{{ item }}</button></nav>
  </header>

  <main class="wrap" @click="searchOpen = false">
    <template v-if="page === 'home'">
      <div class="layout"><section class="feed">
        <div class="title"><div><button :class="{ active: sort === '화제성순' }" @click="selectSort('화제성순')">화제성순</button><button :class="{ active: sort === '최신순' }" @click="selectSort('최신순')">최신순</button></div><time>실시간 기준</time></div>
        <article v-for="issue in feed" :key="issue.id" tabindex="0" @click="detail(issue)" @keydown.enter="detail(issue)">
          <div class="feed-article-body"><div class="feed-kicker"><span>{{ issue.category }}</span><small>·　{{ issue.time }}</small></div><h3>{{ issue.title }}</h3><div class="feed-meta">{{ issue.press }}개 언론사　·　관련 기사 {{ issue.articles }}건 묶음</div></div>
          <div class="feed-briefing-preview"><strong>COMMON FACTS<br>공통사실 브리핑</strong><ol><li v-for="fact in briefingPreview(issue)" :key="fact">{{ fact }}</li></ol></div>
        </article>
        <button v-if="feedHasNext" ref="feedSentinel" class="more" :disabled="feedLoading" @click="loadMoreFeed">{{ feedLoading ? '뉴스를 불러오는 중입니다　○' : '더 많은 뉴스 불러오기' }}</button>
      </section></div>
    </template>

    <template v-else-if="page === 'detail'">
      <section class="detail">
        <span>{{ selected.category }}</span><h1>{{ selected.title }}</h1>
        <p>최초 보도 {{ formatDate(detailData?.firstReportedAt) || '2026.08.27 08:30' }}　 최근 보도 {{ formatDate(detailData?.lastReportedAt) || '14:20' }}　 {{ selected.press }}개 언론사　 기사 {{ selected.articles }}건</p>
        <div class="stanceBtns detail-stance" :class="{ 'ratio-mode': hasRevealedRatio }" aria-label="관점 선택">
          <button v-for="item in (['긍정', '중립', '부정'] as Stance[])" :key="item" :class="stanceSegmentClass(item)" :style="{ '--ratio': stancePercent(item) }" :aria-label="hasRevealedRatio ? `${item} ${stancePercent(item)}%` : item" @click="choose(item)"><span v-if="!hasRevealedRatio || stancePercent(item) > 0">{{ item }}</span><b v-if="stancePercent(item) > 0">{{ stancePercent(item) }}%</b></button>
        </div>
      </section>

      <section class="briefing">
        <div class="briefing-head"><div><label>COMMON FACTS</label><h2>공통사실 브리핑</h2></div><small>{{ briefingFacts.length }}개 핵심 사실</small></div>
        <ol class="briefing-sentences"><li v-for="fact in briefingFacts" :key="fact.text"><span class="briefing-text">{{ fact.text }}</span></li></ol>
      </section>

      <section class="view"><div class="stances"><div v-if="stance" class="group"><div class="opinion-stack">
        <article v-for="card in viewpointCards" :key="card.groupId ?? card.number" class="opinion-card">
          <div class="opinion-head"><span>VIEWPOINT {{ card.number }}</span><small>{{ card.press }}개 언론사 · 기사 {{ card.articleCount }}건</small></div><h3>{{ card.title }}</h3><p v-if="card.description" class="opinion-summary">{{ card.description }}</p>
          <div v-if="card.articles.length" class="opinion-news-grid">
            <a class="latest-news" :href="card.articles[0].link || '#'" target="_blank" rel="noopener noreferrer" @click="handleArticleClick($event, card, card.articles[0])"><img :src="card.articles[0].thumbnail || summitNewsImage" :alt="`${card.articles[0].source} 최신 기사`"><span class="source">{{ card.articles[0].source }}</span><b>{{ articleTitle(card.articles[0]) }}</b><small>{{ card.articles[0].time }} · {{ card.articles[0].byline }}</small></a>
            <div class="other-news"><a v-for="article in card.articles.slice(1, 4)" :key="article.id ?? `${article.source}-${article.headline}`" :href="article.link || '#'" target="_blank" rel="noopener noreferrer" @click="handleArticleClick($event, card, article)"><span class="source">{{ article.source }}</span><b>{{ articleTitle(article) }}</b><small>{{ article.time }} · {{ article.byline }}</small></a></div>
          </div>
          <div v-if="expandedCards.includes(card.number)" class="expanded-news">
            <a v-for="article in card.articles.slice(4)" :key="article.id ?? `${article.source}-${article.headline}`" :href="article.link || '#'" target="_blank" rel="noopener noreferrer" @click="handleArticleClick($event, card, article)"><span class="source">{{ article.source }}</span><div><b>{{ articleTitle(article) }}</b><small>{{ article.time }} · {{ article.byline }}</small></div><em>↗</em></a>
            <button v-if="card.groupId && groupCursor[card.groupId]?.hasNext" class="opinion-more" @click="loadGroupArticles(card.groupId)">기사 더 불러오기 ↓</button>
          </div>
          <button v-if="card.remainingCount > 0 || expandedCards.includes(card.number)" class="opinion-more" @click="toggleOpinion(card)">{{ expandedCards.includes(card.number) ? '관련 기사 접기 ↑' : `관련 기사 ${card.remainingCount}건 더보기 ↓` }}</button>
        </article>
        <button v-if="hasNextViewpointPage" class="coverage-more" @click="loadNextViewpointPage">다음 관점 묶음 불러오기 ›</button><p v-else-if="detailLoading" class="guide">관점 묶음을 불러오는 중입니다.</p><p v-else class="guide">현재 관점 기사 {{ currentStanceArticleCount }}건</p>
      </div></div></div></section>
    </template>

    <template v-else>
      <section class="results"><label>SEARCH RESULTS</label><h1>‘{{ keyword }}’ 검색 결과</h1><p>개별 기사가 아닌 관련 이슈를 모아 보여드립니다.</p><div class="list">
        <article v-for="issue in results" :key="issue.id" @click="detail(issue, 'SEARCH')"><span>{{ issue.category }}</span><div><h3>{{ issue.title }}</h3><small>{{ issue.press }}개 언론사 · 기사 {{ issue.articles }}건</small></div><b>→</b></article>
        <div v-if="!results.length && !searchLoading" class="empty"><b>검색 결과가 없습니다.</b><p>다른 키워드로 다시 검색해보세요.</p></div>
        <button v-if="searchHasNext" ref="searchSentinel" class="more" :disabled="searchLoading" @click="loadMoreSearch">{{ searchLoading ? '검색 결과를 불러오는 중입니다　○' : '검색 결과 더보기' }}</button>
      </div></section>
    </template>
  </main>
  <footer><div class="wrap"><b>한눈</b><span>복잡한 뉴스의 핵심을 한눈에</span><small>© 2026 HANNUN NEWS</small></div></footer>
</template>
