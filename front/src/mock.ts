// 명세서 응답 스키마를 그대로 흉내낸 목 데이터.
// BE 연결 전 디자인·상호작용 확인용. VITE_API_BASE_URL 을 채우면 httpApi 로 교체됩니다.
import thumb from './assets/hero.png'
import type {
  ApiStance,
  ArticleCursorResponse,
  ArticleItem,
  CursorIssueResponse,
  HannunApi,
  IssueDetailResponse,
  IssueListItem,
  SearchResponse,
  ViewpointGroup,
} from './api'
import { STANCES } from './api'

const PAGE = 9
const GROUP_PAGE = 2
const NETWORK_DELAY = 260

const delay = <T>(value: T): Promise<T> => new Promise((r) => setTimeout(() => r(value), NETWORK_DELAY))

// 확정 검색만 집계합니다(preview 제외). 실제 서버가 하는 일을 흉내낸 것입니다.
const confirmedSearches = new Map<string, number>()

interface Seed {
  issueId: number
  category: string
  pressCount: number
  articleCount: number
  score: number
  factSummary: string
  commonFactsBriefing: string[]
  firstReportedAt: string
  lastReportedAt: string
}

const SEEDS: Seed[] = [
  {
    issueId: 90123,
    category: '정치',
    pressCount: 47,
    articleCount: 213,
    score: 982,
    factSummary: '한·미 정상이 안보·경제 협력 확대 방안에 공감했다.',
    commonFactsBriefing: [
      '양국 정상은 8월 26일 정상회담을 열고 공동성명을 발표했다.',
      '성명에는 확장억제 협의체 정례화가 명시됐다.',
      '반도체·배터리 공급망 협력 워킹그룹을 신설한다.',
      '후속 장관급 회의는 10월 중 개최 예정이다.',
    ],
    firstReportedAt: '2026-08-26T09:12:00+09:00',
    lastReportedAt: '2026-08-27T13:48:00+09:00',
  },
  {
    issueId: 90124,
    category: '경제',
    pressCount: 31,
    articleCount: 282,
    score: 907,
    factSummary: '한국은행이 기준금리를 연 2.25%로 동결했다.',
    commonFactsBriefing: [
      '금융통화위원회는 8월 27일 기준금리를 연 2.25%로 유지했다.',
      '동결 결정은 만장일치가 아니었고 인하 소수의견이 1명 있었다.',
      '한은은 올해 성장률 전망치를 기존과 같은 수준으로 제시했다.',
      '다음 금통위는 10월에 열린다.',
    ],
    firstReportedAt: '2026-08-27T09:00:00+09:00',
    lastReportedAt: '2026-08-27T14:20:00+09:00',
  },
  {
    issueId: 90125,
    category: '사회',
    pressCount: 19,
    articleCount: 242,
    score: 861,
    factSummary: '수도권 집중호우로 2명이 사망하고 7,000여 명이 대피했다.',
    commonFactsBriefing: [
      '8월 26일부터 수도권에 시간당 50mm 이상 비가 내렸다.',
      '중앙재난안전대책본부는 대응 2단계를 가동했다.',
      '하천 11곳에 홍수주의보가 발령됐다.',
    ],
    firstReportedAt: '2026-08-26T18:30:00+09:00',
    lastReportedAt: '2026-08-27T12:05:00+09:00',
  },
  {
    issueId: 90126,
    category: '정치',
    pressCount: 28,
    articleCount: 121,
    score: 744,
    factSummary: '여야가 민생 법안 처리를 위한 임시국회 일정에 합의했다.',
    commonFactsBriefing: [
      '양당 원내대표는 8월 27일 임시국회 의사일정에 합의했다.',
      '본회의는 9월 3일과 9월 10일 두 차례 열린다.',
      '우선 처리 법안은 14건으로 정리됐다.',
    ],
    firstReportedAt: '2026-08-27T10:40:00+09:00',
    lastReportedAt: '2026-08-27T13:10:00+09:00',
  },
  {
    issueId: 90127,
    category: '세계',
    pressCount: 25,
    articleCount: 98,
    score: 690,
    factSummary: '주요국 정상회의가 개막해 기후 대응 공동선언을 논의한다.',
    commonFactsBriefing: [
      '정상회의는 8월 27일 개막해 이틀간 진행된다.',
      '의장국은 공동선언 초안에 2035년 감축목표를 포함시켰다.',
      '에너지 전환 기금 조성 방안이 별도 의제로 올랐다.',
    ],
    firstReportedAt: '2026-08-27T08:00:00+09:00',
    lastReportedAt: '2026-08-27T11:30:00+09:00',
  },
  {
    issueId: 90128,
    category: '경제',
    pressCount: 22,
    articleCount: 87,
    score: 612,
    factSummary: '가계대출 증가세가 다시 확대돼 금융당국이 관리 강화를 주문했다.',
    commonFactsBriefing: [
      '7월 가계대출 잔액은 전월 대비 4조원 늘었다.',
      '금융당국은 전 금융권에 자체 관리계획 제출을 요구했다.',
      '주택담보대출이 증가분의 대부분을 차지했다.',
    ],
    firstReportedAt: '2026-08-25T09:20:00+09:00',
    lastReportedAt: '2026-08-27T10:00:00+09:00',
  },
  {
    issueId: 90129,
    category: 'IT',
    pressCount: 18,
    articleCount: 64,
    score: 578,
    factSummary: '정부가 AI 기본법 시행령을 입법 예고했다.',
    commonFactsBriefing: [
      '시행령안은 8월 27일 입법예고에 들어갔다.',
      '고위험 AI 판단 기준과 영향평가 절차가 포함됐다.',
      '의견 수렴 기간은 40일이다.',
    ],
    firstReportedAt: '2026-08-27T09:30:00+09:00',
    lastReportedAt: '2026-08-27T12:40:00+09:00',
  },
  {
    issueId: 90130,
    category: '경제',
    pressCount: 16,
    articleCount: 58,
    score: 520,
    factSummary: '국제 유가가 3%대 상승하며 에너지 시장 변동성이 커졌다.',
    commonFactsBriefing: [
      '브렌트유는 전일 대비 3.2% 올라 마감했다.',
      '주요 산유국이 증산 계획을 유보한 것이 상승 요인으로 지목됐다.',
    ],
    firstReportedAt: '2026-08-26T22:10:00+09:00',
    lastReportedAt: '2026-08-27T09:50:00+09:00',
  },
  {
    issueId: 90131,
    category: '사회',
    pressCount: 15,
    articleCount: 51,
    score: 466,
    factSummary: '청년층 고용률이 석 달 연속 하락해 맞춤 대책이 추진된다.',
    commonFactsBriefing: [
      '7월 청년층 고용률은 전년 동월 대비 0.8%p 하락했다.',
      '정부는 산업별 맞춤형 지원안을 9월에 발표한다.',
    ],
    firstReportedAt: '2026-08-24T09:00:00+09:00',
    lastReportedAt: '2026-08-27T08:30:00+09:00',
  },
  {
    issueId: 90132,
    category: '세계',
    pressCount: 14,
    articleCount: 46,
    score: 410,
    factSummary: '우크라이나 재건 회의에서 국제사회가 주요 합의를 발표했다.',
    commonFactsBriefing: [
      '참가국은 3년간 단계별 재정 지원에 합의했다.',
      '재건 사업 우선순위는 에너지망 복구로 정해졌다.',
    ],
    firstReportedAt: '2026-08-22T17:00:00+09:00',
    lastReportedAt: '2026-08-26T20:15:00+09:00',
  },
  {
    issueId: 90133,
    category: 'IT',
    pressCount: 12,
    articleCount: 39,
    score: 362,
    factSummary: '통신 3사가 5G 요금제 개편안을 공개했다.',
    commonFactsBriefing: [
      '3사는 8월 26일 중저가 구간 요금제를 신설했다.',
      '신규 요금제는 9월 1일부터 가입 가능하다.',
    ],
    firstReportedAt: '2026-08-26T11:00:00+09:00',
    lastReportedAt: '2026-08-27T09:10:00+09:00',
  },
  {
    issueId: 90134,
    category: '사회',
    pressCount: 11,
    articleCount: 33,
    score: 318,
    factSummary: '교육부가 대입 전형 간소화 방안을 발표했다.',
    commonFactsBriefing: [
      '전형 수를 대학별 6개 이내로 제한하는 방안이 담겼다.',
      '적용 시점은 2029학년도 입시부터다.',
    ],
    firstReportedAt: '2026-08-21T14:00:00+09:00',
    lastReportedAt: '2026-08-26T16:40:00+09:00',
  },
]

