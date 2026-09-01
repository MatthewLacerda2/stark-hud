# stark-hud

Blackboard central exibida na TV. Qualquer sessao do Claude — ou qualquer
navegador na LAN — joga conteudo nela e ela mostra, ao vivo.

Nome provisorio. Sucessor espiritual do `kinesis` (que fica como esta, intocado);
o kinesis serve de referencia de features e de vocabulario de MCP, nao de codigo.

---

## Premissas

- **A TV e o unico cliente serio.** Ela nao tem teclado, nao tem mouse, ninguem
  a toca. Tudo que exigir interacao humana e opcional e acontece no macbook.
- O PC fica ligado 24/7 e serve tudo pela LAN.
- **Sem autenticacao.** Aberto pra qualquer um no wifi, por decisao explicita.
- **Sem persistencia** nesta fase. Estado em memoria. Reiniciou, board limpo.
- Responsividade so se vier de graca do Tailwind. Nao e requisito.
- **i18n mantido** (o template ja traz i18next), porque o codigo pode ser
  publicado. **Idioma padrao: ingles.** Nenhuma string solta no JSX.

## Stack

Base: template **GoldStandard**, com o Postgres e o login removidos.

| Camada       | Escolha                                                  |
| ------------ | -------------------------------------------------------- |
| Front        | React 19 + Vite + Tailwind v4 + shadcn/radix + bun        |
| Roteamento   | TanStack Router (ja no template)                          |
| Grid         | `react-grid-layout` — spans, colisao, compactacao, drag   |
| Charts       | Recharts (padrao do shadcn, ja estilizado)                |
| Back         | FastAPI + Pydantic, 4 camadas do template                 |
| Tempo real   | WebSocket, broadcast do board pra todos os clientes       |
| MCP          | servidor HTTP em `0.0.0.0`, exposto na LAN                |
| Estado       | dict em memoria, atras de `repositories/`                 |

**Sai do template:** `sqlalchemy`, `asyncpg`, `pyjwt`, `models/user.py`,
`repositories/users.py`, docker-compose do Postgres, fluxo de login.

**Fica:** Makefile como unico portao de qualidade, CI que roda os mesmos alvos,
linters e regras de eslint proprias, `CLAUDE.md` como contrato operacional,
separacao estrita de 4 camadas.

## Arquitetura

```
              ┌─── stark-hud server (PC, 24/7) ───┐
              │   estado em memoria               │
              │   HTTP  ·  WebSocket  ·  MCP      │
              └───────────────────────────────────┘
        ws ↙            ws ↓             ↘ MCP (http)
   ┌────────┐      ┌──────────┐      ┌──────────────┐
   │  TV    │      │ macbook  │      │ Claude do PC │
   │(browser│      │ celular  │      │ Claude do mac│
   │ do PC) │      │(browser) │      │ qualquer um  │
   └────────┘      └──────────┘      └──────────────┘
```

O board vive atras de `repositories/` mesmo sem banco. Persistir depois =
trocar a implementacao desse repositorio por uma que serializa num `.hudtv`.
Nada fora dessa camada deve tocar o estado.

## Modelo do grid

- **12 colunas x 8 linhas**, fixo, **sem scroll**.
  Motivo: a TV nao rola. Board que passa da tela fica com metade invisivel
  pra sempre. Em 1080p isso da celulas de ~150x125px.
- Cada item tem `x`, `y`, `w`, `h` em **celulas**, nunca em pixels.
- Fonte e espacamento calibrados para leitura a distancia de sofa, nao para
  densidade de dashboard de escritorio.

### Posicionamento (hibrido, automatico como fallback)

```
Claude mandou x,y,w,h?   ──sim──▶  usa isso
        │ nao
        ▼
Usuario fixou o item?    ──sim──▶  respeita
        │ nao
        ▼
auto-placer: primeiro retangulo livre, compacta pra cima
```

**Board cheio:** o placer nao inventa. Devolve erro ao Claude dizendo que nao
coube e quanto espaco resta. O Claude decide se remove algo, encolhe o span ou
avisa o usuario. `board_status` informa ocupacao antes de tentar.

## Tipos de item

Portados do kinesis: `note`, `text`, `box` (aceita filhos), `image`, `arrow`.
Novos: `chart`, `video`, `notification`.

Fora de escopo: handtracking, camera, gestos.

## Ferramentas MCP

Vocabulario herdado do kinesis, adaptado para coordenadas de grid.
Todo `x,y,w,h` e opcional; omitir dispara o auto-placer.

```
add_note(text, x?, y?, w?, h?)          add_text(text, size?, ...)
add_box(label?, ...)                    add_image(path|url, ...)
add_video(path|url, autoplay?, ...)     add_chart(kind, data, title?, ...)
                                        kind: line|bar|pie|area

move_item(id, x, y)                     resize_item(id, w, h)
remove_item(id)                         set_parent(parent_id, ids[])
unparent(ids[])                         clear_board()

notify(message, level?)                 list_items()
                                        board_status()  -> ocupacao, espaco livre
```

### Notificacoes

Item de primeira classe, nao toast efemero. Chega com animacao de entrada e
**fica no board ate ser dispensado**. Servem de caixa de entrada: varias sessoes
do Claude podem anunciar "terminei" e o usuario ve tudo que ficou pendente numa
olhada. Some quando o servidor reinicia, como todo o resto nesta fase.

## Decisoes ja tomadas — nao reabrir sem motivo

1. Web app, nao app nativo. A TV nao roda nada; ela exibe o navegador do PC
   pela HDMI. React Native e Flutter foram descartados por isso.
2. Codigo separado do kinesis. Kinesis nao vira dependencia.
3. Sem auth, sem persistencia, sem scroll — todos por escolha, nao por preguica.
4. FastAPI, nao Node. Perde-se "uma linguagem so", ganha-se o template pronto
   com qualidade ja imposta por ferramenta.

## Midia

Video e imagem chegam como **caminho de arquivo local**, nunca URL externa.

```
add_video("/mnt/d_drive/.../clipe.mkv")
  -> backend valida existencia, registra id, serve bytes em /media/<id>
  -> front:  <video src="/media/<id>">
```

**Arquivo sumiu:** nao quebra e nao some do board. O item vira um bloco de
fundo preto com o texto centralizado da chave i18n `media.missing`
(EN "File not found" / PT "Arquivo perdido"). O caminho continua no item, para
o usuario saber o que faltou.

## Charts

Dados **inline** no `add_chart`. O board nao busca nada, nao conhece fonte de
dados, nao faz polling. Quem tem o numero e o Claude; ele manda o array pronto.
Atualizar um chart = chamar de novo com os dados novos.

Cor, em qualquer lugar que o board aceite uma: hex de 8 digitos carrega alpha
(`#33ccffaa`), entao texto e marcas de chart podem deixar o video de fundo
aparecer atraves delas.

## Passivo por padrao

O board **desenha e nada mais**. Nao troca a entrada da TV, nao mexe no sistema
operacional, nao chama o `~/tvkit/`. Uma sessao do Claude que queira trocar a
entrada chama o CLI diretamente — o board nao precisa saber que a TV existe.

Motivo: juntar superficie de exibicao com plano de controle faria o board
depender de ADB vivo e TV acessivel, e um `add_note` passaria a poder falhar
por causa de rede. Manter separado mantem cada peca simples.

**Unica excecao — som.** Notificacao toca um audio curto no navegador (Web
Audio, nada externo). E o que faz o aviso funcionar de outro comodo, e nao
arrasta nenhuma dependencia nova.

## Em aberto

- Nada bloqueante. Proximo passo e o esqueleto a partir do GoldStandard.
