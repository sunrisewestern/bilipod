def parse_netscape_cookies(cookies_file: str):
    with open(cookies_file, "r") as file:
        cookie_data = file.read()
    # Parse the cookie data
    cookies = {}
    for line in cookie_data.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 7:
            key = parts[5]
            value = parts[6]
            cookies[key] = value

    # Create the YAML structure
    token_data = {
        "bili_jct": cookies.get("bili_jct", ""),
        "buvid3": cookies.get("buvid3", ""),
        "buvid4": cookies.get("buvid4", ""),  # optional
        "dedeuserid": cookies.get("DedeUserID", ""),
        "sessdata": cookies.get("SESSDATA", ""),
    }
    return token_data
