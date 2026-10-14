import cv2
import numpy as np
import matplotlib.pyplot as plt

def bit_plane_slicing(image_path):
    # Carrega a imagem em escala de cinza
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    # Verifica se a imagem foi carregada corretamente
    if img is None:
        print("Erro ao carregar a imagem.")
        return

    planes_visual = []   # Lista para armazenar os planos para visualização (0 ou 255)
    planes_binary = {}   # Dicionário para armazenar os planos binários (0 ou 1)

    # Itera pelos 8 planos de bits (do bit 0 ao bit 7)
    for i in range(8):
        # Cria uma máscara com o valor 2^i (isola o bit i de cada pixel)
        plane_mask = np.full(img.shape, 2 ** i, np.uint8)

        # Aplica AND bit a bit entre a imagem e a máscara, extraindo apenas o bit i
        res = cv2.bitwise_and(img, plane_mask)

        # Converte o resultado para binário (0 ou 1)
        binary_matrix = (res > 0).astype(np.uint8)

        # Salva o plano binário no dicionário
        planes_binary[i] = binary_matrix

        # Salva o plano visual (multiplica por 255 para exibir como branco/preto)
        planes_visual.append(binary_matrix * 255)

    # Salva cada plano de bit como arquivo de texto
    for bit in range(8):
        filename = f'plano_bit_{bit}.txt'
        # Flatten para garantir que salve como sequência contínua de 0s e 1s
        np.savetxt(filename, planes_binary[bit].flatten(), fmt='%d', delimiter='')
        print(f"Plano {bit} salvo com sucesso em: {filename}")

    # Cria uma figura com subplots para exibir os 8 planos de bits
    plt.figure(figsize=(12, 8))
    for i in range(8):
        plt.subplot(2, 4, i + 1)          # Organiza em grade 2x4
        plt.imshow(planes_visual[i], cmap='gray')
        plt.title(f'Plano de Bit {i}')
        plt.axis('off')                    # Remove os eixos para visualização limpa

    plt.tight_layout()
    # Salva a figura com os planos de bits como imagem PNG
    plt.savefig('resultado_planos_bits.png', dpi=300)
    print("Gráfico dos planos de bits salvo com sucesso como 'resultado_planos_bits.png'!")


if __name__ == "__main__":
    import sys
    import os

    target = "foto.png"  # Imagem padrão

    # Verifica se foi passado um argumento pela linha de comando
    if len(sys.argv) > 1:
        target = sys.argv[1]
    elif os.path.exists("foto.png"):   # Usa foto.png se existir
        target = "foto.png"
    elif os.path.exists("foto.jpg"):   # Tenta foto.jpg como alternativa
        target = "foto.jpg"

    bit_plane_slicing(target)
