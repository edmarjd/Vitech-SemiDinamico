# Projeto ANS — compressão de planos de bits com rANS e tANS (semi-dinâmico)

Compressão **sem perdas** de imagens em tons de cinza, feita plano de bit por plano de bit, usando
**ANS (Asymmetric Numeral Systems)**. O projeto tem duas partes que se complementam:

| Parte | Linguagem | Função |
|---|---|---|
| **rANS** (streaming) | Python | Implementação de referência, também semi-dinâmica. Também é quem **gera as tabelas** do tANS. |
| **tANS** (baseado em tabelas) | C | Encoder e decoder rápidos, que consultam as tabelas e adaptam a probabilidade entre lotes de blocos. |

---

## Como funciona

1. **Planos de bits.** Cada pixel (8 bits) é separado em 8 planos binários, do bit 0 ao bit 7. Cada plano
   vira uma sequência de símbolos `0` e `1`, gravada em `plano_bit_N.txt`.
   Os planos altos (6 e 7) são suaves e previsíveis. Os baixos (0 a 3) são quase ruído.
2. **Contexto 1D (lookahead).** A probabilidade de um símbolo depende do **próximo** símbolo do bloco
   (0 no último símbolo). O decoder trabalha de trás para frente (o ANS é LIFO), então o próximo símbolo já
   foi decodificado e o contexto fica disponível sem ser transmitido.
3. **Blocos independentes.** O plano é dividido em blocos (`BLOCK_SIZE`). Cada bloco é codificado sozinho,
   com o estado do ANS reiniciado, e termina com o estado final gravado junto do bitstream.
4. **Probabilidade por plano.** Cada plano começa com a sua própria probabilidade, **independente para cada
   contexto**: `P(0 | próximo = 0)` e `P(0 | próximo = 1)`. O encoder estima os valores a partir do plano
   inteiro e procura em volta o par que gera o menor arquivo. Esse par vai no cabeçalho (2 bytes).
5. **Adaptação a cada n blocos (semi-dinâmico).** Um **lote** são `n` blocos seguidos. Depois de codificar
   um lote, o encoder conta os símbolos dele e estima a probabilidade que será usada no lote seguinte.
   O decoder faz a mesma conta com os símbolos que acabou de decodificar (em ordem inversa, o que dá as
   mesmas contagens). Por isso **só a probabilidade inicial é transmitida**; as dos lotes seguintes são
   reconstruídas dos dois lados pela mesma regra (`adapt.h`).

   ```text
   encoder:  lote 1 [ bitstream | estado ] ──conta os símbolos──▶ prob. do lote 2
   decoder:  lote 1 [ estado | bitstream ] ──conta os símbolos──▶ prob. do lote 2
   ```

   ![Adaptação semi-dinâmica entre lotes](semi.JPG)

   Dentro de um lote a probabilidade não muda. A adaptação não é símbolo a símbolo.
6. **Escolha por plano.** Para cada plano o encoder testa os valores de `L` disponíveis e os valores de `n`
   (`0, 1, 2, 4, 8, 16`), e fica com a combinação de menor tamanho. `n = 0` significa **tabela fixa** durante o
   plano inteiro. O semi-dinâmico, portanto, nunca fica pior que a tabela fixa do mesmo plano.
7. **Tabelas geradas pelo rANS.** O `tans_tables.h` não é escrito à mão. O `ANS-Streaming Encoder.py` aplica
   o encoder rANS (`_encode_symbol`) a cada estado `x` em `[L, 2L-1]`, a cada símbolo e a cada probabilidade
   `f0 = 1 .. L-1`, e grava o resultado. O C só lê essas tabelas.
8. **Modo RAW.** Se o tANS não deixa o plano menor que o original, o plano é gravado sem compressão
   (apenas 13 bytes de cabeçalho a mais).

### Regra de adaptação (`adapt.h` e `context_model.py`)

Para cada contexto `c`, com `n0` zeros e `n1` uns contados no lote:

```text
f0[c] = arredonda( L × (n0 + 0,5) / (n0 + n1 + 1) ),  limitado a 1 .. L-1
```

A conta é feita em inteiros, para dar o mesmo resultado no encoder e no decoder. Se um contexto não teve
nenhuma ocorrência no lote, ele mantém o valor anterior.

A versão Python usa a mesma regra, com 32 níveis (`PRECISION = 32`) em vez de `L`. Lá, cada lote é codificado
com **um estado rANS novo** (as probabilidades do lote seguinte só são conhecidas depois de decodificar o
anterior, então os lotes não podem compartilhar um estado contínuo). A geração das tabelas do tANS não
depende dessa parte: ela usa só `tabela_rans` e `_encode_symbol`.

---

## Requisitos

- Python 3.9 ou superior, com `numpy`, `opencv-python` e `matplotlib`
- `gcc` (ou outro compilador C99) e a biblioteca matemática (`-lm`)

