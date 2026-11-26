/*
 * tANS DECODER SEMI-DINAMICO
 *
 * Le o plano bloco a bloco. Depois de decodificar um lote (n blocos), conta os
 * simbolos recuperados e estima a probabilidade do lote seguinte com a mesma
 * regra do encoder (adapt.h). Dentro de cada bloco a decodificacao e feita do
 * fim para o inicio (LIFO).
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "adapt.h"
#include "tans_tables.h"

/* Buffer estatico para simbolos decodificados */
#define MAX_DECODED_SYMBOLS 12000000

#define BITSTREAM_CAPACITY 1000000

/* Tamanho de bloco - sincronizado com o Encoder */
#ifndef BLOCK_SIZE
#define BLOCK_SIZE 500
#endif

/*
 * DEBUG
 */

#define DEBUG 0

#if DEBUG
#define DBG_PRINTF(...) printf(__VA_ARGS__)
#else
#define DBG_PRINTF(...)
#endif

/*
 * ESTRUTURAS
 */

typedef struct {
    uint32_t state;
} AnsState;

/*
 * Para cada estado de chegada (state_idx) guardamos TODOS os estados de
 * origem possiveis. Cada candidato emitiu 'nbits' bits na codificacao,
 * que sao os 'nbits' bits menos significativos do estado de origem.
 * Os codigos sao livres de prefixo, entao basta ler bit a bit ate
 * coincidir com algum candidato.
 */
#define MAX_L 128
#define MAX_CAND (2 * MAX_L)

typedef struct {
    int ncand;
    uint8_t prev[MAX_CAND];  /* indice do estado de origem (state - RANGE) */
    uint8_t nbits[MAX_CAND]; /* bits emitidos nessa transicao */
    uint8_t sym[MAX_CAND];   /* simbolo codificado nessa transicao */
} DecodeEntry;

typedef struct {
    uint8_t *buffer;
    int total_bits;
    int current_bit;
} BitstreamReader;

/*
 * GLOBAIS
 */

static DecodeEntry g_rlt[2][MAX_L]; /* [ctx_id][state_idx] */
static const TansSet *g_ts;
static int RANGE;
static int FLUSH_BITS;
static uint8_t bitstream_buffer[BITSTREAM_CAPACITY];
static int decoded_symbols[MAX_DECODED_SYMBOLS];

/*
 * BUILD RLT
 */

void build_rlt(int ctx_id, int cfg) {
    const int L = RANGE;
    for (int i = 0; i < L; i++) {
        g_rlt[ctx_id][i].ncand = 0;
    }
    for (int prev_idx = 0; prev_idx < L; prev_idx++) {
        int idx = cfg * L + prev_idx;
        DecodeEntry *e = &g_rlt[ctx_id][g_ts->a_ns[idx] - L];
        e->prev[e->ncand] = (uint8_t)prev_idx;
        e->nbits[e->ncand] = g_ts->a_nb[idx];
        e->sym[e->ncand] = 0;
        e->ncand++;
        e = &g_rlt[ctx_id][g_ts->b_ns[idx] - L];
        e->prev[e->ncand] = (uint8_t)prev_idx;
        e->nbits[e->ncand] = g_ts->b_nb[idx];
        e->sym[e->ncand] = 1;
        e->ncand++;
    }
}

/*
 * BITSTREAM
 */

void bitstream_reader_init(BitstreamReader *reader, uint8_t *buffer,
                           int total_bits) {
    reader->buffer = buffer;
    reader->total_bits = total_bits;
    reader->current_bit = total_bits - 1;
}

uint32_t bitstream_read_bits_lsb(BitstreamReader *reader, int nbits) {
    uint32_t result = 0;
    for (int i = 0; i < nbits; i++) {
        if (reader->current_bit < 0) {
            return 0;
        }
        int bit_index = reader->current_bit;
        uint8_t bit =
            (reader->buffer[bit_index / 8] >> (7 - (bit_index % 8))) & 1;
        if (bit) {
            result |= (1U << i);
        }
        reader->current_bit--;
    }
    return result;
}

