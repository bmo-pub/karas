def install(k):
    k.npm_install("@openai/codex")

def auth(k):
    k.mount_credential("codex", "/home/worker/.codex/auth.json")
