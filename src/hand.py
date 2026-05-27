class HandState:
    def __init__(self):
        # Para cada dedo (1 a 5), guarda:
        #  - nota que está pressionando (ou None)
        #  - instante de liberação (0 se livre)
        self.fingers = {
            1: {"note": None, "release_time": 0},
            2: {"note": None, "release_time": 0},
            3: {"note": None, "release_time": 0},
            4: {"note": None, "release_time": 0},
            5: {"note": None, "release_time": 0},
        }

    def is_available(self, finger, current_time):
        return self.fingers[finger]["release_time"] <= current_time

    def assign(self, finger, note, release_time):
        self.fingers[finger]["note"] = note
        self.fingers[finger]["release_time"] = release_time

    def release(self, finger):
        self.fingers[finger]["note"] = None
        self.fingers[finger]["release_time"] = 0

    def copy(self):
        # para DFS, precisa clonar o estado da mão antes de ramificar
        new_hand = HandState()
        for f in self.fingers:
            new_hand.fingers[f] = self.fingers[f].copy()
        return new_hand

    def currently_pressed(self, current_time):
        # retorna uma lista de notas sendo pressionadas neste instante
        return [f["note"] for f in self.fingers.values() if f["release_time"] > current_time]
