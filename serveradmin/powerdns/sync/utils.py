
def ensure_canonical(name: str) -> str:
    """Ensure that a name ends with a dot"""
    if not name.endswith('.'):
        return name + '.'

    return name


def quote_string(content: str) -> str:
    if content.startswith('"') and content.endswith('"'):
        # looks like it's already quoted
        return content

    """Quote a string for usage in PowerDNS TXT records"""
    return '"' + content.replace('"', '\"') + '"'


def divide_chunks(list: list, n: int) -> list:
    for i in range(0, len(list), n):
        yield list[i:i + n]


def get_dns_zone(domain: str) -> str:
    if not domain:
        return ''

    # A list of common country-code second-level domains.
    cc_slds = ['br', 'co', 'com', 'org', 'no', 'net', 'gov', 'edu', 'mil', 'or']

    # Split the domain into parts.
    parts = domain.split('.')

    # Special case for country-code SLDs.
    if len(parts) > 2 and parts[-2] in cc_slds:
        return '.'.join(parts[-3:])

    # General case for gTLDs and ccTLDs.
    return '.'.join(parts[-2:])
