import re
from myanmar.language import MorphoSyllableBreak, ismyanmar
from myanmar.encodings import UnicodeEncoding

# Built-in dictionary mapping popular Myanmar song names to their romanized equivalents
# Add more entries here as needed — format: "Myanmar Name": "Romanized Name"
MYANMAR_SONG_DICTIONARY = {
    "လမ်းဆုံ": "Lan Sone",
    "ချစ်သူ": "Chit Thu",
    "အချစ်": "A Chit",
    "နှလုံးသား": "Nha Lone Thar",
    "မင်းမရှိတဲ့နေ့": "Min Ma Shi Tae Nay",
    "သီချင်း": "Thi Chin",
    "အိပ်မက်": "Eain Met",
    "ကြယ်": "Kyal",
    "လ": "La",
    "နေ": "Nay",
    "မိုး": "Moe",
    "ပန်း": "Pan",
    "ရေ": "Yay",
    "လွမ်း": "Lwan",
    "မေတ္တာ": "Myitta",
    "အသက်": "A Thet",
    "မင်း": "Min",
    "ငါ": "Nga",
    "ခရီး": "Kha Yi",
    "အိမ်": "Ain",
    "ဘဝ": "Ba Wa",
    "စိတ်": "Sate",
    "နွေ": "Nway",
    "ဆောင်း": "Saung",
    "မုန်းတယ်": "Mone Tal",
    "ချစ်တယ်": "Chit Tal",
    "သတိရ": "Thati Ya",
    "အမှတ်တရ": "A Hmit Ta Ya",
    "လမ်း": "Lan",
    "ကမ္ဘာ": "Kan Ba",
    "တစ်ချိန်": "Ta Chain",
    "နောက်ဆုံး": "Nauk Sone",
    "ပထမ": "Pa Hta Ma",
    "အရိပ်": "A Yate",
    "အလင်း": "A Lin",
    "မျက်ရည်": "Myet Yay",
    "အိမ်မက်": "Ain Met",
}

# Myanmar consonant to romanized mapping
CONSONANT_MAP = {
    'က': 'ka', 'ခ': 'kha', 'ဂ': 'ga', 'ဃ': 'gha', 'င': 'nga',
    'စ': 'sa', 'ဆ': 'hsa', 'ဇ': 'za', 'ဈ': 'za', 'ဉ': 'nya', 'ည': 'nya',
    'ဋ': 'ta', 'ဌ': 'hta', 'ဍ': 'da', 'ဎ': 'dha', 'ဏ': 'na',
    'တ': 'ta', 'ထ': 'hta', 'ဒ': 'da', 'ဓ': 'dha', 'န': 'na',
    'ပ': 'pa', 'ဖ': 'pha', 'ဗ': 'ba', 'ဘ': 'bha', 'မ': 'ma',
    'ယ': 'ya', 'ရ': 'ya', 'လ': 'la', 'ဝ': 'wa',
    'သ': 'tha', 'ဟ': 'ha', 'ဠ': 'la', 'အ': 'a',
}

# Medial consonant modifiers
MEDIAL_MAP = {
    'yapin': 'y',    # ျ
    'yayit': 'y',    # ြ
    'waswe': 'w',    # ွ
    'hatoh': 'h',    # ှ
}

# Vowel combinations to romanized
VOWEL_MAP = {
    # Single vowel signs
    'eVowel': 'ay',       # ေ
    'iVowel': 'i',        # ိ
    'iiVowel': 'ee',      # ီ
    'uVowel': 'u',        # ု or ူ
    'aaVowel': 'ar',      # ာ
    'aiVowel': 'ae',      # ဲ
    'eAboveVowel': 'e',   # ဲ above
}


def is_myanmar_script(text: str) -> bool:
    """Checks if the given text contains Myanmar script characters."""
    for char in text:
        if ismyanmar(char):
            return True
    return False


