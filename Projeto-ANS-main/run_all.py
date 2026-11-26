"""
run_all.py — Executa encoder/decoder rANS (semi-dinâmico) em todos os inputs e planos de bits.
Uso:
    python3 run_all.py --recalc-window 1000 --blocos-por-lote 4
"""

import os
import time
import argparse
from collections import deque

from context_model import ContextModel, PRECISION, contar_lote

# ---------------------------------------------------------------------------
# rANS primitivos
# ---------------------------------------------------------------------------


def _C_rANS(s, state, counts):
    M = counts[0] + counts[1]
    cs = sum(counts[:s])
    fs = counts[s]
    return (state // fs) * M + cs + (state % fs)


def _encode_symbol(state, s, counts, bitstream):
    fs = counts[s]
    while state >= 2 * fs:
        bitstream.append(state & 1)
        state >>= 1
    return _C_rANS(s, state, counts)


def _D_rANS(state, counts):
    M = counts[0] + counts[1]
    slot = state % M
    s = 1 if slot >= counts[0] else 0
    cs = [0, counts[0]]
    prev = (state // M) * counts[s] + slot - cs[s]
    return s, prev


# ---------------------------------------------------------------------------
# Leitura de símbolos
# ---------------------------------------------------------------------------


def load_symbols(path):
    with open(path, "r") as f:
        content = f.read().replace(",", " ").replace("\n", " ").replace("\r", "")
    tokens = content.split()
    if all(len(t) == 1 for t in tokens if t):
        return [int(x) for x in tokens if x in ("0", "1")]
    return [int(c) for c in content if c in ("0", "1")]


# ---------------------------------------------------------------------------
# Lotes: um estado rANS por lote (n blocos), probabilidade reestimada entre lotes
# ---------------------------------------------------------------------------


def encode_lote(symbols, start, end, model):
    """Codifica symbols[start:end] com um estado novo. Devolve (bitstream, estado_final)."""
    bitstream = []
    state = PRECISION
    for i in range(start, end):
        ctx = symbols[i + 1] if i + 1 < end else 0
        state = _encode_symbol(state, symbols[i], model.get_counts(ctx), bitstream)
    return "".join(map(str, bitstream)), state


def decode_lote(bitstream_str, final_state, n_simbolos, model):
    """Decodifica um lote do último símbolo para o primeiro (rANS é LIFO)."""
    bits = deque(map(int, bitstream_str[::-1]))
    decoded = [0] * n_simbolos
    state = final_state
    last_decoded = 0
    for i in range(n_simbolos - 1, -1, -1):
        counts = model.get_counts(last_decoded)
        s, prev = _D_rANS(state, counts)
        M = counts[0] + counts[1]
        while prev < M and bits:
            prev = (prev << 1) | bits.popleft()
        state = prev
        decoded[i] = s
        last_decoded = s
    return decoded


# ---------------------------------------------------------------------------
# Pipeline completo para um arquivo (contexto 1D lookahead)
# ---------------------------------------------------------------------------


def run_one(path, recalc_window, blocos_por_lote):
    symbols = load_symbols(path)
    n = len(symbols)
    tam = recalc_window * max(1, blocos_por_lote)
    n_lotes = (n + tam - 1) // tam

    # Probabilidade inicial do plano (cabeçalho), gravada antes de a adaptação mexer nela
    model_enc = ContextModel()
    model_enc.estimar_inicial(symbols)
    hdr_hex = model_enc.serializar_inicial()

    # -----------------------------------------------------------------------
    # ENCODE (lote a lote; dentro do lote, ordem direta)
    # -----------------------------------------------------------------------
    lotes = []
    trocas = 0
    t0 = time.time()
    for start in range(0, n, tam):
        end = min(start + tam, n)
        lotes.append(encode_lote(symbols, start, end, model_enc))
        if blocos_por_lote > 0:
            trocas += model_enc.atualizar_lote(contar_lote(symbols, start, end))
    t_enc = time.time() - t0

    # -----------------------------------------------------------------------
    # DECODE (lote a lote; dentro do lote, ordem inversa)
    # -----------------------------------------------------------------------
    model_dec = ContextModel()
    model_dec.carregar_inicial(hdr_hex)

    decoded = []
    t0 = time.time()
    for k, (bitstream, final_state) in enumerate(lotes):
        n_lote = min(tam, n - k * tam)
        simbolos = decode_lote(bitstream, final_state, n_lote, model_dec)
        decoded.extend(simbolos)
        if blocos_por_lote > 0:
            model_dec.atualizar_lote(contar_lote(simbolos, 0, len(simbolos)))
    t_dec = time.time() - t0

    ok = decoded == symbols

    # Métricas
    bits_bs = sum(len(b) for b, _ in lotes)
    bits_state = sum(st.bit_length() for _, st in lotes)
    bits_hdr = model_enc.header_overhead_bits()
    bits_pad = model_enc.padding_bits()
    bits_total = bits_bs + bits_state + bits_hdr + bits_pad
    taxa = (1.0 - bits_total / n) * 100 if n > 0 else 0.0

    return {
        "n": n,
        "n_lotes": n_lotes,
        "trocas": trocas,
        "bits_bs": bits_bs,
        "bits_state": bits_state,
        "bits_hdr": bits_hdr,
        "bits_pad": bits_pad,
        "bits_total": bits_total,
        "taxa": taxa,
        "decode_ok": ok,
        "t_enc": t_enc,
        "t_dec": t_dec,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Executa encoder/decoder rANS semi-dinâmico em todos os inputs e planos de bits"
    )
    parser.add_argument(
        "--recalc-window", type=int, default=1000, help="Símbolos por bloco (padrão: 1000)"
    )
    parser.add_argument(
        "--blocos-por-lote",
        type=int,
        default=4,
        help="Blocos por lote: a probabilidade muda a cada n blocos (0 = fixa; padrão: 4)",
    )
    args = parser.parse_args()
    rw = args.recalc_window
    nb = args.blocos_por_lote

    W = 130
    print("=" * W)
    print(f"  RUN ALL  |  contexto=1D lookahead  |  bloco = {rw}  |  blocos por lote = {nb}")
    print("=" * W)

    header_row = (
        f"{'BLOCO':>8} | {'ARQUIVO':<12} | {'ORIGINAL':>10} | {'LOTES':>6} | "
        f"{'OVERHEAD':>10} | {'PADDING':>8} | {'ESTADO':>8} | {'BITSTREAM':>10} | "
        f"{'COMPRIMIDO':>11} | {'TAXA':>8} | {'T_ENC':>8} | {'T_DEC':>8} | OK"
    )

    def print_row(label, r):
        ok = "✓" if r["decode_ok"] else "✗"
        print(
            f"{rw:>8} | {label:<12} | {r['n']:>10} | {r['n_lotes']:>6} | "
            f"{r['bits_hdr']:>10} | {r['bits_pad']:>8} | {r['bits_state']:>8} | "
            f"{r['bits_bs']:>10} | {r['bits_total']:>11} | "
            f"{r['taxa']:>7.2f}% | {r['t_enc']:>7.4f}s | {r['t_dec']:>7.4f}s | {ok}"
        )

    def print_global(g_n, g_bs, g_state, g_hdr, g_pad, g_total):
        if g_n > 0:
            g_taxa = (1.0 - g_total / g_n) * 100
            print("-" * W)
            print(
                f"{'':>8} | {'GLOBAL':<12} | {g_n:>10} | {'':>6} | "
                f"{g_hdr:>10} | {g_pad:>8} | {g_state:>8} | {g_bs:>10} | "
                f"{g_total:>11} | {g_taxa:>7.2f}% | {'':>8} | {'':>8} |"
            )

    def rodar_grupo(titulo, pasta, prefixo, indices, rotulo):
        print(f"\n{'─' * W}")
        print(f"  {titulo} (contexto 1D lookahead, bloco={rw}, blocos por lote={nb})")
        print(f"{'─' * W}")
        print(header_row)
        print("-" * W)

        g_n = g_bs = g_state = g_hdr = g_pad = g_total = 0
        for i in indices:
            nome = f"{prefixo}_{i}.txt"
            path = os.path.join(pasta, nome)
            if not os.path.exists(path):
                print(f"  {nome} não encontrado, pulando.")
                continue
            r = run_one(path, rw, nb)
            print_row(rotulo + str(i), r)
            g_n += r["n"]
            g_bs += r["bits_bs"]
            g_state += r["bits_state"]
            g_hdr += r["bits_hdr"]
            g_pad += r["bits_pad"]
            g_total += r["bits_total"]
        print_global(g_n, g_bs, g_state, g_hdr, g_pad, g_total)

    rodar_grupo("INPUTS", "inputs", "input", range(1, 9), "INPUT_")
    rodar_grupo("PLANOS DE BITS", "Plano_de_Bits", "plano_bit", range(8), "PLANO_")

    print(f"\n{'=' * W}")
    print("  Processamento concluído.")
    print("=" * W)


if __name__ == "__main__":
    main()