"""
generate_per_plane_tables.py
============================
Gera tabelas sintéticas binárias para cada plano de bits (0-7), em três
níveis de dinamismo crescente:

  Nível 0 – ESTÁTICO
      Uma única probabilidade global P(0) para toda a tabela,
      calculada a partir do plano de bits real correspondente.

  Nível 1 – BLOCOS UNIFORMES
      A tabela é dividida em N blocos de igual tamanho.
      Cada bloco recebe uma P(0) sorteada em torno da média global
      com uma dispersão (std_dev configurável), simulando variação
      espacial suave como regiões claras/escuras de uma imagem.

  Nível 2 – DRIFT TEMPORAL
      A probabilidade deriva continuamente ao longo da sequência
      usando um passeio aleatório (random walk) suave, como se a
      imagem tivesse gradientes ou transições de textura ao longo
      das linhas.

Uso:
    python3 generate_per_plane_tables.py [--seed 42] [--std 0.05] [--n-blocks 10]

Saída:
    sinteticos/nivel0/  →  plano_{p}_nivel0.txt
    sinteticos/nivel1/  →  plano_{p}_nivel1.txt
    sinteticos/nivel2/  →  plano_{p}_nivel2.txt
"""

import argparse
import os
import numpy as np


# ---------------------------------------------------------------------------
# Medir probabilidades reais por plano
# ---------------------------------------------------------------------------

def medir_probabilidades(plane_dir: str, n_planes: int = 8) -> list[dict]:
    """Lê cada plano de bits e retorna P(0) global e por bloco."""
    stats = []
    for p in range(n_planes):
        path = os.path.join(plane_dir, f"plano_bit_{p}.txt")
        data = np.loadtxt(path, dtype=np.uint8)
        n    = len(data)
        p0   = float(np.sum(data == 0)) / n
        stats.append({"plano": p, "n": n, "p0": p0, "data": data})
        print(f"  Plano {p}: n={n}  P(0)={p0:.4f}  P(1)={1-p0:.4f}")
    return stats


# ---------------------------------------------------------------------------
# Nível 0 — Estático
# ---------------------------------------------------------------------------

def gerar_nivel0(stats: list[dict], outdir: str, seed: int) -> None:
    """Uma P(0) global fixa para toda a sequência."""
    os.makedirs(outdir, exist_ok=True)
    for s in stats:
        p = s["plano"]
        rng = np.random.default_rng(seed + p)
        syms = rng.choice([0, 1], size=s["n"], p=[s["p0"], 1.0 - s["p0"]])
        path = os.path.join(outdir, f"plano_{p}_nivel0.txt")
        np.savetxt(path, syms, fmt="%d")
        real_p0 = np.sum(syms == 0) / s["n"]
        print(f"  [Nível 0] Plano {p}: P(0) alvo={s['p0']:.4f}  real={real_p0:.4f}  → {path}")


# ---------------------------------------------------------------------------
# Nível 1 — Blocos uniformes
# ---------------------------------------------------------------------------

def gerar_nivel1(stats: list[dict], outdir: str, seed: int,
                 n_blocks: int, std_dev: float) -> None:
    """
    Divide a sequência em n_blocks. Cada bloco tem P(0) sorteada em
    Normal(p0_global, std_dev), truncada em [0.01, 0.99].
    """
    os.makedirs(outdir, exist_ok=True)
    for s in stats:
        p   = s["plano"]
        n   = s["n"]
        rng = np.random.default_rng(seed + p)

        # Sorteia P(0) para cada bloco
        block_p0s = rng.normal(loc=s["p0"], scale=std_dev, size=n_blocks)
        block_p0s = np.clip(block_p0s, 0.01, 0.99)

        # Gera símbolos bloco a bloco
        block_size = n // n_blocks
        syms = []
        for b in range(n_blocks):
            bsize = block_size if b < n_blocks - 1 else (n - block_size * (n_blocks - 1))
            bp0   = block_p0s[b]
            syms.append(rng.choice([0, 1], size=bsize, p=[bp0, 1.0 - bp0]))
        syms = np.concatenate(syms)

        path = os.path.join(outdir, f"plano_{p}_nivel1.txt")
        np.savetxt(path, syms, fmt="%d")
        real_p0 = np.sum(syms == 0) / n
        print(f"  [Nível 1] Plano {p}: P(0) global={s['p0']:.4f}  real={real_p0:.4f}"
              f"  blocos={n_blocks}  std={std_dev:.2f}  → {path}")