const GROUP_LABELS: Record<ApiStance, string[]> = {
  positive: ['A-1 경제적 기대 효과', 'A-2 사회적 형평성', 'A-3 외교 성과 평가'],
  neutral: ['B-1 사실관계 정리', 'B-2 일정·절차 안내', 'B-3 해외 사례 비교'],
  negative: ['C-1 재정 부담 우려', 'C-2 실효성 의문', 'C-3 절차적 논란'],
}

// 실제 수집 대상 언론사 (03_수집_정책.md 기준 10곳 + 통신사)
const COMPANIES = ['연합뉴스', '한겨레', '경향신문', '오마이뉴스', '동아일보', '조선일보', '세계일보', '서울신문', '국민일보', '매일경제', '한국경제']
const REPORTERS = ['김한눈', '이기자', '최기자', '정기자', '한기자', '오기자', '박기자', '윤기자', '장기자']

const toItem = (s: Seed): IssueListItem => ({
  issueId: s.issueId,
  category: s.category,
  pressCount: s.pressCount,
  articleCount: s.articleCount,
  score: s.score,
  factSummary: s.factSummary,
  commonFactsBriefing: s.commonFactsBriefing,
})

function article(seed: Seed, stance: ApiStance, groupId: number, n: number): ArticleItem {
  const tone =
    stance === 'positive' ? '기대 효과에 무게' : stance === 'neutral' ? '쟁점과 일정 정리' : '부담과 한계 지적'
  const published = new Date(new Date(seed.lastReportedAt).getTime() - n * 3600_000).toISOString()
  return {
    articleId: groupId * 1000 + n,
    company: COMPANIES[n % COMPANIES.length],
    title: `${seed.factSummary.replace(/\.$/, '')} — ${tone}`,
    link: 'https://example.com/article',
    published,
    category: seed.category,
    categoryStr: `${seed.category}>주요이슈`,
    reporter: REPORTERS[n % REPORTERS.length],
    thumbnailUrl: n % 3 === 0 ? thumb : null,
  }
}

