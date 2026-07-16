export namespace Legacy {
  export const flag = true;
}

async function load(name: string) {
  return import(name);
}
