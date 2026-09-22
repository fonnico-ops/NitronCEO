# NitronCEO

Uma matriz que mede o negócio, julga o que está fora da linha, **abre ação com
dono e prazo**, e **cobra quem não responde** — por Teams e e-mail.

O cockpit do Sankhya já mostra os números. O que não existia é o que acontece
**depois** do número ficar vermelho — e é isso que este repositório é:

```
medir → julgar → atribuir → cobrar → escalar → registrar
```

Tem painel (`nitronceo dashboard`), mas o painel mostra o **pipeline de
cobranças**: de quem está a bola, há quanto tempo, e em que degrau da escada.
Um indicador que não chega até `cobrar` não entra na matriz.

---

## Estado hoje

35 KPIs. **31 cobram. 4 estão em sombra** — medem e aparecem no pulso, mas não
notificam ninguém, porque o dado de origem ainda não sustenta uma cobrança.

| KPI | Dono | Estado |
|---|---|---|
| Emissão da Teak Brazil | Cristiane Alves | ✅ cobra |
| Gastos de compra fora do padrão | Cristiane Alves | ✅ cobra |
| Carteira disponível para faturar | Ricardo Miyabara | ✅ cobra |
| Estoque de produto inativo | Ricardo Miyabara | ✅ cobra |
| Pedidos esperando aprovação ou recusa | Ricardo Miyabara | ✅ cobra |
| Produtos que pararam de vender | Ricardo Miyabara | ✅ cobra |
| Ritmo de entrada de pedidos | Ricardo Miyabara | ✅ cobra |
| Despesa fora de Compras acima do padrão | Claudia Ribeiro | ✅ cobra |
| Fluxo de caixa dos próximos 7 dias | Claudia Ribeiro | ✅ cobra |
| Grandes devedores | Claudia Ribeiro | ✅ cobra |
| Pedidos travados no crédito | Claudia Ribeiro | ✅ cobra |
| Recebíveis vencidos | Claudia Ribeiro | ✅ cobra |
| Ciclo de injeção acima do padrão | Alex Souza e Charles Silva | ✅ cobra |
| Injetoras paradas agora | Alex Souza e Charles Silva | ✅ cobra |
| Ordens de serviço abertas | Alex Souza e Charles Silva | ✅ cobra |
| Paradas sem motivo apontado | Alex Souza e Charles Silva | ✅ cobra |
| Preventiva contra corretiva | Alex Souza e Charles Silva | ✅ cobra |
| Tempo de setup das injetoras | Alex Souza e Charles Silva | ✅ cobra |
| Agenda de carga contra a capacidade | Expedição e Forla Silva | ✅ cobra |
| Emissão da NTR Log contra o frete pago | Expedição e Forla Silva | ✅ cobra |
| Faturamento sem canhoto de entrega | Expedição e Forla Silva | ✅ cobra |
| Notas com reentrada / refaturamento | Expedição e Forla Silva | ✅ cobra |
| Notas devolvidas | Expedição e Forla Silva | ✅ cobra |
| Ordens de carga montadas por dia | Expedição e Forla Silva | ✅ cobra |
| Ritmo de faturamento | Expedição e Forla Silva | ✅ cobra |
| O que o PCP precisa programar | Anderson Lourenço | ✅ cobra |
| Produtos com estoque curto | Anderson Lourenço | ✅ cobra |
| Produtos sem estoque com pedido na carteira | Anderson Lourenço | ✅ cobra |
| Suspensos que continuam vendendo | Anderson Lourenço | ✅ cobra |
| Injetora parada por molde | Projetos | ✅ cobra |
| Injeção fora da Nitron | Projetos | ✅ cobra |
| Despesa sobre faturamento | Cristiane Alves | 🌓 sombra |
| Performance por canal | Ricardo Miyabara | 🌓 sombra |
| Performance por representante | Ricardo Miyabara | 🌓 sombra |
| Entregas reagendadas | Expedição e Forla Silva | 🌓 sombra |

**Manutenção predial** aparece nas ordens de serviço (168 abertas, mediana de
171 dias) e não tem dono declarado — hoje cai na produção por falta de
alternativa. Só o papel **Qualidade** ficou sem KPI. Alex e Charles continuam donos dos
três de produção — o que está vazio é o papel, não as pessoas. O que
destravaria: `TGFCAB.AD_MOTIVO` está 100% nulo nas 741 devoluções dos últimos
180 dias; preenchê-lo separa erro de faturamento (expedição) de defeito de
produto (qualidade).

O porquê de cada sombra — e o que destrava cada uma — está em
[`docs/achados-de-dados.md`](docs/achados-de-dados.md).

---

## Como rodar