```bash
pip install numpy opencv-python matplotlib
```

---

## Como rodar

Execute tudo de **dentro da pasta do projeto**. Atenção ao `-O2`, que é a letra **O**, não o número zero.

### Comando completo (gera as tabelas, compila e testa uma imagem)

```bash
python3 "ANS-Streaming Encoder.py" --gerar-tabelas && gcc -O2 Encoder_Ans.c -o encoder -lm && gcc -O2 Decoder.c -o decoder && python3 Bit_Planes.py Kodak/kodim19.png
```

O nome do primeiro arquivo tem **espaço**, por isso as aspas. A primeira linha da saída deve ser
`tans_tables.h gerado: L = [16], tabelas f0 = 1..L-1 para cada L`.

### Passo a passo

```bash
# 1. Gerar as tabelas do tANS a partir do rANS
python3 "ANS-Streaming Encoder.py" --gerar-tabelas

# 2. Compilar (o adapt.h precisa estar na mesma pasta)
gcc -O2 Encoder_Ans.c -o encoder -lm
gcc -O2 Decoder.c -o decoder

# 3. Rodar numa imagem (outro caminho funciona do mesmo jeito)
python3 Bit_Planes.py Kodak/kodim19.png
python3 Bit_Planes.py DIV2K/0063.png

# Opcional: mostra o log completo do encoder e do decoder para cada plano
python3 Bit_Planes.py Kodak/kodim19.png --detalhe
```

Sem argumento, o `Bit_Planes.py` usa `foto.png` (ou `foto.jpg`) da pasta atual. O `--detalhe` precisa vir
**depois** do caminho da imagem.

O `Bit_Planes.py` separa a imagem em planos, comprime e decodifica cada um, confere se o resultado é
idêntico ao original e imprime uma tabela com uma coluna por plano e uma coluna `TOTAL`.
Ele também cria `plano_bit_N.txt`, `plano_bit_N_encoded.bin`, `saida_N.txt` e `resultado_planos_bits.png`.

### Rodar o encoder e o decoder em C diretamente

```bash
./encoder plano_bit_7.txt                              # gera plano_bit_7_encoded.bin
./decoder plano_bit_7_encoded.bin saida_7.txt          # reconstrói a sequência

./encoder -n 4 plano_bit_7.txt                         # força lotes de 4 blocos
./encoder -L 16 plano_bit_7.txt                        # força L = 16
./encoder plano_bit_0.txt plano_bit_1.txt              # vários arquivos de uma vez
```

As opções `-L` e `-n` vêm antes dos arquivos. O decoder recebe sempre exatamente dois argumentos: o `.bin`
e o arquivo de saída.

### Versão Python (rANS de referência)

```bash
# Codificar e decodificar um arquivo de símbolos
python3 "ANS-Streaming Encoder.py" --input input.txt --output comprimido.bin --recalc-window 1000 --blocos-por-lote 4
python3 ANS-Streaming-Decoder.py --encoded comprimido.bin --output saida.txt --verify input.txt

# Rodar todos os arquivos de inputs/ e de Plano_de_Bits/ e imprimir uma tabela comparativa
python3 run_all.py --recalc-window 1000 --blocos-por-lote 4
```

Padrões: `--recalc-window 1000` e `--blocos-por-lote 4`. Sem `--input`/`--output`, o encoder usa
`input.txt` e `input_encoded.bin`; o decoder usa `input_encoded.bin` e `output.txt`. O `run_all.py` pula os
arquivos que não existem (a pasta `inputs/` não faz parte do repositório; crie-a se quiser usá-la).

`--recalc-window` é o tamanho do bloco (símbolos) e `--blocos-por-lote` é o `n`: a probabilidade muda a
cada `n` blocos (`0` = probabilidade fixa). O arquivo comprimido do Python guarda os dois valores, então o
decoder não precisa deles na linha de comando. Ele **não** tem o modo RAW do C, por isso planos quase
aleatórios terminam um pouco maiores que o original (cerca de −1,5%).

---

## Estrutura de arquivos

```text
Projeto-ANS-main/
├── ANS-Streaming Encoder.py   Encoder rANS (Python) e gerador do tans_tables.h
├── ANS-Streaming-Decoder.py   Decoder rANS (Python)
├── context_model.py           Modelo de contexto semi-dinâmico da versão Python
├── run_all.py                 Roda o pipeline rANS em inputs/ e Plano_de_Bits/
├── Bit_Planes.py              Separa a imagem em planos, roda o tANS em C e imprime o relatório
├── Encoder_Ans.c              Encoder tANS semi-dinâmico (C)
├── Decoder.c                  Decoder tANS semi-dinâmico (C)
├── adapt.h                    Regra de adaptação, compartilhada pelo encoder e pelo decoder
├── tans_tables.h              Tabelas do tANS (GERADO: não editar à mão)
├── semi.JPG                   Diagrama da adaptação entre lotes
├── Kodak/                     Imagens de teste (kodim01 a kodim24)
├── DIV2K/                     Imagens de teste maiores
├── Plano_de_Bits/             Planos de bits de exemplo (plano_bit_0.txt a plano_bit_7.txt, 102.400 símbolos cada)
└── inputs/                    (opcional, não versionada) Sequências input_1.txt a input_8.txt para o run_all.py
```

