import csv

def read_utterance(file_path):
    scenario_database = []
    with open(file_path, "r", encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        # header = next(reader)
        for row in reader:
            if "#" in row["発話ID"]:
                continue
            scenario_database.append(row)
    return scenario_database