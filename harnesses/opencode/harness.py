def install(k):
    k.npm_install("opencode-ai")

def auth(k):
    k.mount_credential("opencode", "/home/worker/.opencode/data/auth.json")
