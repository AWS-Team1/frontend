# frontend

Bank of Anthos의 **웹 프런트엔드**와 **부하 발생기** 소스 저장소입니다.

## 구성

| 경로 | 역할 | 실행 형태 |
| --- | --- | --- |
| `src/frontend` | Flask 웹 UI. 사용자가 직접 접속하는 유일한 서비스입니다. | `gunicorn "frontend:create_app()"` |
| `src/loadgenerator` | Locust 부하 발생기. frontend를 HTTP로 호출해 배경 트래픽을 만듭니다. | `locust --headless` (웹 UI 없음) |

두 서비스는 코드를 공유하지 않습니다. loadgenerator는 frontend의 HTTP 엔드포인트
(`/login`, `/signup`, `/payment`, `/deposit` 등)만 호출하며 import 관계가 없습니다.
같은 저장소에 두는 이유는 **frontend의 화면과 엔드포인트가 바뀌면 부하 시나리오도 같이 바뀌기
때문**입니다.

## 이미지 빌드

빌드 컨텍스트는 각 서비스 디렉터리입니다. 저장소 루트가 아닙니다.

```sh
docker build -t bank-frontend      ./src/frontend
docker build -t bank-loadgenerator ./src/loadgenerator
```

한 저장소가 이미지 두 개를 만듭니다. CI를 붙일 때는 **경로 필터를 반드시 겁니다.**

```yaml
on:
  push:
    paths: ['src/frontend/**']      # loadgenerator 워크플로는 src/loadgenerator/**
```

필터가 없으면 `locustfile.py` 한 줄을 고쳐도 frontend 이미지가 새로 빌드되고, 새 태그가 배포되어
멀쩡한 frontend Pod가 롤링됩니다.

## 실행 환경

frontend는 백엔드를 **네트워크로만** 호출합니다. 백엔드 소스는 이 저장소에 필요 없습니다.

**frontend**

| 변수 | 용도 |
| --- | --- |
| `USERSERVICE_API_ADDR` `CONTACTS_API_ADDR` `BALANCES_API_ADDR` `HISTORY_API_ADDR` `TRANSACTIONS_API_ADDR` | 백엔드 서비스 주소 |
| `PUB_KEY_PATH` | JWT 검증용 RS256 **공개키** 경로. frontend는 개인키를 갖지 않습니다 |
| `PORT` `LOG_LEVEL` `SCHEME` `LOCAL_ROUTING_NUM` `ENV_PLATFORM` `VERSION` | 동작 설정 |

**loadgenerator**

| 변수 | 용도 |
| --- | --- |
| `FRONTEND_ADDR` | 대상 주소 (예: `frontend:80`) |
| `USERS` | 동시 가상 사용자 수 (기본 10) |
| `LOG_LEVEL` | 로그 수준 |

주입되는 값의 정본은 `gitops` 저장소의 `k8s/base/frontend/` 매니페스트입니다.
실제 인증정보는 이 저장소에 두지 않습니다.

## 주의 — loadgenerator는 더미 데이터를 만듭니다

`locustfile.py`는 랜덤 계정을 생성하며 모든 계정에 같은 비밀번호와 가짜 주민번호를 사용합니다.
1초 간격으로 입금·송금을 반복하므로 **DB가 계속 커집니다.** 외부에 노출된 환경에 붙이지 않습니다.
현재 `gitops` 저장소에 loadgenerator 매니페스트는 없습니다 — 띄우려면 새로 작성해야 합니다.

## 저장소 범위

애플리케이션 코드와 이미지 빌드 정의만 포함합니다. Terraform, Kubernetes 매니페스트, 배포
스크립트는 포함하지 않습니다 — 각각 `infra`, `gitops` 저장소가 소유합니다.

`src/frontend/SECURITY-TRIVY.md`에 이미지 취약점 스캔 현황과 잔여 CVE 근거가 있습니다.

소스 기준: `dlcodb94/aws-bank-of-anthos`의 `0ca63b4` 커밋. 라이선스는 `LICENSE`를 참고합니다.