```bash
pip install -e .          # instala o pacote e as dependências

# confere matriz e monta todo o SQL sem tocar no ERP
nitronceo validar

# rodada completa contra os dados reais de 22/09/2026, sem enviar nada
nitronceo rodar --dry-run

# produção
export SANKHYA_URL=... SANKHYA_USER=... SANKHYA_PASSWORD=...
export MS_TENANT_ID=... MS_CLIENT_ID=... MS_CLIENT_SECRET=... MS_REMETENTE=...
nitronceo rodar

nitronceo pendentes
nitronceo responder a1b2c3d4e5f6 "Protesto entra quinta; top 3 já em acordo."
nitronceo importar respostas.json    # respostas vindas do painel publicado
```

### Painel

```bash
nitronceo dashboard --dry-run -o dashboard.html
```

Gera o painel do pipeline. Duas coisas acontecem nele, não só nele:

- **cada etapa da esteira abre** e mostra quais indicadores estão nela —
  `medido → fora da linha → cobrável → ação → cobrado → escalado → respondido`;
- **cada cobrança abre** e mostra a pergunta, o que foi pedido, os números da
  apuração e a base do cálculo — e recebe a **resposta de quem foi cobrado**,
  assinada e com data, visível para todo mundo que abrir depois.

Tema claro e escuro, funciona no celular.

### O ciclo da resposta

A resposta não fica no HTML: quem responde não é quem publica a página, e o
texto precisa sobreviver à próxima republicação. Ela vai para a base do
artifact (capacidade `db`), e volta para o banco local assim:

```bash
# 1. publique o painel (uma vez por rodada)
nitronceo dashboard -o dashboard.html      # depois publique o arquivo

# 2. as pessoas respondem na própria página

# 3. traga as respostas de volta e encerre as cobranças
nitronceo importar respostas.json
```

`respostas.json` é o que a leitura da coleção `respostas` devolve. **Só as
marcadas com "isto encerra a cobrança" param a escada** — as demais são
recado, não conclusão, e o relógio do SLA continua correndo.

O `--dry-run` usa `tests/fixtures/`, que contém o **resultado real** das
queries em produção. O pulso que ele imprime é o estado verdadeiro da empresa
naquele dia:

```
## Pulso Nitron — 22/09/2026

🚨 Pedidos esperando aprovação ou recusa: 180 dias parados
🚨 Emissão da NTR Log contra o frete pago: 2.6%
🚨 Grandes devedores que ainda compram: 7
🚨 Naturezas de despesa fora do padrão: R$ 3.810.939,21
🔴 Recebíveis vencidos: R$ 9.728.499,68
🔴 Produtos que pararam de vender: R$ 3.921.906,88
🟡 Fluxo de caixa dos próximos 7 dias: R$ -142.357,40
🟢 Ritmo de faturamento: 107.7%
🟢 Notas devolvidas: 0.5%
🟢 Injetoras paradas agora: 1
```

---

## O que ainda falta decidir

O motor funciona e os donos estão cadastrados. O que falta é **acordo
humano**:

1. **A hierarquia de escalonamento.** Hoje tudo sobe direto para o CEO,
   porque não sei quem é gerente de quem. Cada degrau intermediário que você
   declarar em `escalonar_para` é um assunto operacional que para de chegar
   em você.
2. **A concentração no financeiro.** 5 das 13 cobranças caem na Claudia.
   Parte disso é de Compras por natureza — ver a tabela abaixo.
3. **A meta de R$ 500 mil/dia está 37% acima da média realizada** (R$ 364 mil
   nos últimos 63 dias úteis, com só 17,5% dos dias batendo). O KPI nasce
   vermelho e continua vermelho até a operação mudar — é escolha de gestão, e
   está declarada como tal. Para mudar o número:
   `NITRONCEO_META_DIA`.
5. **Os limiares** de cada KPI, com o dono da área. Estão calibrados contra a
   distribuição observada, não contra o orçamento.
6. **O app no Entra ID**, com `Mail.Send`, `ChannelMessage.Send`,
   `Chat.Create`, `ChatMessage.Send`.
7. **Os nomes das equipes e canais do Teams** em `pessoas.yaml`. O motor
   procura equipe e canal por nome e falha se não achar.