function groupsFor(seed: Seed, stance: ApiStance): ViewpointGroup[] {
  return GROUP_LABELS[stance].map((label, i) => {
    const groupId = seed.issueId * 10 + STANCES.indexOf(stance) * 3 + i
    const articleCount = Math.max(6, Math.round(seed.articleCount / (4 + i * 2)))
    const previewArticles = [0, 1, 2].map((n) => article(seed, stance, groupId, n))
    return {
      groupId,
      label,
      stance,
      articleCount,
      pressCount: Math.max(3, Math.round(seed.pressCount / (2 + i))),
      previewArticles,
      remainingCount: articleCount - previewArticles.length,
    }
  })
}

// score(trending) / lastReportedAt(latest) 커서를 명세대로 흉내냅니다.
function paginate(seeds: Seed[], sort: 'trending' | 'latest', cursorValue?: number | string | null, cursorId?: number | null): CursorIssueResponse {
  const sorted = [...seeds].sort((a, b) =>
    sort === 'latest'
      ? b.lastReportedAt.localeCompare(a.lastReportedAt) || b.issueId - a.issueId
      : b.score - a.score || b.issueId - a.issueId,
  )
  let start = 0
  if (cursorValue != null && cursorId != null) {
    const at = sorted.findIndex((s) => s.issueId === cursorId)
    start = at < 0 ? 0 : at + 1
  }
  const slice = sorted.slice(start, start + PAGE)
  const last = slice[slice.length - 1]
  const hasNext = start + PAGE < sorted.length
  return {
    items: slice.map(toItem),
    nextCursorValue: hasNext && last ? (sort === 'latest' ? last.lastReportedAt : last.score) : null,
    nextCursorId: hasNext && last ? last.issueId : null,
    hasNext,
  }
}

const overlaps = (seed: Seed, from: string, to: string) =>
  seed.firstReportedAt.slice(0, 10) <= to && seed.lastReportedAt.slice(0, 10) >= from

