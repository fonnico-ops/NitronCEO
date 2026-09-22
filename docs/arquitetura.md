# Arquitetura

```
              ┌──────────────┐
              │ matriz.yaml  │  37 KPIs: SQL, limiar, dono, ação, SLA
              │ pessoas.yaml │  papéis e escada de escalonamento
              │ renato.md    │  persona e conhecimento da IA de gestão
              └──────┬───────┘
                     │
   Sankhya ──────► Motor ──────► SQLite ──────► Teams / Outlook / GHL
   (Oracle,      medir            sinais         (Graph, LeadConnector)
    leitura)     julgar           ações              ▲
                 atribuir         cobranças          │
                 cobrar                              │
                     │                               │
                     └──────► Renato (claude-opus-5) ┘
                              leitura cruzada + texto da cobrança
```

## Fluxo de uma rodada

1. **medir** — `sankhya.py` monta o SQL (substituindo `{{PARAM}}`), recusa
   qualquer comando de escrita e executa via `DbExplorerSP.executeQuery`.
2. **julgar** — `avaliador.py` aplica os três cortes do KPI e devolve
   verde / amarelo / vermelho / crítico.
3. **atribuir** — `acoes.py` transforma sinal vermelho em ação com dono,
   passos e prazo.
4. **cobrar** — `cobranca.py` varre o que está aberto e decide de quem cobrar
   agora, na escada de três rodadas.
5. **registrar** — `repositorio.py` grava sinal, ação e cobrança. É essa
   memória que permite cobrar amanhã o que foi pedido hoje.

O passo 4 é independente do 1: numa rodada em que tudo esteja verde, as
cobranças pendentes de ontem continuam subindo.

## O Renato

Os cinco passos acima são determinísticos de ponta a ponta, e isso é o que
os torna auditáveis: o mesmo dia de dados produz sempre a mesma cobrança,
para a mesma pessoa, com o mesmo prazo. É também o teto deles — a matriz
compara um número com um limiar de cada vez e nunca vê que a mesma
injetora é a pior em setup *e* em ciclo.

`analista.py` é a camada que olha o conjunto. Ela recebe o dossiê já
apurado (`montar_dossie`) com a persona e os achados de dados carregados
como prefixo em cache, e devolve duas coisas:

- **a leitura cruzada** para o CEO — `nitronceo renato`;
- **o texto de uma cobrança**, quando o template não dá conta do contexto
  — `nitronceo rodar --com-renato`.

Três limites deliberados:

1. **Ele não decide cobrança.** Dono, prazo e nível continuam vindo da
   regra. O que ele escolhe é a redação e a leitura, nunca o alvo.
2. **Ele não fica no caminho crítico.** Se o modelo falhar, a cobrança sai
   com o texto determinístico e a rodada registra a falha em
   `falhas_de_redacao` — uma cobrança genérica é infinitamente melhor que
   uma cobrança que não saiu.
3. **Prazo, link do painel e procedência do número são do sistema**, não
   dele: entram como rodapé depois do texto, para não dependerem de o
   modelo ter lembrado.

O prefixo (`config/renato.md` + `docs/achados-de-dados.md` + os papéis
vigentes) tem cerca de 40 mil tokens e é idêntico entre rodadas, então
carrega `cache_control: ephemeral` no último bloco. A linha de rodapé de
`nitronceo renato` mostra quanto veio do cache.

## Decisões que valem explicação

**Por que YAML e não código.** Quem ajusta limiar é o dono da área, não quem
programa. Um limiar dentro de `.py` é um limiar que ninguém revisa.

**Por que o SQL fica em arquivo e não no YAML.** Porque o cabeçalho de cada
`.sql` carrega a metodologia — a âncora de faturamento, a TOP excluída, a
armadilha conhecida. É onde a auditoria do número começa, e comentário longo
dentro de YAML não sobrevive.

**Por que SQLite.** O volume é de dezenas de linhas por dia. Trocar por
Postgres/Supabase é implementar a mesma interface de `Repositorio`; a decisão
pode esperar até existir mais de um consumidor.

**Por que métrica nula não é verde.** Consulta que volta vazia, coluna ausente
ou valor nulo viram `erro` no sinal, nunca "está tudo bem". O alarme que não
toca porque a bateria acabou é pior que alarme nenhum.

**Por que a fonte de teste existe.** `FonteArquivo` lê `tests/fixtures/*.json`
com o resultado real de 22/09/2026. Toda a lógica de avaliação, ação e escalada
é exercitável sem tocar na produção — e uma mudança de limiar pode ser testada
contra um dia de verdade.

## Integrações

| Serviço | Uso | Credenciais |
|---|---|---|
| Sankhya | leitura (`DbExplorerSP`) | `SANKHYA_URL`, `SANKHYA_USER`, `SANKHYA_PASSWORD` |
| Microsoft Graph | Teams + Outlook | `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_REMETENTE` |
| Claude API | Renato (análise e redação) | `ANTHROPIC_API_KEY` |
| Go High Level | canal de e-mail alternativo | `GHL_TOKEN`, `GHL_LOCATION_ID`, `GHL_REMETENTE`, `GHL_TAG_INTERNA` |

Permissões de aplicação necessárias no Entra ID: `Mail.Send`,
`ChannelMessage.Send`, `Chat.Create`, `ChatMessage.Send`.

Se a TI não liberar chat 1:1 por client credentials, o fallback é mandar no
canal da área e usar o e-mail como trilha individual.

**O GHL ainda não é um canal utilizável para cobrança interna.** A location
da Nitron contém clientes, não funcionários: buscar
`cristiane.alves@nitron.com.br` lá resolve para um contato de cliente com
tags de campanha. Por isso `notificadores/ghl.py` exige que o contato tenha
e-mail idêntico **e** a tag `nitron-interno`, e recusa o envio quando
qualquer das duas falta. Para ligar o canal, é preciso cadastrar os donos de
cobrança (de preferência numa sub-conta separada) e marcá-los com a tag.
