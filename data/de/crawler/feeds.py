"""언론사 RSS 피드 정의.

company 는 8필드 계약의 한글 언론사명 그대로, publisher_id 는 article_v1 변환 때
쓰는 내부 코드다.

**섹션별 피드를 쓴다 (S15P21E105-61).** 전체 피드 하나로 받으면 기사가 어느 분야인지
알 수 없다. RSS 표준에서 category 태그는 선택 항목이라 절반 이상이 안 주고, 주는 곳도
"헤드라인"처럼 피드 이름을 적어 보낸다. 어느 주소에서 받았는지를 카테고리로 쓰면 짐작이
없고 언론사가 HTML 구조를 바꿔도 흔들리지 않는다.

카테고리 이름은 과거 데이터셋에서 많이 쓰인 값으로 통일했다. 섹션이 없는 분야는 비워 두고,
그 분야 기사는 카테고리 없이 들어온다. 같은 기사가 두 섹션에 나오면 seen DB 가 거른다.

주소는 2026-09-11 에 응답과 기사 유무를 확인한 값이다.
"""

FEEDS = [
    # 연합뉴스와 조선일보는 IT과학 섹션 피드를 못 찾았다. 그 분야 기사는 카테고리가 빈다
    {"company": "연합뉴스", "publisher_id": "yonhap",
     "rss": {
         "정치": "https://www.yna.co.kr/rss/politics.xml",
         "경제": "https://www.yna.co.kr/rss/economy.xml",
         "사회": "https://www.yna.co.kr/rss/society.xml",
         "국제": "https://www.yna.co.kr/rss/international.xml",
         "문화": "https://www.yna.co.kr/rss/culture.xml",
         "스포츠": "https://www.yna.co.kr/rss/sports.xml",
         "연예": "https://www.yna.co.kr/rss/entertainment.xml",
         "산업": "https://www.yna.co.kr/rss/industry.xml"}},

    {"company": "SBS", "publisher_id": "sbs",
     "rss": {
         "정치": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01",
         "경제": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=02",
         "사회": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=03",
         "국제": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=07",
         "문화": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=08",
         "스포츠": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=09",
         "연예": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=14"}},

    # 한겨레 피드에는 pubDate 가 없다. published 는 본문 추출 단계에서 채운다
    {"company": "한겨레", "publisher_id": "hani",
     "rss": {
         "정치": "https://www.hani.co.kr/rss/politics/",
         "경제": "https://www.hani.co.kr/rss/economy/",
         "사회": "https://www.hani.co.kr/rss/society/",
         "국제": "https://www.hani.co.kr/rss/international/",
         "문화": "https://www.hani.co.kr/rss/culture/",
         "스포츠": "https://www.hani.co.kr/rss/sports/",
         "IT과학": "https://www.hani.co.kr/rss/science/"}},

    {"company": "경향신문", "publisher_id": "khan",
     "rss": {
         "정치": "https://www.khan.co.kr/rss/rssdata/politic_news.xml",
         "경제": "https://www.khan.co.kr/rss/rssdata/economy_news.xml",
         "사회": "https://www.khan.co.kr/rss/rssdata/society_news.xml",
         "국제": "https://www.khan.co.kr/rss/rssdata/kh_world.xml",
         "문화": "https://www.khan.co.kr/rss/rssdata/culture_news.xml",
         "스포츠": "https://www.khan.co.kr/rss/rssdata/kh_sports.xml",
         "IT과학": "https://www.khan.co.kr/rss/rssdata/it_news.xml",
         "연예": "https://www.khan.co.kr/rss/rssdata/kh_entertainment.xml"}},

    {"company": "조선일보", "publisher_id": "chosun",
     "rss": {
         "정치": "https://www.chosun.com/arc/outboundfeeds/rss/category/politics/?outputType=xml",
         "경제": "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml",
         "사회": "https://www.chosun.com/arc/outboundfeeds/rss/category/national/?outputType=xml",
         "국제": "https://www.chosun.com/arc/outboundfeeds/rss/category/international/?outputType=xml",
         "문화": "https://www.chosun.com/arc/outboundfeeds/rss/category/culture-life/?outputType=xml",
         "스포츠": "https://www.chosun.com/arc/outboundfeeds/rss/category/sports/?outputType=xml",
         "연예": "https://www.chosun.com/arc/outboundfeeds/rss/category/entertainments/?outputType=xml"}},

    {"company": "동아일보", "publisher_id": "donga",
     "rss": {
         "정치": "https://rss.donga.com/politics.xml",
         "경제": "https://rss.donga.com/economy.xml",
         "사회": "https://rss.donga.com/national.xml",
         "국제": "https://rss.donga.com/international.xml",
         "문화": "https://rss.donga.com/culture.xml",
         "스포츠": "https://rss.donga.com/sports.xml",
         "IT과학": "https://rss.donga.com/science.xml",
         "연예": "https://rss.donga.com/entertainment.xml"}},

    {"company": "매일경제", "publisher_id": "mk",
     "rss": {
         "정치": "https://www.mk.co.kr/rss/30200030/",
         "경제": "https://www.mk.co.kr/rss/30100041/",
         "사회": "https://www.mk.co.kr/rss/50400012/",
         "국제": "https://www.mk.co.kr/rss/30300018/",
         "문화": "https://www.mk.co.kr/rss/30000023/",
         "스포츠": "https://www.mk.co.kr/rss/71000001/",
         "IT과학": "https://www.mk.co.kr/rss/50300009/",
         "연예": "https://www.mk.co.kr/rss/30000001/",
         "산업": "https://www.mk.co.kr/rss/50100032/"}},

    {"company": "한국경제", "publisher_id": "hankyung",
     "rss": {
         "정치": "https://www.hankyung.com/feed/politics",
         "경제": "https://www.hankyung.com/feed/economy",
         "사회": "https://www.hankyung.com/feed/society",
         "국제": "https://www.hankyung.com/feed/international",
         "문화": "https://www.hankyung.com/feed/life",
         "스포츠": "https://www.hankyung.com/feed/sports",
         "IT과학": "https://www.hankyung.com/feed/it",
         "연예": "https://www.hankyung.com/feed/entertainment"}},

    # 전자신문은 IT 전문지라 섹션이 넷뿐이다
    {"company": "전자신문", "publisher_id": "etnews",
     "rss": {
         "IT과학": "https://rss.etnews.com/Section901.xml",
         "경제": "https://rss.etnews.com/Section902.xml",
         "산업": "https://rss.etnews.com/Section903.xml",
         "사회": "https://rss.etnews.com/Section904.xml"}},

    {"company": "오마이뉴스", "publisher_id": "ohmynews",
     "rss": {
         "정치": "https://rss.ohmynews.com/rss/politics.xml",
         "경제": "https://rss.ohmynews.com/rss/economy.xml",
         "사회": "https://rss.ohmynews.com/rss/society.xml",
         "국제": "https://rss.ohmynews.com/rss/international.xml",
         "문화": "https://rss.ohmynews.com/rss/culture.xml",
         "스포츠": "https://rss.ohmynews.com/rss/sports.xml"}},

    {"company": "국민일보", "publisher_id": "kmib",
     "rss": {
         "정치": "https://www.kmib.co.kr/rss/data/kmibPolRss.xml",
         "경제": "https://www.kmib.co.kr/rss/data/kmibEcoRss.xml",
         "사회": "https://www.kmib.co.kr/rss/data/kmibSocRss.xml",
         "국제": "https://www.kmib.co.kr/rss/data/kmibIntRss.xml",
         "문화": "https://www.kmib.co.kr/rss/data/kmibCulRss.xml",
         "스포츠": "https://www.kmib.co.kr/rss/data/kmibSpoRss.xml",
         "연예": "https://www.kmib.co.kr/rss/data/kmibEntRss.xml"}},

    # 세계일보 피드에는 pubDate 가 없다. published 는 본문 추출 단계에서 채운다
    {"company": "세계일보", "publisher_id": "segye",
     "rss": {
         "정치": "https://www.segye.com/Articles/RSSList/segye_politic.xml",
         "경제": "https://www.segye.com/Articles/RSSList/segye_economy.xml",
         "사회": "https://www.segye.com/Articles/RSSList/segye_society.xml",
         "국제": "https://www.segye.com/Articles/RSSList/segye_international.xml",
         "문화": "https://www.segye.com/Articles/RSSList/segye_culture.xml",
         "스포츠": "https://www.segye.com/Articles/RSSList/segye_sports.xml",
         "연예": "https://www.segye.com/Articles/RSSList/segye_entertainment.xml"}},

    {"company": "서울신문", "publisher_id": "seoul",
     "rss": {
         "정치": "https://www.seoul.co.kr/xml/rss/google_politics.xml",
         "경제": "https://www.seoul.co.kr/xml/rss/google_economy.xml",
         "사회": "https://www.seoul.co.kr/xml/rss/google_society.xml",
         "국제": "https://www.seoul.co.kr/xml/rss/google_international.xml",
         "스포츠": "https://www.seoul.co.kr/xml/rss/google_sports.xml",
         "연예": "https://www.seoul.co.kr/xml/rss/google_entertainment.xml"}},
]