export const mockApi: HannunApi = {
  getIssues({ category, sort = 'trending', cursorValue, cursorId }) {
    const pool = category === 'ALL' ? SEEDS : SEEDS.filter((s) => s.category === category)
    return delay(paginate(pool, sort, cursorValue, cursorId))
  },

  getIssuesByDateRange({ category, from, to, sort = 'trending', cursorValue, cursorId }) {
    const pool = (category === 'ALL' ? SEEDS : SEEDS.filter((s) => s.category === category)).filter((s) =>
      overlaps(s, from, to),
    )
    return delay(paginate(pool, sort, cursorValue, cursorId))
  },

  getIssue(issueId, stance, page = 0) {
    const seed = SEEDS.find((s) => s.issueId === issueId) ?? SEEDS[0]
    const all = groupsFor(seed, stance)
    const start = page * GROUP_PAGE
    const detail: IssueDetailResponse = {
      issueId: seed.issueId,
      category: seed.category,
      firstReportedAt: seed.firstReportedAt,
      lastReportedAt: seed.lastReportedAt,
      pressCount: seed.pressCount,
      articleCount: seed.articleCount,
      factSummary: seed.factSummary,
      commonFactsBriefing: seed.commonFactsBriefing,
      stanceRatio: { positive: 0.42, neutral: 0.21, negative: 0.37 },
      selectedStance: stance,
      viewpointGroups: all.slice(start, start + GROUP_PAGE),
      viewpointGroupPage: {
        page,
        size: GROUP_PAGE,
        totalCount: all.length,
        totalPages: Math.max(1, Math.ceil(all.length / GROUP_PAGE)),
      },
    }
    return delay(detail)
  },

  getViewpointGroupArticles(issueId, groupId, _cursorPublished, cursorArticleId) {
    const seed = SEEDS.find((s) => s.issueId === issueId) ?? SEEDS[0]
    const stance = STANCES[Math.floor(((groupId - seed.issueId * 10) % 9) / 3)] ?? 'neutral'
    const group = groupsFor(seed, stance).find((g) => g.groupId === groupId)
    const total = group?.articleCount ?? 12
    const from = cursorArticleId ? (cursorArticleId % 1000) + 1 : 3
    const items = Array.from({ length: Math.min(3, Math.max(0, total - from)) }, (_, i) =>
      article(seed, stance, groupId, from + i),
    )
    const last = items[items.length - 1]
    const hasNext = from + items.length < total
    const res: ArticleCursorResponse = {
      items,
      nextCursorPublished: hasNext && last ? last.published : null,
      nextCursorArticleId: hasNext && last ? last.articleId : null,
      hasNext,
    }
    return delay(res)
  },

  getSearchSuggestions() {
    const counted = [...confirmedSearches.entries()].sort((a, b) => b[1] - a[1]).map(([word]) => word)
    const base = ['한·미 정상회담', '기준금리', '집중호우', 'AI 기본법', '가계대출', '국제 유가']
    return delay({ popularKeywords: [...new Set([...counted, ...base])].slice(0, 10) })
  },

  search({ keyword, category, cursorValue, cursorId, preview }) {
    // preview 호출은 집계에서 빼고, 확정 검색(첫 페이지)만 셉니다.
    if (!preview && cursorId == null) confirmedSearches.set(keyword, (confirmedSearches.get(keyword) ?? 0) + 1)
    const hit = SEEDS.filter(
      (s) =>
        (!category || category === 'ALL' || s.category === category) &&
        `${s.factSummary} ${s.category} ${s.commonFactsBriefing.join(' ')}`.includes(keyword),
    )
    let start = 0
    if (cursorValue != null && cursorId != null) {
      const at = hit.findIndex((s) => s.issueId === cursorId)
      start = at < 0 ? 0 : at + 1
    }
    const slice = hit.slice(start, start + PAGE)
    const last = slice[slice.length - 1]
    const hasNext = start + PAGE < hit.length
    const res: SearchResponse = {
      resultType: 'LIST',
      keyword,
      items: slice.map((s) => ({
        issueId: s.issueId,
        category: s.category,
        factSummary: s.factSummary,
        articleCount: s.articleCount,
        pressCount: s.pressCount,
      })),
      nextCursorValue: hasNext && last ? last.score : null,
      nextCursorId: hasNext && last ? last.issueId : null,
      hasNext,
    }
    return delay(res)
  },

  async log(eventType, payload) {
    // 목 모드에서는 콘솔로만 확인합니다. 실제 수집은 httpApi.log 가 POST /api/logs 로 보냅니다.
    console.debug('[log]', eventType, payload)
  },
}
