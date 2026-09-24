def install(k):
    k.npm_install("@google/gemini-cli")

def auth(k):
    k.mount_credential("gemini", "/home/worker/.gemini/oauth_creds.json")