def transliterate_syllable(syllable_info: dict) -> str:
    """Transliterate a single Myanmar syllable to romanized form."""
    result = ''

    # Get consonant
    consonant = syllable_info.get('consonant', '')
    romanized_consonant = CONSONANT_MAP.get(consonant, consonant)

    # Check for medials that modify the consonant
    has_medial = False
    medial_str = ''

    if 'yapin' in syllable_info:  # ျ
        medial_str += 'y'
        has_medial = True
    if 'yayit' in syllable_info:  # ြ
        medial_str += 'y'
        has_medial = True
    if 'waswe' in syllable_info:  # ွ
        medial_str += 'w'
        has_medial = True
    if 'hatoh' in syllable_info:  # ှ
        medial_str += 'h'
        has_medial = True

    # Build the consonant part
    if has_medial:
        # For medials, use shorter consonant form
        short_consonant = romanized_consonant.rstrip('a')
        if not short_consonant:
            short_consonant = romanized_consonant
        result = short_consonant + medial_str
    else:
        result = romanized_consonant

    # Determine vowel sound
    vowel = ''
    has_asat = 'asat' in syllable_info  # ် (killed consonant)

    if 'eVowel' in syllable_info:  # ေ
        if has_asat:
            vowel = 'ay'
        elif 'aaVowel' in syllable_info:  # ော
            vowel = 'aw'
        else:
            vowel = 'ay'
    elif 'aaVowel' in syllable_info:  # ာ
        vowel = 'ar'
    elif 'iVowel' in syllable_info:  # ိ
        vowel = 'i'
    elif 'iiVowel' in syllable_info:  # ီ
        vowel = 'ee'
    elif 'uVowel' in syllable_info:  # ု or ူ
        vowel = 'u'
    elif 'aiVowel' in syllable_info:  # ဲ
        vowel = 'ae'
    elif has_asat:
        # Killed consonant - no vowel
        vowel = ''
    else:
        # Default inherent vowel 'a'
        if not has_medial:
            vowel = 'a'
        else:
            vowel = 'a'

    # Handle anusvara (ံ) - nasal ending
    if 'anusvara' in syllable_info:
        if vowel in ('u', ''):
            vowel = 'one'
        elif vowel == 'i':
            vowel = 'in'
        elif vowel == 'a':
            vowel = 'an'
        elif vowel == 'ay':
            vowel = 'ain'
        elif vowel == 'ar':
            vowel = 'an'

    # Handle asat (်) - stop/killed
    if has_asat and 'anusvara' not in syllable_info:
        # The consonant is killed, remove inherent vowel
        if vowel == 'a':
            vowel = ''
        # Keep other vowels as they are

    # Remove trailing 'a' from consonant if we have a vowel
    if vowel and result.endswith('a') and len(result) > 1:
        result = result[:-1]

    result += vowel

    # Handle visarga (း) - doesn't change romanization much, already handled by vowel length
    return result


def transliterate_myanmar_to_romanized(text: str) -> str:
    """Transliterates Myanmar script text to its romanized equivalent."""
    # Split text by spaces and non-Myanmar characters
    parts = re.split(r'(\s+|[^\u1000-\u109F]+)', text)
    result_parts = []

    for part in parts:
        if not part:
            continue
        if not is_myanmar_script(part):
            result_parts.append(part)
            continue

        # Break into syllables and transliterate
        try:
            syllables = list(MorphoSyllableBreak(part, UnicodeEncoding()))
            romanized_syllables = []
            for syl in syllables:
                romanized = transliterate_syllable(syl)
                if romanized:
                    romanized_syllables.append(romanized)
            result_parts.append(' '.join(romanized_syllables))
        except Exception:
            # Fallback: just use the original text
            result_parts.append(part)

    return ''.join(result_parts).strip()


def get_romanized_query(query: str) -> str:
    """Determines the best romanized query for Deezer search.
    1. Checks if the query matches any entry in MYANMAR_SONG_DICTIONARY.
    2. If not found, checks if the query contains Myanmar script and transliterates it.
    3. Otherwise, returns the original query.
    """
    # Clean up the query
    query = query.strip()

    # 1. Check dictionary (exact match)
    if query in MYANMAR_SONG_DICTIONARY:
        return MYANMAR_SONG_DICTIONARY[query]

    # 2. Check dictionary (case-insensitive / partial match)
    for myanmar_name, romanized_name in MYANMAR_SONG_DICTIONARY.items():
        if myanmar_name in query:
            # Replace Myanmar part with romanized
            query = query.replace(myanmar_name, romanized_name)

    # 3. If still has Myanmar script, transliterate
    if is_myanmar_script(query):
        return transliterate_myanmar_to_romanized(query)

    # 4. If already Latin/English, return as is
    return query
