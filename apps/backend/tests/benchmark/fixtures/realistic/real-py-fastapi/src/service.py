from fastapi import FastAPI

app = FastAPI()


class Settings:
    debug = False


def get_settings():
    return Settings()


@app.get("/users/{user_id}")
def read_user(user_id: int):
    return {"id": user_id}


@app.post("/users")
def create_user(name: str):
    return {"name": name}
