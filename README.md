# NitronCEO

Uma matriz que mede o negócio, julga o que está fora da linha, **abre ação com
dono e prazo**, e **cobra quem não responde** — por Teams, e-mail e GHL.

Em cima dela roda o **Renato**, a IA de gestão: ele conhece a empresa, lê os
37 sinais como conjunto em vez de um a um, e escreve a cobrança quando o
texto padrão não dá conta.

O cockpit do Sankhya já mostra os números. O que não existia é o que acontece
**depois** do número ficar vermelho — e é isso que este repositório é:

```
medir → julgar → atribuir → cobrar → escalar → registrar
                                ↑
                             Renato — lê o conjunto, redige, reporta ao CEO
```

Tem painel (`nitronceo dashboard`), mas o painel mostra o **pipeline de
cobranças**: de quem está a bola, há quanto tempo, e em que degrau da escada.
Um indicador que não chega até `cobrar` não entra na matriz.

---

## Estado hoje

37 KPIs. **33 cobram. 4 estão em sombra** — medem e aparecem no pulso, mas não
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
| Mix do catálogo no e-commerce | Ana Julia | ✅ cobra |
| Ritmo de vendas do e-commerce | Ana Julia | ✅ cobra |
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

# só e-mail — o caminho mais curto para produção (uma permissão, não quatro)
nitronceo rodar --canais email

nitronceo pendentes
nitronceo responder a1b2c3d4e5f6 "Protesto entra quinta; top 3 já em acordo."
nitronceo importar respostas.json    # respostas vindas do painel publicado
```

### Cobrar pelo sender do GHL

A conta GHL da Nitron **já envia** com o domínio `nitron.com.br`
verificado, e já tem fluxo outbound para caixas internas (`expedicao2@`,
`claudia.ribeiro@`, `financeiro@hyakgroup.com.br`). Não precisa de
consentimento no Entra, nem de sincronismo de Outlook.

```bash
export GHL_TOKEN=... GHL_LOCATION_ID=rZ8y7lzqV7fzxsartaX2
nitronceo ghl-contatos          # resolve os contatos e aponta as colisões
nitronceo rodar --canais ghl
```

A cobrança sai de **`renato.fonseca@nitron.com.br`** — é o padrão do
código, sobrescrevível por `GHL_REMETENTE`. O domínio já está verificado
no GHL, então o envio é do sender do GHL e não passa pelo Outlook.

Estado dos contatos em 23/09/2026 — 8 dos 10 papéis completos:

| Área | Contato | |
|---|---|---|
| Financeiro, Comercial, PCP, Logística (2), Produção/Qualidade (2), E-commerce, Projetos | declarados | ✅ |
| CEO | `bnKA8BWCRaTeiBC2rjRs` é um **lead de campanha** (`lead-puro`, Nina Financeiro, anúncio de Instagram) | 🔴 |
| Compras | o e-mail está no contato do cliente **COOPERCOTIA** | 🔴 |

Os dois de fora continuam sendo cobrados por e-mail — é o canal que cala,
não a cobrança.

**O `contactId` é declarado à mão, nunca deduzido.** O GHL só envia para
um contato, e a base da location Nitron mistura funcionário com cliente.
Em 23/09/2026, `cristiane.alves@nitron.com.br` resolvia para um único
contato: *"Cristiane ATLETICO CLUBE"*, o cliente COOPERCOTIA cod 100526,
com as tags da Nina e seguido pela Nina Financeiro. Cobrar Compras por
aquele id levaria assunto interno para a conversa de um cliente.

Por isso `ghl_contato` vive em `pessoas.yaml`, pessoa por pessoa, e
`nitronceo ghl-contatos` só produz o laudo para alguém revisar:

```
✅ Prontos — cole o `ghl_contato` em config/pessoas.yaml:
  # logistica · Expedição <expedicao2@nitron.com.br>
  ghl_contato: AEfhFMAW6yLwumd6TvWE

🔴 NÃO declare estes — o e-mail está num contato de CLIENTE:
  compras · Cristiane Alves <cristiane.alves@nitron.com.br>
      fhnAHYNbq8Inlzb56DQL  Cristiane ATLETICO CLUBE  [sankhya-cliente, ...]
