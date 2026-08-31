<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import summitNewsImage from './assets/summit-news.png'
type Issue={id:number;category:string;title:string;press:number;articles:number;summary:string;time:string}
type Stance='긍정'|'중립'|'부정'
type ViewArticle={source:string;headline:string;byline:string;time:string}
type ViewGroup={press:number;articles:number;summary:string;lead:ViewArticle;related:ViewArticle[]}
type BriefingFact={text:string;source:string;url:string;headline:string;time:string}
type PageName='home'|'detail'|'search'
type NavigationState={__hannun:true;page:PageName;issueId?:number;keyword?:string}
const issues:Issue[]=[
 {id:1,category:'정치',title:'한·미 정상회담, 안보·경제 협력 확대에 공감',press:25,articles:322,summary:'정상회담에서 양국은 안보 협력과 경제 현안에 대한 공조 확대 방안을 논의했습니다.',time:'1시간 전'},
 {id:2,category:'경제',title:'한은, 기준금리 연 2.25% 동결…“성장과 물가 균형 필요”',press:21,articles:282,summary:'한국은행은 대내외 경제 여건과 금융시장 상황을 종합적으로 고려해 기준금리를 동결했습니다.',time:'2시간 전'},
 {id:3,category:'사회',title:'수도권 집중호우로 2명 사망·7,000여 명 대피',press:18,articles:242,summary:'집중호우가 이어지며 침수 피해가 늘어 정부가 긴급 대응과 주민 대피를 지원하고 있습니다.',time:'2시간 전'},
 {id:4,category:'정치',title:'여야, 민생 법안 처리 위한 임시국회 일정 합의',press:28,articles:121,summary:'여야가 주요 민생 법안의 우선 처리와 상임위원회 일정에 합의했습니다.',time:'3시간 전'},
 {id:5,category:'생활/문화',title:'주요국 정상회의 개막, 기후 대응 공동선언 논의',press:25,articles:98,summary:'각국 정상은 기후위기 공동 대응과 에너지 전환을 위한 협력 방안을 논의합니다.',time:'4시간 전'},
 {id:6,category:'경제',title:'가계대출 증가세 다시 확대…금융당국 “관리 강화”',press:22,articles:87,summary:'최근 가계대출이 다시 늘면서 금융당국이 전 금융권의 대출 관리 강화를 주문했습니다.',time:'5시간 전'},
 {id:7,category:'IT/과학',title:'정부, AI 기본법 시행령 입법 예고…산업 지원 본격화',press:18,articles:64,summary:'인공지능 산업 육성과 신뢰 기반 조성을 위한 세부 기준이 마련됩니다.',time:'6시간 전'},
 {id:8,category:'경제',title:'국제 유가 3%대 상승…에너지 시장 변동성 확대',press:16,articles:58,summary:'주요 산유국의 공급 전망 변화로 국제 유가가 상승하며 시장 변동성이 커졌습니다.',time:'7시간 전'},
 {id:9,category:'사회',title:'청년층 고용률 석 달 연속 하락…맞춤 대책 추진',press:15,articles:51,summary:'청년 고용 지표가 둔화하면서 정부가 산업별 맞춤형 일자리 지원책을 추진합니다.',time:'8시간 전'},
 {id:10,category:'생활/문화',title:'우크라이나 재건 회의, 국제사회 주요 합의 발표',press:14,articles:46,summary:'국제사회가 우크라이나 재건을 위한 재정 지원과 장기 협력 방안을 발표했습니다.',time:'9시간 전'}]
