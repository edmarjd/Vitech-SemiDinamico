/*
 * tANS ENCODER SEMI-DINAMICO
 *
 * - Blocos independentes de BLOCK_SIZE simbolos, cada um com seu estado.
 * - Contexto = proximo simbolo (lookahead), 0 no fim do bloco.
 * - A probabilidade muda a cada n blocos (um "lote"): depois de codificar o
 *   lote k, o encoder conta os simbolos dele e estima a probabilidade usada
 *   no lote k+1. O decoder repete a mesma conta (adapt.h), entao nada alem da
 *   probabilidade INICIAL do plano precisa ser transmitido.
 * - Para cada plano o encoder escolhe o melhor L e o melhor n.
 */

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "adapt.h"
#include "tans_tables.h"

#define MAX_SYMBOLS 12000000 /* ate ~12 Mpixels por plano */
#define BITSTREAM_CAPACITY MAX_SYMBOLS

#ifndef BLOCK_SIZE
#define BLOCK_SIZE 500
#endif

/* Cabecalho global: num_symbols(4) RANGE(1) mode(1) num_blocks(4) n(1)
 * f0_inicial_ctx0(1) f0_inicial_ctx1(1) */
#define GLOBAL_HEADER_BYTES 13
#define BLOCK_HEADER_BYTES 4

/* Valores de n (blocos por lote) testados em cada plano. n = 0 significa
 * "sem atualizacao" (tabela fixa durante o plano inteiro). */
static const int NUP_CANDIDATOS[] = {0, 1, 2, 4, 8, 16};
#define NUM_NUP_CANDIDATOS 6

/* Raio da busca em torno da probabilidade inicial estimada (em niveis de f0). */
#define INIT_RAIO 2

static int symbols_buffer[MAX_SYMBOLS];
static uint8_t payload[BITSTREAM_CAPACITY];
static uint8_t raw_buffer[MAX_SYMBOLS / 8 + 16];

typedef struct {
    uint32_t blk_bytes, bits_used;
    size_t offset;
} BlockMeta;
static BlockMeta block_metas[MAX_SYMBOLS / 10 + 100];

typedef struct {
    uint8_t *buf;
    size_t byte_pos;
    int bit_pos, total_bits;
} Writer;

static void put_bits(Writer *w, uint32_t bits, int n) {
    for (int i = n - 1; i >= 0; i--) {
        if ((bits >> i) & 1) {
            w->buf[w->byte_pos] |= (uint8_t)(1 << w->bit_pos);
        }
        w->total_bits++;
        if (--w->bit_pos < 0) {
            w->bit_pos = 7;
            w->byte_pos++;
        }
    }
}

/*
 * Codifica o plano inteiro com o conjunto de tabelas ts, probabilidade
 * inicial f0_init[ctx] e atualizacao a cada nup blocos.
 * Devolve o total de bytes do payload; *trocas recebe quantas vezes a tabela
 * mudou.
 */
