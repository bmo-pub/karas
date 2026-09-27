def install(k):
    k.npm_install("@anthropic-ai/claude-code")

def auth(k):
    return k.mount_credential("claude", "/home/worker/.claude/.credentials.json")