const categories=['정치','경제','사회','생활/문화','IT/과학']
const articleGroups:Record<Stance,ViewGroup>={
 '긍정':{press:8,articles:11,summary:'예상되는 긍정적 효과와 향후 기대를 중심으로 보도한 기사들입니다.',lead:{source:'비즈포커스',headline:'{issue}…협력 확대가 가져올 기대 효과',byline:'이다온 기자',time:'45분 전'},related:[{source:'경제인사이트',headline:'전문가들“후속 협의가 성과로 이어질 것”',byline:'박지훈 기자',time:'1시간 전'},{source:'데일리뷰',headline:'주요 합의 내용과 산업계가 기대하는 변화',byline:'최서윤 기자',time:'2시간 전'},{source:'포커스뉴스',headline:'협력 확대, 국내 시장에 새로운 기회 될까',byline:'오현우 기자',time:'3시간 전'}]},
 '중립':{press:12,articles:24,summary:'확인된 사실과 핵심 내용, 남은 과제를 균형 있게 정리한 기사들입니다.',lead:{source:'뉴스라인',headline:'{issue}…핵심 내용과 향후 일정',byline:'김한결 기자',time:'30분 전'},related:[{source:'하루뉴스',headline:'이번 이슈에서 확인된 주요 사실 5가지',byline:'정민서 기자',time:'1시간 전'},{source:'시사브리프',headline:'주요 발표 내용과 추가로 확인해야 할 쟁점',byline:'유지현 기자',time:'2시간 전'},{source:'데일리리포트',headline:'시간순으로 보는 주요 경과와 관계자 발언',byline:'한유진 기자',time:'3시간 전'}]},
 '부정':{press:7,articles:9,summary:'실효성과 후속 조치, 예상되는 한계를 짚은 기사들입니다.',lead:{source:'이슈저널',headline:'{issue}…실효성과 후속 조치는 아직 과제',byline:'서지민 기자',time:'50분 전'},related:[{source:'팩트포커스',headline:'표현보다 실행이 중요…확인할 세부 조건',byline:'김우주 기자',time:'1시간 전'},{source:'시사인사이드',headline:'엇갈리는 평가, 아직 남아 있는 세 가지 쟁점',byline:'문예린 기자',time:'2시간 전'},{source:'뉴스체크',headline:'반복된 약속과 불투명한 일정을 따져보니',byline:'이선우 기자',time:'4시간 전'}]}
}
const page=ref<PageName>('home'), category=ref('전체'), sort=ref('화제성순'), selected=ref(issues[0]), query=ref(''), keyword=ref(''), searchOpen=ref(false), stance=ref<Stance|null>(null), hasRevealedRatio=ref(false), evidenceOpen=ref(false), recent=ref<string[]>([]), count=ref(5)
const feed=computed(()=>issues.filter(i=>category.value==='전체'||i.category===category.value).slice(0,count.value))
const results=computed(()=>issues.filter(i=>`${i.title} ${i.category}`.includes(keyword.value)))
const currentGroup=computed(()=>stance.value?articleGroups[stance.value]:null)
const briefingFacts=computed<BriefingFact[]>(()=>[
 {text:`${selected.value.title} 관련 공식 발표가 있었으며, 핵심 의제와 합의 방향이 공개됐습니다.`,source:'연합뉴스',url:'https://www.yna.co.kr/',headline:`${selected.value.title}…공식 발표 핵심 내용`,time:'30분 전'},
 {text:'현재까지 확인된 내용은 관계 기관의 발표와 현장 브리핑을 통해 교차 확인됐습니다.',source:'KBS',url:'https://news.kbs.co.kr/',headline:'관계 기관 발표로 확인한 주요 사실과 쟁점',time:'1시간 전'},
 {text:'구체적인 실행 일정과 세부 방안은 향후 후속 협의를 통해 확정될 예정입니다.',source:'한국일보',url:'https://www.hankookilbo.com/',headline:'후속 협의에서 결정될 일정과 세부 과제',time:'2시간 전'}
])
const viewpointNotes:Record<Stance,string[]>={
 '긍정':['협력의 실질적 효과와 산업·사회적 파급을 기대하는 견해입니다.','후속 협의가 예정대로 이어진다면 구체적인 성과가 가능하다는 견해입니다.','이번 발표가 국내 시장과 관련 산업에 새로운 기회를 열 수 있다는 견해입니다.'],
 '중립':['현재까지 확인된 합의 내용과 향후 일정을 중심으로 보는 견해입니다.','발표된 사실과 관계자 발언을 바탕으로 핵심 쟁점을 정리한 견해입니다.','결과를 단정하기보다 후속 조치와 실행 과정을 지켜봐야 한다는 견해입니다.'],
 '부정':['표현된 합의에 비해 구체적인 실행 방안이 부족하다는 견해입니다.','예정된 후속 조치가 실제 성과로 이어질지 불투명하다는 견해입니다.','과거의 유사한 약속과 비교할 때 실효성을 더 엄격히 확인해야 한다는 견해입니다.']}
