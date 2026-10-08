# ADR 004: Rejeicao de Mecanismo de Auto-Atualizacao In-App para Cloud SaaS

## Status
Rejeitado (Descarte Formal de Requisito)

## Data
2026-10-08

## Contexto
Durante a definicao do planejamento inicial do projeto (Fase 6), considerou-se a inclusao de um botao de atualizacao manual na interface web, permitindo que o usuario clicasse em "Atualizar Sistema" para obter a versao mais recente da aplicacao.

Ao aprofundar a analise arquitetural da solucao, identificou-se um conflito conceitual fundamental entre o modelo de distribuicao pretendido e a natureza de uma plataforma SaaS centralizada.

Era preciso estabelecer claramente a distincao entre:
1. **Sistemas On-Premise / Desktop / Self-Hosted:** Onde o software roda na infraestrutura do proprio cliente (desktop local ou servidor privado do escritorio), justificando um botao para que o administrador local aplique *patches* quando conveniente.
2. **Cloud Multi-Tenant SaaS:** Onde o software e hospedado centralmente pelo provedor e servido de forma compartilhada via navegador web para dezenas ou centenas de escritorios assinantes.

## Decisao
**Rejeitou-se a implementacao de qualquer mecanismo de auto-atualizacao in-app acionado pelo usuario final.**

No modelo arquitetural do ParseApp:
1. **Centralizacao do Ciclo de Release:** As atualizações de software sao de responsabilidade exclusiva do provedor de SaaS e gerenciadas de forma automatizada via pipeline de Integracao e Entrega Continua (CI/CD) no GitHub Actions, utilizando a ferramenta *Release Please* com base em *Conventional Commits*.
2. **Zero Downtime:** Novas versoes sao implantadas na nuvem por tecnicas de atualizacao continua (*rolling updates* ou recriacao graciosa de contêineres Docker), sem interrupcao perceptivel para os usuarios conectados.
3. **Impossibilidade de Controle por Tenant:** Nenhum usuario individual deve possuir privilegio operacional para disparar a reconstrucao ou o reinicio de um servico compartilhado que atende multiplos escritorios concorrentes.

## Justificativa Arquitetural

- **Prevencao de Negacao de Servico (DoS):** Se um usuario final pudesse disparar a atualizacao do contêiner central a partir do navegador, ele derrubaria a sessao ativa e os processamentos em andamento de todos os outros escritorios que estivessem utilizando a plataforma naquele instante.
- **Isolamento de Responsabilidades:** O usuario de um SaaS juridico B2B espera que a plataforma esteja continuamente atualizada, confiavel e disponivel, sem a necessidade de gerenciar versoes, dependencias ou migracoes de banco de dados.
- **Integridade do Banco de Dados:** Migracoes relacionais do Alembic devem ser orquestradas de maneira atomica durante a inicializacao controlada do contêiner (`lifespan`), e nao de forma caotica por cliques avulsos de usuarios em tela.

## Consequencias

### Positivas
- **Aderencia aos Principios Cloud Native e SaaS:** O sistema adota o paradigma padrao da industria para aplicacoes em nuvem.
- **Garantia de Disponibilidade (SLA):** Nenhum escritorio e impactado pelas acoes operacionais de outro cliente.
- **Reducao de Codigo e Superficie de Ataque:** Evita a exposicao de endpoints vulneraveis com comandos de sistema operacional (`git pull`, `pip install`, `reboot`) na camada de API.
- **Transparencia para o Usuario:** Novos recursos, correcoes tributarias e melhorias no parser entram em operacao instantaneamente para todos os usuarios assim que a nova versao e publicada.
