"""The one ISO 4217 currency registry (WSF Checkout Phase 1).

Every place that needs to know whether a currency code is real, what it's
called, or how many minor units it has (USD/KES: 2, JPY: 0, KWD: 3) reads
it from here — never a scattered `* 100` or a free-text code. Served to
the admin Payments settings UI as the currency catalogue, so backend and
frontend share one list.

Source: the ISO 4217 "List one" of current active currency codes
(maintained by SIX Financial Information on behalf of ISO), reviewed for
WSF. Deliberately excludes non-currency X-codes that are not legal
tender for a retail checkout (precious metals XAU/XAG/XPD/XPT, the SDR
XDR, bond-market units XBA–XBD, XSU/XUA, the testing code XTS and "no
currency" XXX) and fund/accounting codes (BOV, CHE, CHW, CLF, COU, MXV,
USN, UYI, UYW). Minor units are ISO's own "Minor unit" column.

`symbol` is set only where it is reliable for display without the code
(USD, EUR, GBP); every other currency is displayed as "<CODE> <amount>"
— an ambiguous "$" or "¥" is never guessed. Updating this list (a new
ISO amendment) is a reviewed code change, never an admin free-text field.
"""

# code: (name, minor_unit)
_ISO_4217 = {
    "AED": ("UAE Dirham", 2),
    "AFN": ("Afghani", 2),
    "ALL": ("Lek", 2),
    "AMD": ("Armenian Dram", 2),
    "AOA": ("Kwanza", 2),
    "ARS": ("Argentine Peso", 2),
    "AUD": ("Australian Dollar", 2),
    "AWG": ("Aruban Florin", 2),
    "AZN": ("Azerbaijan Manat", 2),
    "BAM": ("Convertible Mark", 2),
    "BBD": ("Barbados Dollar", 2),
    "BDT": ("Taka", 2),
    "BHD": ("Bahraini Dinar", 3),
    "BIF": ("Burundi Franc", 0),
    "BMD": ("Bermudian Dollar", 2),
    "BND": ("Brunei Dollar", 2),
    "BOB": ("Boliviano", 2),
    "BRL": ("Brazilian Real", 2),
    "BSD": ("Bahamian Dollar", 2),
    "BTN": ("Ngultrum", 2),
    "BWP": ("Pula", 2),
    "BYN": ("Belarusian Ruble", 2),
    "BZD": ("Belize Dollar", 2),
    "CAD": ("Canadian Dollar", 2),
    "CDF": ("Congolese Franc", 2),
    "CHF": ("Swiss Franc", 2),
    "CLP": ("Chilean Peso", 0),
    "CNY": ("Yuan Renminbi", 2),
    "COP": ("Colombian Peso", 2),
    "CRC": ("Costa Rican Colon", 2),
    "CUP": ("Cuban Peso", 2),
    "CVE": ("Cabo Verde Escudo", 2),
    "CZK": ("Czech Koruna", 2),
    "DJF": ("Djibouti Franc", 0),
    "DKK": ("Danish Krone", 2),
    "DOP": ("Dominican Peso", 2),
    "DZD": ("Algerian Dinar", 2),
    "EGP": ("Egyptian Pound", 2),
    "ERN": ("Nakfa", 2),
    "ETB": ("Ethiopian Birr", 2),
    "EUR": ("Euro", 2),
    "FJD": ("Fiji Dollar", 2),
    "FKP": ("Falkland Islands Pound", 2),
    "GBP": ("Pound Sterling", 2),
    "GEL": ("Lari", 2),
    "GHS": ("Ghana Cedi", 2),
    "GIP": ("Gibraltar Pound", 2),
    "GMD": ("Dalasi", 2),
    "GNF": ("Guinean Franc", 0),
    "GTQ": ("Quetzal", 2),
    "GYD": ("Guyana Dollar", 2),
    "HKD": ("Hong Kong Dollar", 2),
    "HNL": ("Lempira", 2),
    "HTG": ("Gourde", 2),
    "HUF": ("Forint", 2),
    "IDR": ("Rupiah", 2),
    "ILS": ("New Israeli Sheqel", 2),
    "INR": ("Indian Rupee", 2),
    "IQD": ("Iraqi Dinar", 3),
    "IRR": ("Iranian Rial", 2),
    "ISK": ("Iceland Krona", 0),
    "JMD": ("Jamaican Dollar", 2),
    "JOD": ("Jordanian Dinar", 3),
    "JPY": ("Yen", 0),
    "KES": ("Kenyan Shilling", 2),
    "KGS": ("Som", 2),
    "KHR": ("Riel", 2),
    "KMF": ("Comorian Franc", 0),
    "KPW": ("North Korean Won", 2),
    "KRW": ("Won", 0),
    "KWD": ("Kuwaiti Dinar", 3),
    "KYD": ("Cayman Islands Dollar", 2),
    "KZT": ("Tenge", 2),
    "LAK": ("Lao Kip", 2),
    "LBP": ("Lebanese Pound", 2),
    "LKR": ("Sri Lanka Rupee", 2),
    "LRD": ("Liberian Dollar", 2),
    "LSL": ("Loti", 2),
    "LYD": ("Libyan Dinar", 3),
    "MAD": ("Moroccan Dirham", 2),
    "MDL": ("Moldovan Leu", 2),
    "MGA": ("Malagasy Ariary", 2),
    "MKD": ("Denar", 2),
    "MMK": ("Kyat", 2),
    "MNT": ("Tugrik", 2),
    "MOP": ("Pataca", 2),
    "MRU": ("Ouguiya", 2),
    "MUR": ("Mauritius Rupee", 2),
    "MVR": ("Rufiyaa", 2),
    "MWK": ("Malawi Kwacha", 2),
    "MXN": ("Mexican Peso", 2),
    "MYR": ("Malaysian Ringgit", 2),
    "MZN": ("Mozambique Metical", 2),
    "NAD": ("Namibia Dollar", 2),
    "NGN": ("Naira", 2),
    "NIO": ("Cordoba Oro", 2),
    "NOK": ("Norwegian Krone", 2),
    "NPR": ("Nepalese Rupee", 2),
    "NZD": ("New Zealand Dollar", 2),
    "OMR": ("Rial Omani", 3),
    "PAB": ("Balboa", 2),
    "PEN": ("Sol", 2),
    "PGK": ("Kina", 2),
    "PHP": ("Philippine Peso", 2),
    "PKR": ("Pakistan Rupee", 2),
    "PLN": ("Zloty", 2),
    "PYG": ("Guarani", 0),
    "QAR": ("Qatari Rial", 2),
    "RON": ("Romanian Leu", 2),
    "RSD": ("Serbian Dinar", 2),
    "RUB": ("Russian Ruble", 2),
    "RWF": ("Rwanda Franc", 0),
    "SAR": ("Saudi Riyal", 2),
    "SBD": ("Solomon Islands Dollar", 2),
    "SCR": ("Seychelles Rupee", 2),
    "SDG": ("Sudanese Pound", 2),
    "SEK": ("Swedish Krona", 2),
    "SGD": ("Singapore Dollar", 2),
    "SHP": ("Saint Helena Pound", 2),
    "SLE": ("Leone", 2),
    "SOS": ("Somali Shilling", 2),
    "SRD": ("Surinam Dollar", 2),
    "SSP": ("South Sudanese Pound", 2),
    "STN": ("Dobra", 2),
    "SVC": ("El Salvador Colon", 2),
    "SYP": ("Syrian Pound", 2),
    "SZL": ("Lilangeni", 2),
    "THB": ("Baht", 2),
    "TJS": ("Somoni", 2),
    "TMT": ("Turkmenistan New Manat", 2),
    "TND": ("Tunisian Dinar", 3),
    "TOP": ("Pa'anga", 2),
    "TRY": ("Turkish Lira", 2),
    "TTD": ("Trinidad and Tobago Dollar", 2),
    "TWD": ("New Taiwan Dollar", 2),
    "TZS": ("Tanzanian Shilling", 2),
    "UAH": ("Hryvnia", 2),
    "UGX": ("Uganda Shilling", 0),
    "USD": ("US Dollar", 2),
    "UYU": ("Peso Uruguayo", 2),
    "UZS": ("Uzbekistan Sum", 2),
    "VED": ("Bolívar Soberano", 2),
    "VES": ("Bolívar Soberano", 2),
    "VND": ("Dong", 0),
    "VUV": ("Vatu", 0),
    "WST": ("Tala", 2),
    "XAF": ("CFA Franc BEAC", 0),
    "XCD": ("East Caribbean Dollar", 2),
    "XCG": ("Caribbean Guilder", 2),
    "XOF": ("CFA Franc BCEAO", 0),
    "XPF": ("CFP Franc", 0),
    "YER": ("Yemeni Rial", 2),
    "ZAR": ("Rand", 2),
    "ZMW": ("Zambian Kwacha", 2),
    "ZWG": ("Zimbabwe Gold", 2),
}

