import database as fb


def main() -> None:
    fb.init()  # reads FIREBASE_SERVICE_ACCOUNT and FIREBASE_URL from .env
    reg = fb.listen_trains("track_1", lambda path, data: print(path, data))
    input("Press Enter to stop...\n")
    reg.close()


