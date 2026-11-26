/*
 * adapt.h - regra de adaptacao das probabilidades (compartilhada).
 *
 * Encoder e decoder incluem ESTE arquivo, entao calculam exatamente a mesma
 * probabilidade a partir dos mesmos simbolos de um lote. Por isso nao e
 * preciso transmitir as probabilidades dos lotes seguintes.
 *
 *   lote  = n blocos consecutivos (n e gravado no cabecalho global);
 *   ctx   = proximo simbolo do bloco (0 no ultimo simbolo do bloco);
 *   f0[c] = frequencia de "0" na tabela, ou seja P(0 | ctx = c) = f0[c] / L.
 */

#ifndef ADAPT_H
#define ADAPT_H

#include <stdint.h>

/* Acumula em cnt[ctx][simbolo] as ocorrencias do bloco [bstart, bend). */
static inline void adapt_contar(const int *sym, int bstart, int bend,
                                uint32_t cnt[2][2]) {
    for (int i = bstart; i < bend; i++) {
        int ctx = (i + 1 < bend) ? sym[i + 1] : 0;
        cnt[ctx][sym[i]]++;
    }
}

/*
 * Estima f0 (1 .. L-1) para um contexto a partir das contagens c[0], c[1]
 * (ocorrencias de 0 e de 1 naquele contexto). Usa suavizacao de Laplace
 * (+0.5) e aritmetica inteira, para o resultado ser identico no encoder e no
 * decoder. Sem observacoes, mantem o valor anterior.
 */
static inline int adapt_estimar_f0(const uint32_t c[2], int L, int anterior) {
    uint64_t n = (uint64_t)c[0] + c[1];
    if (n == 0) {
        return anterior;
    }
    uint64_t x = (2 * (uint64_t)c[0] + 1) * (uint64_t)L;
    uint64_t y = 2 * n + 2;
    int f0 = (int)((2 * x + y) / (2 * y)); /* arredonda x / y */
    if (f0 < 1) {
        f0 = 1;
    }
    if (f0 > L - 1) {
        f0 = L - 1;
    }
    return f0;
}

/*
 * Fecha um lote: reestima f0 de cada contexto so com as contagens do lote que
 * acabou (lote[ctx][simbolo]) e zera as contagens. Devolve quantas
 * probabilidades mudaram.
 */
static inline int adapt_fechar_lote(uint32_t lote[2][2], int L, int f0[2]) {
    int mudancas = 0;
    for (int c = 0; c < 2; c++) {
        int novo = adapt_estimar_f0(lote[c], L, f0[c]);
        if (novo != f0[c]) {
            f0[c] = novo;
            mudancas++;
        }
        lote[c][0] = 0;
        lote[c][1] = 0;
    }
    return mudancas;
}

#endif