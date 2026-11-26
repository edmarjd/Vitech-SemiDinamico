"""
Modelo de contexto semi-dinâmico do rANS (Python).

Mesma ideia da versão em C (adapt.h):
  - o contexto de um símbolo é o PRÓXIMO símbolo do lote (0 no último);
  - cada contexto tem a sua probabilidade c0 / PRECISION de sair o símbolo 0;
  - o plano começa com uma probabilidade inicial própria, gravada no cabeçalho;
  - depois de cada lote (n blocos), as probabilidades são reestimadas só com os
    símbolos desse lote. O decoder repete a mesma conta com os símbolos que acabou
    de decodificar, então as probabilidades seguintes não precisam ser transmitidas.
"""

NUM_CONTEXTS_1D = 2  # contexto = próximo símbolo (0 ou 1)

PRECISION_BITS = 5  # bits de precisão de cada probabilidade
PRECISION = 1 << PRECISION_BITS  # 32 = soma das frequências [c0, c1]


def contar_lote(symbols, start, end):
    """Conta as ocorrências em symbols[start:end]: counts[ctx][símbolo].

    O contexto de symbols[i] é symbols[i + 1] dentro do lote, e 0 no último símbolo.
    """
    counts = [[0, 0] for _ in range(NUM_CONTEXTS_1D)]
    for i in range(start, end):
        ctx = symbols[i + 1] if i + 1 < end else 0
        counts[ctx][symbols[i]] += 1
    return counts


def estimar_c0(n0, n1, anterior):
    """Estima c0 (1 .. PRECISION-1) a partir das contagens de 0 e de 1 de um contexto.

    c0 = arredonda(PRECISION * (n0 + 0,5) / (n0 + n1 + 1)), em inteiros, igual ao
    adapt.h. Sem nenhuma ocorrência, mantém o valor anterior.
    """
    n = n0 + n1
    if n == 0:
        return anterior
    x = (2 * n0 + 1) * PRECISION
    y = 2 * n + 2
    c0 = (2 * x + y) // (2 * y)
    return max(1, min(PRECISION - 1, c0))


class ContextModel:
    def __init__(self, num_contexts=NUM_CONTEXTS_1D):
        self.num_contexts = num_contexts
        self._c0 = [PRECISION // 2] * num_contexts

    # ------------------------------------------------------------------
    # Probabilidades
    # ------------------------------------------------------------------

    def definir_inicial(self, c0_lista):
        """Define c0 de cada contexto (valores entre 1 e PRECISION-1)."""
        if len(c0_lista) != self.num_contexts:
            raise ValueError("número de contextos incorreto")
        for c0 in c0_lista:
            if not 1 <= c0 <= PRECISION - 1:
                raise ValueError(f"c0 fora do intervalo válido: {c0}")
        self._c0 = list(c0_lista)

    def estimar_inicial(self, symbols):
        """Probabilidade inicial do plano: estatística condicional do plano inteiro."""
        counts = contar_lote(symbols, 0, len(symbols))
        self._c0 = [
            estimar_c0(counts[c][0], counts[c][1], PRECISION // 2) for c in range(self.num_contexts)
        ]

    def get_counts(self, ctx):
        """Devolve [c0, c1] do contexto, para uso no rANS."""
        return [self._c0[ctx], PRECISION - self._c0[ctx]]

    def atualizar_lote(self, counts):
        """Reestima as probabilidades com as contagens do lote que acabou.

        Devolve quantas probabilidades mudaram.
        """
        mudancas = 0
        for c in range(self.num_contexts):
            novo = estimar_c0(counts[c][0], counts[c][1], self._c0[c])
            if novo != self._c0[c]:
                self._c0[c] = novo
                mudancas += 1
        return mudancas

    # ------------------------------------------------------------------
    # Cabeçalho: só a probabilidade inicial de cada contexto
    # ------------------------------------------------------------------

    def serializar_inicial(self):
        """Probabilidade inicial como string hex (PRECISION_BITS bits por contexto)."""
        bits = []
        for c0 in self._c0:
            for b in range(PRECISION_BITS - 1, -1, -1):
                bits.append((c0 >> b) & 1)
        while len(bits) % 8:
            bits.append(0)
        valor = int("".join(map(str, bits)), 2)
        return format(valor, f"0{len(bits) // 4}x")

    def carregar_inicial(self, hex_str):
        """Lê a probabilidade inicial gravada por serializar_inicial."""
        n_bits = len(hex_str) * 4
        valor = int(hex_str, 16)
        bits = [(valor >> (n_bits - 1 - i)) & 1 for i in range(n_bits)]
        c0_lista = []
        pos = 0
        for _ in range(self.num_contexts):
            c0 = 0
            for _ in range(PRECISION_BITS):
                c0 = (c0 << 1) | bits[pos]
                pos += 1
            c0_lista.append(c0)
        self.definir_inicial(c0_lista)

    def header_overhead_bits(self):
        """Bits do cabeçalho: num_contexts × PRECISION_BITS (probabilidade inicial)."""
        return self.num_contexts * PRECISION_BITS

    def padding_bits(self):
        """Bits que completam o cabeçalho até um número inteiro de bytes."""
        return (-self.header_overhead_bits()) % 8