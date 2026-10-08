# Changelog

## [0.5.1](https://github.com/thalesgmartins/parse-app/compare/v0.5.0...v0.5.1) (2026-10-08)


### Documentation

* **arch:** adiciona modelo C4, ADRs e mapeamento de conformidade LGPD ([c737a3b](https://github.com/thalesgmartins/parse-app/commit/c737a3b0af46223c46690940b0dcfabbd9b02d92))
* atualiza README principal com arquitetura, setup e logica de extracao do cnis ([5d95723](https://github.com/thalesgmartins/parse-app/commit/5d9572390c0e08c51a75e07b21e1f8d2f5739ed5))
* documentacao completa do projeto, modelo C4, ADRs e conformidade LGPD ([5005f49](https://github.com/thalesgmartins/parse-app/commit/5005f49f201f37fb23114b9415995f3174aaf7fc))

## [0.5.0](https://github.com/thalesgmartins/parse-app/compare/v0.4.0...v0.5.0) (2026-10-08)


### Features

* **api:** implement async cnis pdf processing with htmx polling ([393d422](https://github.com/thalesgmartins/parse-app/commit/393d4222527288310d1cdbd2ef5cd36990ece82a))
* **async-queue:** processamento assincrono de extratos com fila nativa postgresql e volume efemero ([33ea44e](https://github.com/thalesgmartins/parse-app/commit/33ea44e35a00377dc3ecc528f787b553c240acdc))
* **db:** add JobExtracao model and alembic migration for async queue ([e437d21](https://github.com/thalesgmartins/parse-app/commit/e437d217d93ac3779aa88ddd4aa5d306d9d11fab))
* **queue:** implement postgres skip locked job repository and worker ([720ecec](https://github.com/thalesgmartins/parse-app/commit/720ecec9534c7f12a0a70ebdc95043cafcc94d6d))

## [0.4.0](https://github.com/thalesgmartins/parse-app/compare/v0.3.0...v0.4.0) (2026-10-08)


### Features

* **branding:** adiciona paleta oficial do parseapp, logos vazadas e favicon ([bec215b](https://github.com/thalesgmartins/parse-app/commit/bec215b41c94e2c681e2536f354bc79370d4187b))
* **database:** adiciona contagem de extratos auditados por advogado ([87f5522](https://github.com/thalesgmartins/parse-app/commit/87f55221506dd2d61ae10f2bfb81beacde47979a))
* **ui:** redesenha login em split-card e adiciona dropzone no dashboard ([f155239](https://github.com/thalesgmartins/parse-app/commit/f15523957ddc6ef8414c3d25fd1f6bef99b778b1))


### Bug Fixes

* **auth:** redireciona erros de login no navegador para exibicao visual ([c2e445e](https://github.com/thalesgmartins/parse-app/commit/c2e445e7c9370f50c339450d72dfab8d8acc74c9))

## [0.3.0](https://github.com/thalesgmartins/parse-app/compare/v0.2.0...v0.3.0) (2026-10-07)


### Features

* **ui:** adiciona logout, indicador de loading htmx e tratamento de erros visuais ([8c34054](https://github.com/thalesgmartins/parse-app/commit/8c34054d7832049556941916daca484b29b88f6d))
* **web:** adiciona suporte e arquivos estaticos locais para tailwind e htmx ([274124b](https://github.com/thalesgmartins/parse-app/commit/274124b5cc56c65cac262b043e151749d653e8f8))

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
