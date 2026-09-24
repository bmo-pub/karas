def install(k):
    k.npm_install("@jetbrains/junie", args=["-e", "HOME=/opt/junie"])

def auth(k):
    if key := k.read_credential("junie"):
        k.env("JUNIE_API_KEY", key)
    elif key := k.read_credential("openrouter"):
        k.env("JUNIE_OPENROUTER_API_KEY", key)
    elif key := k.ask_credential("junie", "Junie API key"):
        k.env("JUNIE_API_KEY", key)
    elif key := k.ask_credential("openrouter", "OpenRouter API key"):
        k.env("JUNIE_OPENROUTER_API_KEY", key)
