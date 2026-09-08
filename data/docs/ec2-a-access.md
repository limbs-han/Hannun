# EC2 A (J15E105A) 접속 안내

데이터 파트 공용. 서버 작업과 웹 UI 열람에 필요한 것 전부.

## pem 키 보관

pem 키는 다운로드 폴더가 아니라 `~/.ssh/` 에 두고, 본인만 읽게 잠근다.
Windows 는 PowerShell 에서:

```powershell
icacls "$HOME\.ssh\J15E105AT.pem" /inheritance:r /grant:r "$env:USERNAME`:R"
```

## SSH 접속

`~/.ssh/config` 에 아래를 저장해두면 `ssh a` 한 번으로 접속과 HDFS UI 터널이
같이 열린다:

```
Host a
  HostName j15e105a.p.ssafy.io
  User ubuntu
  IdentityFile ~/.ssh/J15E105AT.pem
  LocalForward 9870 localhost:9870
  LocalForward 8080 localhost:8080
```

`a` 는 각자 컴퓨터의 이 설정에만 있는 이름이라, 설정을 만들지 않은 컴퓨터에서 `ssh a` 를 치면
서버 이름을 찾을 수 없다고 나온다. 그때는 아래 전체 주소 형태를 쓴다.

config 없이 직접 치려면:

```bash
ssh -i ~/.ssh/J15E105AT.pem -L 9870:localhost:9870 -L 8080:localhost:8080 ubuntu@j15e105a.p.ssafy.io
```

## 웹 UI

- HDFS NameNode: 무인증 UI 라 서버 내부 전용(127.0.0.1)으로 묶여 있다.
  위 SSH 터널을 켠 상태에서 브라우저로 `http://localhost:9870`
- Airflow: 같은 터널로 `http://localhost:8080`. 화면에서 DAG 를 돌릴 수 있어 실행 권한과 같으므로
  공개하지 않는다. 이미 8080 을 쓰고 있으면 `-L 18080:localhost:8080` 처럼 앞 번호만 바꿔 쓴다
