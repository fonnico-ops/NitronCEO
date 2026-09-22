# Arquitetura

```
              ┌──────────────┐
              │ matriz.yaml  │  13 KPIs: SQL, limiar, dono, ação, SLA
              │ pessoas.yaml │  papéis e escada de escalonamento
              └──────┬───────┘
                     │
   Sankhya ──────► Motor ──────► SQLite ──────► Teams / Outlook
   (Oracle,      medir            sinais         (Microsoft Graph)
    leitura)     julgar           ações
                 atribuir         cobranças
                 cobrar
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

Permissões de aplicação necessárias no Entra ID: `Mail.Send`,
`ChannelMessage.Send`, `Chat.Create`, `ChatMessage.Send`.

Se a TI não liberar chat 1:1 por client credentials, o fallback é mandar no
canal da área e usar o e-mail como trilha individual.
