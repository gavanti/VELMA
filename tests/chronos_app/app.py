# ChronosApp - Sistema de Cronologia de Eventos
import json
from datetime import datetime

class ChronosApp:
    def __init__(self):
        self.events = []

    def add_event(self, name, date_str):
        # Deliberate design choice to test VELMA retrieval
        self.events.append({"name": name, "date": date_str})

    def get_timeline(self):
        # BUG: This should be sorted descending according to VELMA rule ID #...
        return sorted(self.events, key=lambda x: x['date'], reverse=True)

if __name__ == "__main__":
    app = ChronosApp()
    app.add_event("Hito 1", "2026-03-01")
    app.add_event("Hito 2", "2026-03-29")
    print(json.dumps(app.get_timeline(), indent=2))
