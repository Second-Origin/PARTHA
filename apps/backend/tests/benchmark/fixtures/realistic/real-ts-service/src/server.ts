import { createServer } from "http";

export function start(port: number): void {
  createServer().listen(port);
}

export const server = { start };
