
import os
import argparse
import time
from collections import deque

from context_model import ContextModel, PRECISION, contar_lote

# ---------------------------------------------------------------------------
# rANS primitivos (decoder)
# ---------------------------------------------------------------------------


def _D_rANS(state: int, counts: list[int]) -> tuple[int, int]:
    """
    Decodifica um símbolo do estado rANS.
    counts = [c0, c1]. Retorna (símbolo, estado_anterior_não_normalizado).
    """
    M = counts[0] + counts[1]
    cs = [0, counts[0]]  # frequências acumuladas: cs[0]=0, cs[1]=c0
    slot = state % M
    # Encontra o símbolo cujo intervalo cobre 'slot'
    s = 1 if slot >= counts[0] else 0
    prev = (state // M) * counts[s] + slot - cs[s]
    return s, prev


# ---------------------------------------------------------------------------
# Decoder contextual semi-dinâmico (um estado rANS por lote)
#
# Os lotes são decodificados na ordem em que aparecem no arquivo. Dentro de um
# lote a decodificação vai do último símbolo para o primeiro (o rANS é LIFO).
# Depois de cada lote, a mesma regra do encoder reestima as probabilidades.
# ---------------------------------------------------------------------------


def tamanho_lote(recalc_window: int, blocos_por_lote: int) -> int:
    """Símbolos por lote. blocos_por_lote = 0 (probabilidade fixa) usa lotes de 1 bloco."""
    return recalc_window * max(1, blocos_por_lote)


def decode_lote(
    bitstream_str: str, final_state: int, n_simbolos: int, model: ContextModel
) -> tuple[list[int], int, int]:
    """Decodifica um lote. Devolve (símbolos, estado_inicial_recuperado, bits_não_lidos)."""
    bits = deque(map(int, bitstream_str[::-1]))
    decoded = [0] * n_simbolos
    state = final_state
    last_decoded = 0  # contexto do último símbolo do lote

    for i in range(n_simbolos - 1, -1, -1):
        counts = model.get_counts(last_decoded)
        s, prev = _D_rANS(state, counts)
        M = counts[0] + counts[1]
        while prev < M and bits:
            prev = (prev << 1) | bits.popleft()

        state = prev
        decoded[i] = s
        last_decoded = s

    return decoded, state, len(bits)


def decode_stream(
    lotes: list[tuple[str, int]],
    num_symbols: int,
    model: ContextModel,
    recalc_window: int,
    blocos_por_lote: int,
) -> list[int]:
    tam = tamanho_lote(recalc_window, blocos_por_lote)
    decoded: list[int] = []
    for k, (bitstream, final_state) in enumerate(lotes):
        n_lote = min(tam, num_symbols - k * tam)
        simbolos, estado_inicial, sobrou = decode_lote(bitstream, final_state, n_lote, model)
        if estado_inicial != PRECISION or sobrou:
            raise ValueError(
                f"lote {k} inconsistente (estado inicial {estado_inicial}, "
                f"{sobrou} bits não lidos): arquivo corrompido ou parâmetros diferentes do encoder."
            )
        decoded.extend(simbolos)
        if blocos_por_lote > 0:
            model.atualizar_lote(contar_lote(simbolos, 0, len(simbolos)))
    return decoded


# ---------------------------------------------------------------------------
# Leitura do arquivo comprimido
# ---------------------------------------------------------------------------


def load_encoded(path: str) -> dict:
    """Lê o arquivo no formato do encoder e retorna campos como dict."""
    with open(path, "r") as f:
        lines = f.read().split("\n")
    if len(lines) < 5:
        raise ValueError(f"Arquivo '{path}' tem formato inválido (≥ 5 linhas esperadas).")
    lotes = []
    for linha in lines[5:]:
        if not linha.strip():
            continue  # linha em branco (por exemplo, a última, depois do \n final)
        estado, _, bitstream = linha.partition(" ")
        lotes.append((bitstream.strip(), int(estado)))
    return {
        "num_symbols": int(lines[0].strip()),
        "mode": lines[1].strip(),
        "recalc_window": int(lines[2].strip()),
        "blocos_por_lote": int(lines[3].strip()),
        "headers_hex": lines[4].strip(),
        "lotes": lotes,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="ANS Streaming Decoder — Contextual semi-dinâmico")
    parser.add_argument("--encoded", default="input_encoded.bin", help="Arquivo comprimido")
    parser.add_argument("--output", default="output.txt", help="Arquivo de saída")
    parser.add_argument("--verify", default="", help="Arquivo original para verificação")
    args = parser.parse_args()

    if not os.path.exists(args.encoded):
        print(f"Erro: '{args.encoded}' não encontrado.")
        return

    print("=" * 72)
    print("  ANS STREAMING DECODER  |  semi-dinâmico")
    print("=" * 72)

    data = load_encoded(args.encoded)
    num_symbols = data["num_symbols"]
    recalc_window = data["recalc_window"]
    blocos_por_lote = data["blocos_por_lote"]
    lotes = data["lotes"]

    if data["mode"] != "semidinamico":
        print(f"Erro: modo '{data['mode']}' não suportado (esperado: semidinamico).")
        return

    print(f"Símbolos a decodificar : {num_symbols}")
    print("Contexto               : 1D (lookahead-1)")
    print(f"Bloco                  : {recalc_window} símbolos")
    print(f"Blocos por lote        : {blocos_por_lote}")
    print(f"Lotes                  : {len(lotes)}")
    print(f"Bits no bitstream      : {sum(len(b) for b, _ in lotes)}")

    model = ContextModel()
    model.carregar_inicial(data["headers_hex"])

    t0 = time.time()
    decoded = decode_stream(lotes, num_symbols, model, recalc_window, blocos_por_lote)
    t1 = time.time()

    # Salva resultado
    with open(args.output, "w") as f:
        f.write(" ".join(map(str, decoded)))

    print(f"\nSequência decodificada salva em '{args.output}' ({len(decoded)} símbolos).")
    print(f"Tempo de decodificação: {t1 - t0:.6f}s")

    # Verificação de integridade
    verify_path = args.verify
    if not verify_path and os.path.exists("input.txt"):
        verify_path = "input.txt"

    if verify_path and os.path.exists(verify_path):
        with open(verify_path, "r") as f:
            content = f.read().replace(",", " ").replace("\n", " ").replace("\r", "")
        tokens = content.split()
        if all(len(t) == 1 for t in tokens if t):
            original = [int(x) for x in tokens if x in ("0", "1")]
        else:
            original = [int(c) for c in content if c in ("0", "1")]

        if decoded == original:
            print("\n" + "=" * 72)
            print("  ✓  SUCESSO: sequência decodificada é 100% IDÊNTICA à original!")
            print("=" * 72)
        else:
            print("\n" + "!" * 72)
            print("  ✗  ERRO: sequência decodificada DIVERGE da original!")
            diffs = [i for i, (a, b) in enumerate(zip(original, decoded)) if a != b]
            print(f"  Divergências: {len(diffs)} posições. Primeiras: {diffs[:10]}")
            print("!" * 72)
    else:
        print("\nAviso: arquivo original não informado; verificação ignorada.")


if __name__ == "__main__":
    main()