def install(k):
    k.npm_install("@github/copilot")

def auth(k):
    token = k.read_credential("copilot", ask="GitHub token")
    if token:
        k.env("COPILOT_GITHUB_TOKEN", token)