8. **Agendar** conforme [`docs/governanca.md`](docs/governanca.md#rituais).

### Compras e Projetos/Moldes estão cadastrados e sem KPI

Ambos entraram em `pessoas.yaml` mas nenhum indicador aponta para eles. Não
inventei KPI por conta própria; o que eu proporia:

| Papel | KPI candidato | De onde sairia |
|---|---|---|
| Qualidade | Devolução por defeito de produto | hoje impossível: `TGFCAB.AD_MOTIVO` está 100% nulo nas 741 devoluções dos últimos 180 dias. Preenchê-lo separa erro de faturamento (expedição) de defeito (produção) |
| Compras — Cristiane | Naturezas de compra fora do padrão | fatiar `gastos_acima_media`: Matéria Prima, Embalagens, Injeção Terceirizada e Adiantamento a Fornecedores são de Compras; Empréstimos e Dividendos ficam no financeiro |
| Compras — Cristiane | MP que trava programação do PCP | cruzar `demanda_alta_estoque_baixo` com a data de chegada da matéria-prima |
| Projetos/Moldes | Molde parado / manutenção | `AD_PARADAMAQUINA` tinha os motivos `MM` (Manutenção de Molde) e `QM` (Queima de Resistência) — a mesma tabela morta que impede o KPI de setup |

O terceiro depende da mesma instrumentação que o KPI de setup: enquanto a
parada não voltar a ser gravada, Projetos/Moldes não tem o que cobrar.

---

## O que precisa ser instrumentado para as 5 sombras acenderem

Nenhuma é projeto grande. Em ordem de custo/benefício:

| Sombra | O que falta | Tamanho |
|---|---|---|
| Performance por canal | Preencher `AD_ORIGEM` — 27% do faturamento está sem canal | correção de cadastro |
| Entregas reagendadas | Gravar `STATUS='M'` quando a data muda (hoje sobrescreve `NOVADATA` em silêncio) | uma regra de tela |
| Performance por representante | Diretor comercial fixar a meta individual | decisão, não código |
| Ruptura de estoque | Acordar com o PCP a fonte de saldo por linha; separar transferência interna de ruptura real | uma conversa + ajuste no SQL |
| Tempo de setup | Voltar a gravar a parada de setup (parou em 31/10/2024) | reativar tela ou marcar no app do PCP |

---

## Entrada é do comercial, saída é da expedição

A divisão não é por assunto, é por **onde a bola está**:

| | Comercial (Ricardo) | Expedição (Expedição e Forla) |
|---|---|---|
| | entrada de pedidos | **ritmo de faturamento** |
| | carteira disponível para faturar | ordens de carga por dia |
| | pedidos esperando aprovação | agenda de carga vs capacidade |
| | produtos que pararam de vender | **notas devolvidas** |
| | | **reentradas sem refaturamento** |
| | | entregas reagendadas |

Faturar é emitir a nota, e quem emite é quem carrega. O comercial responde
por trazer pedido e por manter a carteira atendível; o que já está vendido e
não sai pela porta é da expedição.

A apuração sustenta a divisão: a carteira tem **4 dias de meta com estoque na
mão** e a agenda tem **9 dias ociosos nos próximos 11 agendados**. Quando o
dia não bate os R$ 500 mil, o que falta não é pedido.

---

## Metodologia dos números

Cada `.sql` abre com a metodologia aplicada e as armadilhas conhecidas. As três
que mais mudam resultado:

- **Faturamento** ancora em `TGFTOP.ATUALCOM='C'`, não em `TIPMOV='V'` — filtrar
  por `TIPMOV` descarta a TOP 3110, que é faturamento real.
- **Filtro de TOP sempre por subquery** em `CODTIPOPER`. `JOIN` na `TGFTOP`
  subconta ~65% do faturamento, porque a tabela é versionada por `DHALTER`.
- **A meta de R$ 500 mil/dia vale para as empresas 1, 2, 4 e 14** — recorte
  diferente do resto da matriz de propósito, porque 3 (NTR Log), 17 (Hyak
  Group) e 20 (ACIUD) não produzem nem expedem.
- **Devolução exclui a TOP 2203** ("Devolução Simbólica Consignado"). Com ela
  dentro, a devolução aparece perto de 11% do faturamento; sem ela, 0,53%.
- **Saldo de estoque exclui o `CODLOCAL 1080000`** ("Estoque para
  Transferência"), que é conta de contrapartida e fica negativa por
  construção. Com ela dentro, o campeão de venda aparecia com −123.641
  unidades em estoque.

Base metodológica: skill `sankhya-especialista` do Grupo Nitron.

---

## Estrutura

```
config/matriz.yaml      os 13 KPIs — limiar, dono, ação, SLA
config/pessoas.yaml     papéis e escada de escalonamento
sql/*.sql               uma query por KPI, com a metodologia no cabeçalho
src/nitronceo/
  sankhya.py            leitura do ERP; recusa comando de escrita
  avaliador.py          número → verde/amarelo/vermelho/crítico
  acoes.py              sinal vermelho → ação com dono e prazo
  cobranca.py           a escada: dono → gestor → CEO → para
  repositorio.py        SQLite: sinais, ações, cobranças
  motor.py              orquestração + pulso do CEO
  dashboard.py          painel do pipeline: drill-down + respostas
  notificadores/        console (dry-run), Teams e Outlook via Graph
tests/                  20 testes; 23 fixtures com dados reais de produção
docs/                   arquitetura, governança, achados de dados
```

```bash
python -m pytest tests/ -q     # 20 passed
```