const companionArticles:Record<Stance,ViewArticle[]>={
 '긍정':[{source:'오늘브리프',headline:'{issue}…현장이 기대하는 새로운 기회',byline:'강서현 기자',time:'1시간 전'},{source:'트렌드뉴스',headline:'후속 협력 논의, 성과로 이어지려면',byline:'임도윤 기자',time:'2시간 전'},{source:'비즈리포트',headline:'산업계가 본 주요 기회와 예상 효과',byline:'전하윤 기자',time:'4시간 전'}],
 '중립':[{source:'오늘브리프',headline:'{issue}…확인된 사실과 아직 남은 과제',byline:'강서현 기자',time:'1시간 전'},{source:'팩트데일리',headline:'관계자 발언으로 본 핵심 쟁점',byline:'임도윤 기자',time:'2시간 전'},{source:'이슈리포트',headline:'후속 일정과 앞으로 확인할 세부 내용',byline:'전하윤 기자',time:'4시간 전'}],
 '부정':[{source:'오늘브리프',headline:'{issue}…실행 방안은 왜 빠졌나',byline:'강서현 기자',time:'1시간 전'},{source:'팩트데일리',headline:'후속 조치의 한계와 현실적인 변수',byline:'임도윤 기자',time:'2시간 전'},{source:'이슈리포트',headline:'유사 사례와 비교한 실효성 점검',byline:'전하윤 기자',time:'4시간 전'}]}
const additionalArticles:ViewArticle[]=[{source:'현장리포트',headline:'{issue} 관련 현장 반응과 후속 일정',byline:'백지안 기자',time:'5시간 전'},{source:'뉴스인사이트',headline:'전문가들이 짚은 핵심 변수와 예상 시나리오',byline:'송민준 기자',time:'6시간 전'},{source:'오늘의쟁점',headline:'발표 이후 남은 쟁점과 추가로 확인할 과제',byline:'노서연 기자',time:'7시간 전'}]
const viewpointTotals=[{press:18,articles:242},{press:15,articles:187},{press:12,articles:134}]
const expandedCards=ref<string[]>([])
const viewpointCards=computed(()=>{if(!stance.value||!currentGroup.value)return[];const base=[currentGroup.value.lead,...currentGroup.value.related].slice(0,3);return base.map((article,index)=>({number:String(index+1).padStart(2,'0'),title:articleTitle(article),description:viewpointNotes[stance.value!][index],press:viewpointTotals[index].press,articleCount:viewpointTotals[index].articles,articles:[article,companionArticles[stance.value!][index],currentGroup.value!.related[Math.min(index+1,currentGroup.value!.related.length-1)],additionalArticles[index],additionalArticles[(index+1)%additionalArticles.length],additionalArticles[(index+2)%additionalArticles.length]]}))})
function applyNavigation(state:NavigationState){
 page.value=state.page;searchOpen.value=false;expandedCards.value=[];evidenceOpen.value=false
 if(state.page==='detail'){
  selected.value=issues.find(issue=>issue.id===state.issueId)||issues[0]
  stance.value='중립';hasRevealedRatio.value=false
 }else{
  stance.value=null;hasRevealedRatio.value=false
  if(state.page==='search'){keyword.value=state.keyword||'';query.value=keyword.value}
 }
 window.scrollTo(0,0)
}
function navigate(state:NavigationState){applyNavigation(state);window.history.pushState(state,'')}
function home(){navigate({__hannun:true,page:'home'})}
function detail(i:Issue){navigate({__hannun:true,page:'detail',issueId:i.id})}
function search(word=query.value){const v=word.trim();if(!v)return;recent.value=[v,...recent.value.filter(x=>x!==v)].slice(0,10);localStorage.setItem('hannun-recent',JSON.stringify(recent.value));navigate({__hannun:true,page:'search',keyword:v})}
function choose(s:Stance){stance.value=s;hasRevealedRatio.value=true;expandedCards.value=[]}
function articleTitle(article:ViewArticle){return article.headline.replace('{issue}',selected.value.title)}
function toggleOpinion(number:string){expandedCards.value=expandedCards.value.includes(number)?expandedCards.value.filter(n=>n!==number):[...expandedCards.value,number]}
function handlePopState(event:PopStateEvent){const state=event.state as NavigationState|null;if(state?.__hannun)applyNavigation(state)}
onMounted(()=>{try{recent.value=JSON.parse(localStorage.getItem('hannun-recent')||'[]')}catch{};window.history.replaceState({__hannun:true,page:'home'} satisfies NavigationState,'');window.addEventListener('popstate',handlePopState)})
onBeforeUnmount(()=>window.removeEventListener('popstate',handlePopState))
</script>