Os executáveis (`encoder`, `decoder`) e os arquivos que o `Bit_Planes.py` cria na pasta do projeto
(`plano_bit_N.txt`, `*_encoded.bin`, `saida_N.txt`, `resultado_planos_bits.png`) não são versionados.

---

## Formato do arquivo comprimido (C)

Cabeçalho global, **13 bytes**:

| Campo | Tamanho |
|---|---|
| Número de símbolos | 4 bytes |
| `RANGE` (L) | 1 byte |
| Modo (`1` = tANS, `0` = RAW) | 1 byte |
| Número de blocos | 4 bytes |
| `n`: blocos por lote (`0` = tabela fixa) | 1 byte |
| `f0` inicial do contexto "próximo símbolo = 0" | 1 byte |
| `f0` inicial do contexto "próximo símbolo = 1" | 1 byte |

No **modo tANS**, cada bloco vem em seguida:

| Campo | Tamanho |
|---|---|
| Tamanho do bloco em bytes | 4 bytes |
| Bits do bloco: símbolos, estado final (`FLUSH_BITS` bits) e *stop bit* | variável |

O bloco não carrega a tabela que usou: o decoder a reconstrói pela regra de adaptação.
No **modo RAW**, o cabeçalho é seguido de 1 bit por símbolo.

---

## Métricas do relatório

| Linha | Significado |
|---|---|
| TAMANHO ORIGINAL | Símbolos do plano (1 bit cada) |
| TABELA (RANGE) | `L=16` quando usa tANS, `RAW` quando não comprime |
| TAMANHO TOTAL DE BLOCOS | Número de blocos tANS (0 em RAW) |
| OVERHEAD | Cabeçalhos: (13 + 4 × blocos) × 8 bits; em RAW, 104 bits |
| BITS DE PREENCHIMENTO | Bits que completam o último byte de cada bloco |
| ESTADO | Estado final de cada bloco: (`FLUSH_BITS` + 1) bits, incluindo o *stop bit* |
| BITSTREAM | Bits produzidos pela codificação dos símbolos |
| COMPRIMIDO GLOBAL | Overhead + preenchimento + estado + bitstream |
| GANHO TOTAL | Original − comprimido (negativo se o arquivo cresceu) |
| TAXA DE COMPRESSAO | (1 − comprimido / original) × 100 |
| TEMPO ENCODER / DECODER | Tempo de relógio de uma execução, incluindo leitura e escrita de arquivo |
| VERIFICACAO LOSSLESS | `OK` quando o plano decodificado é idêntico ao original |

O título da tabela mostra o `BLOCK_SIZE` usado, por exemplo `PLANOS DE BITS BLOCO(500)`. O `n` escolhido,
o número de trocas de tabela e a probabilidade inicial de cada contexto não entram na tabela; aparecem no
log de cada plano com `--detalhe` (linhas `Atualização (blocos)`, `Trocas de tabela` e `Tabela inicial`).

O tempo do encoder é maior que o da versão estática porque ele testa várias combinações de `n` e de
probabilidade inicial em cada plano. O decoder não faz essa busca.

---

## Parâmetros que podem ser alterados

| O quê | Onde | Observação |
|---|---|---|
| Tamanho do bloco | `BLOCK_SIZE` em `Encoder_Ans.c` e `Decoder.c` | **Precisa ser o mesmo valor nos dois programas**. Padrão: 500. Também pode ser passado na compilação: `-DBLOCK_SIZE=1000` |
| Valores de `n` testados | `NUP_CANDIDATOS` em `Encoder_Ans.c` | Padrão: `0, 1, 2, 4, 8, 16`. O decoder lê o `n` do cabeçalho, então não precisa mudar |
| Busca da prob. inicial | `INIT_RAIO` em `Encoder_Ans.c` | Padrão: 2 níveis de `f0` para cada lado da estimativa |
| `n` fixo | `./encoder -n N` | Entre 1 e 255 |
| `L` fixo | `./encoder -L N` | Precisa ser um dos `L` presentes no `tans_tables.h` |
| Limite de símbolos por plano | `MAX_SYMBOLS` (encoder) e `MAX_DECODED_SYMBOLS` (decoder) | Padrão: 12 milhões, o suficiente para as imagens do DIV2K |
| Tamanho das tabelas (L) | `--ranges` ao gerar as tabelas | Padrão: `16`. O estado precisa caber em 8 bits, então L ≤ 128 |

