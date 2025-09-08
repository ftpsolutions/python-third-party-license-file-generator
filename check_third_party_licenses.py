with open("THIRDPARTYLICENSES", "r") as f:
    data = f.read()

parts = data.split("----------------------------------------\n")

parts = parts[1:-1]

data = "----------------------------------------\n".join(parts).strip()

if not data:
    raise AssertionError(
        "THIRDPARTYLICENSES contains no actual licences! (only the header and footer)"
    )
