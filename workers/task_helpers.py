
import random

def createGenericGameName():
    adjectives = ["Swift", "Brave", "Clever", "Mighty", "Nimble", "Fierce", "Wise", "Bold", "Loyal", "Gentle"]
    nouns = ["Lion", "Eagle", "Wolf", "Tiger", "Dragon", "Phoenix", "Bear", "Shark", "Falcon", "Panther"]
    suffix = str(random.randint(100, 999))
    adjective = random.choice(adjectives)
    adjectivetwo = random.choice(adjectives)
    noun = random.choice(nouns)
    return f"{adjective} {adjectivetwo} {noun} {suffix}"