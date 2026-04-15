# Docs

현재 `service_engine` 브랜치의 문서 허브다.
이 디렉토리 안의 문서를 현재 기준 canonical source로 본다.

## Canonical Documents

- [http-contract.md](http-contract.md)
  - 현재 구현된 `UI engine`, `service engine`, `model engine` 간 HTTP wire contract 단일 기준 문서
  - 기존에 분산되어 있던 contract 문서를 대체한다
- [service-engine-boundary.md](service-engine-boundary.md)
  - `service_engine`의 책임 경계, 비목표, 고정된 v0 설계 선택 문서
  - 기존 service boundary, 초안 문서를 대체한다

## Reading Order

1. [service-engine-boundary.md](service-engine-boundary.md)
2. [http-contract.md](http-contract.md)
3. [../service_engine/README.md](../service_engine/README.md)

## Notes

- `service_engine/README.md`는 개발 환경, 실행, CLI 중심의 운영 가이드다.
- API shape나 엔진 간 계약은 이 디렉토리 문서를 source of truth로 유지한다.
