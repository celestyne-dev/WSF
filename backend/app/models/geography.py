from app.extensions import db

# The 8-region taxonomy every Country belongs to, plus the catch-all
# "Global" region used by the GLOBAL/REMOTE pseudo-countries below. Mirrors
# frontend/src/mock/geography.js REGIONS exactly.
REGIONS = (
    "North America",
    "Latin America & Caribbean",
    "Europe",
    "Africa",
    "Asia",
    "Middle East",
    "Oceania",
    "Global",
)

# Pseudo country codes for content that isn't tied to one country.
GLOBAL_CODE = "GLOBAL"
REMOTE_CODE = "REMOTE"


class Country(db.Model):
    """The single source of truth for country/region data (ISO 3166-1
    alpha-2 codes). Every location-bearing model (Person, Author, Job,
    Opportunity, Event, Organization, StorySubmission, Nomination, ...)
    stores a `country_code` that references this table rather than a
    free-text country name, so the platform never needs a developer to
    hard-code a country list per feature. Adding a new country is a data
    change: one row here, nothing else in the app needs to change.
    """

    __tablename__ = "countries"

    code = db.Column(db.String(10), primary_key=True)  # ISO alpha-2, or GLOBAL/REMOTE
    name = db.Column(db.String(100), nullable=False)
    region = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<Country {self.code} {self.name}>"


# Seed data mirroring frontend/src/mock/geography.js COUNTRIES — a
# representative (not exhaustive) set spanning every region. Loaded by
# `flask seed-geography` (see app/services/geography.py) rather than
# hard-coded into application logic.
SEED_COUNTRIES = [
    # North America
    ("US", "United States", "North America"),
    ("CA", "Canada", "North America"),
    # Latin America & Caribbean
    ("BR", "Brazil", "Latin America & Caribbean"),
    ("MX", "Mexico", "Latin America & Caribbean"),
    ("CO", "Colombia", "Latin America & Caribbean"),
    ("AR", "Argentina", "Latin America & Caribbean"),
    # Europe
    ("GB", "United Kingdom", "Europe"),
    ("DE", "Germany", "Europe"),
    ("FR", "France", "Europe"),
    ("IE", "Ireland", "Europe"),
    ("NL", "Netherlands", "Europe"),
    ("ES", "Spain", "Europe"),
    ("SE", "Sweden", "Europe"),
    ("PT", "Portugal", "Europe"),
    # Africa
    ("KE", "Kenya", "Africa"),
    ("NG", "Nigeria", "Africa"),
    ("ZA", "South Africa", "Africa"),
    ("GH", "Ghana", "Africa"),
    ("EG", "Egypt", "Africa"),
    ("RW", "Rwanda", "Africa"),
    ("ET", "Ethiopia", "Africa"),
    ("TZ", "Tanzania", "Africa"),
    ("UG", "Uganda", "Africa"),
    ("SN", "Senegal", "Africa"),
    # Asia
    ("IN", "India", "Asia"),
    ("SG", "Singapore", "Asia"),
    ("PH", "Philippines", "Asia"),
    ("JP", "Japan", "Asia"),
    ("ID", "Indonesia", "Asia"),
    ("VN", "Vietnam", "Asia"),
    ("KR", "South Korea", "Asia"),
    # Middle East
    ("AE", "United Arab Emirates", "Middle East"),
    ("SA", "Saudi Arabia", "Middle East"),
    ("IL", "Israel", "Middle East"),
    ("JO", "Jordan", "Middle East"),
    # Oceania
    ("AU", "Australia", "Oceania"),
    ("NZ", "New Zealand", "Oceania"),
    # Pseudo-locations for content not tied to one country.
    (GLOBAL_CODE, "Global", "Global"),
    (REMOTE_CODE, "Remote", "Global"),
]
