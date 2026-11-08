# Native recall의 근거와 주제 범위

Hindsight 1.1의 `min_scores.reranker`는 유효한 키다. HTTP schema가 이를 받고
Native reranking 뒤의 normalized score와 비교한다. SDK의 0.003 하한은 그대로
유지한다. 이 값은 질의 간에 보정된 관련성 확률이 아니며, reciprocal rank도
관련성 confidence가 아니다.

SDK는 그동안 Native의 `scores`를 버리고 `1 / (rank + 1)`만 반환했다. 이제
승인된 source들에 대응하는 `native_evidence`에 Native ID, 원래 순위,
`final/reranker/semantic/keyword` score와 승인 source ID를 보존한다. 기존
`score`의 순위 의미와 Native 순서는 바꾸지 않는다. 제공되지 않은 score나
raw logit은 만들지 않는다.

주제 범위 판정은 Native가 지명하고 기존 SQL 권한·프로젝트·revision 검사가
확인한 완전한 승인 원문에서만 수행한다. 다른 raw record를 조회하거나
`source_search`로 후보나 점수를 대체하지 않는다. 현재 chunks 경로의 entity
metadata가 비어 있을 수 있으므로 그 필드가 있다고 가정하지 않는다.

승인 원문의 명시적인 소유격·장소격 주제 표현과 문서에 직접 적힌 별칭을
질의의 literal과 대조한다. Unicode NFKC/casefold와 단어 경계, 한국어 조사를
처리하며, 주제가 실제 후보들을 구별하지 않으면 적용하지 않는다. 질의가
확인된 주제를 말할 때 다른 주제를 명시한 후보만 결과 limit 전에 제외한다.
질의에 여러 주제가 있으면 합집합을 사용한다. 주제를 밝히지 않은 예외와
semantic paraphrase, 해석할 수 없는 주제, 애매한 별칭은 Native 결과를
유지한다. 출처의 원문을 자르거나 바꾸지 않는다. 기존 qualified identifier와
class/model/type의 literal 규칙이 있으면 그 규칙을 우선한다.

관사·대명사·지시어와 한 글자 약칭은 원문에 별칭으로 적혀 있어도 독립적인
주제 지정 근거로 사용하지 않는다. 예를 들어 한 글자 프로젝트명의 전체
표현은 그대로 대조할 수 있지만 그 한 글자만으로 범위를 좁히지는 않는다.
명시적인 부정·제외 표현이 있는 질의도 이름 언급을 긍정 지정으로 해석하지
않고 Native 결과로 돌아간다. 부정의 대상을 추론하거나 반대 주제를 선택하지
않는다. 이 처리는 기존 qualified identifier/type 분기의 동작을 바꾸지 않는다.

이 방식은 일반적인 entity 인식 모델이 아니다. 지원하지 않는 구문·암묵적인
별칭·문맥 의존적인 주제의 관련성은 여전히 Native에 의존한다. 새로운
독립 평가를 통과했다는 주장이 아니며, 현재 소진된 평가의 숫자를 맞추는
threshold, 주제명 목록, gold ID 목록, 고정된 반환 개수를 사용하지 않는다.
회귀는 새로 만든 작은 가상 자료이며 실제 평가 원문·질문·라벨을 포함하지 않는다.

현재 실행 중이던 설치 SDK와 원래 평가 결과에는 적용하지 않는다. 새 모듈이
추가되어 SDK Python 모듈 수가 15에서 16으로 바뀐다. 채택 시 새 wheel의
정확한 전체 파일 목록·16개 모듈·SQL bytes·SHA를 검증하고 새 runtime/native
execution freeze를 만들어야 한다. 예전 wheel SHA나 모듈 수를 느슨하게
허용하면 안 된다. 후속 실행 등록은 원래 금융 승인과 동일 ledger 및 기존
소진·실패·unknown 기록을 유지해야 한다.