Exemplo com dois tamanhos de tabela (o encoder escolhe o melhor `L` por plano):

```bash
python3 "ANS-Streaming Encoder.py" --gerar-tabelas --ranges 16,32
gcc -O2 Encoder_Ans.c -o encoder -lm && gcc -O2 Decoder.c -o decoder
```

Depois de mudar `BLOCK_SIZE`, `MAX_SYMBOLS` ou as tabelas, recompile os dois programas em C. Com a opção
`-D`, use o mesmo valor nos dois:

```bash
gcc -O2 -DBLOCK_SIZE=1000 Encoder_Ans.c -o encoder -lm && gcc -O2 -DBLOCK_SIZE=1000 Decoder.c -o decoder
```

---

## Resultados de referência

Versão atual (`BLOCK_SIZE = 500`, `L = 16`), `python3 Bit_Planes.py Kodak/kodim19.png`:

| Plano | 0 a 3 | 4 | 5 | 6 | 7 | **Total** |
|---|---|---|---|---|---|---|
| Modo | RAW | tANS | tANS | tANS | tANS | |
| Taxa | −0,03% | 10,15% | 25,07% | 40,83% | 64,99% | **17,62%** |

Total: 3.145.728 → 2.591.528 bits, verificação lossless `OK` nos 8 planos.

Comparação entre versões do projeto, medida em outra foto de 512 × 768 (3.145.728 bits nos 8 planos),
com `L = 16`, quando o padrão ainda era `BLOCK_SIZE = 10000`:

| Versão | Bits comprimidos | Taxa |
|---|---|---|
| Duas tabelas espelhadas por plano, escolhidas só no encoder (versão anterior) | 2.646.792 | 15,86% |
| Probabilidade independente por contexto, tabela fixa por plano | 2.627.928 | 16,46% |
| Semi-dinâmico (esta versão) | 2.619.912 | 16,72% |

Para comparação, o rANS em Python na mesma foto (blocos de 1000 símbolos): 16,05% com probabilidades por
bloco no cabeçalho (versão anterior), 16,10% com `n = 1` e 16,52% com `n = 4` (padrão).

Numa imagem de 1356 × 2040 a taxa passou de 15,81% (anterior) para 16,44% (contexto independente) e para
17,40% (semi-dinâmico). A adaptação ajuda mais nos planos 6 e 7, cuja estatística muda ao longo da imagem.
Nos planos 4 e 5 o encoder costuma escolher tabela fixa. Os números dependem da imagem.

---

## Problemas comuns

| Mensagem ou sintoma | Causa e solução |
|---|---|
| `Ficheiro ou pasta inexistente` / `No such file` | O terminal está na pasta errada. Use `cd` para a pasta do projeto. |
| `unrecognized command-line option '-02'` | Foi digitado zero em vez da letra O. Use `-O2`. |
| `adapt.h: No such file` | O `adapt.h` precisa estar na mesma pasta do `Encoder_Ans.c` e do `Decoder.c`. |
| `can't open file ... ANS-Streaming_Encoder.py` | O nome real tem espaço: `"ANS-Streaming Encoder.py"`, entre aspas. |
| `'./encoder' não encontrado. Compile antes` | Os programas em C não foram compilados nesta pasta. Rode os dois `gcc`. |
| `Erro ao carregar a imagem.` | Caminho da imagem errado, ou nenhum `foto.png` na pasta quando o script é chamado sem argumento. |
| `ERRO: muitos simbolos` | O plano passa de `MAX_SYMBOLS`. Aumente o valor no encoder e no decoder. |
| `ERRO` na linha VERIFICACAO LOSSLESS | `BLOCK_SIZE` diferente entre encoder e decoder, ou `tans_tables.h` ou `adapt.h` de outra versão. Gere as tabelas de novo e recompile os dois. |
| `RANGE` diferente entre arquivo e decoder | O `.bin` foi gerado com outras tabelas. Recompile o decoder ou gere o `.bin` de novo. |

---

## Observações

- O projeto é **semi-dinâmico**: a probabilidade começa em um valor próprio de cada plano e é recalculada a
  cada `n` blocos, usando apenas os símbolos do lote anterior. Dentro de um lote a tabela é fixa. Não há
  adaptação símbolo a símbolo.
- A versão em C reinicia o estado a cada bloco. A versão Python (`run_all.py`) reinicia o estado a cada
  lote, usa 5 bits de precisão por contexto em vez de tabelas tANS e grava só a probabilidade inicial
  (10 bits) no cabeçalho.
- Os tempos do relatório vêm de uma única execução e incluem a leitura e a escrita de arquivos. Servem de
  referência, não de medida precisa do desempenho do tANS.