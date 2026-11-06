# Um algoritmo de busca para o dedilhado ao piano

Código do Trabalho de Conclusão de Curso *Um algoritmo de busca para o dedilhado ao piano:
atribuição conjunta de mãos e dedos com controle de dificuldade*, de Gustavo Adriel Mittelmann
(Bacharelado em Ciência da Computação, Instituto Federal Catarinense, Campus Blumenau, 2026).

A partir de um arquivo MIDI, o sistema decide qual mão e qual dedo tocam cada nota e grava uma
partitura com o dedilhado indicado. As duas decisões são tomadas juntas e julgadas pela mesma
função de custo ergonômico, montada a partir de trabalhos publicados, sem dados de treinamento.
Se for pedido, o sistema também reduz a dificuldade da peça antes de dedilhá-la. O mesmo método
aceita mãos com dedos ausentes e mais de duas mãos no mesmo teclado, como num dueto a quatro
mãos.

## Sumário

- [Como funciona](#como-funciona)
- [Requisitos e instalação](#requisitos-e-instalação)
- [Dedilhar uma peça](#dedilhar-uma-peça-mainpy)
- [Medir a dificuldade](#medir-a-dificuldade-difficulty_profilepy)
- [Avaliação e testes](#avaliação-e-testes-evaluatepy)
- [O conjunto de dados PIG](#o-conjunto-de-dados-pig)
- [Organização do código](#organização-do-código)
- [Referências](#referências)

## Como funciona

```
arquivo MIDI
   │  leitura: as notas são agrupadas em camadas, uma por instante de início
   ▼
redução por dificuldade (opcional)
   │  suprime ou transpõe notas internas e, se preciso, diminui o andamento
   ▼
atribuição de mãos
   │  decide a mão de cada nota
   ▼
busca do dedilhado
   │  caminho de custo mínimo, mão a mão, pelo algoritmo de Viterbi
   ▼
gravação: partitura em LilyPond (.ly) e PDF
```

O custo ergonômico combina as tabelas de dificuldade dos movimentos de Hart, Bosch e Tsai
(2000) com os limites de abertura da mão de Parncutt et al. (1997). Ele se divide em custo
simultâneo (o esforço de um acorde) e custo de transição (o esforço de passar de um acorde ao
seguinte), como em Al Kasimi, Nichols e Raphael (2007). A medida de dificuldade e a redução
seguem Nakamura e Yoshii (2018), com o custo ergonômico no lugar do modelo estatístico.

A atribuição de mãos tem três variantes, que vão da decisão separada à decisão conjunta:

| Variante | Como decide a mão de cada nota |
|---|---|
| `split` | Uma busca sobre a peça escolhe uma fronteira de altura por instante, guiada por um custo aproximado que não olha os dedos. |
| `joint-local` | A mesma busca, mas cada fronteira é julgada pelo custo real do melhor dedilhado do seu instante, visto isoladamente. |
| `joint-full` | Fronteiras e dedilhado de cada mão decididos numa única busca sobre a peça inteira. É a contribuição do trabalho e a única variante que aceita mais de duas mãos. |

## Requisitos e instalação

- **Python 3** (testado com 3.14);
- **[mido](https://mido.readthedocs.io)** (testado com 1.3), para ler os arquivos MIDI;
- **[LilyPond](https://lilypond.org)** (testado com 2.26), no `PATH`, para gerar o PDF da
  partitura. O arquivo `.ly` gerado declara a versão 2.26.

```bash
git clone https://github.com/gsmitt/tcc.git
cd tcc
python3 -m venv .venv
source .venv/bin/activate
pip install mido
```

O LilyPond se instala pelo gerenciador de pacotes do sistema ou pelo site oficial. Para conferir
se ele está no `PATH`:

```bash
lilypond --version
```

## Dedilhar uma peça: `main.py`

```bash
python main.py
```

O programa lê `data/mond_1.mid`, o primeiro movimento da Sonata ao Luar de Beethoven, usado como
exemplo. Em seguida, ele reduz a dificuldade, atribui as mãos, calcula o dedilhado e grava
`output/mond_1.ly` e `output/mond_1.pdf`. No terminal aparecem o andamento lido, o que a redução
mudou e o custo do dedilhado de cada mão.

### Configuração

As opções ficam em constantes no topo do `main.py`:

| Constante | O que define | Padrão |
|---|---|---|
| `ASSIGNER` | Variante de atribuição de mãos: `"split"`, `"joint-local"` ou `"joint-full"` | `"joint-full"` |
| `SOLVER` | Busca do dedilhado: `"viterbi"` (exata, a usada no trabalho), `"dynamic"` ou `"graph"` (buscas em profundidade, exponenciais, só para comparação) | `"viterbi"` |
| `REDUCE` | Reduzir a dificuldade antes de dedilhar | `True` |
| `TARGET` | Tetos de dificuldade da mão esquerda, da direita e das duas juntas, em custo por segundo | `(44, 57, 89)` |
| `HANDS` | Mãos para as quais a peça é dedilhada | duas mãos completas |
| `SLICE` | Número máximo de camadas lidas do arquivo | `2000` |

Para dedilhar outro arquivo, troque o caminho em `read_midi("data/mond_1.mid")` e o nome de
saída em `out_path="output/mond_1"`, as duas dentro da função `main()`.

### Mãos com dedos ausentes e duetos

Cada mão é descrita por um `Hand` (em `src/hands.py`):

```python
Hand(name, side, fingers=(1, 2, 3, 4, 5), register=60.0, group=None)
```

- `side` é `"L"` ou `"R"` e define a geometria da mão (de que lado fica o polegar);
- `fingers` são os dedos disponíveis, numerados de 1 (polegar) a 5 (mínimo);
- `register` é a altura MIDI central da mão, que ordena as mãos da mais grave à mais aguda e dá
  o ponto de partida das fronteiras entre elas;
- `group` reúne as pautas de um mesmo executante na partitura.

Uma mão direita sem o anelar:

```python
HANDS = [Hand("L", "L", register=53.0),
         Hand("R", "R", fingers=(1, 2, 3, 5), register=67.0)]
REDUCE = False
```

Um dueto a quatro mãos:

```python
HANDS = [Hand("S-L", "L", register=41.0, group="Secondo"),
         Hand("S-R", "R", register=53.0, group="Secondo"),
         Hand("P-L", "L", register=67.0, group="Primo"),
         Hand("P-R", "R", register=79.0, group="Primo")]
REDUCE = False
ASSIGNER = "joint-full"
```

Com qualquer configuração diferente das duas mãos completas, use `REDUCE = False`: a redução
ainda mede a dificuldade com duas mãos de cinco dedos. Mais de duas mãos exige
`ASSIGNER = "joint-full"`, e dedos ausentes exigem uma das variantes acopladas (`joint-local`
ou `joint-full`).

## Medir a dificuldade: `difficulty_profile.py`

```bash
python difficulty_profile.py [arquivo.mid] [bpm]
```

Mostra a distribuição da dificuldade da peça em cada instante de início: o mínimo, a mediana, o
percentil 90, o máximo e o número de instantes sem dedilhado possível, para a mão esquerda
(`D_L`), a direita (`D_R`) e as duas juntas (`D_B`). A dificuldade é um custo por segundo, numa
janela de 1 s. Por isso, ela depende do andamento: o `bpm` opcional substitui o do arquivo, e
dobrar o andamento deve dobrar a dificuldade. Sem argumentos, o programa usa `data/mond_1.mid`.

## Avaliação e testes: `evaluate.py`

```bash
python evaluate.py <modo> [opções]
```

| Modo | O que faz |
|---|---|
| `selftest` | Testes automáticos em exemplos pequenos (abaixo) |
| `pig` | Dedilha as peças do PIG e compara com os pianistas |
| `agreement` | Compara os pianistas do PIG entre si, a referência humana |
| `compare` | Compara duas execuções de `pig`, peça a peça |
| `ablation` | Cruza redução, variante de atribuição e busca num arquivo MIDI |
| `beamgap` | Mede quanto a busca em feixe do `joint-full` perde para a busca exata |

Os modos que produzem dados gravam uma tabela em CSV e em JSON na pasta `output/`. Ao lado de
cada tabela fica um `.meta.json` com a impressão digital do código (um hash do `evaluate.py` e de
`src/`), o commit, a máquina e as opções usadas. Assim dá para saber de onde veio cada
resultado.

### Testes

```bash
python evaluate.py selftest
```

Os testes conferem, entre outras coisas:

- que a busca de Viterbi encontra o mesmo custo que uma busca exaustiva em 300 entradas
  aleatórias, com notas que continuam soando;
- a ordem entre as taxas de correspondência e a definição original da taxa de recombinação;
- que uma nota sem previsão conta como erro;
- que a dificuldade cresce na mesma proporção do andamento;
- que uma nota presa fora do alcance da mão é solta, e que a transposição da redução nunca
  passa da melodia nem do baixo;
- que um acorde impossível já no primeiro instante falha de forma controlada;
- um dueto a quatro mãos, com uma das mãos limitada a três dedos, do início ao fim.

Se o PIG estiver na pasta padrão, um último teste confere que o dedilhado do primeiro pianista,
passado pelo mesmo caminho de uma execução real, acerta 100% contra ele mesmo. Sem o PIG, esse
teste é pulado e os outros rodam normalmente.

### No conjunto PIG

```bash
python evaluate.py pig [pasta/FingeringFiles] [--assigner joint-full] [--limits tcc] [--remove-finger R4] [--repeats 1] [--out output/eval_pig]
```

- `--assigner` aceita as três variantes e duas referências: `fixed`, que divide as mãos no dó
  central, e `oracle`, que recebe as mãos do primeiro pianista e só calcula os dedos (a mesma
  condição dos métodos de Nakamura, Saito e Yoshii, 2020);
- `--limits parncutt` troca os limites de abertura dos pares com o polegar pelos do artigo
  original;
- `--remove-finger R4` tira um dedo de uma mão (aqui, o anelar da direita) e exige uma variante
  acoplada;
- `--repeats` repete cada peça e registra a mediana do tempo.

Para cada peça, a tabela traz as quatro taxas de correspondência de Nakamura, Saito e Yoshii
(2020), calculadas só sobre o número do dedo (`M_gen`, `M_high`, `M_soft`, `M_rec`) e sobre o
dedo com a mão (`S_*`). Traz também a acurácia de mão, a fração de notas com dedilhado
(`coverage`), o custo total e o tempo. As notas de uma mão que a busca não conseguiu dedilhar
contam como erro, para que todas as variantes sejam medidas sobre as mesmas notas.

Para comparar duas variantes peça a peça:

```bash
python evaluate.py pig --assigner split      --out output/pig_split
python evaluate.py pig --assigner joint-full --out output/pig_joint-full
python evaluate.py compare output/pig_split.json output/pig_joint-full.json [--subset test-30]
```

O `compare` mostra, para cada medida, a diferença média com intervalo de confiança de 95%
(bootstrap), quantas peças melhoraram e quantas pioraram, e o teste de postos sinalizados de
Wilcoxon, com os valores-p ajustados por Holm. `--subset test-30` restringe a comparação às 30
peças do conjunto de teste de Nakamura, Saito e Yoshii (2020).

### Num arquivo MIDI

```bash
python evaluate.py ablation [arquivo.mid] [--slice 120] [--max-dfs 80]
python evaluate.py beamgap  [arquivo.mid] [--length 16] [--stride 50]
```

As buscas em profundidade (`dynamic` e `graph`) são exponenciais. Por isso, o `ablation` lê só
as primeiras `--slice` camadas e pula essas buscas quando a parte de uma mão passa de
`--max-dfs` camadas. O `beamgap` compara o `joint-full` com e sem o feixe em trechos curtos
(`--length` instantes, um a cada `--stride`), porque a busca sem feixe também é exponencial.

## O conjunto de dados PIG

O PIG (Nakamura, Saito e Yoshii, 2020) reúne trechos de 150 peças dedilhados por pianistas. Ele
**não acompanha este repositório** e precisa ser baixado no
[site do conjunto](http://beam.kisarazu.ac.jp/research/PianoFingeringDataset/). O uso é
permitido **só para pesquisa acadêmica sem fins lucrativos**, e os autores pedem que o artigo
seja citado:

> E. Nakamura, Y. Saito e K. Yoshii. Statistical learning and estimation of piano fingering.
> *Information Sciences*, v. 517, p. 68-85, 2020.

O `evaluate.py` procura o conjunto em
`PianoFingeringDataset_v1.2/PianoFingeringDataset_v1.2/FingeringFiles`, a partir da raiz do
repositório. Se ele estiver em outro lugar, passe o caminho da pasta `FingeringFiles` como
argumento dos modos `pig` e `agreement`. Essa pasta fica fora do git (`.gitignore`).

## Organização do código

```
main.py                   dedilha uma peça e grava a partitura
difficulty_profile.py     mostra a dificuldade de uma peça
evaluate.py               avaliação, experimentos e testes
data/mond_1.mid           peça de exemplo
src/
  midi_reader.py          leitura do MIDI: camadas e andamento
  pig_loader.py           leitura do PIG
  hands.py                descrição das mãos (lado, dedos, registro, executante)
  costs.py                modelo de custo ergonômico (tabelas e limites de abertura)
  hand.py                 estado dos dedos durante a busca
  assigners/              atribuição de mãos: split, joint-local, joint-full e fixed
  hand_assigner.py        atribuição por ponto de divisão e separação das notas por mão
  solvers/                busca do dedilhado: viterbi, dynamic e graph
  difficulty.py           medida de dificuldade
  sheet_reducer.py        redução por dificuldade
  sheet_export.py         gravação da partitura com o LilyPond
  metrics.py              taxas de correspondência, acurácia de mão e teste de Wilcoxon
```

Os módulos principais começam com uma documentação, em inglês, que explica o que fazem e cita
os trabalhos de onde vem cada parte.

## Referências

- AL KASIMI, A.; NICHOLS, E.; RAPHAEL, C. A simple algorithm for automatic generation of
  polyphonic piano fingerings. In: *International Conference on Music Information Retrieval*,
  2007. p. 355-356.
- HART, M.; BOSCH, R.; TSAI, E. Finding optimal piano fingerings. *The UMAP Journal*, v. 21,
  n. 2, p. 167-177, 2000.
- NAKAMURA, E.; SAITO, Y.; YOSHII, K. Statistical learning and estimation of piano fingering.
  *Information Sciences*, v. 517, p. 68-85, 2020.
- NAKAMURA, E.; YOSHII, K. Statistical piano reduction controlling performance difficulty.
  *APSIPA Transactions on Signal and Information Processing*, v. 7, e13, 2018.
- PARNCUTT, R.; SLOBODA, J. A.; CLARKE, E. F.; RAEKALLIO, M.; DESAIN, P. An ergonomic model of
  keyboard fingering for melodic fragments. *Music Perception*, v. 14, n. 4, p. 341-382, 1997.

## Créditos do arquivo de exemplo

`data/mond_1.mid` é de Bernd Krueger, [piano-midi.de](http://www.piano-midi.de), distribuído
sob a licença Creative Commons Attribution-ShareAlike (Alemanha).
