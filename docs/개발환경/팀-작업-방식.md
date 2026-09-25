# 팀 작업 방식

문제 조사, interview, 결정 기록은 Notion을 사용합니다. 실행 가능한 설정, 아키텍처, 운영 문서는
release와 일치하도록 이 저장소에 둡니다.

GitHub Project 상태는 `Backlog / Ready / In progress / Review / Done` 구성을 권장합니다.
각 issue에는 사용자에게 생기는 결과, acceptance criteria, 담당자, 근거 link를 적습니다.
개발자는 구현과 인프라를 맡고 팀원은 interview 근거, 데이터 접근, 평가 case, demo script를 맡을 수 있습니다.

주제를 정하기 전에 다음 내용을 기록합니다.

- 목표 사용자와 반복해서 수행하는 구체적인 작업
- 사용할 수 있는 실제 데이터, 접근 권한, 작은 대표 sample
- 현재 걸리는 시간·오류율과 개선 목표
- 3분 안에 보여줄 수 있는 demo 흐름
- 성공 case 5개와 실패·경계 case 5개

Notion, GitHub, GCP MCP 연결은 선택적인 개발 도구이며 제품 의존성이 아닙니다. URL을 저장했다고
MCP가 연결되는 것은 아닙니다. 현재 설정은 GitHub CLI와 gcloud 자동화를 지원합니다. Notion은 인증된
connector 또는 범위를 제한한 별도 integration이 필요합니다. Notion token, GCP credential,
GitHub token을 저장소에 보관하지 않습니다.