<template>
 <header><div class="head wrap"><time>2026년 8월 27일 목요일</time><button class="logo" @click="home">한눈<small>뉴스를 한눈에, 관점을 한눈에</small></button><div class="searchbox"><form @submit.prevent="search()"><input v-model="query" @focus="searchOpen=true" placeholder="이슈, 키워드 검색" aria-label="이슈 검색"><button aria-label="검색">⌕</button></form><div v-if="searchOpen" class="recent"><section class="recent-words"><b>최근 검색어</b><p v-if="!recent.length">최근 검색어가 없습니다.</p><button v-for="word in recent" :key="word" @click="search(word)">{{word}}</button></section><section class="search-trends"><div><b>실시간 이슈 TOP 10</b><time>14:00 기준</time></div><button v-for="(i,n) in issues" :key="i.id" @click="detail(i);searchOpen=false"><em>{{n+1}}</em><span>{{i.title}}</span></button></section></div></div></div><nav class="wrap"><button v-for="c in categories" :key="c" :class="{active:category===c}" @click="category=c;home()">{{c}}</button></nav></header>
 <main class="wrap" @click="searchOpen=false">
  <template v-if="page==='home'">
   <div class="layout"><section class="feed"><div class="title"><div><button :class="{active:sort==='화제성순'}" @click="sort='화제성순'">화제성순</button><button :class="{active:sort==='최신순'}" @click="sort='최신순'">최신순</button></div><time>1시간 전 기준</time></div><article v-for="i in feed" :key="i.id" @click="detail(i)"><div><div class="feed-kicker"><span>{{i.category}}</span><small>·　{{i.time}}</small></div><h3>{{i.title}}</h3><div class="feed-meta">{{i.press}}개 언론사　·　관련 기사 {{i.articles}}건 묶음</div></div><b>묶음 펼쳐보기 ›</b></article><button v-if="count<issues.length" class="more" @click="count=issues.length">더 많은 뉴스를 불러오는 중입니다　○</button></section></div>
  </template>
  <template v-else-if="page==='detail'">
   <section class="detail"><span>{{selected.category}}</span><h1>{{selected.title}}</h1><p>최초 보도 2026.08.27 08:30　 최근 보도 14:20　 {{selected.press}}개 언론사　 기사 {{selected.articles}}건</p><div class="stanceBtns detail-stance" :class="{'ratio-mode':hasRevealedRatio}" aria-label="관점 선택"><button v-for="s in (['긍정','중립','부정'] as Stance[])" :key="s" :class="{active:stance===s}" @click="choose(s)"><span>{{s}}</span><b>{{s==='긍정'?32:s==='중립'?46:22}}%</b></button></div></section><section class="briefing"><div class="briefing-head"><div><label>COMMON FACTS</label><h2>공통사실 브리핑</h2></div><small>3개 출처 교차 확인</small></div><ol class="briefing-sentences"><li v-for="fact in briefingFacts" :key="fact.source"><span>{{fact.text}}</span><a :href="fact.url" target="_blank" rel="noopener noreferrer" :aria-label="`${fact.source} 출처 기사 열기`">{{fact.source}}</a></li></ol><button class="evidence-toggle" :aria-expanded="evidenceOpen" @click="evidenceOpen=!evidenceOpen">{{evidenceOpen?'근거 기사 접기 ↑':`근거 기사 ${briefingFacts.length}건 보기 ↓`}}</button><div v-if="evidenceOpen" class="evidence-list"><a v-for="fact in briefingFacts" :key="fact.headline" :href="fact.url" target="_blank" rel="noopener noreferrer"><span>{{fact.source}}</span><div><b>{{fact.headline}}</b><small>{{fact.time}} · 원문 기사</small></div><em>↗</em></a></div></section><section class="view"><div class="stances"><div v-if="stance&&currentGroup" class="group"><div class="opinion-stack"><article v-for="card in viewpointCards" :key="card.number" class="opinion-card"><div class="opinion-head"><span>VIEWPOINT {{card.number}}</span><small>{{card.press}}개 언론사 · 기사 {{card.articleCount}}건</small></div><h3>{{card.title}}</h3><p class="opinion-summary">{{card.description}}</p><div class="opinion-news-grid"><a class="latest-news" href="#" @click.prevent><img :src="summitNewsImage" :alt="`${card.articles[0].source} 최신 기사`"><span class="source">{{card.articles[0].source}}</span><b>{{articleTitle(card.articles[0])}}</b><small>{{card.articles[0].time}} · {{card.articles[0].byline}}</small></a><div class="other-news"><a v-for="article in card.articles.slice(1,4)" :key="article.source" href="#" @click.prevent><span class="source">{{article.source}}</span><b>{{articleTitle(article)}}</b><small>{{article.time}} · {{article.byline}}</small></a></div></div><div v-if="expandedCards.includes(card.number)" class="expanded-news"><a v-for="article in card.articles.slice(4)" :key="article.source" href="#" @click.prevent><span class="source">{{article.source}}</span><div><b>{{articleTitle(article)}}</b><small>{{article.time}} · {{article.byline}}</small></div><em>↗</em></a></div><button class="opinion-more" @click="toggleOpinion(card.number)">{{expandedCards.includes(card.number)?'관련 기사 접기 ↑':'관련 기사 더보기 ↓'}}</button></article><button class="coverage-more">이 관점 기사 {{currentGroup.articles}}건 모두 보기 ›</button></div></div></div></section>
  </template>
  <template v-else><section class="results"><label>SEARCH RESULTS</label><h1>‘{{keyword}}’ 검색 결과</h1><p>개별 기사가 아닌 관련 이슈를 모아 보여드립니다.</p><div class="list"><article v-for="i in results" :key="i.id" @click="detail(i)"><span>{{i.category}}</span><div><h3>{{i.title}}</h3><p><mark>{{keyword}}</mark>와 관련된 주요 보도를 하나의 이슈로 정리했습니다.</p><small>{{i.press}}개 언론사 · 기사 {{i.articles}}건</small></div><b>→</b></article><div v-if="!results.length" class="empty"><b>검색 결과가 없습니다.</b><p>다른 키워드로 다시 검색해보세요.</p></div></div></section></template>
 </main><footer><div class="wrap"><b>한눈</b><span>복잡한 뉴스의 핵심을 한눈에</span><small>© 2026 HANNUN NEWS</small></div></footer>
</template>
