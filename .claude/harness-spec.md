# Graphify harness spec

이 레포가 소유하는 하네스 컴포넌트의 기준선이다. `audit_harness.py`가 이 파일과 디스크를 대조한다.

## 목적

Claude가 코드베이스 질문에 답할 때 grep을 반복하는 대신 지속되는 그래프(`graphify`)를 쓰게 만든다. 원칙: **도구가 자기 인터페이스로 가르치는 것은 스킬이 다시 말하지 않는다.**

설계 근거와 실측(F1~F19)은 `.claude/plans/260831_Graphify 스킬 재작성 계획.md`에 있다.

## 컴포넌트

| 컴포넌트 | 레이어 | 무엇을 지나 |
|---|---|---|
| `.claude/skills/Graphify/SKILL.md` | skill | `query`의 문자열 매칭 함정, 읽기 명령 7개의 선택 기준, 빌드/갱신/복구. `graphify --help`가 말할 수 있는 것은 담지 않는다 |
| `.claude/skills/Graphify/scripts/build.py` | skill script | 2단계 빌드 계약(`extract` → `label`)과 자동 선택되지 않는 `--backend claude-cli` 플래그를 파라미터 공간으로 소유한다 |
| `~/.claude/CLAUDE.md` 1줄 | user CLAUDE.md | 발동 조건이 어투가 아니라 파일시스템 사실(`graphify-out/` 존재)이라서, description이 못 지는 조건을 이 한 줄이 진다 |
| `tests/test_build.py` | (하네스 밖) | build.py의 명령 계약을 가짜 shim으로, 실제 동작을 진짜 CLI 1회로 검증 |

`rules/`·`agents/`·`workflows/`·`hooks`·`permissions`·프로젝트 `CLAUDE.md`는 **의도적으로 비어 있다**. 이 레포에서 매 세션 필요한 프로젝트 사실이 아직 없다.

## 레이어 결정에서 뒤집은 것

- **`references/` 없음.** 단일 SKILL.md가 500줄 기준선의 절반이고, 모델이 어차피 전부 읽는다. 라우팅 결정을 사는 대신 조각을 놓칠 위험만 산다.
- **SessionStart 훅 기각.** 그래프 없는 레포에서 비용 0이라는 이점보다, 훅 + `test_hook.py` + 보호경로 프롬프트를 추가해 아끼는 것이 CLAUDE.md 한 줄뿐이다. 훅은 "절대 실패하면 안 되는 보장"의 층이고 이것은 조언성 라우팅이다.
- **`graphify claude install` 미사용.** 벤더 섹션을 CLAUDE.md에 써넣는데 그 파일은 하우스룰이 소유한다.
- **description은 좁게.** 벤더는 "any question about a codebase"로 넓게 잡았다. 전역 설치되면 그래프 없는 모든 레포의 질문까지 낚아채므로 좁게 쓰고 조건은 CLAUDE.md가 진다.

## Validation 시나리오

Graphify 레포가 **아닌** 다른 레포에서 새 세션을 열고 확인한다.

| 시나리오 | 통과 기준 |
|---|---|
| 그래프 없는 레포에서 "이 코드베이스 구조 설명해줘" | 스킬 발동 → 빌드 제안 → `build.py` 1회. 인라인 Python 0줄 |
| 빌드 직후 `git status` | `graphify-out/`이 나타나지 않는다 |
| 빌드 후 "X를 고치면 뭐가 깨져?" | `affected`를 쓴다. grep으로 되돌아가지 않는다 |
| **한국어로 코드베이스 질문** | `No matching nodes found.`를 "없다"로 보고하지 않고, 실제 어휘를 확인해 재질의한다 |
| "전체 아키텍처 리뷰해줘" | `GRAPH_REPORT.md`를 통째로 읽지 않는다 (41KB) |
| 코드 수정 후 다시 질문 | `build.py` 재실행으로 갱신. 별도 절차를 발명하지 않는다 |
| **그래프 없는 레포**에서 평범한 코드베이스 질문 | Graphify 스킬을 열지 **않는다** |

네 번째가 이 스킬의 존재 이유다. 나머지가 다 통과해도 이것이 실패하면 재작성 실패로 본다.

## 기각한 최적화 — `label --missing-only`

**재빌드 6~7초를 0초로 줄일 수 있지만 쓰지 않는다.** 실측: 무변경 재빌드 6초 중 `extract`가 0초, 전부 `label`이다. `label --missing-only`는 기존 이름을 보존하고 없는 것만 채우므로 무변경 시 0초다.

그런데 **커뮤니티 번호는 재사용되고, `--missing-only`는 기존 이름이 아직 맞는지 보지 않는다.** 재현: 2모듈 코퍼스에 다른 도메인 3개를 넣고 원래 2개를 지운 뒤 `--missing-only`로 갱신하자, `"Alpha Greeting Module"`이라는 이름이 `inventory_*` 함수 3개를 담게 되고 `"Beta Text Normalization"`이 `payments_*`를 담게 됐다. 경고는 없었다.

기각 사유는 속도-정확도 절충이 아니라 **이 스킬의 존재 이유와 충돌한다**는 것이다. SKILL.md의 중심 함정은 "커뮤니티 이름은 `query`가 매칭하는 어휘의 일부"이고, 빈 결과에서 회복하는 경로가 바로 그 어휘를 확인하는 것이다. 스테일 라벨은 **함정을 고치는 도구를 오염시켜** 없는 코드가 있다고 말하게 만든다. 6초로 살 수 없는 것이다.

