import numpy as np
import time
import os
import argparse

from context_model import ContextModel, PRECISION, contar_lote

# ---------------------------------------------------------------------------
# rANS primitivos
# ---------------------------------------------------------------------------


def _C_rANS(s: int, state: int, counts: list[int]) -> int:
    """Codifica símbolo s no estado rANS. counts = [c0, c1]."""
    M = counts[0] + counts[1]
    cs = sum(counts[:s])  # frequência acumulada até s
    fs = counts[s]
    return (state // fs) * M + cs + (state % fs)


def _encode_symbol(state: int, s: int, counts: list[int], bitstream: list[int]) -> int:
    """
    Normaliza o estado e codifica o símbolo s.
    Emite bits para manter o estado no intervalo válido.
    """
    fs = counts[s]
    # Normalização: emite bits enquanto estado >= 2 * f_s
    while state >= 2 * fs:
        bitstream.append(state & 1)
        state >>= 1
    return _C_rANS(s, state, counts)


# ---------------------------------------------------------------------------
# Geração das tabelas tANS (tans_tables.h) a partir do rANS acima
#
# Cada entrada é o encoder rANS streaming (_encode_symbol, equação (7) do
# tutorial LASCAS 2025) aplicado a um estado x em [L, 2L-1], um símbolo s e uma
# configuração (f0, L-f0), com M = L, F(0)=f0, F(1)=L-f0, C(0)=0, C(1)=f0.
# O decoder em C monta sua tabela inversa a partir destas mesmas entradas
# (equivalente à equação (8) do rANS).
# ---------------------------------------------------------------------------


def tabela_rans(L, f0):
    """Para a cfg (f0, L-f0) devolve, por símbolo, listas [novo_estado, valor_bits, nbits]
    indexadas por (estado - L)."""
    counts = [f0, L - f0]
    out = {0: [], 1: []}
    for s in (0, 1):
        for x in range(L, 2 * L):
            emitidos = []  # ordem de emissão (LSB primeiro)
            novo = _encode_symbol(x, s, counts, emitidos)  # <- rANS do projeto
            k = len(emitidos)
            # o writer em C grava o valor MSB primeiro: 1º bit emitido = bit mais alto
            valor = 0
            for b in emitidos:
                valor = (valor << 1) | b
            out[s].append((novo, valor, k))
    return out


LS_PADRAO = "16"


def gerar(Ls):
    """Gera tans_tables.h com, para cada L, uma tabela por f0 = 1..L-1
    (P(0) = f0/L), todas obtidas do rANS (tabela_rans)."""
    h = []
    h.append(
        "/* tans_tables.h - GERADO por ANS-Streaming Encoder.py (--gerar-tabelas). Nao editar.\n"
    )
    h.append(
        " *\n * Para cada L (RANGE) ha L-1 configuracoes: cfg = f0-1, P(0) = f0/L, P(1) = (L-f0)/L.\n"
    )
    h.append(" * Cada entrada e o encoder rANS streaming do projeto aplicado a x em [L, 2L-1]:\n")
    h.append(" *   renormaliza (while x >= 2F: emite x&1, x >>= 1) e novo estado =\n")
    h.append(" *   (x/F)*L + C(s) + x mod F  (equacao (7) do tutorial LASCAS 2025).\n")
    h.append(" * Arrays planos: indice = cfg*L + (estado - L). EMPTY (0xFF) = nenhum bit.\n */\n\n")
    h.append(
        "#ifndef TANS_TABLES_H\n#define TANS_TABLES_H\n\n#include <stdint.h>\n\n#define EMPTY 0xFF\n\n"
    )
    for L in Ls:
        assert L <= 128, "L maximo 128 (estados cabem em uint8_t)"
        tabs = [tabela_rans(L, f0) for f0 in range(1, L)]

        def arr(nome, sym, campo):
            vals = []
            for t in tabs:
                for novo, valor, k in t[sym]:
                    vals.append(
                        novo if campo == 0 else ((0xFF if k == 0 else valor) if campo == 1 else k)
                    )
            lin = ",".join(str(v) for v in vals)
            h.append(f"static const uint8_t {nome}_{L}[{len(vals)}] = {{{lin}}};\n")

        arr("A_ns", 0, 0)
        arr("A_bits", 0, 1)
        arr("A_nb", 0, 2)
        arr("B_ns", 1, 0)
        arr("B_bits", 1, 1)
        arr("B_nb", 1, 2)
        h.append("\n")
    h.append(
        "typedef struct { int L, ncfg, flush;\n"
        "  const uint8_t *a_ns, *a_bits, *a_nb, *b_ns, *b_bits, *b_nb; } TansSet;\n"
    )
    h.append("static const TansSet tans_sets[] = {\n")
    for L in Ls:
        fl = (L - 1).bit_length()
        h.append(
            f"  {{{L}, {L-1}, {fl}, A_ns_{L}, A_bits_{L}, A_nb_{L}, B_ns_{L}, B_bits_{L}, B_nb_{L}}},\n"
        )
    h.append("};\n")
    h.append(f"#define NUM_SETS {len(Ls)}\n\n")
    h.append(
        "static const TansSet *tans_find(int L) {\n  for (int i = 0; i < NUM_SETS; i++) if (tans_sets[i].L == L) return &tans_sets[i];\n  return 0;\n}\n\n#endif\n"
    )
    return "".join(h)


# ---------------------------------------------------------------------------
# Encoder contextual semi-dinâmico (um estado rANS por lote)
#
# Lote = n blocos seguidos. Cada lote é codificado com um estado novo e vira
# [bitstream | estado]. Depois de cada lote, o encoder conta os símbolos dele e
# estima as probabilidades do lote seguinte; o decoder faz a mesma conta.
# ---------------------------------------------------------------------------


def tamanho_lote(recalc_window: int, blocos_por_lote: int) -> int:
    """Símbolos por lote. blocos_por_lote = 0 (probabilidade fixa) usa lotes de 1 bloco."""
    return recalc_window * max(1, blocos_por_lote)


def encode_lote(symbols: list[int], start: int, end: int, model: ContextModel) -> tuple[str, int]:
    """Codifica symbols[start:end] com um estado novo. Devolve (bitstream, estado_final)."""
    bitstream: list[int] = []
    state = PRECISION
    for i in range(start, end):
        ctx = symbols[i + 1] if i + 1 < end else 0
        state = _encode_symbol(state, symbols[i], model.get_counts(ctx), bitstream)
    return "".join(map(str, bitstream)), state


def encode_stream(
    symbols: list[int], model: ContextModel, recalc_window: int, blocos_por_lote: int
) -> tuple[list[tuple[str, int]], int]:
    """Codifica o plano lote a lote.

    Devolve (lista de (bitstream, estado_final) por lote, número de trocas de probabilidade).
    """
    n = len(symbols)
    tam = tamanho_lote(recalc_window, blocos_por_lote)
    lotes = []
    trocas = 0
    for start in range(0, n, tam):
        end = min(start + tam, n)
        lotes.append(encode_lote(symbols, start, end, model))
        if blocos_por_lote > 0:
            trocas += model.atualizar_lote(contar_lote(symbols, start, end))
    return lotes, trocas


# ---------------------------------------------------------------------------
# Leitura de input
# ---------------------------------------------------------------------------


def load_symbols(path: str) -> list[int]:
    with open(path, "r") as f:
        content = f.read().replace(",", " ").replace("\n", " ").replace("\r", "")
    tokens = content.split()
    if all(len(t) == 1 for t in tokens if t):
        return [int(x) for x in tokens if x in ("0", "1")]
    return [int(c) for c in content if c in ("0", "1")]


# ---------------------------------------------------------------------------
# Salvar arquivo comprimido
# ---------------------------------------------------------------------------


def save_encoded(
    path: str,
    num_symbols: int,
    recalc_window: int,
    blocos_por_lote: int,
    headers_hex: str,
    lotes: list[tuple[str, int]],
) -> None:
    """
    Formato do arquivo comprimido (texto):
      Linha 0: num_symbols
      Linha 1: modo ("semidinamico")
      Linha 2: recalc_window (símbolos por bloco)
      Linha 3: blocos_por_lote (0 = probabilidade fixa)
      Linha 4: probabilidade inicial (hex)
      Linhas 5...: um lote por linha, "estado_final bitstream"
    """
    with open(path, "w") as f:
        f.write(f"{num_symbols}\n")
        f.write("semidinamico\n")
        f.write(f"{recalc_window}\n")
        f.write(f"{blocos_por_lote}\n")
        f.write(f"{headers_hex}\n")
        for bitstream, final_state in lotes:
            f.write(f"{final_state} {bitstream}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="ANS Streaming Encoder — Contextual semi-dinâmico")
    parser.add_argument("--input", default="input.txt", help="Arquivo de entrada")
    parser.add_argument("--output", default="input_encoded.bin", help="Arquivo de saída")
    parser.add_argument(
        "--recalc-window", type=int, default=1000, help="Símbolos por bloco (padrão: 1000)"
    )
    parser.add_argument(
        "--blocos-por-lote",
        type=int,
        default=4,
        help="Blocos por lote: a probabilidade muda a cada n blocos (0 = fixa; padrão: 4)",
    )
    parser.add_argument(
        "--gerar-tabelas", action="store_true", help="Gera tans_tables.h a partir do rANS e sai"
    )
    parser.add_argument(
        "--ranges", default=LS_PADRAO, help="valores de L (RANGE) gerados, ex.: 16,32"
    )
    parser.add_argument(
        "--saida",
        default="tans_tables.h",
        help="Arquivo de saída das tabelas (padrão: tans_tables.h)",
    )
    args = parser.parse_args()

    if args.gerar_tabelas:
        Ls = [int(x) for x in args.ranges.split(",")]
        with open(args.saida, "w", encoding="utf-8") as f:
            f.write(gerar(Ls))
        print(f"{args.saida} gerado: L = {Ls}, tabelas f0 = 1..L-1 para cada L")
        return

    if not os.path.exists(args.input):
        print(f"Erro: arquivo '{args.input}' não encontrado.")
        return
    if args.recalc_window < 1 or args.blocos_por_lote < 0:
        print("Erro: --recalc-window deve ser >= 1 e --blocos-por-lote >= 0.")
        return

    print("=" * 72)
    print(
        f"  ANS STREAMING ENCODER  |  semi-dinâmico  |  bloco={args.recalc_window}  |  "
        f"n={args.blocos_por_lote}"
    )
    print("=" * 72)

    symbols = load_symbols(args.input)
    num_symbols_real = len(symbols)
    print(f"Símbolos lidos: {num_symbols_real}")
    print("Contexto: 1D (lookahead-1)  |  2 contextos")

    # Probabilidade inicial do plano (vai no cabeçalho). Serializa ANTES de codificar,
    # porque a codificação vai alterando as probabilidades a cada lote.
    model = ContextModel()
    model.estimar_inicial(symbols)
    headers_hex = model.serializar_inicial()

    t0 = time.time()
    lotes, trocas = encode_stream(symbols, model, args.recalc_window, args.blocos_por_lote)
    t1 = time.time()

    # Métricas
    bits_bitstream = sum(len(b) for b, _ in lotes)
    bits_state = sum(st.bit_length() for _, st in lotes)
    bits_header_oh = model.header_overhead_bits()
    bits_pad = model.padding_bits()
    bits_total_tx = bits_bitstream + bits_state + bits_header_oh + bits_pad
    taxa_compressao = (
        (1.0 - bits_total_tx / num_symbols_real) * 100 if num_symbols_real > 0 else 0.0
    )

    # Entropia global
    c0 = symbols.count(0)
    c1 = symbols.count(1)
    p0 = c0 / num_symbols_real
    p1 = c1 / num_symbols_real
    H = 0.0
    if p0 > 0:
        H -= p0 * np.log2(p0)
    if p1 > 0:
        H -= p1 * np.log2(p1)

    print(f"\nEntropia global H = {H:.6f} bits/símbolo")
    print(f"Limite teórico (sem contexto): {H * num_symbols_real:.1f} bits totais\n")

    print("-" * 72)
    print(f"{'Métrica':<40} {'Valor':>12} {'Unidade'}")
    print("-" * 72)
    print(f"{'Símbolos originais (sem padding)':<40} {num_symbols_real:>12} bits")
    print(f"{'Lotes':<40} {len(lotes):>12}")
    print(f"{'Trocas de probabilidade':<40} {trocas:>12}")
    print(f"{'Bits no bitstream rANS':<40} {bits_bitstream:>12} bits")
    print(f"{'Bits dos estados finais':<40} {bits_state:>12} bits")
    print(f"{'Overhead de cabeçalho':<40} {bits_header_oh:>12} bits")
    print(f"{'Preenchimento do cabeçalho':<40} {bits_pad:>12} bits")
    print(f"{'Total transmitido':<40} {bits_total_tx:>12} bits")
    print(f"{'Taxa de compressão':<40} {taxa_compressao:>11.2f}%")
    print(f"{'Tempo de codificação':<40} {t1 - t0:>11.6f}s")
    print("-" * 72)

    save_encoded(
        args.output,
        num_symbols_real,
        args.recalc_window,
        args.blocos_por_lote,
        headers_hex,
        lotes,
    )

    print(f"\nArquivo salvo: '{args.output}'")
    print("=" * 72)


if __name__ == "__main__":
    main()