# pytest 가 이 디렉토리(data/de)를 sys.path 에 넣게 하는 conftest.
#
# jobs 도 함께 넣는다. 잡들이 `import metrics` 처럼 같은 폴더의 모듈을 형제로 임포트하는데
# (spark-submit 은 스크립트 폴더를 sys.path 에 올려 준다) pytest 는 그러지 않아서
# 테스트만 ImportError 가 났다.
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for path in (HERE, os.path.join(HERE, "jobs")):
    if path not in sys.path:
        sys.path.insert(0, path)
