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
```

config 없이 직접 치려면:

```bash
ssh -i ~/.ssh/J15E105AT.pem -L 9870:localhost:9870 ubuntu@j15e105a.p.ssafy.io
```

## 웹 UI

- Airflow: `http://j15e105a.p.ssafy.io:8080` — 계정 admin, 비밀번호는 서버에서
  `docker compose exec airflow cat standalone_admin_password.txt`
- HDFS NameNode: 무인증 UI 라 서버 내부 전용(127.0.0.1)으로 묶여 있다.
  위 SSH 터널을 켠 상태에서 브라우저로 `http://localhost:9870`
