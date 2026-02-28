import math
from itertools import combinations
import random

DISTANCE_COST = {
    -4: 9, -3: 6, -2: 4, -1: 2, 0: 0,
    1: 1, 2: 2, 3: 3, 4: 4, 5: 5
}

"""
TO DO:

receber entrada midi
cada layer precisa manter o instante em que ocorre e cada nota o instante em que acaba 
cada layer representa um evento de key_down, mas inclui todas as notas que ainda nao acabaram
pensar: como diferenciar uma nota nova vs a continuação de outra nota?
-----
enquando explora a arvore, utilizar o objeto hand para manter quais dedos estao disponiveis e quando
cada ramificaçao cria um clone do estado da mão, por isso é importante usar busca em profundidade e não largura, 
já que quando um ramo é descartado ou concluido, a sua respectiva instancia do objeto Hand pode ser destruida,
evitando a nescessidade de todas as instancias (produtorio do numero de nos de cada camada) existirem ao mesmo tempo
n maximo de instancias existentes em uma musica com 1 nota por camada
N_BFS = 5**(numero_camadas)
N_DFS = numero_camadas
-----
calcular peso dos vertices baseado na dificuldade de todos os dedos sendo usados (por enquanto apenas o peso das arestas é levado em conta)
ignorar nós que usam dedos em cooldown ou com combinações "impossíveis"
considerar impossiveis combinações que cruzem dedos (Ex: [61, 62, 63, 64] com dedos [2,1,4,3]) com excessão do polegar (Ex: 2,3,1)
o pruning precisa ser bem agressivo, considerando que uma simples musica de 100 notas unicas já teria 5**100 ~= 7.9*10**69 nós na arvore de busca
-----
levar em conta a existencia de duas mãos.
especialmente problematico, sem pruning aumenta o tamanho da arvore de busca exponencialmente
considerar deixar fora do escopo do trabalho
penalizar o cruzamento de mãos
-----

calcular se uma nota é branca ou preta (e usar o custo apropriado bb bw wb ww)
busca de monte carlo (pq a arvore vai ser enorme em uma musica real)
"""
MAX_MOVE_COST = 10
DISTANCE_COSTS = {
    "w-w": {
        "1-2": [1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3],
        "1-3": [1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 3],
        "1-4": [2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
        "1-5": [3, 3, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1],
        "2-1": [2, 2, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4],
        "2-3": [1, 1, 1, 1, 2, 2, 3, 3, 3, 3, 3, 3],
        "2-4": [2, 2, 1, 1, 1, 1, 2, 3, 3, 3, 3, 3],
        "2-5": [3, 3, 2, 2, 1, 1, 1, 1, 1, 2, 2, 2],
        "3-1": [2, 2, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4],
        "3-4": [1, 1, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3],
        "3-5": [3, 3, 1, 1, 1, 1, 3, 3, 3, 3, 3, 3],
        "4-1": [2, 2, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        "4-5": [1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3],
        "5-1": [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
    },
    "w-b": {},
    "b-w": {}
}

def finger_move_cost(note_prev, note_curr, finger_prev, finger_curr):
    note_span = abs(note_curr - note_prev)
    if note_curr < note_prev:
        key = f"{finger_curr}-{finger_prev}"
    else:
        key = f"{finger_prev}-{finger_curr}"
    finger_combo = DISTANCE_COSTS["w-w"].get(key, None)

    if finger_combo is None:
        return note_span + 2
    if note_span >= len(finger_combo):
        return note_span + 2
    return finger_combo[note_span]


def fingering_transition_cost(prev_notes, curr_notes, prev_fingers, curr_fingers):
    max_cost = 0
    for (n_prev, f_prev, n_curr, f_curr) in zip(prev_notes, prev_fingers, curr_notes, curr_fingers):
        if n_prev != n_curr:
            c = finger_move_cost(n_prev, n_curr, f_prev, f_curr)
            max_cost = max(max_cost, c)
    return max_cost


def chord_complexity(notes):
    return 0 if len(notes) == 1 else len(notes) - 1


class PianoFingeringDFS:
    def __init__(self, chords):
        self.chords = [sorted(c) for c in chords]
        self.best_cost = math.inf
        self.best_path = []
        self.node_visits = 0

    def _possible_fingerings(self, n):
        return list(combinations(range(1, 6), n))

    def _dfs(self, idx, prev_notes, prev_fingers, total_cost, path):
        self.node_visits += 1

        if idx == len(self.chords):
            if total_cost < self.best_cost:
                self.best_cost = total_cost
                self.best_path = path[:]
            return

        chord = self.chords[idx]
        chord_cost = chord_complexity(chord)

        for fingers in self._possible_fingerings(len(chord)):
            if prev_notes is None:
                move_cost = 0
            else:
                move_cost = fingering_transition_cost(prev_notes, chord, prev_fingers, fingers)

            # prune paths that are too costly
            #if move_cost > MAX_MOVE_COST:
            #    continue

            new_cost = total_cost + move_cost + chord_cost

            # prune paths already worse than current best
            if new_cost >= self.best_cost:
                continue

            path.append((chord, fingers))
            self._dfs(idx + 1, chord, fingers, new_cost, path)
            path.pop()

    def solve(self):
        self._dfs(0, None, None, 0, [])
        return self.best_cost, self.best_path, self.node_visits


def main():
    chords = [[random.randint(60, 70)] for i in range(20)]


    solver = PianoFingeringDFS(chords)
    cost, path, visits = solver.solve()
    print("Best cost:", cost)
    print("Path:")
    for step in path:
        print(" ", step)
    print("Node visits:", visits)


if __name__ == "__main__":
    main()