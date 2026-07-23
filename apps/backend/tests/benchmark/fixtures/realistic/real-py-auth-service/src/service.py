from fastapi import FastAPI, Depends

app = FastAPI()


def get_current_user(token: str = Depends(oauth2_scheme)):
    return token


class UserService:
    def get_user(self):
        pass


class UserModel:
    pass


@app.get("/me")
def read_me(user=Depends(get_current_user)):
    return user
