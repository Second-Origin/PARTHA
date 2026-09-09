import httpx as hx
import requests

SESSION = requests.Session()


def list_users():
    return requests.get("https://api.example.com/v1/users")


def create_user(payload):
    return hx.post("https://api.example.com/v1/users", json=payload)


def delete_user():
    return SESSION.request("DELETE", "https://api.example.com/v1/users/1")


def probe(host):
    return requests.get(host)