static size_t encode_all(const TansSet *ts, int n, uint32_t num_blocks, int nup,
                         const int f0_init[2], uint32_t *trocas) {
    const int L = ts->L;
    size_t total = 0;
    int f0[2] = {f0_init[0], f0_init[1]};
    uint32_t acc[2][2] = {{0, 0}, {0, 0}};
    uint32_t mudancas = 0;

    for (uint32_t b = 0; b < num_blocks; b++) {
        int bstart = (int)(b * BLOCK_SIZE);
        int bend = bstart + BLOCK_SIZE;
        if (bend > n) {
            bend = n;
        }

        const int cfg[2] = {f0[0] - 1, f0[1] - 1};
        Writer w = {payload + total, 0, 7, 0};
        memset(w.buf, 0, (size_t)(bend - bstart) * 2 + 64);
        uint32_t state = (uint32_t)L;

        for (int i = bstart; i < bend; i++) {
            int nxt = (i + 1 < bend) ? symbols_buffer[i + 1] : 0;
            int idx = cfg[nxt] * L + (int)(state - L);
            uint8_t ns, bits, nb;
            if (symbols_buffer[i] == 0) {
                ns = ts->a_ns[idx];
                bits = ts->a_bits[idx];
                nb = ts->a_nb[idx];
            } else {
                ns = ts->b_ns[idx];
                bits = ts->b_bits[idx];
                nb = ts->b_nb[idx];
            }
            if (nb > 0 && bits != EMPTY) {
                put_bits(&w, bits, nb);
            }
            state = ns;
        }
        put_bits(&w, state - L, ts->flush);
        put_bits(&w, 1, 1); /* stop bit */

        uint32_t blk_bytes = (uint32_t)((w.total_bits + 7) / 8);
        block_metas[b] = (BlockMeta){blk_bytes, (uint32_t)w.total_bits, total};
        total += blk_bytes;

        /* Fim do lote: reestima a probabilidade a partir dos simbolos dele. */
        adapt_contar(symbols_buffer, bstart, bend, acc);
        if (nup > 0 && (b + 1) % (uint32_t)nup == 0) {
            mudancas += (uint32_t)adapt_fechar_lote(acc, L, f0);
        }
    }
    if (trocas) {
        *trocas = mudancas;
    }
    return total;
}

/* Probabilidade inicial do plano: estatistica condicional do plano inteiro. */
static void f0_inicial(const TansSet *ts, int n, uint32_t num_blocks,
                       int f0_init[2]) {
    uint32_t acc[2][2] = {{0, 0}, {0, 0}};
    for (uint32_t b = 0; b < num_blocks; b++) {
        int bstart = (int)(b * BLOCK_SIZE);
        int bend = bstart + BLOCK_SIZE;
        if (bend > n) {
            bend = n;
        }
        adapt_contar(symbols_buffer, bstart, bend, acc);
    }
    for (int c = 0; c < 2; c++) {
        f0_init[c] = adapt_estimar_f0(acc[c], ts->L, ts->L / 2);
    }
}

