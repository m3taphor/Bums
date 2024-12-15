import json

try:
    import hashlib
except ImportError:
    print("Error: hashlib is not installed. Install manually by 'pip intall hashlib'.")
import random


def card_details(card_id):
    try:
        with open("./card-list.json", "r", encoding='utf8') as file:
            data = json.load(file)
            if str(card_id) in data:
                title = data[str(card_id)].get("title", "No title available")
                description = data[str(card_id)].get(
                    "desc", "No description available")
                return [title, description]
            else:
                return [card_id, "ID not found"]
    except FileNotFoundError:
        return [card_id, "File not found"]
    except json.JSONDecodeError:
        return [card_id, "Error reading JSON"]


def tapHash(taps_amount, collect_seq):
    secretData = str(taps_amount) + str(collect_seq) + \
        "7be2a16a82054ee58398c5edb7ac4a5a"

    hashCode = hashlib.md5(secretData.encode('utf-8')).hexdigest()

    return hashCode


def generate_taps(tap_value, left_energy, bonus_chance, bonus_multiplier):
    if tap_value < left_energy:
        gain = False
        if tap_value * bonus_multiplier / 100 <= left_energy:
            gain = random.randint(0, 100) <= bonus_chance / 100
            tap_value = tap_value * bonus_multiplier / 100 if gain else tap_value
            return int(tap_value)
        return 0


def task_answer(task_name, method):
    try:
        with open("./youtube-codes.json", "r", encoding='utf8') as file:
            data = json.load(file)

        if method == 'get-code':
            for task in data.get("codes", []):
                if task["name"].strip() == task_name:
                    return int(task["code"])
            return None

        elif method == 'error-code':
            for task in data.get("codes", []):
                if task["name"].strip() == task_name:
                    data["incorrect_codes"].append(task)
                    data["codes"].remove(task)
                    with open("./youtube-codes.json", "w", encoding='utf8') as file:
                        json.dump(data, file, indent=4)
                    return None

    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def combo_answer(method='get'):
    try:
        with open("./combo.json", "r", encoding='utf8') as file:
            data = json.load(file)

        if method == 'get':
            if 'combo' in data and len(data['combo']) == 3:
                return data['combo']
            return None

        elif method == 'wrong':
            data["combo"] = []

            with open("./combo.json", "w", encoding='utf8') as file:
                json.dump(data, file, indent=4)
            return None
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def count_spin(value):
    valid_values = [1, 2, 3, 5, 10, 50]
    return max([v for v in valid_values if v <= value], default=0)


async def get_profit_card(cards):

    for card in cards:
        card["nextLevelCost"] = int(card["nextLevelCost"])
        card["perHourReward"] = int(card["perHourReward"])
        card["nextPerHourReward"] = int(card["nextPerHourReward"])

    most_profitable_card = None
    highest_ratio = float('-inf')

    for card in cards:
        profit_increase = card["nextPerHourReward"] - card["perHourReward"]
        cost = card["nextLevelCost"]

        if cost > 0:
            ratio = profit_increase / cost

            if ratio > highest_ratio:
                highest_ratio = ratio
                most_profitable_card = card

    return most_profitable_card


def fnum(number):
    try:
        number = float(number)
    except ValueError:
        return number
    
    return (
        f"{number / 1e9:.1f}B" if number >= 1e9 else
        f"{number / 1e6:.1f}M" if number >= 1e6 else
        f"{number / 1e3:.1f}K" if number >= 1e3 else
        str(number)
    )
