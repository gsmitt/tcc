# Um algoritmo de busca para o dedilhado ao piano

Código do Trabalho de Conclusão de Curso *Um algoritmo de busca para o dedilhado ao piano:
atribuição conjunta de mãos e dedos com controle de dificuldade*, de Gustavo Adriel Mittelmann
(Bacharelado em Ciência da Computação, Instituto Federal Catarinense, Campus Blumenau, 2026).

A partir de um arquivo MIDI, o sistema decide qual mão e qual dedo tocam cada nota e grava uma
partitura com o dedilhado indicado. As duas decisões são tomadas juntas e julgadas pela mesma
função de custo ergonômico, montada a partir de trabalhos publicados; só os poucos valores que
essas fontes não dão foram ajustados a dedilhados anotados por pianistas. Se for pedido, o sistema também reduz a dificuldade da peça antes de dedilhá-la. O mesmo método
aceita mãos com dedos ausentes e mais de duas mãos no mesmo teclado, como num dueto a quatro
mãos.

## Sumário

- [Como funciona](#como-funciona)
- [Requisitos e instalação](#requisitos-e-instalação)
- [O conjunto de dados PIG](#o-conjunto-de-dados-pig)
- [Dedilhar uma peça](#dedilhar-uma-peça-mainpy)
- [Medir a dificuldade](#medir-a-dificuldade-difficulty_profilepy)
- [Avaliação e testes](#avaliação-e-testes-evaluatepy)
- [Otimização dos parâmetros](#otimização-dos-parâmetros-otimizarpy)
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

## O conjunto de dados PIG

A avaliação, os experimentos e o ajuste dos parâmetros usam o PIG (*Piano Fingering Dataset*),
de Nakamura, Saito e Yoshii (2020): trechos de 150 peças do repertório clássico, com 309
dedilhados anotados nota a nota por pianistas. O conjunto **não acompanha este repositório** e
pode ser obtido na página dos autores:

**<https://beam.kisarazu.ac.jp/research/PianoFingeringDataset/>**

A página leva a um cadastro para o download. O uso é permitido só para pesquisa acadêmica sem
fins lucrativos, e os autores pedem que todo trabalho que use o conjunto cite o artigo da lista
de [referências](#referências). O código foi usado com a versão 1.2 (2022/5/12).

Sem o PIG, o `main.py`, o `difficulty_profile.py` e quase todos os testes funcionam
normalmente. Só os modos de avaliação listados abaixo e o `otimizar.py` precisam dele.

### Onde colocar os arquivos

O código procura os arquivos de dedilhado nesta pasta, a partir da raiz do repositório:

```
PianoFingeringDataset_v1.2/PianoFingeringDataset_v1.2/FingeringFiles/
```

É o caminho que resulta de extrair o arquivo baixado numa pasta `PianoFingeringDataset_v1.2/`,
já que o próprio arquivo traz uma pasta com esse nome:

```bash
unzip <arquivo-baixado>.zip -d PianoFingeringDataset_v1.2
ls PianoFingeringDataset_v1.2/PianoFingeringDataset_v1.2/FingeringFiles | head -3
# 001-1_fingering.txt
# 001-2_fingering.txt
# 001-5_fingering.txt
```

A pasta está no `.gitignore` e nunca vai para o repositório. Se os arquivos estiverem em outro
lugar, passe o caminho da pasta `FingeringFiles` como argumento: `python evaluate.py pig
/caminho/FingeringFiles` nos modos de avaliação, e `--root /caminho/FingeringFiles` no
`otimizar.py`. Para conferir se o conjunto foi encontrado, rode `python evaluate.py selftest`:
com o PIG no lugar, o teste de identidade (abaixo) deixa de ser pulado.

### Como o código lê o PIG

Cada arquivo `<peça>-<pianista>_fingering.txt` traz uma nota por linha, com o início e o fim em
segundos, a altura, o canal (0 para a mão direita, 1 para a esquerda) e o dedo, negativo na mão
esquerda. A leitura, em `src/pig_loader.py`:

- agrupa num mesmo acorde as notas cujos inícios distam até 30 ms, como no artigo;
- lê no início seguinte o fim de uma nota que passa até 30 ms dele, o legato dos arquivos MIDI,
  que de outro modo deixaria o dedo preso no acorde seguinte;
- usa o primeiro dedo quando o pianista indica troca de dedo sobre a nota (`3_1`);
- lê os tempos como se a semibreve durasse 1 s, isto é, a 240 semínimas por minuto, de modo que
  a dificuldade fica no andamento da própria peça.

Um teste automático confere essa leitura de ponta a ponta: o dedilhado do primeiro pianista,
passado pelos mesmos passos de uma execução real, precisa acertar 100% contra si mesmo em
todas as 150 peças.

### Treino e teste

As peças 001 a 030 (dez de Bach, dez de Mozart e dez de Chopin, cada uma com quatro a seis
dedilhados) são o conjunto de teste de Nakamura, Saito e Yoshii (2020). Elas nunca entram no
ajuste dos parâmetros, que usa só as 120 restantes (031 a 150). Os resultados comparados com os
pianistas devem vir das 30 de teste (`--pieces test-30` ou `--subset test-30`).

### Experimentos com o PIG

| Comando | O que faz |
|---|---|
| `python evaluate.py pig --assigner joint-full` | Dedilha as peças com uma variante (`split`, `joint-local`, `joint-full`) ou uma referência: `fixed`, a fronteira fixa no dó central, e `oracle`, que recebe as mãos do primeiro pianista e só escolhe os dedos. Mede as taxas de correspondência de Nakamura, Saito e Yoshii ($M_{gen}$, $M_{high}$, $M_{soft}$, $M_{rec}$), as mesmas taxas com mão e dedo ($S_{gen}$ etc.), a acurácia de mão, o custo, a dificuldade e o tempo. |
| `python evaluate.py agreement` | Compara os pianistas entre si pelas mesmas taxas: a referência humana. |
| `python evaluate.py reduction` | Reduz as 30 peças de teste até os tetos, só com edições de notas e com edições e andamento, e mede a eficácia e a fidelidade com cada variante. |
| `python evaluate.py beamgap` | Compara o `joint-full` com e sem o feixe nos 16 primeiros instantes de cada peça. |
| `python evaluate.py compare A.json B.json --subset test-30` | Compara duas execuções peça a peça: diferença média com intervalo de 95% de confiança, teste de Wilcoxon e correção de Holm. |

Opções do modo `pig`:

| Opção | O que faz |
|---|---|
| `--pieces test-30` | Só as 30 peças de teste (o padrão é `all`, as 150) |
| `--repeats 3` | Repete cada peça e registra a mediana dos tempos |
| `--beam 128` | Muda o feixe do `joint-full` (padrão 32) |
| `--limits parncutt` | Usa os limites de abertura do polegar do artigo de Parncutt et al. |
| `--remove-finger R4` | Tira um dedo de uma mão (aqui, o anelar da direita); exige `joint-local` ou `joint-full` |

Os experimentos do Capítulo 5 do TCC são, em resumo:

```bash
for a in split joint-local joint-full fixed oracle; do
  python evaluate.py pig --assigner $a --repeats 3 --out output/cap5/pig_$a
done
python evaluate.py agreement --out output/cap5/agreement
python evaluate.py reduction --out output/cap5/reduction
python evaluate.py beamgap   --out output/cap5/beamgap
python evaluate.py pig --assigner joint-full --beam 128 --pieces test-30 --out output/cap5/pig_joint-full_feixe128
python evaluate.py pig --assigner joint-full --limits parncutt --out output/cap5/pig_joint-full_parncutt
python evaluate.py pig --assigner joint-full --remove-finger R4 --out output/cap5/pig_joint-full_semR4
python evaluate.py compare output/cap5/pig_split.json output/cap5/pig_joint-full.json --subset test-30
```

Os tempos do TCC foram medidos com um processo por vez, preso a um núcleo (`taskset -c 0`), com
o aumento automático de frequência desligado. O `.meta.json` de cada execução registra essas
condições.

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
| `TARGET` | Tetos de dificuldade da mão esquerda, da direita e das duas juntas, em custo por segundo | `None`: o teto em vigor, do `parametros.json` |
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

A redução aceita mãos com dedos ausentes: mede a dificuldade com os dedos que cada mão
tem, e o mesmo teto pede, para uma mão incompleta, uma partitura mais simples. Com mais de
duas mãos, use `REDUCE = False`, porque a redução mede as duas mãos de um único
executante. Mais de duas mãos exige `ASSIGNER = "joint-full"`, e dedos ausentes exigem
uma das variantes acopladas (`joint-local` ou `joint-full`).

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
| `ablation` | Cruza redução, variante de atribuição e busca num arquivo MIDI |
| `beamgap` | Mede quanto a busca em feixe do `joint-full` perde para a busca exata, no PIG ou num arquivo MIDI |
| `pig`, `agreement`, `reduction`, `compare` | Avaliação no PIG (veja [O conjunto de dados PIG](#o-conjunto-de-dados-pig)) |

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

Dois testes usam o PIG, que não acompanha o repositório: o de identidade da leitura e a parte do
teste do ajuste que confere que as peças de teste ficam de fora. Sem o PIG, eles são pulados e os
outros rodam normalmente.

### Experimentos

```bash
python evaluate.py ablation [arquivo.mid] [--slice 120] [--max-dfs 80]
python evaluate.py beamgap  [pasta do PIG ou arquivo.mid] [--length 16] [--stride 50]
```

As buscas em profundidade (`dynamic` e `graph`) são exponenciais. Por isso, o `ablation` lê só
as primeiras `--slice` camadas e pula essas buscas quando a parte de uma mão passa de
`--max-dfs` camadas. O `beamgap` compara o `joint-full` com e sem o feixe em trechos curtos
(`--length` instantes), porque a busca sem feixe também é exponencial. No PIG, o padrão, o trecho
é o começo de cada peça; num arquivo MIDI, é um trecho a cada `--stride` instantes.

## Otimização dos parâmetros: `otimizar.py`

Alguns números do modelo não vêm de nenhuma fonte e foram escolhidos neste trabalho. O
`otimizar.py` ajusta os que mudam o dedilhado ou a divisão entre as mãos, usando só as 120
peças do PIG que ficam fora do conjunto de teste (031 a 150), e por isso precisa do PIG
(veja [O conjunto de dados PIG](#o-conjunto-de-dados-pig)). As peças 001 a 030, o conjunto
de teste de Nakamura, Saito e Yoshii (2020), nunca entram no ajuste.

```bash
python otimizar.py all                                 # as três etapas, na ordem da tabela
python otimizar.py cost                                # só os pesos do custo (e o teto)
python otimizar.py stability --variant joint-full      # só a estabilidade de uma variante (e o teto)
python otimizar.py ceiling                             # só a nova medição do teto
```

| Etapa | O que ajusta | Como |
|---|---|---|
| `cost` | pesos do custo ergonômico: esticar além do confortável, soltar uma nota presa, movimentos fora das tabelas, uníssono e limite do par 1-5 | com as mãos anotadas no PIG, para não favorecer nenhuma variante, maximizando $M_{gen}$ |
| `stability` | o peso de estabilidade da fronteira de cada variante; no `joint-full`, também o limiar e o peso da abertura total do acorde, que não mudam o dedilhado, só a divisão entre as mãos | com cada variante, maximizando $S_{gen}$, em que mão e dedo precisam coincidir; o `joint-full` vem antes do `joint-local`, que usa os mesmos valores do acorde |
| `ceiling` | o teto de dificuldade | não é ajuste: mede de novo o percentil 90 da dificuldade com os pesos novos e o `joint-local`; toda execução termina com essa medição |

A busca é por coordenadas: a partir dos valores escolhidos à mão, cada rodada testa todos os
valores da grade de um parâmetro, com os outros fixos. O valor de melhor média só substitui o
atual se o ganho, peça a peça, tiver intervalo de confiança de 95% acima de zero; um peso que
os dados não distinguem do valor de partida fica com ele. A busca para quando uma rodada
inteira não muda nada. As peças são avaliadas em paralelo (`--processes`), e cada
combinação é avaliada uma vez só. Quando o melhor valor de um parâmetro é o maior da grade,
o programa avisa e registra isso no `parametros.json`, porque o melhor valor pode estar além
dela.

O resultado vai para `parametros.json`, na raiz do repositório, com os valores, o teto e
como foram obtidos. O `main.py` e o `evaluate.py` passam a usar esse arquivo quando ele
existe. Para avaliar com os valores escolhidos à mão:

```bash
python evaluate.py --params hand-picked pig --assigner joint-full
```

Os valores de partida, as grades e os motivos para não ajustar os demais números (feixe,
janela, parâmetros da redução e da gravação, e os valores que representam "impossível")
estão em `src/params.py`. Lá também estão os três termos retirados do modelo porque o ajuste
mostrou que não faziam nada ou atrapalhavam: a penalidade de cruzamento dentro do acorde
(nenhum dedilhado de acorde gerado é cruzado), a parcela fixa do custo de esticar e a
penalidade do `split` por separar um acorde que cabe numa mão. Cada tentativa fica registrada em `output/otimizacao/`.

## Organização do código

```
main.py                   dedilha uma peça e grava a partitura
difficulty_profile.py     mostra a dificuldade de uma peça
evaluate.py               avaliação, experimentos e testes
otimizar.py               ajuste dos parâmetros nas peças de treino do PIG
parametros.json           valores ajustados em uso (gerado pelo otimizar.py)
data/mond_1.mid           peça de exemplo
src/
  midi_reader.py          leitura do MIDI: camadas e andamento
  pig_loader.py           leitura do conjunto de dedilhados PIG (Nakamura, Saito e Yoshii, 2020)
  hands.py                descrição das mãos (lado, dedos, registro, executante)
  params.py               parâmetros sem fonte: valores, grades e os que não se ajustam
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
