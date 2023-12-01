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

