"""언론사 RSS 피드 정의.

company 는 8필드 계약의 한글 언론사명 그대로, publisher_id 는 article_v1 변환 때
쓰는 내부 코드다. URL 은 2026-08-28 feedparser 로 실동작 확인한 값.
"""

FEEDS = [
    {"company": "연합뉴스", "publisher_id": "yonhap",
     "rss": ["https://www.yna.co.kr/rss/news.xml"]},
    {"company": "SBS", "publisher_id": "sbs",
     "rss": ["https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01"]},
    # 한겨레 피드에는 pubDate 가 없다. published 는 본문 추출 단계에서 채운다.
    {"company": "한겨레", "publisher_id": "hani",
     "rss": ["https://www.hani.co.kr/rss/"]},
    {"company": "경향신문", "publisher_id": "khan",
     "rss": ["https://www.khan.co.kr/rss/rssdata/total_news.xml"]},
    {"company": "조선일보", "publisher_id": "chosun",
     "rss": ["https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"]},
    {"company": "동아일보", "publisher_id": "donga",
     "rss": ["https://rss.donga.com/total.xml"]},
    {"company": "매일경제", "publisher_id": "mk",
     "rss": ["https://www.mk.co.kr/rss/30000001/"]},
    {"company": "한국경제", "publisher_id": "hankyung",
     "rss": ["https://www.hankyung.com/feed/all-news"]},
    {"company": "전자신문", "publisher_id": "etnews",
     "rss": ["https://rss.etnews.com/Section901.xml"]},
    {"company": "오마이뉴스", "publisher_id": "ohmynews",
     "rss": ["https://rss.ohmynews.com/rss/ohmynews.xml"]},
    {"company": "국민일보", "publisher_id": "kmib",
     "rss": ["https://www.kmib.co.kr/rss/data/kmibRssAll.xml"]},
]
