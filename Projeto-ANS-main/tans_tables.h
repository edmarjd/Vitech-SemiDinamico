/* =============================================================================
 * tans_tables.h  —  Tabelas pré-computadas para codificação tANS estática
 *
 * Alfabeto binário: símbolo 0 e símbolo 1
 * RANGE = 10  →  espaço de estados [10, 19]  (índices 0..9)
 * FLUSH_BITS = 4  (ceil(log2(10)) bits para salvar o estado final)
 *
 * Configurações disponíveis (RANGE == 10):
 *   cfg 0 : P(0) = 9/10 = 90%,  P(1) = 1/10 = 10%
 *   cfg 1 : P(1) = 9/10 = 90%,  P(0) = 1/10 = 10%
 *
 * Como as tabelas foram geradas
 * ─────────────────────────────
 * 1. Distribui "slots" de estados entre os símbolos proporcionalmente
 *    à frequência usando espalhamento uniforme (interleave proporcional).
 * 2. Para cada estado x ∈ [RANGE, 2·RANGE-1] e símbolo s:
 *      - Normaliza x para [freq_s, 2·freq_s-1] emitindo os bits LSB excedentes.
 *      - Mapeia o estado normalizado ao slot do símbolo s correspondente.
 * 3. As tabelas de bits emitidos usam 0xFF (EMPTY) para indicar que
 *    nenhum bit é emitido naquela transição.
 *
 * Convenção de nomes:
 *   a_*  →  símbolo 0     b_*  →  símbolo 1
 *   *_table      novo estado após a transição
 *   *_bitstream  bits emitidos (0xFF = nenhum bit)
 *   *_nbits      número de bits emitidos
 * ============================================================================= */

#ifndef TANS_TABLES_H
#define TANS_TABLES_H

#include <stdint.h>

/* --------------------------------------------------------------------------- */
/*  Constantes globais                                                          */
/* --------------------------------------------------------------------------- */

#define RANGE      10    /* Tamanho do espaço de estados L: estados em [L, 2L-1] */
#define FLUSH_BITS  4    /* Bits necessários para armazenar o estado final: ceil(log2(RANGE)) */
#define EMPTY      0xFF  /* Sentinela: nenhum bit emitido nesta transição */

/* --------------------------------------------------------------------------- */
/*  RANGE == 10  —  2 configurações                                             */
/*                                                                              */
/*  cfg 0 : freq_0 = 9  →  P(0) ≈ 90%,  P(1) ≈ 10%                           */
/*  cfg 1 : freq_0 = 1  →  P(0) ≈ 10%,  P(1) ≈ 90%                           */
/*                                                                              */
/*  Cada linha [cfg][state_idx] onde state_idx = state - RANGE                 */
/* --------------------------------------------------------------------------- */

/* Novo estado ao encodar símbolo 0 */
static const uint8_t a_range10[2][10] = {
    {11, 12, 13, 14, 16, 17, 18, 19, 10, 10}, /* cfg 0: P(0)=9/10 ≈ 90% */
    {14, 14, 14, 14, 14, 14, 14, 14, 14, 14}, /* cfg 1: P(0)=1/10 ≈ 10% */
};

/* Bits emitidos ao encodar símbolo 0 (0xFF = nenhum bit) */
static const uint8_t a_bitstream_range10[2][10] = {
    {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x01}, /* cfg 0 */
    {0x02, 0x06, 0x01, 0x05, 0x03, 0x07, 0x00, 0x08, 0x04, 0x0C}, /* cfg 1 */
};

/* Número de bits emitidos ao encodar símbolo 0 */
static const uint8_t a_nbits_range10[2][10] = {
    {0, 0, 0, 0, 0, 0, 0, 0, 1, 1}, /* cfg 0: P(0)=9/10 */
    {3, 3, 3, 3, 3, 3, 4, 4, 4, 4}, /* cfg 1: P(0)=1/10 */
};

/* Novo estado ao encodar símbolo 1 */
static const uint8_t b_range10[2][10] = {
    {15, 15, 15, 15, 15, 15, 15, 15, 15, 15}, /* cfg 0: P(1)=1/10 ≈ 10% */
    {11, 12, 13, 15, 16, 17, 18, 19, 10, 10}, /* cfg 1: P(1)=9/10 ≈ 90% */
};

/* Bits emitidos ao encodar símbolo 1 (0xFF = nenhum bit) */
static const uint8_t b_bitstream_range10[2][10] = {
    {0x02, 0x06, 0x01, 0x05, 0x03, 0x07, 0x00, 0x08, 0x04, 0x0C}, /* cfg 0 */
    {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x01},  /* cfg 1 */
};

/* Número de bits emitidos ao encodar símbolo 1 */
static const uint8_t b_nbits_range10[2][10] = {
    {3, 3, 3, 3, 3, 3, 4, 4, 4, 4}, /* cfg 0: P(1)=1/10 */
    {0, 0, 0, 0, 0, 0, 0, 0, 1, 1}, /* cfg 1: P(1)=9/10 */
};

/* Frequência do símbolo 0 por configuração (usada em select_cfg) */
static const int freq_a_range10[2] = {9, 1};

#endif /* TANS_TABLES_H */