void process_file(const char *filename, int forceL, int forceN) {
    FILE *file = fopen(filename, "r");
    if (!file) {
        perror("fopen entrada");
        return;
    }
    int n = 0, count0 = 0, count1 = 0, symbol;
    while (fscanf(file, "%d", &symbol) == 1) {
        if (n >= MAX_SYMBOLS) {
            fprintf(stderr, "ERRO: muitos simbolos (limite %d)\n", MAX_SYMBOLS);
            fclose(file);
            return;
        }
        if (symbol == 0 || symbol == 1) {
            symbols_buffer[n++] = symbol;
            if (symbol) {
                count1++;
            } else {
                count0++;
            }
        }
    }
    fclose(file);
    if (n == 0) {
        fprintf(stderr, "AVISO: arquivo vazio.\n");
        return;
    }

    char out_name[512];
    const char *slash = strrchr(filename, '/');
    const char *dot = strrchr(filename, '.');
    int base_len = (dot && (!slash || dot > slash)) ? (int)(dot - filename)
                                                    : (int)strlen(filename);
    if (base_len > 490) {
        base_len = 490;
    }
    strncpy(out_name, filename, (size_t)base_len);
    strcpy(out_name + base_len, "_encoded.bin");

    uint32_t num_blocks = (uint32_t)((n + BLOCK_SIZE - 1) / BLOCK_SIZE);

    /* Varredura por plano: cada L disponivel e cada n candidato; fica com a
     * combinacao de menor payload. */
    const TansSet *best = 0;
    int best_nup = 1;
    int best_f0[2] = {0, 0};
    size_t best_total = (size_t)-1;
    for (int k = 0; k < NUM_SETS; k++) {
        const TansSet *ts = &tans_sets[k];
        if (forceL && ts->L != forceL) {
            continue;
        }
        int est[2];
        f0_inicial(ts, n, num_blocks, est);

        /* Etapa 1: melhor n (com a probabilidade inicial estimada). */
        int set_nup = 1;
        size_t set_total = (size_t)-1;
        for (int j = 0; j < NUM_NUP_CANDIDATOS; j++) {
            int nup = forceN ? forceN : NUP_CANDIDATOS[j];
            size_t t = encode_all(ts, n, num_blocks, nup, est, 0);
            if (t < set_total) {
                set_total = t;
                set_nup = nup;
            }
            if (forceN) {
                break;
            }
        }

        /* Etapa 2: para esse n (e tambem para n = 0, a tabela fixa), procura
         * em volta da estimativa o par de probabilidades iniciais que gera o
         * menor payload: o arredondamento para L niveis nem sempre e o melhor
         * para o tANS. */
        int set_f0[2] = {est[0], est[1]};
        int nups[2] = {set_nup, forceN ? set_nup : 0};
        for (int u = 0; u < 2; u++) {
            if (u == 1 && nups[1] == nups[0]) {
                break;
            }
            for (int d0 = -INIT_RAIO; d0 <= INIT_RAIO; d0++) {
                for (int d1 = -INIT_RAIO; d1 <= INIT_RAIO; d1++) {
                    int cand[2] = {est[0] + d0, est[1] + d1};
                    if (cand[0] < 1 || cand[0] > ts->L - 1 || cand[1] < 1 ||
                        cand[1] > ts->L - 1) {
                        continue;
                    }
                    size_t t = encode_all(ts, n, num_blocks, nups[u], cand, 0);
                    if (t < set_total) {
                        set_total = t;
                        set_nup = nups[u];
                        set_f0[0] = cand[0];
                        set_f0[1] = cand[1];
                    }
                }
            }
        }

        if (set_total < best_total) {
            best_total = set_total;
            best = ts;
            best_nup = set_nup;
            best_f0[0] = set_f0[0];
            best_f0[1] = set_f0[1];
        }
    }
    if (!best) {
        fprintf(stderr, "ERRO: L=%d nao existe em tans_tables.h\n", forceL);
        return;
    }
    uint32_t trocas = 0;
    size_t total_payload =
        encode_all(best, n, num_blocks, best_nup, best_f0, &trocas);

    size_t tans_bytes = GLOBAL_HEADER_BYTES +
                        (size_t)num_blocks * BLOCK_HEADER_BYTES + total_payload;
    size_t raw_bytes_payload = (size_t)(n + 7) / 8;
    size_t raw_bytes = GLOBAL_HEADER_BYTES + raw_bytes_payload;
    uint8_t mode = (tans_bytes < raw_bytes) ? 1 : 0;
    size_t final_bytes = mode ? tans_bytes : raw_bytes;

    FILE *fout = fopen(out_name, "wb");
    if (!fout) {
        perror("fopen saida");
        return;
    }
    uint32_t ns = (uint32_t)n, nb_val = num_blocks;
    uint8_t range_val = (uint8_t)best->L;
    uint8_t nup_b = mode ? (uint8_t)best_nup : 0;
    uint8_t f0a = mode ? (uint8_t)best_f0[0] : 0;
    uint8_t f0b = mode ? (uint8_t)best_f0[1] : 0;
    fwrite(&ns, 4, 1, fout);
    fwrite(&range_val, 1, 1, fout);
    fwrite(&mode, 1, 1, fout);
    fwrite(&nb_val, 4, 1, fout);
    fwrite(&nup_b, 1, 1, fout);
    fwrite(&f0a, 1, 1, fout);
    fwrite(&f0b, 1, 1, fout);
    if (mode) {
        for (uint32_t b = 0; b < num_blocks; b++) {
            fwrite(&block_metas[b].blk_bytes, 4, 1, fout);
            fwrite(payload + block_metas[b].offset, 1, block_metas[b].blk_bytes,
                   fout);
        }
    } else {
        memset(raw_buffer, 0, raw_bytes_payload);
        for (int i = 0; i < n; i++) {
            if (symbols_buffer[i]) {
                raw_buffer[i / 8] |= (uint8_t)(1 << (7 - (i % 8)));
            }
        }
        fwrite(raw_buffer, 1, raw_bytes_payload, fout);
    }
    fclose(fout);

    double p0 = (double)count0 / n, p1 = 1.0 - p0, h = 0.0;
    if (p0 > 0) {
        h -= p0 * log2(p0);
    }
    if (p1 > 0) {
        h -= p1 * log2(p1);
    }
    double taxa = (1.0 - (double)(final_bytes * 8) / n) * 100.0;

    printf("\n================================================================="
           "=====\n");
    printf("  tANS SEMI-DINAMICO  |  RANGE=%d  |  BLOCK_SIZE=%d\n", best->L,
           BLOCK_SIZE);
    printf("==================================================================="
           "===\n");
    printf("Arquivo           : %s\n", filename);
    printf("Símbolos lidos    : %d (0s: %d, 1s: %d)\n", n, count0, count1);
    printf("Blocos            : %u (tamanho fixo %d símbolos)\n", num_blocks,
           BLOCK_SIZE);
    printf("Modo selecionado  : %s\n",
           mode ? "tANS semi-dinamico (Blocos Independentes)"
                : "RAW (Fallback sem perda)");
    printf("Entropia H (ord0) : %.6f bits/símbolo\n", h);
    printf("Total transmitido : %zu bytes  (%zu bits)\n", final_bytes,
           final_bytes * 8);
    printf("Taxa de compressão: %.2f%%\n", taxa);
    {
        long long ov, est = 0, pad, bs;
        if (mode) {
            long long used = 0, alloc = 0;
            for (uint32_t b = 0; b < num_blocks; b++) {
                used += block_metas[b].bits_used;
                alloc += (long long)block_metas[b].blk_bytes * 8;
            }
            ov = (GLOBAL_HEADER_BYTES +
                  (long long)num_blocks * BLOCK_HEADER_BYTES) *
                 8;
            est = (long long)num_blocks * (best->flush + 1);
            pad = alloc - used;
            bs = used - est;
        } else {
            ov = GLOBAL_HEADER_BYTES * 8;
            pad = (long long)raw_bytes_payload * 8 - n;
            bs = n;
        }
        printf("Blocos tANS       : %u\n", mode ? num_blocks : 0);
        printf("Overhead (bits)   : %lld\n", ov);
        printf("Preenchimento (bits): %lld\n", pad);
        printf("Estado (bits)     : %lld\n", est);
        printf("Bitstream (bits)  : %lld\n", bs);
        printf("Comprimido (bits) : %zu\n", final_bytes * 8);
    }
    if (mode) {
        printf("Atualização (blocos): %d%s\n", best_nup,
               best_nup ? "" : " (tabela fixa)");
        printf("Trocas de tabela  : %u\n", trocas);
        printf("Tabela inicial    : %d/%d = %d%%  (ctx prox=0)  |  %d/%d = "
               "%d%%  (ctx prox=1)\n",
               best_f0[0], best->L, 100 * best_f0[0] / best->L, best_f0[1],
               best->L, 100 * best_f0[1] / best->L);
    }
    printf("Arquivo gerado    : %s\n", out_name);
    printf("==================================================================="
           "===\n");
}

int main(int argc, char *argv[]) {
    printf("tANS Contextual 1D Encoder (semi-dinamico)\n");
    int forceL = 0, forceN = 0, first = 1;
    while (argc > first + 1) {
        if (strcmp(argv[first], "-L") == 0) {
            forceL = atoi(argv[first + 1]);
        } else if (strcmp(argv[first], "-n") == 0) {
            forceN = atoi(argv[first + 1]);
        } else {
            break;
        }
        first += 2;
    }
    if (forceN < 0 || forceN > 255) {
        fprintf(stderr, "ERRO: -n deve estar entre 1 e 255.\n");
        return 1;
    }
    if (argc <= first) {
        fprintf(stderr,
                "Uso: %s [-L N] [-n BLOCOS_POR_LOTE] <arquivo.txt>...\n",
                argv[0]);
        return 1;
    }
    for (int i = first; i < argc; i++) {
        process_file(argv[i], forceL, forceN);
    }
    printf("\nProcessamento concluido.\n");
    return 0;
}