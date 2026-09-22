"""언론사 한글명 → 내부 코드(publisher_id) 매핑 (article_v1 계약).

article_id = sha256(publisher_id | 정규화 link) 의 해시 입력이라 한 번 정한 값은
바꾸면 안 된다. 데이터셋 34개사, 빅카인즈 전국일간지, 실시간 RSS 언론사를 한 표로
관리하며, 같은 언론사의 다른 표기(SBS·SBS뉴스, 한겨레·한겨례)는 같은 코드로 모인다.
"한겨례"는 데이터셋 원문 오타 그대로다.
"""

PUBLISHER_ID = {
    # SSAFY 데이터셋 34개사
    "서울경제": "sedaily", "KBS뉴스": "kbs", "동아일보": "donga", "연합뉴스": "yonhap",
    "중앙일보": "joongang", "SBS뉴스": "sbs", "국민일보": "kmib", "머니S": "moneys",
    "서울신문": "seoul", "MBN": "mbn", "뉴스1": "news1", "파이낸셜뉴스": "fnnews",
    "데일리안": "dailian", "한겨례": "hani", "더팩트": "tf", "JTBC": "jtbc",
    "한국경제TV": "wowtv", "TV조선": "tvchosun", "세계일보": "segye", "매일신문": "imaeil",
    "오마이뉴스": "ohmynews", "아시아경제": "asiae", "문화일보": "munhwa", "블로터": "bloter",
    "코메디닷컴": "kormedi", "여성신문": "womennews", "디지털타임": "dt", "조세일보": "joseilbo",
    "경기일보": "kyeonggi", "시사저널": "sisajournal", "비즈니스워치": "bizwatch",
    "미디어오늘": "mediatoday", "국제신문": "kookje", "디지털데일리": "ddaily",
    # 빅카인즈 전국일간지 (위와 겹치지 않는 것)
    "경향신문": "khan", "내일신문": "naeil", "아시아투데이": "asiatoday", "조선일보": "chosun",
    "한겨레": "hani", "한국일보": "hankookilbo",
    # 실시간 RSS (위와 겹치지 않는 것)
    "SBS": "sbs", "매일경제": "mk", "한국경제": "hankyung", "전자신문": "etnews",
}