uint32_t bitstream_read_bits_msb(BitstreamReader *reader, int nbits) {
    uint32_t result = 0;
    for (int i = 0; i < nbits; i++) {
        if (reader->current_bit < 0) {
            return 0;
        }
        int bit_index = reader->current_bit;
        uint8_t bit =
            (reader->buffer[bit_index / 8] >> (7 - (bit_index % 8))) & 1;
        result = (result << 1) | bit;
        reader->current_bit--;
    }
    return result;
}

/*
 * DECODE
 */

int ans_decode_symbol_ctx(int ctx_id, AnsState *state,
                          BitstreamReader *reader) {
    int idx = state->state - RANGE;
    if (idx < 0 || idx >= RANGE) {
        fprintf(stderr, "Estado invalido: %u\n", state->state);
        return -1;
    }
    DecodeEntry *e = &g_rlt[ctx_id][idx];

    /* Le bit a bit (MSB primeiro) ate casar com os 'k' bits baixos de algum
     * estado de origem que emitiu exatamente 'k' bits. */
    uint32_t r = 0;
    for (int k = 0; k <= 8; k++) {
        for (int c = 0; c < e->ncand; c++) {
            uint32_t prev_state = RANGE + e->prev[c];
            uint32_t mask = (1u << k) - 1u;
            if (e->nbits[c] == k && (prev_state & mask) == r) {
                state->state = prev_state;
                return e->sym[c];
            }
        }
        r = (r << 1) | bitstream_read_bits_msb(reader, 1);
    }
    return -1;
}

/*
 * PROCESS FILE
 */

