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

23 KPIs. **18 cobram. 5 estão em sombra** — medem e aparecem no pulso, mas não
notificam ninguém, porque o dado de origem ainda não sustenta uma cobrança.

| KPI | Área | Dono | Estado |
|---|---|---|---|
| Ritmo de faturamento | Comercial | Diretoria Comercial | ✅ cobra |
| Ritmo de entrada de pedidos | Comercial | Diretoria Comercial | ✅ cobra |
| Pedidos esperando aprovação ou recusa | Comercial | Diretoria Comercial | ✅ cobra |
| Produtos que pararam de vender | Comercial | Diretoria Comercial | ✅ cobra |
| Ordens de carga montadas/dia | Logística | Logística | ✅ cobra |
| Notas devolvidas | Qualidade | Qualidade | ✅ cobra |
| Reentradas / refaturamento | Qualidade | Qualidade | ✅ cobra |
| Injetoras paradas agora | Produção | Gerência de Produção | ✅ cobra |
| Produtos com estoque curto | PCP | PCP | ✅ cobra |
| O que o PCP precisa programar | PCP | PCP | ✅ cobra |
| Ruptura de estoque na carteira | PCP | PCP | ✅ cobra |
| Fluxo de caixa D0–D30 | Financeiro | Financeiro | ✅ cobra |
| Recebíveis vencidos | Financeiro | Financeiro | ✅ cobra |
| Grandes devedores | Financeiro | Financeiro | ✅ cobra |
| Pedidos travados no crédito | Financeiro | Financeiro | ✅ cobra |
| Naturezas de despesa fora do padrão | Financeiro | Financeiro | ✅ cobra |
| Emissão da NTR Log contra o frete pago | Financeiro | Financeiro | ✅ cobra |
| Emissão da Teak Brazil | Financeiro | Financeiro | ✅ cobra |
| Performance por representante | Comercial | Diretoria Comercial | 🌓 sombra |
| Performance por canal | Comercial | Diretoria Comercial | 🌓 sombra |
| Entregas reagendadas | Logística | Logística | 🌓 sombra |
| Tempo de setup das injetoras | Produção | Gerência de Produção | 🌓 sombra |
| Despesa sobre faturamento | Financeiro | Financeiro | 🌓 sombra |

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
```

### Dashboard

```bash
nitronceo dashboard --dry-run -o dashboard.html
```

Gera o painel do pipeline: os 23 indicadores por área, a esteira
`medido → fora da linha → cobrável → ação → cobrado → escalado → respondido`,
as cobranças abertas com dono e prazo, e o que está em sombra. Tema claro e
escuro, funciona no celular.

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

## O que é preciso decidir para os 8 ativos virarem cobrança de verdade

O motor funciona. O que falta é **acordo humano**, e é rápido:

1. **Preencher `config/pessoas.yaml`** — nomes e e-mails reais. Hoje está
   `(preencher)`. Sem isso o motor cobra endereços genéricos.
2. **Fixar a meta mensal de faturamento** (`NITRONCEO_META_MENSAL`). Hoje usa
   R$ 8 mi de placeholder.
3. **Confirmar os limiares** de cada KPI com o dono da área. Estão calibrados
   contra a distribuição observada, não contra o orçamento.
4. **Registrar o app no Entra ID** com `Mail.Send`, `ChannelMessage.Send`,
   `Chat.Create`, `ChatMessage.Send`.
5. **Agendar** conforme [`docs/governanca.md`](docs/governanca.md#rituais).

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

## Metodologia dos números

Cada `.sql` abre com a metodologia aplicada e as armadilhas conhecidas. As três
que mais mudam resultado:

- **Faturamento** ancora em `TGFTOP.ATUALCOM='C'`, não em `TIPMOV='V'` — filtrar
  por `TIPMOV` descarta a TOP 3110, que é faturamento real.
- **Filtro de TOP sempre por subquery** em `CODTIPOPER`. `JOIN` na `TGFTOP`
  subconta ~65% do faturamento, porque a tabela é versionada por `DHALTER`.
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
  dashboard.py          painel do pipeline em HTML (claro/escuro)
  notificadores/        console (dry-run), Teams e Outlook via Graph
tests/                  20 testes; 23 fixtures com dados reais de produção
docs/                   arquitetura, governança, achados de dados
```

```bash
python -m pytest tests/ -q     # 20 passed
```
