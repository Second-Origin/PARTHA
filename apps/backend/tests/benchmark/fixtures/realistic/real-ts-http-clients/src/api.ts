import client from "axios";

export async function listUsers() {
  return fetch("https://api.example.com/v1/users");
}

export async function createUser(body: string) {
  return fetch("https://api.example.com/v1/users", { method: "POST", body });
}

export async function deleteUser() {
  return client.delete("https://api.example.com/v1/users/1");
}

export async function probe(host: string) {
  return fetch(`https://${host}/v1`);
}
