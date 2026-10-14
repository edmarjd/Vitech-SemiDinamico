"""
generate_synthetic_tables.py — Gera tabelas sintéticas de 0s e 1s com
probabilidades controladas, no mesmo formato dos planos de bits reais.

Tabelas geradas:
  - synthetic_p25_zeros.txt  →  P(0) = 25%  /  P(1) = 75%
  - synthetic_p75_zeros.txt  →  P(0) = 75%  /  P(1) = 25%

Uso:
    python3 generate_synthetic_tables.py [--n 102400] [--seed 42]
"""

import argparse
import numpy as np
import os


def generate_table(filename: str, p_zero: float, n: int, seed: int) -> None:
    """Gera uma sequência binária com P(0)=p_zero e salva no formato padrão."""
    rng = np.random.default_rng(seed)
    # 0 com prob p_zero, 1 com prob (1-p_zero)
    symbols = rng.choice([0, 1], size=n, p=[p_zero, 1.0 - p_zero])

    # Calcula probabilidades reais obtidas
    real_p0 = np.sum(symbols == 0) / n
    real_p1 = np.sum(symbols == 1) / n

    # Salva no mesmo formato dos planos de bits: um valor por linha
    np.savetxt(filename, symbols, fmt="%d", delimiter="")
    print(f"[OK] {filename}")
    print(f"     Tamanho   : {n} símbolos")
    print(f"     P(0) alvo : {p_zero*100:.1f}%  →  real: {real_p0*100:.2f}%")
    print(f"     P(1) alvo : {(1-p_zero)*100:.1f}%  →  real: {real_p1*100:.2f}%")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Gera tabelas sintéticas binárias com probabilidades controladas"
    )
    parser.add_argument(
        "--n", type=int, default=102400,
        help="Número de símbolos (padrão: 102400, igual aos planos de bits)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Semente aleatória para reprodutibilidade (padrão: 42)"
    )
    parser.add_argument(
        "--outdir", type=str, default="inputs_sinteticos",
        help="Diretório de saída (padrão: inputs_sinteticos)"
    )
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    print(f"Gerando tabelas sintéticas  |  n={args.n}  |  seed={args.seed}\n")

    # Tabela 1: P(0) = 25%  →  maioria de 1s
    generate_table(
        filename=os.path.join(args.outdir, "synthetic_p25_zeros.txt"),
        p_zero=0.25,
        n=args.n,
        seed=args.seed,
    )

    # Tabela 2: P(0) = 75%  →  maioria de 0s  (P(1) = 25%)
    generate_table(
        filename=os.path.join(args.outdir, "synthetic_p75_zeros.txt"),
        p_zero=0.75,
        n=args.n,
        seed=args.seed + 1,  # semente diferente para independência
    )

    print("Concluído. Arquivos salvos em:", os.path.abspath(args.outdir))


if __name__ == "__main__":
    main()
