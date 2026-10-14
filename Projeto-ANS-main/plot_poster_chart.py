import matplotlib.pyplot as plt
import numpy as np

# Dados dos 8 planos
planes = [f'Plane {i}' for i in range(7, -1, -1)]  # 7 down to 0
planes_labels = ['Plane 7\n(MSB)', 'Plane 6', 'Plane 5', 'Plane 4', 'Plane 3', 'Plane 2', 'Plane 1', 'Plane 0\n(LSB)']

# Entropia empírica
h0 = [0.9942, 0.9819, 0.9999, 0.9892, 1.0000, 1.0000, 1.0000, 1.0000]
h1 = [0.3711, 0.6182, 0.7349, 0.8445, 0.9244, 0.9596, 0.9768, 0.9809]

# Bits totais / 102400 para obter bits/símbolo reais
n = 102400.0
static_order0 = [103747/n, 102413/n, 102414/n, 102413/n, 102414/n, 102414/n, 102414/n, 102414/n]
static_lookahead = [39687/n, 63300/n, 78861/n, 86122/n, 99856/n, 102286/n, 103627/n, 104214/n]
proposed_w5000 = [34866/n, 58108/n, 71478/n, 83264/n, 92391/n, 98408/n, 101868/n, 102197/n]

x = np.arange(len(planes_labels))
width = 0.18

fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)

plt.rcParams['font.sans-serif'] = 'DejaVu Sans'

rects1 = ax.bar(x - 2*width + width/2, h0, width, label='Order-0 Entropy (H₀)', color='#9E9E9E', alpha=0.85)
rects2 = ax.bar(x - width + width/2, h1, width, label='Lookahead-1 Entropy (H₁)', color='#42A5F5', alpha=0.9)
rects3 = ax.bar(x + width/2, static_lookahead, width, label='Static rANS + Lookahead', color='#FFA726', alpha=0.9)
rects4 = ax.bar(x + width + width/2, proposed_w5000, width, label='Proposed Block-Adaptive (W=5000)', color='#1E88E5', edgecolor='#0D47A1', linewidth=1.2)

ax.set_ylabel('Coding Rate (bits / symbol)', fontsize=12, fontweight='bold')
ax.set_title('Bit-Plane Compression Rate vs. Empirical Shannon Limits (320x320 Image)', fontsize=14, fontweight='bold', pad=15)
ax.set_xticks(x)
ax.set_xticklabels(planes_labels, fontsize=10, fontweight='bold')
ax.set_ylim(0, 1.15)
ax.axhline(1.0, color='red', linestyle='--', linewidth=0.8, alpha=0.6, label='Uncompressed Baseline (1.0 bit/sym)')

ax.grid(axis='y', linestyle=':', alpha=0.6)
ax.legend(loc='lower right', framealpha=0.95, fontsize=10)

plt.tight_layout()
plt.savefig('fig_results_barchart.png')
print('Gráfico salvo com sucesso como fig_results_barchart.png')
