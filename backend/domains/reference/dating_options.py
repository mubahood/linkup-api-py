"""
Canonical dating-profile option catalog (P-API-01).

ONE source of truth for every profile/preference dropdown, served to the mobile
app via GET /v1/reference/dating-options. The app renders these and the matching
engine compares against the same values — so they can never drift. Uganda-localised
where it matters (religion, tribe, languages, industry).

Each catalog is a list of {value, label}. `value` is the stable token stored on
the profile; `label` is the human string shown in the UI.
"""
from __future__ import annotations


def _opts(*pairs):
    return [{"value": v, "label": l} for v, l in pairs]


# App-wide gender is strictly binary: every form and filter uses exactly these
# two values (male/female). Used for both "I am" and "interested in".
GENDER = _opts(("male", "Man"), ("female", "Woman"))

ORIENTATION = _opts(
    ("straight", "Straight"), ("gay", "Gay"), ("lesbian", "Lesbian"),
    ("bisexual", "Bisexual"), ("pansexual", "Pansexual"), ("asexual", "Asexual"),
    ("queer", "Queer"), ("questioning", "Questioning"), ("prefer_not", "Prefer not to say"),
)

RELATIONSHIP_GOAL = _opts(
    ("long_term", "Long-term partner"),
    ("long_open_short", "Long-term, open to short"),
    ("short_open_long", "Short-term, open to long"),
    ("short_term", "Short-term fun"),
    ("marriage", "Marriage-minded"),
    ("friendship", "New friends"),
    ("figuring_out", "Still figuring it out"),
)

SMOKING = _opts(
    ("no", "Non-smoker"), ("social", "Social smoker"), ("yes", "Regular smoker"),
    ("quitting", "Trying to quit"), ("prefer_not", "Prefer not to say"),
)

DRINKING = _opts(
    ("no", "Don't drink"), ("social", "Socially"), ("yes", "Regularly"),
    ("sober", "Sober"), ("prefer_not", "Prefer not to say"),
)

MARIJUANA = _opts(
    ("never", "Never"), ("sometimes", "Sometimes"), ("yes", "Regularly"),
    ("prefer_not", "Prefer not to say"),
)

DIET = _opts(
    ("omnivore", "I eat everything"),
    ("no_pork", "No pork"),
    ("halal", "Halal only"),
    ("vegetarian", "No meat (veggies & beans)"),
    ("pescatarian", "Only fish, no meat"),
    ("vegan", "No animal products"),
    ("other", "Other"),
)

EXERCISE = _opts(
    ("daily", "Every day"), ("often", "Often"), ("sometimes", "Sometimes"),
    ("rarely", "Rarely"), ("never", "Never"),
)

PETS = _opts(
    ("dog", "Dog"), ("cat", "Cat"), ("both", "Dog & cat"), ("other", "Other"),
    ("none", "No pets"), ("want", "Want a pet"), ("allergic", "Allergic"),
)

RELIGION = _opts(
    ("catholic", "Catholic"), ("anglican", "Anglican / Protestant"),
    ("pentecostal", "Pentecostal / Born-again"), ("sda", "Seventh-day Adventist"),
    ("orthodox", "Orthodox"), ("muslim", "Muslim"), ("hindu", "Hindu"),
    ("traditional", "Traditional / African"), ("spiritual", "Spiritual"),
    ("agnostic", "Agnostic"), ("atheist", "Atheist"),
    ("other", "Other"), ("prefer_not", "Prefer not to say"),
)

RELIGIOSITY = _opts(
    ("very", "Very religious"), ("somewhat", "Somewhat religious"),
    ("not_really", "Not religious"), ("prefer_not", "Prefer not to say"),
)

POLITICS = _opts(
    ("none", "Not into politics"),
    ("nrm", "NRM"),
    ("nup", "NUP"),
    ("fdc", "FDC"),
    ("dp", "DP"),
    ("upc", "UPC"),
    ("ant", "ANT"),
    ("independent", "Independent"),
    ("other", "Other"),
    ("prefer_not", "Prefer not to say"),
)

HAS_CHILDREN = _opts(
    ("no", "No"), ("yes_with_me", "Yes — they live with me"),
    ("yes_sometimes", "Yes — sometimes"), ("yes_not_with_me", "Yes — they don't live with me"),
    ("prefer_not", "Prefer not to say"),
)

WANTS_CHILDREN = _opts(
    ("want", "Want children"), ("dont_want", "Don't want children"),
    ("open", "Open to children"), ("not_sure", "Not sure yet"),
    ("have_want_more", "Have & want more"), ("have_dont_want_more", "Have & don't want more"),
    ("prefer_not", "Prefer not to say"),
)

EDUCATION_LEVEL = _opts(
    ("secondary", "Secondary"), ("certificate", "Certificate"), ("diploma", "Diploma"),
    ("bachelors", "Bachelor's degree"), ("masters", "Master's degree"),
    ("phd", "PhD / Doctorate"), ("vocational", "Vocational"), ("other", "Other"),
)

