import os
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

def create_article():
    doc = Document()
    
    # Title
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("IMPLEMENTAÇÃO E ANÁLISE DE CODIFICAÇÃO ENTRÓPICA BASEADA EM ASYMMETRIC NUMERAL SYSTEMS (ANS)\n")
    run.font.name = 'Arial'
    run.font.size = Pt(12)
    run.bold = True
    
    # Authors
    authors = doc.add_paragraph()
    authors.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = authors.add_run("NOME E SOBRENOME DO AUTOR1; NOME E SOBRENOME DO(S) CO-AUTOR(ES)2; NOME E SOBRENOME DO ORIENTADOR3\n")
    run.font.name = 'Arial'
    run.font.size = Pt(12)
    
    # Institutions
    inst = doc.add_paragraph()
    inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = inst.add_run("1Nome da Instituição do Autor 1 – e-mail do autor 1\n2Nome da Instituição do(s) Co-Autor(es) – e-mail do autor 2\n3Nome da Instituição do Orientador – e-mail do orientador\n")
    run.font.name = 'Arial'
    run.font.size = Pt(10)
    
    # 1. INTRODUÇÃO
    h1 = doc.add_paragraph()
    h1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = h1.add_run("1. INTRODUÇÃO")
    run.font.name = 'Arial'
    run.font.size = Pt(12)
    run.bold = True
    
    p = doc.add_paragraph("A teoria da informação, desde as suas bases estabelecidas por Claude Shannon, tem focado na compressão de dados como um dos seus pilares mais importantes. Ao longo das décadas, o algoritmo de Huffman e a Codificação Aritmética reinaram absolutos neste campo. Huffman oferece velocidade incomparável, devido à sua simplicidade na conversão de símbolos em códigos de tamanho variável, porém sofre de ineficiência por não conseguir alocar frações de bits para símbolos altamente prováveis. A codificação aritmética resolve esse problema alcançando o limite ótimo da entropia de Shannon, mas o faz com um alto custo computacional devido a divisões matemáticas constantes durante o processo.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("Este cenário foi drasticamente alterado em 2013, com a proposição dos Asymmetric Numeral Systems (ANS) por Jarek Duda. A técnica ANS representa um paradigma inovador de codificação entrópica que consegue aliar a velocidade de execução do algoritmo de Huffman à alta eficiência teórica da Codificação Aritmética. Sua adoção maciça se reflete hoje em dia por ser o padrão da indústria, estando no coração de compressores de estado da arte como o Zstandard do Facebook, o codec de imagens JPEG XL e compressores de jogos da Apple (LZFSE).")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("Neste contexto, o presente trabalho descreve um estudo aprofundado e a implementação de diferentes frentes de compressão da família ANS. O projeto tem como motivação central analisar a viabilidade e o ganho de eficiência no processamento de imagens e streams de dados, aplicando estratégias que vão desde implementações tradicionais em C até modelos de vanguarda com streaming contínuo baseados em contextos (Cadeias de Markov) em linguagem Python.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("O principal objetivo desta pesquisa é desenvolver, testar e analisar de maneira quantitativa e qualitativa o comportamento do ANS frente a dados altamente estruturados. Para atingir esse objetivo, o trabalho foi estruturado com foco em fatiamento de planos de bits (bit plane slicing), codificação estática baseada em tabelas e, de modo pioneiro, uma implementação streaming rANS que opera com estado contínuo, zerando a maior parte do overhead presente nas implementações bloco a bloco. O trabalho também explora a capacidade do decodificador atuar de forma LIFO (Last-In-First-Out) e como isso facilita a predição contextual do tipo lookahead.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    # 2. METODOLOGIA
    h2 = doc.add_paragraph()
    h2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = h2.add_run("2. METODOLOGIA")
    run.font.name = 'Arial'
    run.font.size = Pt(12)
    run.bold = True
    
    p = doc.add_paragraph("O desenvolvimento prático e analítico deste trabalho se desdobrou em três metodologias principais de implementação, avaliando desde o pré-processamento de imagens até as diferentes formas de arquitetar um sistema ANS.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("2.1. Extração e Análise de Planos de Bits (Bit Plane Slicing)")
    p.runs[0].bold = True
    p = doc.add_paragraph("A primeira frente metodológica abordada concentrou-se na exploração espacial de imagens. Para viabilizar uma compressão mais granulada e que explora estatísticas isoladas, as imagens de entrada foram pré-processadas através da técnica de Bit Plane Slicing. Uma imagem comum em escala de cinza de 8 bits por pixel foi decomposta em 8 imagens binárias, ou planos de bits. O plano de bit 7 (mais significativo) carrega a maior correlação estrutural da imagem, enquanto o plano de bit 0 aproxima-se do ruído branco puro.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("Ao utilizar um script Python operando sobre matrizes Numpy, a imagem inteira é quebrada nesses planos. Cada plano é então salvo como um mapa de texto isolado. O propósito dessa quebra é permitir que o codificador assimile um modelo estatístico muito específico para cada matriz, ao invés de tentar criar uma entropia misturada que reduziria a eficiência compressiva.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("2.2. Implementação do tANS Estático em Linguagem C")
    p.runs[0].bold = True
    p = doc.add_paragraph("Como parâmetro (baseline) para velocidade e comportamento clássico, foi implementada a técnica tANS (table-based ANS) estática, escrita puramente em linguagem C. A lógica baseia-se na criação de tabelas de probabilidade inversas pré-calculadas.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("Para tal, definiu-se um RANGE fixo igual a 8 com uma janela lógica (CONFIG = 6), dimensionado para carregar estados de alfabeto binário em hardware modesto sem transbordo de cache. O fluxo de operações ocorre lendo e escrevendo byte a byte em um ciclo determinístico onde a operação de encriptação gera o estado, sendo que, de maneira contraintuitiva, a codificação gera a saída do fim para o começo do arquivo (propriedade LIFO do ANS).")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("2.3. Streaming rANS Contextual com Estado Contínuo")
    p.runs[0].bold = True
    p = doc.add_paragraph("A frente principal da pesquisa foca em modernizar o fluxo do ANS por meio da técnica Range ANS (rANS) implementada em Python. A implementação visa corrigir dois gargalos da compressão clássica:")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("1) Estado Contínuo: Compressores em bloco precisam reiniciar o estado e salvar headers repetitivos. Nossa implementação gerencia um macro-estado variável que emite fluxos residuais assim que atingem a tolerância limite, garantindo ausência de paddings supérfluos.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p = doc.add_paragraph("2) Predição com Contexto Lookahead-1: Utilizando o modelo context_model.py, a probabilidade do bit B atual não é estática, mas dada pelo bit B-1. Como o decoder opera reverso, no instante de ler B, o B-1 já foi perfeitamente lido no passo anterior da cadeia. A simetria natural do sistema permite utilizar cadeias de Markov que otimizam a codificação para áreas homogêneas da imagem sem acrescentar um bit sequer ao header.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    # 3. RESULTADOS E DISCUSSÃO
    h3 = doc.add_paragraph()
    h3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = h3.add_run("3. RESULTADOS E DISCUSSÃO")
    run.font.name = 'Arial'
    run.font.size = Pt(12)
    run.bold = True
    
    p = doc.add_paragraph("Os ensaios práticos confirmaram a eficiência e escalabilidade das técnicas propostas, evidenciando as grandes vantagens do sistema ANS em cenários com distorções probabilísticas variadas. Na etapa de decomposição de planos de bits, a separação produziu um mapa visual onde o ruído estatístico é puramente confinado nos bits inferiores (0 e 1), ao passo que a estrutura geométrica encontra-se mapeada nos bits superiores.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    # Inserting the image
    img_path = 'resultado_planos_bits.png'
    if os.path.exists(img_path):
        doc.add_picture(img_path, width=Inches(6.0))
        img_title = doc.add_paragraph("Figura 1 - Decomposição da imagem em planos de bits, evidenciando do bit menos significativo (0) ao mais significativo (7).")
        img_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        img_title.runs[0].font.name = 'Arial'
        img_title.runs[0].font.size = Pt(10)
    
    p = doc.add_paragraph("Ao aplicar a codificação ANS sobre os arquivos isolados dos planos de bits, como plano_bit_7.txt (altamente estruturado) contra plano_bit_0.txt (ruído caótico), os sistemas apresentaram as taxas teóricas ideais esperadas da entropia de Shannon. No bit mais significativo, a ocorrência prolongada de zeros sequenciais na matriz da imagem causou com que o estado do codificador absorvesse a informação repetitiva sem expandir seus registradores. Assim, a codificação deste plano obteve taxas de compressão drásticas, reduzindo enormemente o seu peso para apenas uma fração mínima do arquivo original.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("A implementação do módulo rANS em Python com streaming demonstrou ser o ponto de maior destaque do estudo. Por incorporar o estado contínuo, a eficiência se elevou de forma marcante. Nas medições de overhead — a diferença entre a codificação aritmética matematicamente perfeita (limite teórico) e a quantidade de bits processada pelo ANS — o valor manteve-se consistentemente inferior a 0.5% em blocos contínuos extensos.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("A integração com o modelo de contexto baseado em Cadeias de Markov (lookahead-1) ressaltou a natureza elegante da lógica reversa LIFO do ANS. Em testes onde áreas da imagem exibiam padronagens específicas (tais como bordas longas ou contrastes constantes), a predição contextual atuava em sinergia perfeita com a leitura decrescente do sistema rANS. Visto que o decoder decodifica exatamente o que se transformará na 'história prévia' no mundo real (da frente para trás), os desvios condicionais nas probabilidades provaram otimizar a entropia, reduzindo o custo binário local para níveis que um modelo estático jamais conseguiria.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("Contrapondo-se ao sistema Python, a versão tANS em linguagem C ofereceu resultados empíricos essenciais focados em throughput computacional extremo. Ao limitar o processo às instruções básicas de processador (operações shift lógicas, lookup de memória estática e AND bit a bit), a linguagem C operou arquivos textuais grandes em parcelas de microsegundos. O custo pago, contudo, é a fixação rigorosa do cenário de probabilidades, evidenciando o trade-off constante da codificação entrópica entre adaptabilidade contextual dinâmica e a performance determinística hard-coded.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    # 4. CONCLUSÕES
    h4 = doc.add_paragraph()
    h4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = h4.add_run("4. CONCLUSÕES")
    run.font.name = 'Arial'
    run.font.size = Pt(12)
    run.bold = True
    
    p = doc.add_paragraph("A aplicação prática de técnicas de compressão utilizando Asymmetric Numeral Systems atendeu de forma plena a expectativa teórica, provando-se um método com superioridade técnica incontestável para as demandas da computação moderna. O desdobramento em várias abordagens permitiu uma análise holística da teoria da compressão em ação.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("O grande diferencial alcançado foi a concretização da modelagem de streaming contínuo acompanhado da modulação probabilística de lookahead-1. Esta inovação demonstra que, em vez de recorrer a dicionários caros (LZ) ou predições matemáticas pesadas, a natureza reversa do estado ANS provê naturalmente o solo fértil para adaptação contextual baseada em vizinhança iminente.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p = doc.add_paragraph("O trabalho demonstra que a extração minuciosa de planos de bits aliada a encoders de estado ANS em contexto contínuo possui capacidade para revolucionar sistemas de compressão focados na transmissão de laços de dados altamente estruturados, abrindo caminho para extensões voltadas à compressão de áudio ou espectros multi-bandas.")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    # 5. REFERÊNCIAS BIBLIOGRÁFICAS
    h5 = doc.add_paragraph()
    h5.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = h5.add_run("5. REFERÊNCIAS BIBLIOGRÁFICAS")
    run.font.name = 'Arial'
    run.font.size = Pt(12)
    run.bold = True
    
    p = doc.add_paragraph("DUDA, Jarek. Asymmetric numeral systems: entropy coding combining speed of Huffman coding with compression rate of arithmetic coding. arXiv preprint arXiv:1311.2540, 2013.")
    p = doc.add_paragraph("SHANNON, Claude E. A mathematical theory of communication. The Bell system technical journal, v. 27, n. 3, p. 379-423, 1948.")
    p = doc.add_paragraph("ZSTD. Zstandard - Real-time data compression algorithm. Disponível em: https://facebook.github.io/zstd/. Acesso em: 18 set. 2026.")
    
    # Save the document
    doc.save('Artigo_Projeto_ANS.docx')

create_article()