```

Duas travas: o id tem que estar declarado, **e** o contato é reconferido a
cada envio — um contato interno pode ganhar a tag `sankhya-cliente` numa
sincronização depois de declarado. Quem não tem id não é cobrado por ali;
segue pelo e-mail, que é o certo.

### Cobrar do seu e-mail, e ler a resposta

`MS_REMETENTE` decide de qual caixa a cobrança sai. Apontando para a sua,
ela chega como sua — com o peso que isso tem — e as pessoas respondem o
e-mail, não o painel. Então o sistema precisa ler a resposta de volta,
senão quem respondeu continua sendo cobrado:

```bash
export MS_REMETENTE=renato.fonseca@nitron.com.br
nitronceo rodar --canais email
nitronceo respostas                  # lê a caixa e amarra à ação
```

O elo é um token no assunto, que sobrevive ao `RE:` do Outlook:

```
⏰ COBRANÇA [NTR-a1b2c3d4]: NTR Log emitiu apenas 2.6% do frete
```

Duas regras, e as duas são deliberadas:

- **Responder não encerra.** Uma resposta é registrada, aparece no painel e
  segura os lembretes por 24h (`NITRONCEO_CARENCIA_H`). A ação só fecha
  quando a pessoa começa a resposta com **RESOLVIDO**. "Vou ver amanhã" é
  retorno legítimo e não é solução — encerrar nele ensinaria o sistema a
  aceitar evasiva.
- **A carência é uma promessa que o código cumpre.** O corpo da cobrança
  diz que responder segura o lembrete; `cobrar_pendentes` pula quem
  respondeu dentro da janela. Responder e ser cobrado na rodada seguinte é
  a forma mais rápida de ensinar o time a ignorar o sistema.

Dedupe por `internetMessageId`: a caixa é varrida inteira a cada rodada, e
a mesma resposta nunca entra duas vezes.

### Canais: dá para rodar só com e-mail

`--canais` escolhe o que fica no ar. **O GHL nunca liga sozinho** — ele só
existe se `GHL_TOKEN` e `GHL_LOCATION_ID` estiverem no ambiente, e ainda
assim recusa qualquer destinatário que não seja um contato interno marcado.
Cobrança interna não passa por ele.

```bash
nitronceo rodar --canais email          # só e-mail
nitronceo rodar --canais teams,email    # o padrão
```

A armadilha do modo só-e-mail, e como ela é tratada: **35 dos 37 KPIs
mandam o nível amarelo só pelo Teams**, e `reentradas` e `ecommerce_mix`
mandam até o vermelho só por lá. Sem tratamento, desligar o Teams
silenciaria a maior parte das cobranças. Por isso o motor tem fallback: o
canal que a matriz pediu e não está no ar vira e-mail, e o pulso mostra
quais desviaram. Nenhuma ação aberta fica sem mensagem.

Na prática isso muda a conversa com a TI. O Teams por *client credentials*
precisa de `ChannelMessage.Send`, `Chat.Create` e `ChatMessage.Send` — e
mensagem direta 1:1 por aplicação é justamente a permissão mais difícil de
aprovar. O e-mail precisa de **`Mail.Send` e mais nada**. Começar por
`--canais email` tira o sistema do papel com uma permissão; o Teams entra
depois, sem mudar uma linha de configuração da matriz.

### O Renato

```bash
pip install -e ".[renato]"
export ANTHROPIC_API_KEY=...

# o material que ele leria, sem gastar uma chamada
nitronceo renato --dry-run --dossie

# a leitura cruzada da rodada, para o CEO
nitronceo renato

# ele escreve o texto de cada cobrança desta rodada
nitronceo rodar --com-renato
```

`config/renato.md` é quem ele é: a persona, o mapa de empresas e donos, as
armadilhas de dado já descobertas e as regras de como ele escreve. Editar
esse arquivo muda o comportamento dele — ele não é documentação *sobre* o
Renato, ele **é** o Renato.

Três limites, de propósito:

- **ele não escolhe quem cobrar.** Dono, prazo e nível continuam vindo da
  regra determinística; ele escolhe a redação e a leitura.
- **ele não fica no caminho crítico.** Modelo fora do ar → a cobrança sai
  com o texto padrão e a rodada registra a falha. Cobrança genérica é
  melhor que cobrança que não saiu.
- **ele não inventa número.** Só cita o que está no dossiê apurado; prazo,
  link do painel e procedência do número são acrescentados pelo sistema,
  não por ele.

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
config/matriz.yaml      os 37 KPIs — limiar, dono, ação, SLA
config/pessoas.yaml     papéis e escada de escalonamento
config/renato.md        a persona e o conhecimento da IA de gestão
sql/*.sql               uma query por KPI, com a metodologia no cabeçalho
src/nitronceo/
  sankhya.py            leitura do ERP; recusa comando de escrita
  avaliador.py          número → verde/amarelo/vermelho/crítico
  acoes.py              sinal vermelho → ação com dono e prazo
  cobranca.py           a escada: dono → gestor → CEO → para
  repositorio.py        SQLite: sinais, ações, cobranças
  motor.py              orquestração + pulso do CEO
  analista.py           Renato: dossiê, leitura cruzada, redação da cobrança
  respostas.py          lê a caixa e amarra a resposta de volta na ação
  dashboard.py          painel do pipeline: drill-down + respostas
  notificadores/        console (dry-run), Teams/Outlook (Graph) e GHL
tests/                  58 testes; 23 fixtures com dados reais de produção
docs/                   arquitetura, governança, achados de dados,
                        pedido de permissões para a TI
```

```bash
python -m pytest tests/ -q     # 58 passed
```