BODY_TYPE = _opts(
    ("slim", "Slim"), ("athletic", "Athletic"), ("average", "Average"),
    ("curvy", "Curvy"), ("plus_size", "Plus-size"), ("prefer_not", "Prefer not to say"),
)

ZODIAC = _opts(
    ("aries", "Aries"), ("taurus", "Taurus"), ("gemini", "Gemini"), ("cancer", "Cancer"),
    ("leo", "Leo"), ("virgo", "Virgo"), ("libra", "Libra"), ("scorpio", "Scorpio"),
    ("sagittarius", "Sagittarius"), ("capricorn", "Capricorn"),
    ("aquarius", "Aquarius"), ("pisces", "Pisces"),
)

PERSONALITY_TYPE = _opts(*[(t.lower(), t) for t in [
    "INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP",
]] + [("unknown", "Don't know")])

LOVE_LANGUAGES = _opts(
    ("words", "Words of affirmation"), ("quality_time", "Quality time"),
    ("acts", "Acts of service"), ("gifts", "Receiving gifts"), ("touch", "Physical touch"),
)

COMMUNICATION_STYLE = _opts(
    ("big_texter", "Big texter"), ("phone_caller", "Phone caller"),
    ("video_chat", "Video chatter"), ("in_person", "Better in person"),
    ("slow_texter", "Slow texter"),
)

LANGUAGES = _opts(
    ("en", "English"), ("lg", "Luganda"), ("sw", "Swahili"), ("nyn", "Runyankole"),
    ("ach", "Acholi"), ("xog", "Lusoga"), ("lgg", "Lugbara"), ("teo", "Ateso"),
    ("cgg", "Rukiga"), ("nyo", "Runyoro"), ("ttj", "Rutooro"), ("laj", "Langi"),
    ("fr", "French"), ("ar", "Arabic"),
)

# Sensitive — opt-in / match-only (mode separation + ARCHITECTURE.md §7.6)
TRIBE = _opts(
    ("muganda", "Muganda"), ("munyankole", "Munyankole"), ("musoga", "Musoga"),
    ("mukiga", "Mukiga"), ("iteso", "Iteso"), ("acholi", "Acholi"),
    ("lugbara", "Lugbara"), ("mugisu", "Mugisu"), ("munyoro", "Munyoro"),
    ("langi", "Langi"), ("alur", "Alur"), ("mutooro", "Mutooro"),
    ("karamojong", "Karamojong"), ("japadhola", "Japadhola"), ("other", "Other"),
)

INDUSTRY = _opts(
    ("technology", "Technology"), ("finance", "Banking & Finance"),
    ("healthcare", "Healthcare"), ("education", "Education"),
    ("agriculture", "Agriculture"), ("engineering", "Engineering"),
    ("legal", "Legal"), ("media", "Media & Creative"), ("government", "Government"),
    ("ngo", "NGO / Development"), ("business", "Business / Entrepreneur"),
    ("sales_marketing", "Sales & Marketing"), ("hospitality", "Hospitality & Tourism"),
    ("transport", "Transport & Logistics"), ("construction", "Construction"),
    ("arts", "Arts & Entertainment"), ("student", "Student"), ("other", "Other"),
)

# Tolerance scales used by preferences ("looking for")
TOLERANCE = _opts(
    ("any", "Doesn't matter"), ("no", "Must not"), ("social_ok", "Socially is fine"),
    ("prefer_not", "Prefer they don't"),
)

# Sensitive catalogs (only sent when client asks include_sensitive=true)
_SENSITIVE = {"tribe", "politics"}

CATALOG = {
    "gender": GENDER, "orientation": ORIENTATION, "relationship_goal": RELATIONSHIP_GOAL,
    "smoking": SMOKING, "drinking": DRINKING, "marijuana": MARIJUANA, "diet": DIET,
    "exercise": EXERCISE, "pets": PETS, "religion": RELIGION, "religiosity": RELIGIOSITY,
    "politics": POLITICS, "has_children": HAS_CHILDREN, "wants_children": WANTS_CHILDREN,
    "education_level": EDUCATION_LEVEL, "body_type": BODY_TYPE, "zodiac": ZODIAC,
    "personality_type": PERSONALITY_TYPE, "love_languages": LOVE_LANGUAGES,
    "communication_style": COMMUNICATION_STYLE, "languages": LANGUAGES, "tribe": TRIBE,
    "industry": INDUSTRY, "tolerance": TOLERANCE,
}


def get_catalog(include_sensitive: bool = True) -> dict:
    if include_sensitive:
        return CATALOG
    return {k: v for k, v in CATALOG.items() if k not in _SENSITIVE}


def valid_values(catalog_key: str) -> set:
    return {o["value"] for o in CATALOG.get(catalog_key, [])}