void decode_file(const char *input_file, const char *output_file) {
    FILE *f = fopen(input_file, "rb");
    if (!f) {
        perror("fopen entrada");
        return;
    }

    /* Cabecalho global: 13 B -> [num_symbols (4B)] [RANGE (1B)] [mode (1B)]
     * [num_blocks (4B)] [n blocos por lote (1B)] [f0 inicial ctx0 (1B)]
     * [f0 inicial ctx1 (1B)] */
    uint32_t num_symbols = 0, num_blocks = 0;
    uint8_t file_range = 0, mode = 0, nup = 0, f0_ini[2] = {0, 0};

    if (fread(&num_symbols, 4, 1, f) != 1 || fread(&file_range, 1, 1, f) != 1 ||
        fread(&mode, 1, 1, f) != 1 || fread(&num_blocks, 4, 1, f) != 1) {
        fprintf(stderr,
                "ERRO: cabecalho global invalido ou arquivo truncado.\n");
        fclose(f);
        return;
    }
    if (fread(&nup, 1, 1, f) != 1 || fread(&f0_ini[0], 1, 1, f) != 1 ||
        fread(&f0_ini[1], 1, 1, f) != 1) {
        fprintf(stderr, "ERRO: cabecalho truncado.\n");
        fclose(f);
        return;
    }

    if (num_symbols == 0 || num_symbols > MAX_DECODED_SYMBOLS) {
        fprintf(stderr, "ERRO: numero de simbolos invalido (%u).\n",
                num_symbols);
        fclose(f);
        return;
    }

    int f0[2] = {f0_ini[0], f0_ini[1]};
    if (mode == 1) {
        g_ts = tans_find(file_range);
        if (!g_ts) {
            fprintf(stderr,
                    "ERRO: RANGE=%u do arquivo nao existe em tans_tables.h.\n",
                    file_range);
            fclose(f);
            return;
        }
        RANGE = g_ts->L;
        FLUSH_BITS = g_ts->flush;
        if (f0[0] < 1 || f0[0] >= RANGE || f0[1] < 1 || f0[1] >= RANGE) {
            fprintf(stderr, "ERRO: parametros de adaptacao invalidos.\n");
            fclose(f);
            return;
        }
        build_rlt(0, f0[0] - 1); /* ctx prox=0: P(0)=f0[0]/L */
        build_rlt(1, f0[1] - 1); /* ctx prox=1: P(0)=f0[1]/L */
    }

    FILE *out = fopen(output_file, "w");
    if (!out) {
        perror("fopen saida");
        fclose(f);
        return;
    }

    if (mode == 1) {
        /* Modo tANS semi-dinamico por blocos independentes */
        uint32_t acc[2][2] = {{0, 0}, {0, 0}};
        for (uint32_t b = 0; b < num_blocks; b++) {
            int bstart = (int)(b * BLOCK_SIZE);
            int bend = bstart + BLOCK_SIZE;
            if (bend > (int)num_symbols) {
                bend = (int)num_symbols;
            }
            int blk_syms = bend - bstart;

            uint32_t blk_bytes = 0;

            if (fread(&blk_bytes, 4, 1, f) != 1) {
                fprintf(stderr, "ERRO: falha ao ler cabecalho do bloco %u.\n",
                        b);
                fclose(f);
                fclose(out);
                return;
            }

            if (blk_bytes > BITSTREAM_CAPACITY) {
                fprintf(stderr,
                        "ERRO: tamanho do bloco %u excede capacidade (%u "
                        "bytes).\n",
                        b, blk_bytes);
                fclose(f);
                fclose(out);
                return;
            }

            size_t bytes_read = fread(bitstream_buffer, 1, blk_bytes, f);
            if (bytes_read != blk_bytes) {
                fprintf(stderr,
                        "ERRO: bloco %u truncado (%zu de %u bytes lidos).\n", b,
                        bytes_read, blk_bytes);
                fclose(f);
                fclose(out);
                return;
            }

            int total_bits = (int)blk_bytes * 8;
            while (total_bits > FLUSH_BITS + 1) {
                int bi = total_bits - 1;
                if ((bitstream_buffer[bi / 8] >> (7 - (bi % 8))) & 1) {
                    break;
                }
                total_bits--;
            }

            BitstreamReader reader;
            bitstream_reader_init(&reader, bitstream_buffer, total_bits);
            reader.current_bit--; /* pula stop bit */

            uint32_t off = bitstream_read_bits_lsb(&reader, FLUSH_BITS);
            AnsState state;
            state.state = RANGE + off;

            /* Decodifica do fim para o inicio com contexto lookahead 1D */
            for (int i = blk_syms - 1; i >= 0; i--) {
                int nxt =
                    (i + 1 < blk_syms) ? decoded_symbols[bstart + i + 1] : 0;
                int sym = ans_decode_symbol_ctx(nxt, &state, &reader);
                if (sym == -1) {
                    fprintf(stderr,
                            "ERRO: decodificacao falhou no bloco %u, simbolo "
                            "%d.\n",
                            b, i);
                    fclose(f);
                    fclose(out);
                    return;
                }
                decoded_symbols[bstart + i] = sym;
            }

            /* Fim do lote: mesma regra do encoder para o proximo lote. */
            adapt_contar(decoded_symbols, bstart, bend, acc);
            if (nup > 0 && (b + 1) % nup == 0) {
                int antes[2] = {f0[0], f0[1]};
                adapt_fechar_lote(acc, RANGE, f0);
                for (int c = 0; c < 2; c++) {
                    if (f0[c] != antes[c]) {
                        build_rlt(c, f0[c] - 1);
                    }
                }
            }
        }
    } else {
        /* Modo RAW */
        size_t raw_payload_bytes = (num_symbols + 7) / 8;
        size_t bytes_read = fread(bitstream_buffer, 1, raw_payload_bytes, f);
        if (bytes_read != raw_payload_bytes) {
            fprintf(stderr,
                    "ERRO: payload RAW truncado (%zu de %zu bytes lidos).\n",
                    bytes_read, raw_payload_bytes);
            fclose(f);
            fclose(out);
            return;
        }
        for (uint32_t i = 0; i < num_symbols; i++) {
            decoded_symbols[i] = (bitstream_buffer[i / 8] >> (7 - (i % 8))) & 1;
        }
    }

    fclose(f);

    /* Grava simbolos decodificados */
    for (uint32_t i = 0; i < num_symbols; i++) {
        fprintf(out, "%d", decoded_symbols[i]);
        if (i + 1 < num_symbols) {
            fprintf(out, " ");
        }
    }
    fclose(out);

    printf("Arquivo decodificado com sucesso: %s (%u simbolos, modo %s)\n",
           output_file, num_symbols,
           (mode == 1 ? "tANS semi-dinamico" : "RAW"));
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Uso: %s <arquivo_encoded.bin> <arquivo_decoded.txt>\n",
                argv[0]);
        return 1;
    }
    decode_file(argv[1], argv[2]);
    return 0;
}