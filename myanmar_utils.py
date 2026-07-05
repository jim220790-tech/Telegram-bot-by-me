
import re
from myanmar.language import get_script_type
from myanmar.romanizer import romanize, BGN_PCGN, MLCTS

# Built-in dictionary mapping popular Myanmar song names to their romanized equivalents
MYANMAR_SONG_DICTIONARY = {
    "လမ်းဆုံ": "Lan Sone",
    # Add more entries here as needed
}

def is_myanmar_script(text: str) -> bool:
    """Checks if the given text contains Myanmar script characters."""
    return any(get_script_type(char) == 'myanmar' for char in text)

def transliterate_myanmar_to_romanized(text: str) -> str:
    """Transliterates Myanmar script text to its romanized equivalent.
    Prioritizes BGN_PCGN, falls back to MLCTS if BGN_PCGN fails or returns empty.
    """
    # Attempt BGN_PCGN romanization first
    romanized_text = romanize(text, BGN_PCGN)
    if romanized_text and romanized_text.strip() != '':
        return romanized_text
    
    # Fallback to MLCTS if BGN_PCGN is not effective
    romanized_text = romanize(text, MLCTS)
    return romanized_text

def get_romanized_query(query: str) -> str:
    """Determines the best romanized query for Deezer search.
    1. Checks if the query matches any entry in MYANMAR_SONG_DICTIONARY.
    2. If not found, checks if the query contains Myanmar script and transliterates it.
    3. Otherwise, returns the original query.
    """
    # 1. Check dictionary
    if query in MYANMAR_SONG_DICTIONARY:
        return MYANMAR_SONG_DICTIONARY[query]

    # 2. Check for Myanmar script and transliterate
    if is_myanmar_script(query):
        return transliterate_myanmar_to_romanized(query)

    # 3. If already Latin/English, return as is
    return query
