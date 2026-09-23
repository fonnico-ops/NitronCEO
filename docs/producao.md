# Ligar o NitronCEO em produção

O sistema roda no **GitHub Actions** e guarda a memória no **Supabase**.
Não precisa de servidor: são dois comandos por dia, de poucos minutos, e
o que eles produzem sobrevive ao runner porque mora no banco.

```
 GitHub Actions (cron)
        │
        ├── 17h, dias úteis ──► nitronceo disparar     (a cada 2 dias)
        │                       nitronceo relatorio --enviar
        └── 07h30, dias úteis ► nitronceo respostas --canal ghl
                                        │
     Sankhya (leitura) ──────────────────┤
     Supabase (memória) ◄────────────────┤
     GHL (envio e resposta) ◄────────────┘
```

---

## 1. Os secrets

Em **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Onde achar | Sem ele |
|---|---|---|
| `NITRONCEO_DATABASE_URL` | Supabase → Settings → Database → Connection string (URI) | cai no SQLite do runner e **perde tudo** a cada execução |
| `SANKHYA_URL` | `https://<host>/mge` | não mede nada |
| `SANKHYA_USER` | usuário de leitura do ERP | idem |
| `SANKHYA_PASSWORD` | | idem |
| `GHL_TOKEN` | GHL → Settings → Private Integrations | não envia nada |
| `GHL_LOCATION_ID` | `rZ8y7lzqV7fzxsartaX2` (location Nitron) | idem |
| `ANTHROPIC_API_KEY` | console.anthropic.com | roda sem a leitura do Renato; o resto funciona |

E uma **variable** (não secret, porque não é segredo):

| Variable | Valor |
|---|---|
| `GHL_REMETENTE` | `renato.fonseca@nitron.com.br` |

A connection string do Supabase: prefira a do **pooler** (porta 6543) —
o Actions abre e fecha conexão a cada execução, e o pooler é feito para
isso. A direta (5432) funciona igual para este volume.

O workflow confere os secrets antes de qualquer envio e falha com a lista
do que está faltando. Falhar cedo é melhor que rodar meio.

---

## 2. Um pré-requisito que precisa ser verificado

**O GitHub Actions alcança o Sankhya?** O runner é uma máquina na nuvem da
Microsoft, fora da rede da Nitron. Se o `SANKHYA_URL` for:

- **cloud / exposto na internet** → funciona;
- **on-premise sem exposição** → não funciona, e a primeira execução vai
  falhar no timeout.

Se for o segundo caso, há duas saídas: liberar o IP de saída do Actions no
firewall, ou rodar num servidor da empresa com um cron simples:

```cron
0 17 * * 1-5  cd /opt/nitronceo && nitronceo disparar && nitronceo relatorio --enviar --com-renato
30 7 * * 1-5  cd /opt/nitronceo && nitronceo respostas --canal ghl
```

O código é o mesmo nos dois casos. Só muda quem chama.

---

## 3. A primeira execução

Não espere o cron. Vá em **Actions → NitronCEO → Run workflow** e rode
nesta ordem:

1. **`validar`** — confere a matriz e monta os 37 SQL sem tocar no ERP e
   sem enviar nada. Se isto falha, nada mais importa.
2. **`respostas`** — lê as conversas do GHL. Não envia nada. Prova que o
   token e a location estão certos, e já traz quem respondeu às cobranças
   de 23/09.
3. **`relatorio`** — mede tudo e manda o acompanhamento para os três.
   Este **envia e-mail de verdade**.
4. **`disparar`** — cobra os gestores. Só rode quando os três acima
   estiverem limpos; a cadência segura, então sem `--agora` ele recusa
   antes de 25/09.

---

## 4. O que já está no banco

A rodada de 23/09/2026 foi migrada: **21 cobranças abertas**, 8 donos, com
os tokens que estão nas caixas das pessoas. As respostas que chegarem vão
casar.

```sql
SELECT dono, COUNT(*) FROM nitronceo.acoes
 WHERE estado = 'aberta' GROUP BY dono ORDER BY 2 DESC;
```

O próximo disparo cai em **25/09**, porque a cadência é de 2 dias e o
último ficou registrado em 23/09 02:50.

---

## 5. Onde olhar quando algo der errado

| Sintoma | Provável causa |
|---|---|
| `Secrets faltando:` | o que o passo lista não foi configurado |
| timeout no `validar` ou na medição | Actions não alcança o Sankhya (§2) |
| `Nenhuma cobrança em aberto` | ninguém saiu da linha, ou a medição falhou — veja o log |
| `Fora da janela` | rodou fora das 17h; use `agora: true` no dispatch |
| `Último disparo em ...; a cadência é de 2 dias` | ainda não é dia |
| cobrança não chega a alguém | `ghl_contato` ausente em `pessoas.yaml`, ou contato com tag de cliente — o log diz qual |

Os logs ficam em **Actions**, por execução. Cada passo imprime o que fez.
