# Changelog

## [0.2.0](https://github.com/thalesgmartins/parse-app/compare/v0.1.2...v0.2.0) (2026-10-07)


### Features

* **auth:** implementa autenticacao nativa com bcrypt e jwt em cookie httponly ([e50026c](https://github.com/thalesgmartins/parse-app/commit/e50026c3f276784d7617833a8c740c31ba9e1e15))
* **database:** adiciona execucao automatica de migracoes do alembic no lifespan ([09fc4d2](https://github.com/thalesgmartins/parse-app/commit/09fc4d2dc839fce5b51764c36a0a240f0cfac30f))
* **database:** cria modelos relacionais sqlalchemy 2.0 e migracao inicial do alembic ([bc49964](https://github.com/thalesgmartins/parse-app/commit/bc49964a40420fdd30696e69d478cfb01f1f0fc8))
* **infra:** adiciona configuracao do postgres no docker-compose e dependencias ([4c7dea5](https://github.com/thalesgmartins/parse-app/commit/4c7dea5db51ba19eaf41dbce1440d8bd9ab82371))


### Bug Fixes

* **deps:** adiciona httpx2 nas dependencias de dev para execucao do TestClient ([93874e8](https://github.com/thalesgmartins/parse-app/commit/93874e8117913794b09167ab44dd6156ffb27a81))
* **lint:** define alembic como third-party e organiza imports ([7b36a12](https://github.com/thalesgmartins/parse-app/commit/7b36a1258b8130ec84d6eb93a674ffe0dcb5fafd))
* **test:** ignora migracoes do alembic durante execucao do pytest ([9f6948e](https://github.com/thalesgmartins/parse-app/commit/9f6948ec6c6368c852847a615db7362c155d4f51))

## [0.1.2](https://github.com/thalesgmartins/parse-app/compare/v0.1.1...v0.1.2) (2026-10-06)


### Bug Fixes

* **docker:** corrige caminho do codigo fonte e adiciona dockerignore ([79c38a1](https://github.com/thalesgmartins/parse-app/commit/79c38a189959405829e4c16e12feefebcb167922))

## [0.1.1](https://github.com/thalesgmartins/parse-app/compare/v0.1.0...v0.1.1) (2026-10-06)


### Bug Fixes

* melhoria na configuração de logs e removida pasta com logs em arquivo ([748c63b](https://github.com/thalesgmartins/parse-app/commit/748c63b678d2679d0ece58c8f29fe45f26840020))

## 0.1.0 (2026-10-06)


### Bug Fixes

* adequações as exigencias do ruff ([46ca208](https://github.com/thalesgmartins/parse-app/commit/46ca2089bdd2c695a30246ae19e6bd6c07b72651))