# ---------------------------------------------------------------------------
# Nível 2 — Drift temporal (random walk suave)
# ---------------------------------------------------------------------------

def gerar_nivel2(stats: list[dict], outdir: str, seed: int,
                 drift_std: float, smooth_window: int) -> None:
    """
    A probabilidade P(0) deriva continuamente ao longo da sequência
    via passeio aleatório suavizado com janela deslizante.
    """
    os.makedirs(outdir, exist_ok=True)
    for s in stats:
        p   = s["plano"]
        n   = s["n"]
        rng = np.random.default_rng(seed + p)

        # Passeio aleatório de tamanho n com passo drift_std
        steps = rng.normal(loc=0.0, scale=drift_std, size=n)
        # Acumulado e suavizado → curva de P(0) variando ao longo do tempo
        walk  = np.cumsum(steps)
        # Normaliza para centrar em p0_global
        walk  = walk - walk.mean() + s["p0"]
        # Suaviza com média móvel para evitar oscilações bruscas
        kernel = np.ones(smooth_window) / smooth_window
        p0_curve = np.convolve(walk, kernel, mode="same")
        p0_curve = np.clip(p0_curve, 0.01, 0.99)

        # Gera cada símbolo com a P(0) local
        syms = (rng.random(n) > p0_curve).astype(np.uint8)  # 1 se rand > p0, else 0
        # Corrige: símbolo 0 se rand < p0_local
        u    = rng.random(n)
        syms = np.where(u < p0_curve, 0, 1).astype(np.uint8)

        path = os.path.join(outdir, f"plano_{p}_nivel2.txt")
        np.savetxt(path, syms, fmt="%d")
        real_p0 = np.sum(syms == 0) / n
        print(f"  [Nível 2] Plano {p}: P(0) alvo={s['p0']:.4f}  real={real_p0:.4f}"
              f"  drift_std={drift_std}  smooth={smooth_window}  → {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Gera tabelas sintéticas por plano de bits em 3 níveis de dinamismo"
    )
    parser.add_argument("--plane-dir",    default="Plano_de_Bits",
                        help="Diretório com os planos de bits reais")
    parser.add_argument("--outdir",       default="sinteticos",
                        help="Diretório raiz de saída")
    parser.add_argument("--seed",         type=int,   default=42)
    parser.add_argument("--std",          type=float, default=0.05,
                        help="Desvio padrão de P(0) entre blocos  [Nível 1]")
    parser.add_argument("--n-blocks",     type=int,   default=10,
                        help="Número de blocos                    [Nível 1]")
    parser.add_argument("--drift-std",    type=float, default=0.002,
                        help="Desvio do passo do random walk      [Nível 2]")
    parser.add_argument("--smooth",       type=int,   default=500,
                        help="Janela de suavização do drift       [Nível 2]")
    args = parser.parse_args()

    print("=" * 65)
    print("  Medindo probabilidades reais dos planos de bits...")
    print("=" * 65)
    stats = medir_probabilidades(args.plane_dir)

    print("\n" + "=" * 65)
    print("  Nível 0 — Estático (P global fixa)")
    print("=" * 65)
    gerar_nivel0(stats, os.path.join(args.outdir, "nivel0"), args.seed)

    print("\n" + "=" * 65)
    print(f"  Nível 1 — Blocos Uniformes (n_blocks={args.n_blocks}, std={args.std})")
    print("=" * 65)
    gerar_nivel1(stats, os.path.join(args.outdir, "nivel1"),
                 args.seed, args.n_blocks, args.std)

    print("\n" + "=" * 65)
    print(f"  Nível 2 — Drift Temporal (drift_std={args.drift_std}, smooth={args.smooth})")
    print("=" * 65)
    gerar_nivel2(stats, os.path.join(args.outdir, "nivel2"),
                 args.seed, args.drift_std, args.smooth)

    print("\n" + "=" * 65)
    print("  Concluído.")
    print("=" * 65)


if __name__ == "__main__":
    main()