# Only symbols that are unambiguous enough to show WITHOUT the code.
_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}

# Shown first in the admin currency picker (WSF's audience), then the rest
# alphabetically — every code stays selectable.
FEATURED_CURRENCIES = ("USD", "KES", "EUR", "GBP", "CAD", "AUD", "ZAR", "GHS", "NGN", "JPY", "CHF", "NZD", "SGD")


class UnknownCurrencyError(ValueError):
    pass


def normalize_currency(code):
    """Uppercased, stripped code if it is a real ISO 4217 currency in this
    registry; raises UnknownCurrencyError otherwise (never guesses)."""
    if not isinstance(code, str):
        raise UnknownCurrencyError("Currency must be an ISO 4217 code.")
    normalized = code.strip().upper()
    if normalized not in _ISO_4217:
        raise UnknownCurrencyError(f"{code!r} is not a supported ISO 4217 currency code.")
    return normalized


def is_currency(code):
    try:
        normalize_currency(code)
    except UnknownCurrencyError:
        return False
    return True


def currency_info(code):
    normalized = normalize_currency(code)
    name, minor_unit = _ISO_4217[normalized]
    return {"code": normalized, "name": name, "symbol": _SYMBOLS.get(normalized), "minorUnit": minor_unit}


def minor_unit(code):
    return _ISO_4217[normalize_currency(code)][1]


def currency_catalogue():
    """Featured codes first, then every other code alphabetically."""
    rest = sorted(code for code in _ISO_4217 if code not in FEATURED_CURRENCIES)
    return [currency_info(code) for code in (*FEATURED_CURRENCIES, *rest)]