같은 이유로 `graphify hook install`(post-commit 자동 재빌드)도 채택하지 않았다. 훅이 부르는 `watch._rebuild_code`는 문서상 "AST extraction + build + optional cluster + report. **No LLM needed**"라 커뮤니티 재명명을 하지 않는다 — 같은 결함을 공유할 가능성이 있으나 직접 확인하지는 않았다.

## 기계적 게이트

```bash
python3 /Users/seongjin/.claude/skills/harness-creator/scripts/validate_harness.py --path .   # 에러 0
python3 -m pytest tests/ -q                                                                   # 통과
wc -l .claude/skills/Graphify/scripts/build.py                                                # <= 60
test ! -d .claude/skills/Graphify/references                                                  # references 없음
test -L ~/.claude/skills/Graphify                                                             # 심볼릭 링크
```

## Change history

- **2026-08-31** — 최초 생성. 벤더 스킬(SKILL.md 713줄 + references 865줄)을 CLI 인터페이스 위의 얇은 판단 스킬로 재작성. 컴포넌트: 스킬 1개 + 스크립트 1개 + 전역 CLAUDE.md 1줄.
  - codex 적대적 검증에서 나온 계획 수정 3건을 반영:
    1. `diagnose multigraph`가 벤더 Step 4.5(빌드 전 raw 진단)를 대체한다는 주장을 철회. 확인 결과 v0.9.51의 `extract --no-cluster`는 raw `.graphify_extract.json`이 아니라 post-build `graph.json`을 쓰므로 그 게이트는 CLI 표면에 존재하지 않는다. 명령은 post-build 무결성 점검으로 남긴다.
    2. placeholder 검사 대상을 `.graphify_labels.json`으로 명시하고, **claude-cli 성공의 증거로 해석하지 않는다** — LLM이 전부 실패하면 `label`은 `Community N`이 아니라 결정론적 hub 라벨로 대체하므로 검사를 통과한다 (`cli.py:2091`).
    3. `--code-only` 기본값이 문서를 건너뛴다는 사실이 F7 함정과 같은 모양의 오답을 만든다 — SKILL.md에 명시.
  - codex 네 프레임 리뷰 3회전으로 잡은 것 (restated-help 5건 → 2건 → 0건, rail 0건 유지):
    - `query`의 매칭 모델을 **다시 썼다**. 계획서 F7의 "case-folded 부분문자열"은 실측과 다르다. 실제로는 질문을 토큰화해 불용어를 버리고, 남은 용어를 노드 라벨에 exact → prefix → substring 3계층으로, source path에는 평면 보너스로 매기며 희소한 용어에 가중치를 준다. 함정의 결론(빈 결과는 부재의 증거가 아니다)은 그대로지만 *왜*가 달라졌고, 원인 목록에 "정말로 없다"를 마지막 항목으로 넣어 세 원인이 전부라는 잘못된 함의를 없앴다.
    - 한국어 질문이 항상 실패한다는 계획서 서술은 틀렸다. 그래프에 한국어 라벨이 있으면 한국어로 매칭된다 — e2e에서 실제로 확인했다(`Naver-News`, 23노드).
    - `diagnose multigraph`를 9개 명령에서 뺐다. 벤더 Step 4.5의 빌드 전 raw 진단은 v0.9.51의 CLI 표면에 존재하지 않고, post-build 진단은 `--help`가 이미 설명한다.
    - 읽기 명령 선택 표와 `GRAPH_REPORT.md` 섹션 이름 목록을 삭제했다. 계획서는 "서브커맨드 `--help`가 없으므로 산문이 져야 한다"고 봤지만, 전역 `--help`가 명령마다 한 줄씩 이미 설명한다.
    - 근거가 저장되지 않은 수치(24.8배, 2,400노드/5초, 41KB)를 전부 삭제했다. `graphify benchmark`도 실측이 아니라 4 chars/token 추정이라 가리키지 않는다.
    - `build.py`: `.git` 포인터 파일 직접 파싱을 버리고 `git rev-parse --git-common-dir`에 위임했다 — linked worktree와 submodule에서 실제 git이 읽는 위치를 정확히 맞춘다. stale `graph.json` 방지(mtime_ns), git 부재 시 crash 대신 best-effort, placeholder 잔존 시 exit 0이 아니라 실패.
    - `pytest.ini`에 `addopts = -m "not integration"`. 없으면 평범한 `pytest`가 최대 900초짜리 live LLM 호출을 돈다.

- **알려진 한계**
  - `graphify` CLI가 PATH에 없으면 `build.py`는 깔끔한 메시지 대신 `FileNotFoundError` traceback으로 끝난다. 60줄 상한을 지키기 위해 남긴 것이고, traceback 마지막 줄이 `'graphify'`를 지목하므로 조치는 가능하다.
  - `st_mtime_ns` 비교는 타임스탬프 해상도가 낮은 파일시스템(FAT 등)에서 정상 쓰기를 stale로 오판할 수 있다. APFS에서는 문제없다.
  - 이미 `graphify-out/`을 커밋한 레포에서는 `.git/info/exclude`가 무력하다. SKILL.md가 이 경우를 경고한다.
